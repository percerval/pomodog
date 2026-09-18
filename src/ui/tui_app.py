import math
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Literal

from textual.app import App, ComposeResult
from textual.content import Content
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Select, Static

from src.core.pomodoro_engine import PomodoroEngine, TimerState
from src.data.json_repository import JSONRepository
from src.notifications.desktop_notifier import DesktopEvent, DesktopNotifierProtocol
from src.notifications.sound_notifier import SessionNotifier

_TITLE_3D = """
██████╗  ██████╗ ███╗   ███╗ ██████╗ ██████╗  ██████╗  ██████╗ 
██╔══██╗██╔═══██╗████╗ ████║██╔═══██╗██╔══██╗██╔═══██╗██╔════╝ 
██████╔╝██║   ██║██╔████╔██║██║   ██║██║  ██║██║   ██║██║  ███╗
██╔═══╝ ██║   ██║██║╚██╔╝██║██║   ██║██║  ██║██║   ██║██║   ██║
██║     ╚██████╔╝██║ ╚═╝ ██║╚██████╔╝██████╔╝╚██████╔╝╚██████╔╝
╚═╝      ╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝ 

"""

ResetDecision = Literal["save", "discard"]
TaskAction = Literal["create", "select", "unassociate", "complete"]
TaskDecision = tuple[TaskAction, str | None]


def _current_time() -> datetime:
    return datetime.now(timezone.utc)


class ResetConfirmationModal(ModalScreen[ResetDecision]):
    """Solicita uma decisão para o foco parcial antes do reset."""

    AUTO_FOCUS = "#btn-cancel-reset"
    BINDINGS = [("escape", "cancel", "Cancel")]
    DIALOG_TITLE = "Reset current cycle?"
    DIALOG_QUESTION = "Save this partial session before resetting?"

    CSS = """
    ResetConfirmationModal {
        align: center middle;
    }

    #reset-dialog {
        width: 82;
        height: 15;
        border: heavy #00E5FF;
        padding: 1 2;
        background: #0D1117;
    }

    #reset-title {
        text-align: center;
        text-style: bold;
        color: #FFFFFF;
        margin-bottom: 1;
    }

    #reset-message {
        text-align: center;
        color: #FFFFFF;
        margin-bottom: 1;
    }

    #reset-actions {
        height: 3;
        align: center middle;
    }

    #btn-save-reset {
        background: #006D77;
        color: #FFFFFF;
    }

    #btn-discard-reset {
        background: #8F3A46;
        color: #FFFFFF;
    }

    #btn-cancel-reset {
        background: #5F3B8C;
        color: #FFFFFF;
    }
    """

    def __init__(self, elapsed_seconds: float):
        super().__init__()
        self.elapsed_seconds = elapsed_seconds

    def compose(self) -> ComposeResult:
        minutes, seconds = divmod(max(1, math.ceil(self.elapsed_seconds)), 60)
        with Container(id="reset-dialog"):
            yield Static(self.DIALOG_TITLE, id="reset-title")
            yield Static(
                f"You focused for {minutes:02d}:{seconds:02d}. {self.DIALOG_QUESTION}",
                id="reset-message",
            )
            with Horizontal(id="reset-actions"):
                yield Button("Save Partial", id="btn-save-reset")
                yield Button("Discard", id="btn-discard-reset")
                yield Button("Cancel", id="btn-cancel-reset")

    def action_cancel(self) -> None:
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        decisions: dict[str, ResetDecision | None] = {
            "btn-save-reset": "save",
            "btn-discard-reset": "discard",
            "btn-cancel-reset": None,
        }
        self.dismiss(decisions[event.button.id])


class ExitConfirmationModal(ResetConfirmationModal):
    """Solicita uma decisão para o foco parcial antes de sair."""

    DIALOG_TITLE = "Exit Pomodog?"
    DIALOG_QUESTION = "Save this partial session before exiting?"


class TaskManagerModal(ModalScreen[TaskDecision]):
    """Criar e selecionar a task usada pelos próximos focos."""

    AUTO_FOCUS = "#task-title-input"
    BINDINGS = [("escape", "cancel", "Close")]

    CSS = """
    TaskManagerModal {
        align: center middle;
    }

    #task-dialog {
        width: 82;
        height: 20;
        border: heavy #00E5FF;
        padding: 1 2;
        background: #0D1117;
    }

    #task-title, #task-active, #task-lock-message {
        text-align: center;
        margin-bottom: 1;
    }

    #task-title {
        text-style: bold;
        color: #FFFFFF;
    }

    #task-lock-message {
        color: $warning;
    }

    #task-actions {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    #task-actions Button {
        width: 15;
        margin: 0 1;
    }

    #task-close {
        width: 18;
        margin: 1 29 0 29;
    }
    """

    def __init__(
        self,
        *,
        tasks: list[dict],
        active_task: dict | None,
        changes_locked: bool,
    ):
        super().__init__()
        self.tasks = tasks
        self.active_task = active_task
        self.changes_locked = changes_locked

    def compose(self) -> ComposeResult:
        active_title = self.active_task["title"] if self.active_task else "None"
        selected_task_id = (
            self.active_task["id"] if self.active_task is not None else Select.NULL
        )
        options = [(Content(task["title"]), task["id"]) for task in self.tasks]

        with Container(id="task-dialog"):
            yield Static("Manage Tasks", id="task-title")
            yield Static(
                f"Active Task: {active_title}",
                id="task-active",
                markup=False,
            )
            if self.changes_locked:
                yield Static(
                    "Task changes are locked while a focus is in progress.",
                    id="task-lock-message",
                )
            yield Input(
                placeholder="New task title",
                id="task-title-input",
                disabled=self.changes_locked,
            )
            yield Select(
                options,
                prompt="Select an open task",
                value=selected_task_id,
                id="task-select",
                disabled=self.changes_locked,
            )
            with Horizontal(id="task-actions"):
                yield Button(
                    "Create",
                    id="task-create",
                    disabled=self.changes_locked,
                )
                yield Button(
                    "Select",
                    id="task-select-button",
                    disabled=self.changes_locked,
                )
                yield Button(
                    "Unassociate",
                    id="task-unassociate",
                    disabled=self.changes_locked,
                )
                yield Button(
                    "Complete",
                    id="task-complete",
                    disabled=self.changes_locked,
                )
            yield Button("Close", id="task-close")

    def action_cancel(self) -> None:
        self.dismiss()

    def _selected_task_id(self) -> str | None:
        value = self.query_one("#task-select", Select).value
        return None if value is Select.NULL else str(value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "task-close":
            self.dismiss()
            return
        if self.changes_locked:
            return

        if event.button.id == "task-create":
            title = self.query_one("#task-title-input", Input).value.strip()
            if not title:
                self.notify("Task title cannot be empty", severity="warning")
                return
            self.dismiss(("create", title))
            return
        if event.button.id == "task-unassociate":
            self.dismiss(("unassociate", None))
            return

        task_id = self._selected_task_id()
        if task_id is None:
            self.notify("Select a task first", severity="warning")
            return
        if event.button.id == "task-select-button":
            self.dismiss(("select", task_id))
        elif event.button.id == "task-complete":
            self.dismiss(("complete", task_id))


class PomodoroTUI(App):
    """
    Interface de Terminal (TUI) interativa para o Pomodoro Dog.
    """

    CSS = """
    Screen {
        align: center middle;
        background: #000000;
    }

    #title-display {
        text-align: center;
        color: #FFFFFF;
        text-style: bold;
        width: 90;
        height: 8;
        margin-bottom: 1;
    }

    #main-container {
        width: 90;
        height: 20;
        border: heavy #00E5FF;
        padding: 1 2;
        background: #0D1117;
    }

    #state-label {
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    #active-task-display {
        text-align: center;
        color: #00E5FF;
        margin-bottom: 1;
    }

    #timer-display {
        text-align: center;
        text-style: bold;
        content-align: center middle;
        height: 3;
        border: panel $primary;
        color: $text;
        margin-bottom: 1;
    }

    #stats-panel {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    #button-bar {
        height: 3;
        align: center middle;
    }

    #btn-toggle {
        background: #006D77;
        color: #FFFFFF;
    }

    #btn-toggle:hover {
        background: #007F8B;
    }

    #btn-skip {
        background: #5F3B8C;
        color: #FFFFFF;
    }

    #btn-skip:hover {
        background: #7049A5;
    }

    #btn-reset {
        background: #8F3A46;
        color: #FFFFFF;
    }

    #btn-reset:hover {
        background: #A44755;
    }

    Button {
        width: 20;
        margin: 0 2;
    }
    """

    BINDINGS = [ 
        ("space", "toggle_timer", "Start/Pause"),
        ("s", "skip_phase", "Skip Phase"),
        ("r", "reset_timer", "Reset"),
        ("m", "toggle_sound", "Mute Sound"),
        ("t", "manage_tasks", "Tasks"),
        ("q", "request_quit", "Quit"),
    ]

    def __init__(
        self,
        engine: PomodoroEngine,
        repository: JSONRepository,
        now: Callable[[], datetime] = _current_time,
        *,
        notifier: SessionNotifier | None = None,
        desktop_notifier: DesktopNotifierProtocol | None = None,
    ):
        super().__init__()
        self.engine = engine
        self.repo = repository
        self._notifier = notifier
        self._desktop_notifier = desktop_notifier
        self._sound_enabled = True
        self._now = now
        self._focus_started_at: datetime | None = None
        self._focus_started_clock: float | None = None
        self._focus_task_id: str | None = None
        self._reset_was_running = False
        self._pending_reset_elapsed_seconds = 0.0
        self._pending_reset_ended_at: datetime | None = None
        self._exit_was_running = False
        self._pending_exit_elapsed_seconds = 0.0
        self._pending_exit_ended_at: datetime | None = None
        self._exit_confirmation_pending = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(_TITLE_3D, id="title-display")
        with Container(id="main-container"):
            yield Static(" CURRENT STATUS: FOCUS ", id="state-label")
            active_task = self.repo.get_active_task()
            active_task_title = active_task["title"] if active_task else "None"
            yield Static(
                f"Active Task: {active_task_title}",
                id="active-task-display",
                markup=False,
            )
            yield Static(self.engine.formatted_time(), id="timer-display")

            with Vertical(id="stats-panel"):
                stats = self.repo.get_today_stats()
                yield Static(
                    f"Sessions Today: {stats['completed_sessions']} | Focus Minutes: {stats['focus_minutes']}",
                    id="stats-text",
                )

            with Horizontal(id="button-bar"):
                yield Button("Start (Space)", id="btn-toggle")
                yield Button("Skip (S)", id="btn-skip")
                yield Button("Reset (R)", id="btn-reset")

        yield Footer()

    def on_mount(self) -> None:
        """
        Executado quando a TUI é carregada.
        Configura o timer contínuo (1 segundo).
        """
        self.set_interval(1.0, self._on_tick)

    def _on_tick(self) -> None:
        """
        Chamado a cada 1 segundo pelo timer do Textual.
        """
        if self.engine.is_running:
            previous_state = self.engine.current_state
            phase_completed = self.engine.tick()
            self._handle_phase_completion(previous_state, phase_completed)
        # Atualizamos a interface visual a cada tick independente de estar rodando
        self._update_ui()

    def _handle_phase_completion(
        self, previous_state: TimerState, phase_completed: bool
    ) -> None:
        if not phase_completed:
            return

        if previous_state == TimerState.FOCUS:
            if (
                self._focus_started_at is not None
                and self._focus_started_clock is not None
            ):
                elapsed_time = (
                    self.engine.elapsed_clock_time()
                    - self._focus_started_clock
                    - self.engine.completion_overdue_seconds
                )
                started_at = self._focus_started_at
                ended_at = started_at + timedelta(seconds=max(0.0, elapsed_time))
            else:
                ended_at = self._now() - timedelta(
                    seconds=self.engine.completion_overdue_seconds
                )
                started_at = ended_at - timedelta(seconds=self.engine.focus_time)
            self.repo.save_focus_session(
                started_at=started_at,
                ended_at=ended_at,
                planned_seconds=self.engine.focus_time,
                actual_seconds=self.engine.focus_time,
                status="completed",
                task_id=self._focus_task_id,
            )
            self._focus_started_at = None
            self._focus_started_clock = None
            self._focus_task_id = None

        self._play_completion_sound()
        self._show_completion_notification(previous_state)

    def _play_completion_sound(self) -> None:
        if not self._sound_enabled:
            return
        if self._notifier is None or not self._notifier.notify(
            on_failure=self._ring_terminal_bell_from_thread
        ):
            self.bell()

    def _ring_terminal_bell_from_thread(self) -> None:
        try:
            self.call_from_thread(self.bell)
        except RuntimeError:
            # A reprodução pode falhar depois que a TUI já foi encerrada.
            pass

    def _show_completion_notification(self, previous_state: TimerState) -> None:
        if self._desktop_notifier is None:
            return
        event: DesktopEvent = (
            "focus-complete"
            if previous_state == TimerState.FOCUS
            else "break-complete"
        )
        try:
            self._desktop_notifier.notify(event)
        except Exception:
            # Notificação desktop nunca pode quebrar o timer.
            pass

    def _update_ui(self) -> None:
        """
        Atualiza os textos de tempo e estado na tela.
        """
        timer_widget = self.query_one("#timer-display", Static)
        state_widget = self.query_one("#state-label", Static)
        toggle_button = self.query_one("#btn-toggle", Button)

        timer_widget.update(f"[bold size=2]{self.engine.formatted_time()}[/]")

        estado_nome = self.engine.current_state.value.replace("_", " ")
        state_widget.update(f" CURRENT STATUS: {estado_nome} ")
        toggle_button.label = (
            "Pause (Space)" if self.engine.is_running else "Start (Space)"
        )
        self._update_active_task_display()
        self._update_stats_display()

    def _update_active_task_display(self) -> None:
        active_task = self.repo.get_active_task()
        title = active_task["title"] if active_task else "None"
        self.query_one("#active-task-display", Static).update(f"Active Task: {title}")

    def _update_stats_display(self) -> None:
        """
        Atualiza as estatísticas exibidas na tela.
        """
        stats = self.repo.get_today_stats()
        stats_widget = self.query_one("#stats-text", Static)
        stats_widget.update(
            f"Sessions Today: {stats['completed_sessions']} | Focus Minutes: {stats['focus_minutes']}"
        )

    # --- Ações de Teclado e Botões ---
    def action_toggle_timer(self) -> None:
        if self.engine.is_running:
            previous_state = self.engine.current_state
            phase_completed = self.engine.pause()
            self._handle_phase_completion(previous_state, phase_completed)
        else:
            self.engine.start()
            if self.engine.current_state == TimerState.FOCUS:
                if self._focus_started_at is None:
                    self._focus_started_at = self._now()
                    self._focus_started_clock = self.engine.elapsed_clock_time()
                    active_task = self.repo.get_active_task()
                    self._focus_task_id = (
                        active_task["id"] if active_task is not None else None
                    )
        self._update_ui()

    def action_skip_phase(self) -> None:
        """Pula a fase atual sem registrar uma sessão concluída."""
        if self.engine.is_running:
            previous_state = self.engine.current_state
            phase_completed = self.engine.tick()
            self._handle_phase_completion(previous_state, phase_completed)
            if phase_completed:
                self._update_ui()
                return

        skipped_focus = self.engine.current_state == TimerState.FOCUS
        self.engine.skip_phase()
        if skipped_focus:
            self._focus_started_at = None
            self._focus_started_clock = None
            self._focus_task_id = None
        self._update_ui()

    def action_reset_timer(self) -> None:
        was_running = self.engine.is_running
        if was_running:
            previous_state = self.engine.current_state
            phase_completed = self.engine.pause()
            self._handle_phase_completion(previous_state, phase_completed)

        elapsed_time = self.engine.focus_elapsed_time
        elapsed_seconds = elapsed_time
        if elapsed_seconds > 0:
            self._reset_was_running = was_running
            self._pending_reset_elapsed_seconds = elapsed_seconds
            self._pending_reset_ended_at = self._partial_focus_ended_at()
            self._update_ui()
            self.push_screen(
                ResetConfirmationModal(elapsed_seconds),
                self._handle_reset_decision,
            )
            return

        self._perform_reset()

    def _handle_reset_decision(self, decision: ResetDecision | None) -> None:
        if decision is None:
            if self._reset_was_running:
                self.engine.start()
            self._reset_was_running = False
            self._pending_reset_elapsed_seconds = 0.0
            self._pending_reset_ended_at = None
            self._update_ui()
            return

        if decision == "save":
            ended_at = self._pending_reset_ended_at or self._now()
            self._save_partial_focus(
                elapsed_seconds=self._pending_reset_elapsed_seconds,
                ended_at=ended_at,
            )

        self._perform_reset()

    def _perform_reset(self) -> None:
        self.engine.reset()
        self._focus_started_at = None
        self._focus_started_clock = None
        self._focus_task_id = None
        self._reset_was_running = False
        self._pending_reset_elapsed_seconds = 0.0
        self._pending_reset_ended_at = None
        self._update_ui()

    def action_request_quit(self) -> None:
        if self._exit_confirmation_pending:
            return

        was_running = self.engine.is_running
        if was_running:
            previous_state = self.engine.current_state
            phase_completed = self.engine.pause()
            self._handle_phase_completion(previous_state, phase_completed)
            if phase_completed:
                self._finish_exit()
                return

        elapsed_seconds = self.engine.focus_elapsed_time
        if self.engine.current_state == TimerState.FOCUS and elapsed_seconds > 0:
            self._exit_was_running = was_running
            self._pending_exit_elapsed_seconds = elapsed_seconds
            self._pending_exit_ended_at = self._partial_focus_ended_at()
            self._exit_confirmation_pending = True
            self._update_ui()
            self.push_screen(
                ExitConfirmationModal(elapsed_seconds),
                self._handle_exit_decision,
            )
            return

        self._finish_exit()

    def action_quit(self) -> None:
        """Redireciona o Ctrl+Q herdado do Textual para a saída segura."""
        self.action_request_quit()

    def _handle_exit_decision(self, decision: ResetDecision | None) -> None:
        if decision is None:
            if self._exit_was_running:
                self.engine.start()
            self._clear_pending_exit()
            self._update_ui()
            return

        if decision == "save":
            ended_at = self._pending_exit_ended_at or self._now()
            self._save_partial_focus(
                elapsed_seconds=self._pending_exit_elapsed_seconds,
                ended_at=ended_at,
            )

        self._focus_started_at = None
        self._focus_started_clock = None
        self._focus_task_id = None
        self._clear_pending_exit()
        self._finish_exit()

    def _partial_focus_ended_at(self) -> datetime:
        if (
            self._focus_started_at is not None
            and self._focus_started_clock is not None
        ):
            elapsed_time = self.engine.elapsed_clock_time() - self._focus_started_clock
            return self._focus_started_at + timedelta(seconds=max(0.0, elapsed_time))
        return self._now()

    def _save_partial_focus(
        self, *, elapsed_seconds: float, ended_at: datetime
    ) -> None:
        started_at = self._focus_started_at or ended_at - timedelta(
            seconds=elapsed_seconds
        )
        self.repo.save_focus_session(
            started_at=started_at,
            ended_at=ended_at,
            planned_seconds=self.engine.focus_time,
            actual_seconds=elapsed_seconds,
            status="interrupted",
            task_id=self._focus_task_id,
        )

    def _clear_pending_exit(self) -> None:
        self._exit_was_running = False
        self._pending_exit_elapsed_seconds = 0.0
        self._pending_exit_ended_at = None
        self._exit_confirmation_pending = False

    def _finish_exit(self) -> None:
        for notifier in (self._notifier, self._desktop_notifier):
            wait = getattr(notifier, "wait", None)
            if wait is None:
                continue
            try:
                wait(timeout=1.0)
            except Exception:
                # Falhas no shutdown de integrações externas não impedem a saída.
                pass
        self.exit()

    def action_manage_tasks(self) -> None:
        self.push_screen(
            TaskManagerModal(
                tasks=self.repo.get_tasks(status="open"),
                active_task=self.repo.get_active_task(),
                changes_locked=self._task_changes_locked(),
            ),
            self._handle_task_decision,
        )

    def _handle_task_decision(self, decision: TaskDecision | None) -> None:
        if decision is None:
            return
        if self._task_changes_locked():
            self.notify(
                "Task changes are locked while a focus is in progress",
                severity="warning",
            )
            return

        action, value = decision
        if action == "create":
            task = self.repo.create_task(value or "")
            self.repo.set_active_task(task["id"])
            self.notify(f"Task created: {task['title']}", markup=False)
        elif action == "select" and value is not None:
            task = self.repo.set_active_task(value)
            self.notify(f"Task selected: {task['title']}", markup=False)
        elif action == "unassociate":
            self.repo.set_active_task(None)
            self.notify("Task unassociated")
        elif action == "complete" and value is not None:
            task = self.repo.complete_task(value)
            self.notify(f"Task completed: {task['title']}", markup=False)
        self._update_ui()

    def _task_changes_locked(self) -> bool:
        return (
            self.engine.current_state == TimerState.FOCUS
            and self._focus_started_at is not None
        )

    def action_toggle_sound(self) -> None:
        self._sound_enabled = not self._sound_enabled
        status = "enabled" if self._sound_enabled else "muted"
        self.notify(f"Sound {status}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Lida com cliques de mouse nos botões."""
        if event.button.id == "btn-toggle":
            self.action_toggle_timer()
        elif event.button.id == "btn-skip":
            self.action_skip_phase()
        elif event.button.id == "btn-reset":
            self.action_reset_timer()

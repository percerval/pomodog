import math
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Literal

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Static

from src.core.pomodoro_engine import PomodoroEngine, TimerState
from src.data.json_repository import JSONRepository

_TITLE_3D = """
██████╗  ██████╗ ███╗   ███╗ ██████╗ ██████╗  ██████╗  ██████╗ 
██╔══██╗██╔═══██╗████╗ ████║██╔═══██╗██╔══██╗██╔═══██╗██╔════╝ 
██████╔╝██║   ██║██╔████╔██║██║   ██║██║  ██║██║   ██║██║  ███╗
██╔═══╝ ██║   ██║██║╚██╔╝██║██║   ██║██║  ██║██║   ██║██║   ██║
██║     ╚██████╔╝██║ ╚═╝ ██║╚██████╔╝██████╔╝╚██████╔╝╚██████╔╝
╚═╝      ╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝ 

"""

ResetDecision = Literal["save", "discard"]


def _current_time() -> datetime:
    return datetime.now(timezone.utc)


class ResetConfirmationModal(ModalScreen[ResetDecision]):
    """Solicita uma decisão para o foco parcial antes do reset."""

    AUTO_FOCUS = "#btn-cancel-reset"
    BINDINGS = [("escape", "cancel", "Cancel")]

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
            yield Static("Reset current cycle?", id="reset-title")
            yield Static(
                f"You focused for {minutes:02d}:{seconds:02d}. "
                "Save this partial session before resetting?",
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
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        engine: PomodoroEngine,
        repository: JSONRepository,
        now: Callable[[], datetime] = _current_time,
    ):
        super().__init__()
        self.engine = engine
        self.repo = repository
        self._now = now
        self._focus_started_at: datetime | None = None
        self._focus_started_clock: float | None = None
        self._reset_was_running = False
        self._pending_reset_elapsed_seconds = 0.0
        self._pending_reset_ended_at: datetime | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(_TITLE_3D, id="title-display")
        with Container(id="main-container"):
            yield Static(" CURRENT STATUS: FOCUS ", id="state-label")
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
            self._record_completed_focus(previous_state, phase_completed)
        # Atualizamos a interface visual a cada tick independente de estar rodando
        self._update_ui()

    def _record_completed_focus(
        self, previous_state: TimerState, phase_completed: bool
    ) -> None:
        if not phase_completed or previous_state != TimerState.FOCUS:
            return

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
        )
        self._focus_started_at = None
        self._focus_started_clock = None

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
        self._update_stats_display()

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
            self._record_completed_focus(previous_state, phase_completed)
        else:
            self.engine.start()
            if self.engine.current_state == TimerState.FOCUS:
                if self._focus_started_at is None:
                    self._focus_started_at = self._now()
                    self._focus_started_clock = self.engine.elapsed_clock_time()
        self._update_ui()

    def action_skip_phase(self) -> None:
        """Pula a fase atual sem registrar uma sessão concluída."""
        if self.engine.is_running:
            previous_state = self.engine.current_state
            phase_completed = self.engine.tick()
            self._record_completed_focus(previous_state, phase_completed)
            if phase_completed:
                self._update_ui()
                return

        skipped_focus = self.engine.current_state == TimerState.FOCUS
        self.engine.skip_phase()
        if skipped_focus:
            self._focus_started_at = None
            self._focus_started_clock = None
        self._update_ui()

    def action_reset_timer(self) -> None:
        was_running = self.engine.is_running
        if was_running:
            previous_state = self.engine.current_state
            phase_completed = self.engine.pause()
            self._record_completed_focus(previous_state, phase_completed)

        elapsed_time = self.engine.focus_elapsed_time
        elapsed_seconds = elapsed_time
        if elapsed_seconds > 0:
            self._reset_was_running = was_running
            self._pending_reset_elapsed_seconds = elapsed_seconds
            if (
                self._focus_started_at is not None
                and self._focus_started_clock is not None
            ):
                session_elapsed_time = (
                    self.engine.elapsed_clock_time() - self._focus_started_clock
                )
                ended_at = self._focus_started_at + timedelta(
                    seconds=max(0.0, session_elapsed_time)
                )
            else:
                ended_at = self._now()
            self._pending_reset_ended_at = ended_at
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
            started_at = self._focus_started_at or ended_at - timedelta(
                seconds=self._pending_reset_elapsed_seconds
            )
            self.repo.save_focus_session(
                started_at=started_at,
                ended_at=ended_at,
                planned_seconds=self.engine.focus_time,
                actual_seconds=self._pending_reset_elapsed_seconds,
                status="interrupted",
            )

        self._perform_reset()

    def _perform_reset(self) -> None:
        self.engine.reset()
        self._focus_started_at = None
        self._focus_started_clock = None
        self._reset_was_running = False
        self._pending_reset_elapsed_seconds = 0.0
        self._pending_reset_ended_at = None
        self._update_ui()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Lida com cliques de mouse nos botões."""
        if event.button.id == "btn-toggle":
            self.action_toggle_timer()
        elif event.button.id == "btn-skip":
            self.action_skip_phase()
        elif event.button.id == "btn-reset":
            self.action_reset_timer()

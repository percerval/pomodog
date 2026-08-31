from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from src.core.pomodoro_engine import PomodoroEngine, TimerState
from src.data.json_repository import JSONRepository

class PomodoroTUI(App):
    """
    Interface de Terminal (TUI) interativa para o Pomodoro Dog.
    """

    CSS = """
    Screen {
        align: center middle;
        background: $surface;
    }

    #main-container {
        width: 60;
        height: 22;
        border: heavy $accent;
        padding: 1 2;
        background: $panel;
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

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [ 
        ("space", "toggle_timer", "Iniciar/Pausar"),
        ("s", "skip_phase", "Pular Fase"),
        ("r", "reset_timer", "Resetar"),
        ("q", "quit", "Sair"),
    ]

    def __init__(self, engine: PomodoroEngine, repository: JSONRepository):
        super().__init__()
        self.engine = engine
        self.repo = repository

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            yield Static(" POMODORO DOG ", id="state-label")
            yield Static(self.engine.formatted_time(), id="timer-display")

            with Vertical(id="stats-panel"):
                stats = self.repo.get_today_stats()
                yield Static(
                    f"Sessions Today: {stats['completed_sessions']} | Focus Minutes: {stats['focus_minutes']}",
                    id="stats-text",
                )

            with Horizontal(id="button-bar"):
                yield Button("Iniciar (Espaço)", id="btn-toggle", variant="success")
                yield Button("Pular (S)", id="btn-skip", variant="warning")
                yield Button("Resetar (R)", id="btn-reset", variant="error")

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
            fase_concluida = self.engine.tick()

            # Se a fase de foco terminou, gravamos os dados!
            if fase_concluida and self.engine.current_state != TimerState.FOCUS:
                self.repo.save_completed_session(self.engine.focus_time // 60)
                self._update_stats_display()

            self._update_ui()

    def _update_ui(self) -> None:
        """
        Atualiza os textos de tempo e estado na tela.
        """
        timer_widget = self.query_one("#timer-display", Static)
        state_widget = self.query_one("#state-label", Static)

        timer_widget.update(f"[bold size=2]{self.engine.formatted_time()}[/]")

        estado_nome = self.engine.current_state.value.replace("_", " ")
        state_widget.update(f" CURRENT STATUS: {estado_nome} ")

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
            self.engine.pause()
            self.query_one("#btn-toggle", Button).label = "Iniciar (Espaço)"
        else:
            self.engine.start()
            self.query_one("#btn-toggle", Button).label = "Pausar (Espaço)"

    def action_skip_phase(self) -> None:
        self.engine._advance_to_next_state()
        self._update_ui()

    def action_reset_timer(self) -> None:
        self.engine.reset()
        self._update_ui()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Lida com cliques de mouse nos botões."""
        if event.button.id == "btn-toggle":
            self.action_toggle_timer()
        elif event.button.id == "btn-skip":
            self.action_skip_phase()
        elif event.button.id == "btn-reset":
            self.action_reset_timer()
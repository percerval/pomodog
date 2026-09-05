from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
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
        background: #5B21B6;
        color: #FFFFFF;
    }

    #btn-toggle:hover {
        background: #6D28D9;
    }

    #btn-skip {
        background: #9A3412;
        color: #FFFFFF;
    }

    #btn-skip:hover {
        background: #C2410C;
    }

    #btn-reset {
        background: #991B1B;
        color: #FFFFFF;
    }

    #btn-reset:hover {
        background: #B91C1C;
    }

    Button {
        margin: 0 2;
    }
    """

    BINDINGS = [ 
        ("space", "toggle_timer", "Start/Pause"),
        ("s", "skip_phase", "Skip Phase"),
        ("r", "reset_timer", "Reset"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, engine: PomodoroEngine, repository: JSONRepository):
        super().__init__()
        self.engine = engine
        self.repo = repository

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
            # 1. Guardamos o estado antes do tick
            estado_anterior = self.engine.current_state
            # 2. Executamos o tick
            fase_concluida = self.engine.tick()
            # 3. Se a fase terminou e era de FOCO, salva no JSON!
            if fase_concluida and estado_anterior == TimerState.FOCUS:
                self.repo.save_completed_session(self.engine.focus_time // 60)
        # Atualizamos a interface visual a cada tick independente de estar rodando
        self._update_ui()

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
            self.engine.pause()
            self.query_one("#btn-toggle", Button).label = "Start (Space)"
        else:
            self.engine.start()
            self.query_one("#btn-toggle", Button).label = "Pause (Space)"

    def action_skip_phase(self) -> None:
        """Pula a fase atual sem registrar uma sessão concluída."""
        self.engine.skip_phase()
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

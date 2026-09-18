import math
import time
from collections.abc import Callable
from enum import Enum


def _system_elapsed_time() -> float:
    if hasattr(time, "CLOCK_BOOTTIME"):
        return time.clock_gettime(time.CLOCK_BOOTTIME)
    return time.monotonic()

class TimerState(Enum):
    """
    Representa os possíveis estados do temporizador.
    """

    STOPPED = "STOPPED"
    FOCUS = "FOCUS"
    SHORT_BREAK = "SHORT_BREAK"
    LONG_BREAK = "LONG_BREAK"

class PomodoroEngine:
    """
    Gerencia a lógica de tempo, ciclos e estados do Pomodoro.
    ---
    Esta classe não possui dependências de interface visual (UI)
    Nem banco de dados.
    """

    def __init__(
        self,
        focus_time: int = 25 * 60,
        short_break_time: int = 5 * 60,
        long_break_time: int = 10 * 60,
        cycles_before_long_break: int = 4,
        clock: Callable[[], float] = _system_elapsed_time,
    ):
        # Configurações de tempo (em segundos)
        self.focus_time = focus_time
        self.short_break_time = short_break_time
        self.long_break_time = long_break_time
        self.cycles_before_long_break = cycles_before_long_break
        self._clock = clock
        # Estado interno (Encapsulamento)
        self._current_state = TimerState.STOPPED
        self._current_focus_duration = self.focus_time
        self._seconds_remaining = float(self.focus_time)
        self._completed_cycles = 0
        self._is_running = False
        self._deadline: float | None = None
        self._completion_overdue_seconds = 0.0

    #--------------------------------------------------
    # Getters (Interface pública para leitura de dados)
    #--------------------------------------------------
    @property
    def current_state(self) -> TimerState:
        return self._current_state
    
    @property
    def seconds_remaining(self) -> int:
        return max(0, math.ceil(self._seconds_remaining))

    @property
    def completed_cycles(self) -> int:
        return self._completed_cycles

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def completion_overdue_seconds(self) -> float:
        return self._completion_overdue_seconds

    @property
    def focus_elapsed_time(self) -> float:
        if self._current_state != TimerState.FOCUS:
            return 0.0
        return max(0.0, self._current_focus_duration - self._seconds_remaining)

    @property
    def focus_planned_seconds(self) -> int:
        return self._current_focus_duration

    def elapsed_clock_time(self) -> float:
        return self._clock()

    #--------------------------------------
    # Métodos de Ação (Comandos do usuário)
    #--------------------------------------
    def start(self):
        """
        Iniciar Contagem.
        ---
        Se o estado for STOPPED, define estado inicial para FOCUS.
        """
        if self._is_running:
            return

        if self._current_state == TimerState.STOPPED:
            self._current_state = TimerState.FOCUS
            self._current_focus_duration = self.focus_time
            self._seconds_remaining = float(self.focus_time)
        
        self._is_running = True
        self._deadline = self._clock() + self._seconds_remaining
        self._completion_overdue_seconds = 0.0

    def pause(self) -> bool:
        """
        Sincronizar e pausar a contagem, concluindo a fase se o prazo expirou.
        """
        phase_completed = self.tick()
        if self._is_running:
            self._is_running = False
            self._deadline = None
        return phase_completed

    def reset(self):
        """
        Resetar o temporizador para p estado inicial.
        """
        self._is_running = False
        self._current_state = TimerState.STOPPED
        self._current_focus_duration = self.focus_time
        self._seconds_remaining = float(self.focus_time)
        self._completed_cycles = 0
        self._deadline = None
        self._completion_overdue_seconds = 0.0

    def restore_focus(
        self, elapsed_seconds: float, planned_seconds: int | None = None
    ) -> None:
        """Restaurar um foco pausado a partir de um checkpoint persistido."""
        focus_duration = self.focus_time if planned_seconds is None else planned_seconds
        if focus_duration <= 0:
            raise ValueError("Recovered focus duration must be greater than zero")
        if elapsed_seconds < 0 or elapsed_seconds > focus_duration:
            raise ValueError("Recovered focus elapsed time is out of range")

        self._current_focus_duration = focus_duration
        self._current_state = TimerState.FOCUS
        self._seconds_remaining = float(focus_duration - elapsed_seconds)
        self._is_running = False
        self._deadline = None
        self._completion_overdue_seconds = 0.0

    def skip_phase(self):
        """Pula a fase atual sem contabilizar um foco concluído."""
        if self._current_state == TimerState.STOPPED:
            return

        self._advance_to_next_state(count_completed_focus=False)
    
    def tick(self) -> bool:
        """
        Sincronizar o temporizador com o tempo realmente decorrido.
        ---
        Deve ser chamado periodicamente pelo 'loop' do sistema.
        Retorna True se o ciclo/fase foi concluído neste tick.
        Caso contrário False.
        """
        if not self._is_running or self._deadline is None:
            return False

        seconds_until_deadline = self._deadline - self._clock()
        self._seconds_remaining = max(0.0, seconds_until_deadline)

        # Quando o tempo zerar, avançar para a próxima fase
        if self._seconds_remaining <= 0:
            self._completion_overdue_seconds = max(0.0, -seconds_until_deadline)
            self._advance_to_next_state()
            return True # Sinaliza que uma fase acabou

        self._completion_overdue_seconds = 0.0
        return False

    #-------------------------------------------------------------
    # Métodos Privados / Auxiliares (Regras internas de transição)
    #-------------------------------------------------------------
    def _advance_to_next_state(self, count_completed_focus: bool = True):
        """
        Gerenciar a transição automatica entre FOCUS -> PAUSE -> FOCUS.
        """
        self._is_running = False # Pausa ao trocar de fase
        self._deadline = None

        if self._current_state == TimerState.FOCUS:
            if count_completed_focus:
                self._completed_cycles += 1

            # Decidir se vai para Pausa longa ou Pausa curta
            if (
                count_completed_focus
                and self._completed_cycles % self.cycles_before_long_break == 0
            ):
                self._current_state = TimerState.LONG_BREAK
                self._seconds_remaining = float(self.long_break_time)
            else:
                self._current_state = TimerState.SHORT_BREAK
                self._seconds_remaining = float(self.short_break_time)

        elif self._current_state in (
            TimerState.SHORT_BREAK,
            TimerState.LONG_BREAK,
        ):
            # Terminou a pausa, voltar ao foco
            self._current_state = TimerState.FOCUS
            self._current_focus_duration = self.focus_time
            self._seconds_remaining = float(self.focus_time)

    def formatted_time(self) -> str:
        """
        Método utilitário para formatar o tempo restante em MM:SS.
        """
        minutes, seconds = divmod(self.seconds_remaining, 60)
        return f"{minutes:02d}:{seconds:02d}"

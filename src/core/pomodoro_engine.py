from enum import Enum

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
    ):
        # Configurações de tempo (em segundos)
        self.focus_time = focus_time
        self.short_break_time = short_break_time
        self.long_break_time = long_break_time
        self.cycles_before_long_break = cycles_before_long_break
        # Estado interno (Encapsulamento)
        self._current_state = TimerState.STOPPED
        self._seconds_remaining = self.focus_time
        self._completed_cycles = 0
        self._is_running = False

    #--------------------------------------------------
    # Getters (Interface pública para leitura de dados)
    #--------------------------------------------------
    @property
    def current_state(self) -> TimerState:
        return self._current_state
    
    @property
    def seconds_remaining(self) -> int:
        return self._seconds_remaining

    @property
    def completed_cycles(self) -> int:
        return self._completed_cycles

    @property
    def is_running(self) -> bool:
        return self._is_running

    #--------------------------------------
    # Métodos de Ação (Comandos do usuário)
    #--------------------------------------
    def start(self):
        """
        Iniciar Contagem.
        ---
        Se o estado for STOPPED, define estado inicial para FOCUS.
        """
        if self._current_state == TimerState.STOPPED:
            self._current_state = TimerState.FOCUS
            self._seconds_remaining = self.focus_time
        
        self._is_running = True

    def pause(self):
        """
        Pausar temporariamente a contagem sem alterar o estado atual.
        """
        self._is_running = False

    def reset(self):
        """
        Resetar o temporizador para p estado inicial.
        """
        self._is_running = False
        self._current_state = TimerState.STOPPED
        self._seconds_remaining = self.focus_time

    def skip_phase(self):
        """Pula a fase atual sem contabilizar um foco concluído."""
        if self._current_state == TimerState.STOPPED:
            return

        self._advance_to_next_state(count_completed_focus=False)
    
    def tick(self) -> bool:
        """
        Avançar 1 segundo no temporizador.
        ---
        Deve ser chamado periodicamente pelo 'loop' do sistema.
        Retorna True se o ciclo/fase foi concluído neste tick.
        Caso contrário False.
        """
        if not self._is_running or self._seconds_remaining <= 0:
            return False
        
        self._seconds_remaining -= 1

        # Quando o tempo zerar, avançar para a próxima fase
        if self._seconds_remaining == 0:
            self._advance_to_next_state()
            return True # Sinaliza que uma fase acabou

        return False

    #-------------------------------------------------------------
    # Métodos Privados / Auxiliares (Regras internas de transição)
    #-------------------------------------------------------------
    def _advance_to_next_state(self, count_completed_focus: bool = True):
        """
        Gerenciar a transição automatica entre FOCUS -> PAUSE -> FOCUS.
        """
        self._is_running = False # Pausa ao trocar de fase

        if self._current_state == TimerState.FOCUS:
            if count_completed_focus:
                self._completed_cycles += 1

            # Decidir se vai para Pausa longa ou Pausa curta
            if (
                count_completed_focus
                and self._completed_cycles % self.cycles_before_long_break == 0
            ):
                self._current_state = TimerState.LONG_BREAK
                self._seconds_remaining = self.long_break_time
            else:
                self._current_state = TimerState.SHORT_BREAK
                self._seconds_remaining = self.short_break_time

        elif self._current_state in (
            TimerState.SHORT_BREAK,
            TimerState.LONG_BREAK,
        ):
            # Terminou a pausa, voltar ao foco
            self._current_state = TimerState.FOCUS
            self._seconds_remaining = self.focus_time

    def formatted_time(self) -> str:
        """
        Método utilitário para formatar o tempo restante em MM:SS.
        """
        minutes = self._seconds_remaining // 60
        seconds = self._seconds_remaining % 60
        return f"{minutes:02d}:{seconds:02d}"

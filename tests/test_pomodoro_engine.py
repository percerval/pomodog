from src.core.pomodoro_engine import PomodoroEngine, TimerState


def test_completed_focus_advances_to_short_break():
    engine = PomodoroEngine(focus_time=1)

    engine.start()

    assert engine.tick() is True
    assert engine.current_state == TimerState.SHORT_BREAK
    assert engine.completed_cycles == 1
    assert engine.is_running is False


def test_fourth_completed_focus_advances_to_long_break():
    engine = PomodoroEngine(
        focus_time=1,
        short_break_time=1,
        cycles_before_long_break=4,
    )

    for _ in range(3):
        engine.start()
        engine.tick()
        engine.start()
        engine.tick()

    engine.start()
    engine.tick()

    assert engine.current_state == TimerState.LONG_BREAK
    assert engine.completed_cycles == 4


def test_skipped_focus_is_not_counted_as_completed():
    engine = PomodoroEngine()
    engine.start()

    engine.skip_phase()

    assert engine.current_state == TimerState.SHORT_BREAK
    assert engine.completed_cycles == 0
    assert engine.is_running is False


def test_skip_does_nothing_while_stopped():
    engine = PomodoroEngine()

    engine.skip_phase()

    assert engine.current_state == TimerState.STOPPED
    assert engine.seconds_remaining == engine.focus_time


def test_reset_clears_completed_cycles():
    engine = PomodoroEngine(focus_time=1)
    engine.start()
    engine.tick()

    engine.reset()

    assert engine.current_state == TimerState.STOPPED
    assert engine.completed_cycles == 0
    assert engine.seconds_remaining == engine.focus_time

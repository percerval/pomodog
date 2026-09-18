import pytest

import src.core.pomodoro_engine as engine_module
from src.core.pomodoro_engine import PomodoroEngine, TimerState


def test_completed_focus_advances_to_short_break(fake_clock):
    engine = PomodoroEngine(focus_time=1, clock=fake_clock)

    engine.start()
    fake_clock.advance(1)

    assert engine.tick() is True
    assert engine.current_state == TimerState.SHORT_BREAK
    assert engine.completed_cycles == 1
    assert engine.is_running is False


def test_fourth_completed_focus_advances_to_long_break(fake_clock):
    engine = PomodoroEngine(
        focus_time=1,
        short_break_time=1,
        cycles_before_long_break=4,
        clock=fake_clock,
    )

    for _ in range(3):
        engine.start()
        fake_clock.advance(1)
        engine.tick()
        engine.start()
        fake_clock.advance(1)
        engine.tick()

    engine.start()
    fake_clock.advance(1)
    engine.tick()

    assert engine.current_state == TimerState.LONG_BREAK
    assert engine.completed_cycles == 4


def test_skipped_focus_is_not_counted_as_completed(fake_clock):
    engine = PomodoroEngine(clock=fake_clock)
    engine.start()

    engine.skip_phase()

    assert engine.current_state == TimerState.SHORT_BREAK
    assert engine.completed_cycles == 0
    assert engine.is_running is False


def test_skip_does_nothing_while_stopped(fake_clock):
    engine = PomodoroEngine(clock=fake_clock)

    engine.skip_phase()

    assert engine.current_state == TimerState.STOPPED
    assert engine.seconds_remaining == engine.focus_time


def test_reset_clears_completed_cycles(fake_clock):
    engine = PomodoroEngine(focus_time=1, clock=fake_clock)
    engine.start()
    fake_clock.advance(1)
    engine.tick()

    engine.reset()

    assert engine.current_state == TimerState.STOPPED
    assert engine.completed_cycles == 0
    assert engine.seconds_remaining == engine.focus_time


def test_delayed_tick_uses_actual_elapsed_time(fake_clock):
    engine = PomodoroEngine(focus_time=10, clock=fake_clock)
    engine.start()

    fake_clock.advance(3.4)
    phase_completed = engine.tick()

    assert phase_completed is False
    assert engine.seconds_remaining == 7


def test_delayed_tick_completes_phase_after_deadline(fake_clock):
    engine = PomodoroEngine(focus_time=10, clock=fake_clock)
    engine.start()

    fake_clock.advance(15)

    assert engine.tick() is True
    assert engine.current_state == TimerState.SHORT_BREAK
    assert engine.completion_overdue_seconds == 5


def test_pause_and_resume_preserve_fractional_elapsed_time(fake_clock):
    engine = PomodoroEngine(focus_time=10, clock=fake_clock)
    engine.start()
    fake_clock.advance(2.4)

    assert engine.pause() is False
    assert engine.seconds_remaining == 8

    fake_clock.advance(100)
    assert engine.tick() is False
    assert engine.seconds_remaining == 8

    engine.start()
    fake_clock.advance(7.6)

    assert engine.tick() is True
    assert engine.current_state == TimerState.SHORT_BREAK


def test_restore_focus_continues_from_persisted_elapsed_time(fake_clock):
    engine = PomodoroEngine(focus_time=10, clock=fake_clock)

    engine.restore_focus(4.5)

    assert engine.current_state == TimerState.FOCUS
    assert engine.focus_elapsed_time == 4.5
    assert engine.is_running is False

    engine.start()
    fake_clock.advance(5.5)

    assert engine.tick() is True
    assert engine.current_state == TimerState.SHORT_BREAK


def test_restore_focus_rejects_elapsed_time_outside_duration(fake_clock):
    engine = PomodoroEngine(focus_time=10, clock=fake_clock)

    with pytest.raises(ValueError, match="out of range"):
        engine.restore_focus(11)

    with pytest.raises(ValueError, match="greater than zero"):
        engine.restore_focus(0, planned_seconds=0)


def test_recovered_duration_does_not_change_future_focus_configuration(fake_clock):
    engine = PomodoroEngine(
        focus_time=10,
        short_break_time=1,
        clock=fake_clock,
    )
    engine.restore_focus(4, planned_seconds=8)
    engine.start()
    fake_clock.advance(4)

    assert engine.tick() is True
    assert engine.current_state == TimerState.SHORT_BREAK

    engine.start()
    fake_clock.advance(1)

    assert engine.tick() is True
    assert engine.current_state == TimerState.FOCUS
    assert engine.focus_planned_seconds == 10
    assert engine.seconds_remaining == 10


def test_system_clock_uses_boottime_when_available(monkeypatch):
    monkeypatch.setattr(engine_module.time, "CLOCK_BOOTTIME", 7, raising=False)
    monkeypatch.setattr(
        engine_module.time, "clock_gettime", lambda clock_id: 42.0, raising=False
    )

    assert engine_module._system_elapsed_time() == 42.0


def test_system_clock_falls_back_to_monotonic(monkeypatch):
    monkeypatch.delattr(engine_module.time, "CLOCK_BOOTTIME", raising=False)
    monkeypatch.setattr(engine_module.time, "monotonic", lambda: 42.0)

    assert engine_module._system_elapsed_time() == 42.0

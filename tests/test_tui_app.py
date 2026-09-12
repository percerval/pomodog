import asyncio

import pytest
from textual.widgets import Button

from src.core.pomodoro_engine import PomodoroEngine, TimerState
from src.data.json_repository import JSONRepository
from src.ui.tui_app import PomodoroTUI, ResetConfirmationModal


def run_scenario(scenario):
    asyncio.run(scenario())


def test_reset_can_save_partial_focus(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            engine.tick()
            fake_clock.advance(1)
            engine.tick()
            await pilot.press("r")

            assert isinstance(app.screen, ResetConfirmationModal)
            assert engine.is_running is False
            reset_ended_at = app._pending_reset_ended_at

            await pilot.click("#btn-save-reset")
            await pilot.pause()

            session = repository.get_stats()["sessions"][0]
            assert session["status"] == "interrupted"
            assert session["actual_seconds"] == 2
            assert session["ended_at"] == reset_ended_at.isoformat()
            assert engine.current_state == TimerState.STOPPED
            assert engine.completed_cycles == 0

    run_scenario(scenario)


def test_completed_focus_is_saved_as_completed_session(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=1, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            app._on_tick()

            session = repository.get_stats()["sessions"][0]
            assert session["status"] == "completed"
            assert session["actual_seconds"] == 1
            assert engine.current_state == TimerState.SHORT_BREAK

    run_scenario(scenario)


def test_delayed_callback_records_deadline_as_session_end(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(15)
            app._on_tick()

            session = repository.get_stats()["sessions"][0]
            assert session["started_at"] == "2026-09-05T14:00:00+00:00"
            assert session["ended_at"] == "2026-09-05T14:00:10+00:00"

    run_scenario(scenario)


def test_pause_at_deadline_saves_completed_focus_once(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=1, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            await pilot.press("space")
            app._on_tick()

            sessions = repository.get_stats()["sessions"]
            assert len(sessions) == 1
            assert sessions[0]["status"] == "completed"
            assert engine.current_state == TimerState.SHORT_BREAK

    run_scenario(scenario)


def test_pause_and_resume_keep_precise_session_deadline(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(2.4)
            await pilot.press("space")
            fake_clock.advance(10)
            await pilot.press("space")
            fake_clock.advance(7.6)
            app._on_tick()

            session = repository.get_stats()["sessions"][0]
            assert session["ended_at"] == "2026-09-05T14:00:20+00:00"

    run_scenario(scenario)


def test_skip_at_deadline_completes_focus_without_skipping_break(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=1, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            await pilot.press("s")

            assert engine.current_state == TimerState.SHORT_BREAK
            assert len(repository.get_stats()["sessions"]) == 1

    run_scenario(scenario)


def test_delayed_reset_uses_actual_elapsed_time(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(3.4)
            await pilot.press("r")

            assert isinstance(app.screen, ResetConfirmationModal)
            assert app.screen.elapsed_seconds == pytest.approx(3.4)

    run_scenario(scenario)


def test_reset_after_fractional_second_opens_modal(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(0.2)
            await pilot.press("r")

            assert isinstance(app.screen, ResetConfirmationModal)
            assert app.screen.elapsed_seconds == pytest.approx(0.2)
            await pilot.click("#btn-save-reset")
            await pilot.pause()
            session = repository.get_stats()["sessions"][0]
            assert session["actual_seconds"] == pytest.approx(0.2)
            assert session["started_at"] == "2026-09-05T14:00:00+00:00"
            assert session["ended_at"] == "2026-09-05T14:00:00.200000+00:00"

    run_scenario(scenario)


def test_reset_can_discard_partial_focus(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            engine.tick()
            await pilot.press("r")
            await pilot.click("#btn-discard-reset")
            await pilot.pause()

            assert repository.get_stats()["sessions"] == []
            assert engine.current_state == TimerState.STOPPED

    run_scenario(scenario)


def test_cancel_reset_restores_running_timer(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            engine.tick()
            await pilot.press("r")
            await pilot.press("escape")
            await pilot.pause()

            assert engine.current_state == TimerState.FOCUS
            assert engine.is_running is True
            assert repository.get_stats()["sessions"] == []
            assert str(app.query_one("#btn-toggle", Button).label) == "Pause (Space)"

    run_scenario(scenario)


def test_cancel_reset_keeps_paused_timer_paused(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            engine.tick()
            await pilot.press("space")
            await pilot.press("r")
            await pilot.press("escape")
            await pilot.pause()

            assert engine.current_state == TimerState.FOCUS
            assert engine.is_running is False
            assert repository.get_stats()["sessions"] == []
            assert str(app.query_one("#btn-toggle", Button).label) == "Start (Space)"

    run_scenario(scenario)

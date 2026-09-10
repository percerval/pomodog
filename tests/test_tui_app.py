import asyncio

from textual.widgets import Button

from src.core.pomodoro_engine import PomodoroEngine, TimerState
from src.data.json_repository import JSONRepository
from src.ui.tui_app import PomodoroTUI, ResetConfirmationModal


def run_scenario(scenario):
    asyncio.run(scenario())


def test_reset_can_save_partial_focus(tmp_path):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10)
        app = PomodoroTUI(engine, repository)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            engine.tick()
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
            assert session["ended_at"] == reset_ended_at.isoformat(timespec="seconds")
            assert engine.current_state == TimerState.STOPPED
            assert engine.completed_cycles == 0

    run_scenario(scenario)


def test_completed_focus_is_saved_as_completed_session(tmp_path):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=1)
        app = PomodoroTUI(engine, repository)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            app._on_tick()

            session = repository.get_stats()["sessions"][0]
            assert session["status"] == "completed"
            assert session["actual_seconds"] == 1
            assert engine.current_state == TimerState.SHORT_BREAK

    run_scenario(scenario)


def test_reset_can_discard_partial_focus(tmp_path):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10)
        app = PomodoroTUI(engine, repository)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            engine.tick()
            await pilot.press("r")
            await pilot.click("#btn-discard-reset")
            await pilot.pause()

            assert repository.get_stats()["sessions"] == []
            assert engine.current_state == TimerState.STOPPED

    run_scenario(scenario)


def test_cancel_reset_restores_running_timer(tmp_path):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10)
        app = PomodoroTUI(engine, repository)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            engine.tick()
            await pilot.press("r")
            await pilot.press("escape")
            await pilot.pause()

            assert engine.current_state == TimerState.FOCUS
            assert engine.is_running is True
            assert repository.get_stats()["sessions"] == []
            assert str(app.query_one("#btn-toggle", Button).label) == "Pause (Space)"

    run_scenario(scenario)


def test_cancel_reset_keeps_paused_timer_paused(tmp_path):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10)
        app = PomodoroTUI(engine, repository)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
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

import asyncio
from datetime import timedelta

import pytest
from textual.widgets import Button, Input, Select, Static

from src.core.pomodoro_engine import PomodoroEngine, TimerState
from src.data.json_repository import JSONRepository
from src.ui.tui_app import (
    ExitConfirmationModal,
    FocusRecoveryModal,
    PomodoroTUI,
    ResetConfirmationModal,
    TaskManagerModal,
)


class FakeNotifier:
    def __init__(self, succeeds=True):
        self.succeeds = succeeds
        self.notifications = 0
        self.wait_calls = []

    def notify(self, on_failure=None):
        self.notifications += 1
        return self.succeeds

    def wait(self, timeout):
        self.wait_calls.append(timeout)


class FakeDesktopNotifier:
    def __init__(self, raises=False):
        self.raises = raises
        self.events = []
        self.wait_calls = []

    def notify(self, event):
        if self.raises:
            raise RuntimeError("desktop indisponível")
        self.events.append(event)
        return True

    def wait(self, timeout):
        self.wait_calls.append(timeout)


def run_scenario(scenario):
    asyncio.run(scenario())


def test_reset_can_save_partial_focus(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        notifier = FakeNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            notifier=notifier,
            now=fake_clock.now,
        )

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
            assert notifier.notifications == 0

    run_scenario(scenario)


def test_focus_and_break_completion_use_same_notifier(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(
            focus_time=1,
            short_break_time=1,
            clock=fake_clock,
        )
        notifier = FakeNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            notifier=notifier,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            app._on_tick()
            assert notifier.notifications == 1

            await pilot.press("space")
            fake_clock.advance(1)
            app._on_tick()
            assert notifier.notifications == 2

    run_scenario(scenario)


def test_skip_and_reset_do_not_play_sound(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        notifier = FakeNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            notifier=notifier,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            await pilot.press("s")
            await pilot.press("r")

            assert notifier.notifications == 0

    run_scenario(scenario)


def test_mute_suppresses_sound_until_enabled(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(
            focus_time=1,
            short_break_time=1,
            clock=fake_clock,
        )
        notifier = FakeNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            notifier=notifier,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("m")
            await pilot.press("space")
            fake_clock.advance(1)
            app._on_tick()
            assert notifier.notifications == 0

            await pilot.press("m")
            await pilot.press("space")
            fake_clock.advance(1)
            app._on_tick()
            assert notifier.notifications == 1

    run_scenario(scenario)


def test_unavailable_notifier_uses_terminal_bell(tmp_path, fake_clock, monkeypatch):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=1, clock=fake_clock)
        notifier = FakeNotifier(succeeds=False)
        app = PomodoroTUI(
            engine,
            repository,
            notifier=notifier,
            now=fake_clock.now,
        )
        bell_calls = []
        monkeypatch.setattr(app, "bell", lambda: bell_calls.append(True))

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            app._on_tick()

            assert notifier.notifications == 1
            assert bell_calls == [True]

    run_scenario(scenario)


def test_late_sound_failure_after_app_exit_is_ignored(tmp_path, fake_clock):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    engine = PomodoroEngine(clock=fake_clock)
    app = PomodoroTUI(engine, repository, now=fake_clock.now)

    app._ring_terminal_bell_from_thread()


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
        notifier = FakeNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            notifier=notifier,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            await pilot.press("space")
            app._on_tick()

            sessions = repository.get_stats()["sessions"]
            assert len(sessions) == 1
            assert sessions[0]["status"] == "completed"
            assert engine.current_state == TimerState.SHORT_BREAK
            assert notifier.notifications == 1

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
        notifier = FakeNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            notifier=notifier,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            await pilot.press("s")

            assert engine.current_state == TimerState.SHORT_BREAK
            assert len(repository.get_stats()["sessions"]) == 1
            assert notifier.notifications == 1

    run_scenario(scenario)


def test_reset_at_deadline_completes_focus_and_notifies_once(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=1, clock=fake_clock)
        notifier = FakeNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            notifier=notifier,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            await pilot.press("r")

            assert engine.current_state == TimerState.STOPPED
            assert len(repository.get_stats()["sessions"]) == 1
            assert notifier.notifications == 1

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


def test_desktop_notification_distinguishes_focus_and_break(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(
            focus_time=1,
            short_break_time=1,
            clock=fake_clock,
        )
        desktop = FakeDesktopNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            desktop_notifier=desktop,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            app._on_tick()
            assert desktop.events == ["focus-complete"]

            await pilot.press("space")
            fake_clock.advance(1)
            app._on_tick()
            assert desktop.events == ["focus-complete", "break-complete"]

    run_scenario(scenario)


def test_desktop_notification_is_silent_on_skip_and_reset(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        desktop = FakeDesktopNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            desktop_notifier=desktop,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            await pilot.press("s")
            await pilot.press("r")

            assert desktop.events == []

    run_scenario(scenario)


def test_mute_does_not_suppress_desktop_notification(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=1, clock=fake_clock)
        notifier = FakeNotifier()
        desktop = FakeDesktopNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            notifier=notifier,
            desktop_notifier=desktop,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("m")
            await pilot.press("space")
            fake_clock.advance(1)
            app._on_tick()

            assert notifier.notifications == 0
            assert desktop.events == ["focus-complete"]

    run_scenario(scenario)


def test_desktop_failure_does_not_break_completion(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=1, clock=fake_clock)
        desktop = FakeDesktopNotifier(raises=True)
        app = PomodoroTUI(
            engine,
            repository,
            desktop_notifier=desktop,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            app._on_tick()

            assert engine.current_state == TimerState.SHORT_BREAK
            assert len(repository.get_stats()["sessions"]) == 1

    run_scenario(scenario)


@pytest.mark.parametrize("quit_key", ["q", "ctrl+q"])
def test_quit_at_deadline_saves_completion_and_waits_for_notifications(
    tmp_path, fake_clock, quit_key
):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=1, clock=fake_clock)
        notifier = FakeNotifier()
        desktop = FakeDesktopNotifier()
        app = PomodoroTUI(
            engine,
            repository,
            notifier=notifier,
            desktop_notifier=desktop,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(1)
            await pilot.press(quit_key)

        sessions = repository.get_stats()["sessions"]
        assert len(sessions) == 1
        assert sessions[0]["status"] == "completed"
        assert notifier.notifications == 1
        assert desktop.events == ["focus-complete"]
        assert notifier.wait_calls == [1.0]
        assert desktop.wait_calls == [1.0]

    run_scenario(scenario)


def test_quit_can_save_partial_focus(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(2)
            await pilot.press("q")

            assert isinstance(app.screen, ExitConfirmationModal)
            await pilot.click("#btn-save-reset")

        session = repository.get_stats()["sessions"][0]
        assert session["status"] == "interrupted"
        assert session["actual_seconds"] == 2

    run_scenario(scenario)


def test_quit_can_discard_partial_focus(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(2)
            await pilot.press("q")
            await pilot.click("#btn-discard-reset")

        assert repository.get_stats()["sessions"] == []

    run_scenario(scenario)


def test_cancel_quit_restores_running_focus(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(2)
            await pilot.press("q")
            await pilot.press("escape")
            await pilot.pause()

            assert engine.current_state == TimerState.FOCUS
            assert engine.is_running is True
            assert repository.get_stats()["sessions"] == []

    run_scenario(scenario)


def test_cancel_quit_keeps_paused_focus_paused(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(2)
            await pilot.press("space")
            await pilot.press("q")
            await pilot.press("escape")
            await pilot.pause()

            assert engine.current_state == TimerState.FOCUS
            assert engine.is_running is False
            assert repository.get_stats()["sessions"] == []

    run_scenario(scenario)


def test_repeated_ctrl_q_does_not_stack_exit_modals(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(2)
            await pilot.press("ctrl+q")
            await pilot.press("ctrl+q")
            await pilot.press("escape")
            await pilot.pause()

            assert not isinstance(app.screen, ExitConfirmationModal)
            assert engine.current_state == TimerState.FOCUS
            assert engine.is_running is True
            assert repository.get_stats()["sessions"] == []

    run_scenario(scenario)


def test_task_manager_creates_and_activates_task(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        app = PomodoroTUI(
            PomodoroEngine(clock=fake_clock),
            repository,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("t")
            assert isinstance(app.screen, TaskManagerModal)
            app.screen.query_one("#task-title-input", Input).value = "Write x[/] docs"
            await pilot.click("#task-create")
            await pilot.pause()

            active_task = repository.get_active_task()
            assert active_task is not None
            assert active_task["title"] == "Write x[/] docs"
            assert str(app.query_one("#active-task-display", Static).render()) == (
                "Active Task: Write x[/] docs"
            )

            await pilot.press("t")
            assert isinstance(app.screen, TaskManagerModal)

    run_scenario(scenario)


def test_task_manager_can_select_unassociate_and_complete_task(
    tmp_path, fake_clock
):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        first_task = repository.create_task("First")
        second_task = repository.create_task("Second")
        repository.set_active_task(first_task["id"])
        app = PomodoroTUI(
            PomodoroEngine(clock=fake_clock),
            repository,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("t")
            app.screen.query_one("#task-select", Select).value = second_task["id"]
            await pilot.click("#task-select-button")
            await pilot.pause()
            assert repository.get_active_task()["id"] == second_task["id"]

            await pilot.press("t")
            await pilot.click("#task-unassociate")
            await pilot.pause()
            assert repository.get_active_task() is None

            await pilot.press("t")
            app.screen.query_one("#task-select", Select).value = second_task["id"]
            await pilot.click("#task-complete")
            await pilot.pause()
            assert repository.get_tasks(status="completed")[0]["id"] == second_task[
                "id"
            ]
            assert repository.get_tasks(status="open") == [first_task]

    run_scenario(scenario)


def test_task_changes_are_locked_during_running_and_paused_focus(
    tmp_path, fake_clock
):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        task = repository.create_task("Protected")
        app = PomodoroTUI(
            PomodoroEngine(focus_time=10, clock=fake_clock),
            repository,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            await pilot.press("t")
            assert app.screen.query_one("#task-title-input", Input).disabled is True
            assert app.screen.query_one("#task-select", Select).disabled is True
            await pilot.press("escape")

            await pilot.press("space")
            await pilot.press("t")
            assert app.screen.query_one("#task-create", Button).disabled is True
            assert app.screen.query_one("#task-complete", Button).disabled is True
            await pilot.press("escape")

            assert repository.get_tasks(status="open") == [task]
            assert repository.get_active_task() is None

    run_scenario(scenario)


def test_completed_focus_keeps_task_selected_at_start(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        first_task = repository.create_task("Initial")
        second_task = repository.create_task("Changed externally")
        repository.set_active_task(first_task["id"])
        engine = PomodoroEngine(focus_time=1, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            repository.set_active_task(second_task["id"])
            fake_clock.advance(1)
            app._on_tick()

            session = repository.get_stats()["sessions"][0]
            assert session["task_id"] == first_task["id"]

    run_scenario(scenario)


def test_partial_focus_keeps_task_association(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        task = repository.create_task("Partial work")
        repository.set_active_task(task["id"])
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(2)
            await pilot.press("r")
            await pilot.click("#btn-save-reset")
            await pilot.pause()

            session = repository.get_stats()["sessions"][0]
            assert session["status"] == "interrupted"
            assert session["task_id"] == task["id"]

    run_scenario(scenario)


def test_running_focus_is_checkpointed_every_five_seconds(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            initial_checkpoint = repository.get_active_focus()
            assert initial_checkpoint["elapsed_seconds"] == 0
            assert initial_checkpoint["is_running"] is True

            fake_clock.advance(4)
            app._on_tick()
            assert repository.get_active_focus()["elapsed_seconds"] == 0

            fake_clock.advance(1)
            app._on_tick()
            checkpoint = repository.get_active_focus()
            assert checkpoint["elapsed_seconds"] == 5
            assert checkpoint["checkpointed_at"] == (
                "2026-09-05T14:00:05+00:00"
            )

    run_scenario(scenario)


def test_pause_and_resume_update_recovery_checkpoint(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("space")
            fake_clock.advance(2)
            await pilot.press("space")
            assert repository.get_active_focus()["is_running"] is False
            assert repository.get_active_focus()["elapsed_seconds"] == 2

            await pilot.press("space")
            assert repository.get_active_focus()["is_running"] is True
            assert repository.get_active_focus()["elapsed_seconds"] == 2

    run_scenario(scenario)


def test_recovery_resume_preserves_task_and_session_timestamps(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        task = repository.create_task("Recovered task")
        started_at = fake_clock.now()
        repository.save_active_focus(
            started_at=started_at,
            checkpointed_at=started_at + timedelta(seconds=4),
            planned_seconds=10,
            elapsed_seconds=4,
            task_id=task["id"],
            is_running=True,
        )
        engine = PomodoroEngine(focus_time=10, clock=fake_clock)
        app = PomodoroTUI(engine, repository, now=fake_clock.now)

        async with app.run_test(size=(120, 40)) as pilot:
            assert isinstance(app.screen, FocusRecoveryModal)
            await pilot.click("#recovery-resume")
            await pilot.pause()

            assert engine.current_state == TimerState.FOCUS
            assert engine.is_running is True
            assert engine.focus_elapsed_time == 4

            fake_clock.advance(6)
            app._on_tick()

            session = repository.get_stats()["sessions"][0]
            assert session["started_at"] == "2026-09-05T14:00:00+00:00"
            assert session["ended_at"] == "2026-09-05T14:00:10+00:00"
            assert session["task_id"] == task["id"]
            assert repository.get_active_focus() is None

    run_scenario(scenario)


def test_recovery_can_save_partial_focus(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        started_at = fake_clock.now()
        repository.save_active_focus(
            started_at=started_at,
            checkpointed_at=started_at + timedelta(seconds=4),
            planned_seconds=10,
            elapsed_seconds=4,
            task_id=None,
            is_running=False,
        )
        app = PomodoroTUI(
            PomodoroEngine(focus_time=10, clock=fake_clock),
            repository,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            assert isinstance(app.screen, FocusRecoveryModal)
            await pilot.click("#recovery-save")
            await pilot.pause()

            session = repository.get_stats()["sessions"][0]
            assert session["status"] == "interrupted"
            assert session["actual_seconds"] == 4
            assert session["ended_at"] == "2026-09-05T14:00:04+00:00"
            assert repository.get_active_focus() is None

    run_scenario(scenario)


def test_recovery_can_discard_focus(tmp_path, fake_clock):
    async def scenario():
        repository = JSONRepository(str(tmp_path / "stats.json"))
        started_at = fake_clock.now()
        repository.save_active_focus(
            started_at=started_at,
            checkpointed_at=started_at + timedelta(seconds=2),
            planned_seconds=10,
            elapsed_seconds=2,
            task_id=None,
            is_running=True,
        )
        app = PomodoroTUI(
            PomodoroEngine(focus_time=10, clock=fake_clock),
            repository,
            now=fake_clock.now,
        )

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.click("#recovery-discard")
            await pilot.pause()

            assert repository.get_active_focus() is None
            assert repository.get_stats()["sessions"] == []

    run_scenario(scenario)

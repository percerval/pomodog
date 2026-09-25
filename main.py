from pathlib import Path

from src.core.pomodoro_engine import PomodoroEngine
from src.data.json_repository import JSONRepository
from src.notifications.desktop_notifier import DesktopNotifier
from src.notifications.sound_notifier import SoundNotifier
from src.ui.tui_app import PomodoroTUI


def main():
    project_root = Path(__file__).parent
    engine = PomodoroEngine(
        focus_time=25 * 60, short_break_time=5 * 60, long_break_time=15 * 60
    )
    repo = JSONRepository(str(project_root / "data" / "stats.json"))
    notifier = SoundNotifier(project_root / "assets" / "sounds" / "session-alarm.wav")
    desktop_notifier = DesktopNotifier(project_root / "assets" / "icons" / "pomodog.png")

    app = PomodoroTUI(
        engine=engine,
        repository=repo,
        notifier=notifier,
        desktop_notifier=desktop_notifier,
    )
    app.run()


if __name__ == "__main__":
    main()

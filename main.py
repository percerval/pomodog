from pathlib import Path

from src.core.pomodoro_engine import PomodoroEngine
from src.data.json_repository import JSONRepository
from src.ui.tui_app import PomodoroTUI


def main():
    engine = PomodoroEngine(
        focus_time=25 * 60, short_break_time=5 * 60, long_break_time=15 * 60
    )
    repo = JSONRepository(str(Path(__file__).parent / "data" / "stats.json"))

    app = PomodoroTUI(engine=engine, repository=repo)
    app.run()


if __name__ == "__main__":
    main()

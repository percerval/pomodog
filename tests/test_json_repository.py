import json
from datetime import date

from src.data.json_repository import JSONRepository


def test_repository_creates_an_empty_stats_file(tmp_path):
    stats_path = tmp_path / "stats.json"

    repository = JSONRepository(str(stats_path))

    assert repository.get_stats() == {
        "total_focus_time_minutes": 0,
        "history": {},
    }


def test_repository_saves_completed_session(tmp_path):
    stats_path = tmp_path / "stats.json"
    repository = JSONRepository(str(stats_path))

    repository.save_completed_session(25)

    today = date.today().isoformat()
    assert repository.get_stats() == {
        "total_focus_time_minutes": 25,
        "history": {
            today: {
                "completed_sessions": 1,
                "focus_minutes": 25,
            }
        },
    }
    assert json.loads(stats_path.read_text(encoding="utf-8"))["history"][today][
        "completed_sessions"
    ] == 1

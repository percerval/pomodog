import json
from datetime import date, datetime

import pytest

from src.data.json_repository import JSONRepository


def test_repository_creates_an_empty_stats_file(tmp_path):
    stats_path = tmp_path / "stats.json"

    repository = JSONRepository(str(stats_path))

    assert repository.get_stats() == {
        "schema_version": 2,
        "total_focus_seconds": 0,
        "history": {},
        "sessions": [],
    }


def test_repository_saves_completed_session(tmp_path):
    stats_path = tmp_path / "stats.json"
    repository = JSONRepository(str(stats_path))
    started_at = datetime(2026, 9, 5, 14, 0)
    ended_at = datetime(2026, 9, 5, 14, 25)

    session = repository.save_focus_session(
        started_at=started_at,
        ended_at=ended_at,
        planned_seconds=1500,
        actual_seconds=1500,
        status="completed",
    )

    data = repository.get_stats()
    assert session["status"] == "completed"
    assert data["total_focus_seconds"] == 1500
    assert data["history"]["2026-09-05"] == {
        "completed_sessions": 1,
        "focus_seconds": 1500,
    }
    assert len(data["sessions"]) == 1


def test_interrupted_session_adds_time_without_completing_session(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    started_at = datetime.combine(date.today(), datetime.min.time())

    repository.save_focus_session(
        started_at=started_at,
        ended_at=started_at.replace(minute=12),
        planned_seconds=1500,
        actual_seconds=754,
        status="interrupted",
    )

    assert repository.get_today_stats() == {
        "completed_sessions": 0,
        "focus_seconds": 754,
        "focus_minutes": 12,
    }


def test_repository_migrates_legacy_aggregates(tmp_path):
    stats_path = tmp_path / "stats.json"
    stats_path.write_text(
        json.dumps(
            {
                "total_focus_time_minutes": 100,
                "history": {
                    "2026-08-30": {
                        "completed_sessions": 4,
                        "focus_minutes": 100,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    data = JSONRepository(str(stats_path)).get_stats()

    assert data == {
        "schema_version": 2,
        "total_focus_seconds": 6000,
        "history": {
            "2026-08-30": {
                "completed_sessions": 4,
                "focus_seconds": 6000,
            }
        },
        "sessions": [],
    }


def test_repository_rejects_invalid_session_duration(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    timestamp = datetime(2026, 9, 5, 14, 0)

    with pytest.raises(ValueError, match="greater than zero"):
        repository.save_focus_session(
            started_at=timestamp,
            ended_at=timestamp,
            planned_seconds=1500,
            actual_seconds=0,
            status="interrupted",
        )


def test_repository_rejects_unknown_schema_without_changing_file(tmp_path):
    stats_path = tmp_path / "stats.json"
    original_data = {"schema_version": 3, "sessions": [{"future": True}]}
    stats_path.write_text(json.dumps(original_data), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported schema version: 3"):
        JSONRepository(str(stats_path)).get_stats()

    assert json.loads(stats_path.read_text(encoding="utf-8")) == original_data


def test_repository_groups_session_by_end_date(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))

    repository.save_focus_session(
        started_at=datetime(2026, 9, 5, 23, 50),
        ended_at=datetime(2026, 9, 6, 0, 15),
        planned_seconds=1500,
        actual_seconds=1500,
        status="completed",
    )

    assert "2026-09-05" not in repository.get_stats()["history"]
    assert repository.get_stats()["history"]["2026-09-06"][
        "completed_sessions"
    ] == 1


def test_repository_normalizes_fractional_totals(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    started_at = datetime(2026, 9, 5, 14, 0)

    for actual_seconds in (59.9, 0.1):
        repository.save_focus_session(
            started_at=started_at,
            ended_at=started_at.replace(minute=1),
            planned_seconds=60,
            actual_seconds=actual_seconds,
            status="interrupted",
        )

    data = repository.get_stats()
    assert data["total_focus_seconds"] == 60.0
    assert data["history"]["2026-09-05"]["focus_seconds"] == 60.0

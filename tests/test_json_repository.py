import json
from datetime import date, datetime

import pytest

from src.data.json_repository import JSONRepository


def test_repository_creates_an_empty_stats_file(tmp_path):
    stats_path = tmp_path / "stats.json"

    repository = JSONRepository(str(stats_path))

    assert repository.get_stats() == {
        "schema_version": 3,
        "total_focus_seconds": 0,
        "history": {},
        "tasks": [],
        "active_task_id": None,
        "active_focus": None,
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
    assert session["task_id"] is None
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
        "schema_version": 3,
        "total_focus_seconds": 6000,
        "history": {
            "2026-08-30": {
                "completed_sessions": 4,
                "focus_seconds": 6000,
            }
        },
        "tasks": [],
        "active_task_id": None,
        "active_focus": None,
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
    original_data = {"schema_version": 4, "sessions": [{"future": True}]}
    stats_path.write_text(json.dumps(original_data), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported schema version: 4"):
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


def test_repository_migrates_v2_sessions_without_losing_data(tmp_path):
    stats_path = tmp_path / "stats.json"
    original_session = {
        "id": "session-1",
        "started_at": "2026-09-05T14:00:00",
        "ended_at": "2026-09-05T14:25:00",
        "planned_seconds": 1500,
        "actual_seconds": 1500,
        "status": "completed",
    }
    stats_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "total_focus_seconds": 1500,
                "history": {
                    "2026-09-05": {
                        "completed_sessions": 1,
                        "focus_seconds": 1500,
                    }
                },
                "sessions": [original_session],
            }
        ),
        encoding="utf-8",
    )

    data = JSONRepository(str(stats_path)).get_stats()

    assert data["schema_version"] == 3
    assert data["tasks"] == []
    assert data["active_task_id"] is None
    assert data["active_focus"] is None
    assert data["sessions"] == [{**original_session, "task_id": None}]
    assert data["total_focus_seconds"] == 1500


def test_repository_creates_selects_and_completes_task(tmp_path):
    stats_path = tmp_path / "stats.json"
    repository = JSONRepository(str(stats_path))

    task = repository.create_task("  Implementar tasks  ")

    assert task["title"] == "Implementar tasks"
    assert task["status"] == "open"
    assert repository.get_tasks(status="open") == [task]
    assert repository.set_active_task(task["id"]) == task
    assert JSONRepository(str(stats_path)).get_active_task() == task

    completed_task = repository.complete_task(task["id"])

    assert completed_task["status"] == "completed"
    assert repository.get_active_task() is None
    assert repository.get_tasks(status="open") == []
    assert repository.get_tasks(status="completed") == [completed_task]


def test_repository_rejects_empty_task_title(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))

    with pytest.raises(ValueError, match="cannot be empty"):
        repository.create_task("   ")

    assert repository.get_tasks() == []


def test_repository_rejects_unknown_or_completed_active_task(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))

    with pytest.raises(ValueError, match="Unknown task"):
        repository.set_active_task("missing")

    task = repository.create_task("Concluir depois")
    repository.complete_task(task["id"])

    with pytest.raises(ValueError, match="cannot be selected"):
        repository.set_active_task(task["id"])


def test_repository_saves_session_with_task(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    task = repository.create_task("Escrever testes")
    started_at = datetime(2026, 9, 5, 14, 0)

    session = repository.save_focus_session(
        started_at=started_at,
        ended_at=started_at.replace(minute=25),
        planned_seconds=1500,
        actual_seconds=1500,
        status="completed",
        task_id=task["id"],
    )

    assert session["task_id"] == task["id"]


def test_repository_rejects_session_with_unknown_task(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    started_at = datetime(2026, 9, 5, 14, 0)

    with pytest.raises(ValueError, match="Unknown task"):
        repository.save_focus_session(
            started_at=started_at,
            ended_at=started_at.replace(minute=25),
            planned_seconds=1500,
            actual_seconds=1500,
            status="completed",
            task_id="missing",
        )

    assert repository.get_stats()["sessions"] == []


def test_repository_adds_active_focus_to_existing_v3_file(tmp_path):
    stats_path = tmp_path / "stats.json"
    original_data = {
        "schema_version": 3,
        "total_focus_seconds": 0,
        "history": {},
        "tasks": [],
        "active_task_id": None,
        "sessions": [],
    }
    stats_path.write_text(json.dumps(original_data), encoding="utf-8")

    data = JSONRepository(str(stats_path)).get_stats()

    assert data == {**original_data, "active_focus": None}


def test_repository_saves_and_clears_active_focus(tmp_path):
    stats_path = tmp_path / "stats.json"
    repository = JSONRepository(str(stats_path))
    task = repository.create_task("Recover me")
    started_at = datetime(2026, 9, 5, 14, 0)
    checkpointed_at = datetime(2026, 9, 5, 14, 5)

    active_focus = repository.save_active_focus(
        started_at=started_at,
        checkpointed_at=checkpointed_at,
        planned_seconds=1500,
        elapsed_seconds=300,
        task_id=task["id"],
        is_running=True,
    )

    assert JSONRepository(str(stats_path)).get_active_focus() == active_focus
    assert active_focus == {
        "started_at": "2026-09-05T14:00:00",
        "checkpointed_at": "2026-09-05T14:05:00",
        "planned_seconds": 1500,
        "elapsed_seconds": 300,
        "task_id": task["id"],
        "is_running": True,
    }

    repository.clear_active_focus()

    assert repository.get_active_focus() is None


def test_repository_rejects_invalid_active_focus_without_overwriting(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    timestamp = datetime(2026, 9, 5, 14, 0)

    with pytest.raises(ValueError, match="out of range"):
        repository.save_active_focus(
            started_at=timestamp,
            checkpointed_at=timestamp,
            planned_seconds=1500,
            elapsed_seconds=1501,
            task_id=None,
            is_running=True,
        )

    assert repository.get_active_focus() is None


def test_saving_session_can_atomically_resolve_active_focus(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    started_at = datetime(2026, 9, 5, 14, 0)
    ended_at = datetime(2026, 9, 5, 14, 5)
    repository.save_active_focus(
        started_at=started_at,
        checkpointed_at=ended_at,
        planned_seconds=1500,
        elapsed_seconds=300,
        task_id=None,
        is_running=True,
    )

    repository.save_focus_session(
        started_at=started_at,
        ended_at=ended_at,
        planned_seconds=1500,
        actual_seconds=300,
        status="interrupted",
        resolve_active_focus=True,
    )

    data = repository.get_stats()
    assert len(data["sessions"]) == 1
    assert data["active_focus"] is None


def test_task_productivity_aggregates_and_orders_sessions(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    primary = repository.create_task("Primary")
    secondary = repository.create_task("Secondary")
    idle = repository.create_task("Idle")
    started_at = datetime(2026, 9, 5, 14, 0)

    sessions = [
        (primary["id"], 120, "completed"),
        (primary["id"], 30, "interrupted"),
        (secondary["id"], 60, "completed"),
        (None, 20, "interrupted"),
    ]
    for task_id, seconds, status in sessions:
        repository.save_focus_session(
            started_at=started_at,
            ended_at=started_at.replace(minute=5),
            planned_seconds=300,
            actual_seconds=seconds,
            status=status,
            task_id=task_id,
        )

    rows = repository.get_task_productivity()

    assert [row["title"] for row in rows] == [
        "Primary",
        "Secondary",
        "Sem task",
        "Idle",
    ]
    assert rows[0] == {
        "task_id": primary["id"],
        "title": "Primary",
        "task_status": "open",
        "focus_seconds": 150.0,
        "completed_sessions": 1,
        "interrupted_sessions": 1,
    }
    assert rows[2]["task_id"] is None
    assert rows[2]["interrupted_sessions"] == 1
    assert rows[3]["task_id"] == idle["id"]
    assert rows[3]["focus_seconds"] == 0


def test_task_productivity_can_filter_by_end_date(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    task = repository.create_task("Daily")

    for ended_at, seconds in (
        (datetime(2026, 9, 5, 23, 59), 60),
        (datetime(2026, 9, 6, 0, 1), 120),
    ):
        repository.save_focus_session(
            started_at=ended_at.replace(minute=0),
            ended_at=ended_at,
            planned_seconds=300,
            actual_seconds=seconds,
            status="completed",
            task_id=task["id"],
        )

    rows = repository.get_task_productivity(day=date(2026, 9, 5))

    assert len(rows) == 1
    assert rows[0]["focus_seconds"] == 60.0
    assert rows[0]["completed_sessions"] == 1


def test_delete_task_unassociates_history_and_active_focus_atomically(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    task = repository.create_task("Delete me")
    repository.set_active_task(task["id"])
    started_at = datetime(2026, 9, 5, 14, 0)
    ended_at = datetime(2026, 9, 5, 14, 5)
    for status in ("completed", "interrupted"):
        repository.save_focus_session(
            started_at=started_at,
            ended_at=ended_at,
            planned_seconds=300,
            actual_seconds=300,
            status=status,
            task_id=task["id"],
        )
    repository.save_active_focus(
        started_at=started_at,
        checkpointed_at=ended_at,
        planned_seconds=1500,
        elapsed_seconds=300,
        task_id=task["id"],
        is_running=False,
    )
    result = repository.delete_task(task["id"])

    data = repository.get_stats()
    assert result == {"task": task, "unassociated_sessions": 2}
    assert data["tasks"] == []
    assert data["active_task_id"] is None
    assert data["active_focus"]["task_id"] is None
    assert all(session["task_id"] is None for session in data["sessions"])
    assert data["total_focus_seconds"] == 600
    assert data["history"]["2026-09-05"]["completed_sessions"] == 1


def test_delete_task_rejects_unknown_id_without_changing_data(tmp_path):
    repository = JSONRepository(str(tmp_path / "stats.json"))
    original_data = repository.get_stats()

    with pytest.raises(ValueError, match="Unknown task"):
        repository.delete_task("missing")

    assert repository.get_stats() == original_data

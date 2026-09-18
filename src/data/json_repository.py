import json
import os
import tempfile
from datetime import date, datetime
from typing import Literal
from uuid import uuid4


SessionStatus = Literal["completed", "interrupted"]
TaskStatus = Literal["open", "completed"]

class JSONRepository:
    """
    Gerencia a persistência de dados e o histórico de sessões do Pomodoro em um arquivo JSON.
    Seguindo o padrão Repository para desacoplar o armazenamento de dados das interfaces.
    """

    def __init__(self, file_path: str = "data/stats.json"):
        self.file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """
        Método privado que garante que a pasta e o arquivo JSON existam no disco.
        """
        folder = os.path.dirname(self.file_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

        if not os.path.exists(self.file_path):
            self._write_json(self._initial_data())

    @staticmethod
    def _initial_data() -> dict:
        return {
            "schema_version": 3,
            "total_focus_seconds": 0,
            "history": {},
            "tasks": [],
            "active_task_id": None,
            "sessions": [],
        }

    def _migrate_data(self, data: dict) -> dict:
        schema_version = data.get("schema_version")
        if schema_version == 3:
            return data
        if schema_version == 2:
            migrated_data = {
                **data,
                "schema_version": 3,
                "tasks": [],
                "active_task_id": None,
                "sessions": [
                    {**session, "task_id": session.get("task_id")}
                    for session in data.get("sessions", [])
                ],
            }
            self._write_json(migrated_data)
            return migrated_data
        if schema_version is not None:
            raise ValueError(f"Unsupported schema version: {schema_version}")

        history = {}
        for day, stats in data.get("history", {}).items():
            history[day] = {
                "completed_sessions": stats.get("completed_sessions", 0),
                "focus_seconds": stats.get("focus_minutes", 0) * 60,
            }

        migrated_data = {
            "schema_version": 3,
            "total_focus_seconds": data.get("total_focus_time_minutes", 0) * 60,
            "history": history,
            "tasks": [],
            "active_task_id": None,
            "sessions": [],
        }
        self._write_json(migrated_data)
        return migrated_data
    
    def _read_json(self) -> dict:
        """
        Lê e converte o conteúdo do arquivo JSON para um dicionário Python.
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as  file:
                return self._migrate_data(json.load(file))
        except(json.JSONDecodeError, FileNotFoundError):
            # Se o arquivo estiver corrompido ou ausente, restaura a estrutura inicial
            initial_data = self._initial_data()
            self._write_json(initial_data)
            return initial_data

    def _write_json(self, data: dict):
        """
        Escreve a estrutura de dados novamente no JSON com formatação legível.
        """
        folder = os.path.dirname(self.file_path) or "."
        file_descriptor, temporary_path = tempfile.mkstemp(
            dir=folder, prefix=".stats-", suffix=".tmp"
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.file_path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    #---------------------------------------------------
    # Métodos Públicos (Interface utilizada pelo App/UI)
    #---------------------------------------------------
    def save_focus_session(
        self,
        *,
        started_at: datetime,
        ended_at: datetime,
        planned_seconds: int,
        actual_seconds: float,
        status: SessionStatus,
        task_id: str | None = None,
    ) -> dict:
        """Registra uma sessão de foco e atualiza os agregados diários."""
        if status not in ("completed", "interrupted"):
            raise ValueError(f"Unsupported session status: {status}")
        if planned_seconds <= 0 or actual_seconds <= 0:
            raise ValueError("Session durations must be greater than zero")
        if actual_seconds > planned_seconds:
            raise ValueError("Actual duration cannot exceed planned duration")
        if ended_at < started_at:
            raise ValueError("Session end cannot precede its start")

        actual_seconds = round(actual_seconds, 6)
        data = self._read_json()
        if task_id is not None and not any(
            task["id"] == task_id for task in data["tasks"]
        ):
            raise ValueError(f"Unknown task: {task_id}")
        session = {
            "id": str(uuid4()),
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "planned_seconds": planned_seconds,
            "actual_seconds": actual_seconds,
            "status": status,
            "task_id": task_id,
        }
        data["sessions"].append(session)
        data["total_focus_seconds"] = round(
            data["total_focus_seconds"] + actual_seconds, 6
        )

        session_day = (
            ended_at.astimezone().date() if ended_at.tzinfo else ended_at.date()
        ).isoformat()
        if session_day not in data["history"]:
            data["history"][session_day] = {
                "completed_sessions": 0,
                "focus_seconds": 0,
            }

        if status == "completed":
            data["history"][session_day]["completed_sessions"] += 1
        data["history"][session_day]["focus_seconds"] = round(
            data["history"][session_day]["focus_seconds"] + actual_seconds, 6
        )

        self._write_json(data)
        return session

    def create_task(self, title: str) -> dict:
        """Criar e persistir uma task aberta."""
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Task title cannot be empty")

        data = self._read_json()
        task = {
            "id": str(uuid4()),
            "title": normalized_title,
            "status": "open",
        }
        data["tasks"].append(task)
        self._write_json(data)
        return task

    def get_tasks(self, status: TaskStatus | None = None) -> list[dict]:
        """Listar tasks, opcionalmente filtradas pelo status."""
        tasks = self._read_json()["tasks"]
        if status is None:
            return tasks
        return [task for task in tasks if task["status"] == status]

    def get_active_task(self) -> dict | None:
        """Retornar a task selecionada para os próximos focos."""
        data = self._read_json()
        active_task_id = data["active_task_id"]
        return next(
            (task for task in data["tasks"] if task["id"] == active_task_id),
            None,
        )

    def set_active_task(self, task_id: str | None) -> dict | None:
        """Selecionar uma task aberta ou remover a seleção atual."""
        data = self._read_json()
        if task_id is None:
            data["active_task_id"] = None
            self._write_json(data)
            return None

        task = next(
            (task for task in data["tasks"] if task["id"] == task_id),
            None,
        )
        if task is None:
            raise ValueError(f"Unknown task: {task_id}")
        if task["status"] != "open":
            raise ValueError("Completed task cannot be selected")

        data["active_task_id"] = task_id
        self._write_json(data)
        return task

    def complete_task(self, task_id: str) -> dict:
        """Marcar uma task como concluída, preservando seu histórico."""
        data = self._read_json()
        task = next(
            (task for task in data["tasks"] if task["id"] == task_id),
            None,
        )
        if task is None:
            raise ValueError(f"Unknown task: {task_id}")

        task["status"] = "completed"
        if data["active_task_id"] == task_id:
            data["active_task_id"] = None
        self._write_json(data)
        return task

    def get_stats(self) -> dict:
        """
        Retorna o dicionário completo de estatísticas e histórico.
        """
        return self._read_json()

    def get_today_stats(self) -> dict:
        """Retorna estatísticas apenas da data atual (sessões e minutos)."""
        data = self._read_json()
        today = date.today().isoformat()
        stats = data["history"].get(
            today, {"completed_sessions": 0, "focus_seconds": 0}
        )
        return {
            "completed_sessions": stats["completed_sessions"],
            "focus_seconds": stats["focus_seconds"],
            "focus_minutes": int(stats["focus_seconds"] // 60),
        }

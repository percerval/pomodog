"""Notificações desktop via Freedesktop Notifications (notify-send)."""

import shutil
import subprocess
import threading
from pathlib import Path
from typing import Literal, Protocol

DesktopEvent = Literal["focus-complete", "break-complete"]

_MESSAGES: dict[DesktopEvent, tuple[str, str]] = {
    "focus-complete": ("Foco concluído", "Hora de fazer uma pausa."),
    "break-complete": ("Pausa concluída", "Hora de voltar ao foco."),
}


class DesktopNotifierProtocol(Protocol):
    def notify(self, event: DesktopEvent) -> bool:
        """Exibir uma notificação e informar se o envio foi iniciado."""
        ...


class DesktopNotifier:
    """Envia popups do sistema sem bloquear a aplicação."""

    def __init__(self, icon_path: str | Path | None = None):
        self.icon_path = Path(icon_path) if icon_path is not None else None

    def notify(self, event: DesktopEvent) -> bool:
        title, body = _MESSAGES[event]
        executable = shutil.which("notify-send")
        if executable is None:
            return False

        command = [
            executable,
            "--app-name=Pomodog",
            "--urgency=normal",
            "--expire-time=5000",
        ]
        if self.icon_path is not None and self.icon_path.is_file():
            command.append(f"--icon={self.icon_path}")
        command.extend([title, body])

        def send_notification() -> None:
            try:
                subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass

        try:
            threading.Thread(target=send_notification, daemon=True).start()
        except RuntimeError:
            return False
        return True

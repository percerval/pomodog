"""Notificações desktop via notify-send, com fallback para KDE."""

import shutil
import subprocess
import threading
import time
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
        self._threads: set[threading.Thread] = set()
        self._threads_lock = threading.RLock()

    def notify(self, event: DesktopEvent) -> bool:
        title, body = _MESSAGES[event]
        commands = self._commands(title, body)
        if not commands:
            return False

        def send_notification() -> None:
            try:
                for command in commands:
                    try:
                        result = subprocess.run(
                            command,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=10,
                            check=False,
                        )
                    except (OSError, subprocess.TimeoutExpired):
                        continue
                    if result.returncode == 0:
                        return
            finally:
                with self._threads_lock:
                    self._threads.discard(thread)

        thread = threading.Thread(target=send_notification, daemon=True)
        with self._threads_lock:
            self._threads.add(thread)
            try:
                thread.start()
            except RuntimeError:
                self._threads.discard(thread)
                return False
        return True

    def _commands(self, title: str, body: str) -> list[list[str]]:
        commands = []
        icon_exists = self.icon_path is not None and self.icon_path.is_file()

        notify_send = shutil.which("notify-send")
        if notify_send is not None:
            command = [
                notify_send,
                "--app-name=Pomodog",
                "--urgency=critical",
                "--expire-time=8000",
            ]
            if icon_exists:
                command.append(f"--icon={self.icon_path}")
            command.extend([title, body])
            commands.append(command)

        kdialog = shutil.which("kdialog")
        if kdialog is not None:
            command = [kdialog, "--title", "Pomodog"]
            if icon_exists:
                command.extend(["--icon", str(self.icon_path)])
            command.extend(["--passivepopup", f"{title}\n{body}", "8"])
            commands.append(command)

        return commands

    def wait(self, timeout: float) -> None:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            with self._threads_lock:
                threads = tuple(self._threads)
            if not threads:
                return

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            threads[0].join(remaining)

import shutil
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class SessionNotifier(Protocol):
    def notify(self, on_failure: Callable[[], None] | None = None) -> bool:
        """Emitir uma notificação e informar se ela foi iniciada."""
        ...


class SoundNotifier:
    """Reproduz um arquivo de áudio sem bloquear a aplicação."""

    _PLAYERS = (
        ("pw-play", ()),
        ("paplay", ()),
        ("aplay", ("--quiet",)),
    )

    def __init__(self, sound_path: str | Path):
        self.sound_path = Path(sound_path)

    def notify(self, on_failure: Callable[[], None] | None = None) -> bool:
        if not self.sound_path.is_file():
            return False

        commands = []
        for player, options in self._PLAYERS:
            executable = shutil.which(player)
            if executable is not None:
                commands.append([executable, *options, str(self.sound_path)])

        if not commands:
            return False

        def play_sound() -> None:
            for command in commands:
                try:
                    result = subprocess.run(
                        command,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                        check=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    continue

                if result.returncode == 0:
                    return

            if on_failure is not None:
                on_failure()

        try:
            threading.Thread(target=play_sound, daemon=True).start()
        except RuntimeError:
            return False
        return True

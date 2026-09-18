import shutil
import subprocess
import threading
import time
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
        self._threads: set[threading.Thread] = set()
        self._threads_lock = threading.RLock()

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
            try:
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
            finally:
                with self._threads_lock:
                    self._threads.discard(thread)

        thread = threading.Thread(target=play_sound, daemon=True)
        with self._threads_lock:
            self._threads.add(thread)
            try:
                thread.start()
            except RuntimeError:
                self._threads.discard(thread)
                return False
        return True

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

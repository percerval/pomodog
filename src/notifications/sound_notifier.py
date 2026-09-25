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

    def stop(self) -> None:
        """Interromper notificações em andamento."""
        ...


class SoundNotifier:
    """Reproduz um arquivo de áudio sem bloquear a aplicação."""

    _PLAYERS = (
        ("pw-play", ()),
        ("paplay", ()),
        ("aplay", ("--quiet",)),
    )

    def __init__(self, sound_path: str | Path, max_duration: float = 8.0):
        self.sound_path = Path(sound_path)
        self.max_duration = max(0.0, max_duration)
        self._threads: set[threading.Thread] = set()
        self._stop_events: set[threading.Event] = set()
        self._processes: set[subprocess.Popen] = set()
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

        self.stop()
        stop_event = threading.Event()

        def play_sound() -> None:
            deadline = time.monotonic() + self.max_duration
            try:
                for command in commands:
                    if stop_event.is_set():
                        return
                    try:
                        process = subprocess.Popen(
                            command,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except OSError:
                        continue

                    with self._threads_lock:
                        self._processes.add(process)

                    while process.poll() is None:
                        remaining = deadline - time.monotonic()
                        if stop_event.wait(min(0.05, max(0.0, remaining))):
                            self._terminate_and_wait(process)
                            return
                        if remaining <= 0:
                            self._terminate_and_wait(process)
                            if on_failure is not None:
                                on_failure()
                            return

                    with self._threads_lock:
                        self._processes.discard(process)
                    if process.returncode == 0:
                        return

                if on_failure is not None:
                    on_failure()
            finally:
                with self._threads_lock:
                    self._processes.discard(locals().get("process"))
                    self._stop_events.discard(stop_event)
                    self._threads.discard(thread)

        thread = threading.Thread(target=play_sound, daemon=True)
        with self._threads_lock:
            self._threads.add(thread)
            self._stop_events.add(stop_event)
            try:
                thread.start()
            except RuntimeError:
                self._threads.discard(thread)
                self._stop_events.discard(stop_event)
                return False
        return True

    def stop(self) -> None:
        with self._threads_lock:
            stop_events = tuple(self._stop_events)
            processes = tuple(self._processes)

        for stop_event in stop_events:
            stop_event.set()
        for process in processes:
            self._request_termination(process)

    @staticmethod
    def _request_termination(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
        except OSError:
            pass

    @staticmethod
    def _terminate_and_wait(process: subprocess.Popen) -> None:
        if process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        try:
            process.wait(timeout=0.5)
            return
        except OSError:
            return
        except subprocess.TimeoutExpired:
            pass

        try:
            process.kill()
            process.wait(timeout=0.5)
        except (OSError, subprocess.TimeoutExpired):
            pass

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

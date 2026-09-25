import subprocess
import threading
import wave
from pathlib import Path

import src.notifications.sound_notifier as sound_module
from src.notifications.sound_notifier import SoundNotifier


class ImmediateThread:
    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


class FailingThread(ImmediateThread):
    def start(self):
        raise RuntimeError("thread unavailable")


class FinishedProcess:
    def __init__(self, returncode=0):
        self.returncode = returncode

    def poll(self):
        return self.returncode


class BlockingProcess:
    def __init__(self, started=None, release=None):
        self.returncode = None
        self.terminated = False
        self.killed = False
        self._started = started
        self._release = release
        if started is not None:
            started.set()

    def poll(self):
        if self._release is not None and self._release.is_set():
            self.returncode = 0
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


class SlowTerminationProcess(BlockingProcess):
    def __init__(self):
        super().__init__()
        self.wait_calls = 0

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.wait_calls += 1
        if not self.killed:
            raise subprocess.TimeoutExpired("player", timeout)
        self.returncode = -9
        return self.returncode


def configure_players(monkeypatch, available, *, immediate_thread=True):
    monkeypatch.setattr(
        sound_module.shutil,
        "which",
        lambda player: f"/usr/bin/{player}" if player in available else None,
    )
    if immediate_thread:
        monkeypatch.setattr(sound_module.threading, "Thread", ImmediateThread)


def test_bundled_alarm_fits_inside_playback_limit():
    sound_path = Path(__file__).parents[1] / "assets" / "sounds" / "session-alarm.wav"

    with wave.open(str(sound_path), "rb") as sound:
        duration = sound.getnframes() / sound.getframerate()

    assert 7.0 <= duration < 8.0


def test_notifier_prefers_pw_play(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    calls = []
    configure_players(monkeypatch, {"pw-play", "paplay", "aplay"})

    def popen(command, **options):
        calls.append((command, options))
        return FinishedProcess()

    monkeypatch.setattr(sound_module.subprocess, "Popen", popen)

    assert SoundNotifier(sound_path).notify() is True
    assert calls == [
        (
            ["/usr/bin/pw-play", str(sound_path)],
            {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            },
        )
    ]


def test_notifier_falls_back_after_nonzero_exit(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    commands = []
    configure_players(monkeypatch, {"pw-play", "paplay"})

    def popen(command, **options):
        commands.append(command)
        return FinishedProcess(1 if command[0].endswith("pw-play") else 0)

    monkeypatch.setattr(sound_module.subprocess, "Popen", popen)

    assert SoundNotifier(sound_path).notify() is True
    assert commands == [
        ["/usr/bin/pw-play", str(sound_path)],
        ["/usr/bin/paplay", str(sound_path)],
    ]


def test_aplay_uses_quiet_option(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    commands = []
    configure_players(monkeypatch, {"aplay"})
    monkeypatch.setattr(
        sound_module.subprocess,
        "Popen",
        lambda command, **options: commands.append(command) or FinishedProcess(),
    )

    assert SoundNotifier(sound_path).notify() is True
    assert commands == [["/usr/bin/aplay", "--quiet", str(sound_path)]]


def test_notifier_calls_failure_callback_when_all_players_fail(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    failures = []
    configure_players(monkeypatch, {"pw-play"})
    monkeypatch.setattr(
        sound_module.subprocess,
        "Popen",
        lambda command, **options: FinishedProcess(1),
    )

    assert SoundNotifier(sound_path).notify(lambda: failures.append(True)) is True
    assert failures == [True]


def test_stop_terminates_active_alarm(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    started = threading.Event()
    process = BlockingProcess(started=started)
    configure_players(monkeypatch, {"pw-play"}, immediate_thread=False)
    monkeypatch.setattr(sound_module.subprocess, "Popen", lambda *args, **kwargs: process)
    notifier = SoundNotifier(sound_path)

    assert notifier.notify() is True
    assert started.wait(timeout=1)
    notifier.stop()
    notifier.wait(timeout=1)

    assert process.terminated is True
    assert notifier._threads == set()


def test_notifier_stops_player_at_max_duration(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    process = BlockingProcess()
    configure_players(monkeypatch, {"pw-play"}, immediate_thread=False)
    monkeypatch.setattr(sound_module.subprocess, "Popen", lambda *args, **kwargs: process)
    failures = []
    notifier = SoundNotifier(sound_path, max_duration=0.01)

    assert notifier.notify(lambda: failures.append(True)) is True
    notifier.wait(timeout=1)

    assert process.terminated is True
    assert failures == [True]


def test_stop_does_not_wait_for_player_in_calling_thread(tmp_path):
    notifier = SoundNotifier(tmp_path / "sound.wav")
    process = SlowTerminationProcess()
    notifier._processes.add(process)

    notifier.stop()

    assert process.terminated is True
    assert process.wait_calls == 0


def test_timeout_kills_and_reaps_unresponsive_player(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    process = SlowTerminationProcess()
    configure_players(monkeypatch, {"pw-play"}, immediate_thread=False)
    monkeypatch.setattr(sound_module.subprocess, "Popen", lambda *args, **kwargs: process)
    notifier = SoundNotifier(sound_path, max_duration=0.01)

    assert notifier.notify() is True
    notifier.wait(timeout=1)

    assert process.killed is True
    assert process.wait_calls == 2


def test_notifier_returns_false_when_thread_cannot_start(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    configure_players(monkeypatch, {"pw-play"})
    monkeypatch.setattr(sound_module.threading, "Thread", FailingThread)

    assert SoundNotifier(sound_path).notify() is False


def test_notifier_returns_false_without_sound_file(tmp_path):
    assert SoundNotifier(tmp_path / "missing.wav").notify() is False


def test_notifier_returns_false_without_player(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    monkeypatch.setattr(sound_module.shutil, "which", lambda player: None)

    assert SoundNotifier(sound_path).notify() is False


def test_wait_allows_started_sound_to_finish(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    started = threading.Event()
    release = threading.Event()
    process = BlockingProcess(started=started, release=release)
    configure_players(monkeypatch, {"pw-play"}, immediate_thread=False)
    monkeypatch.setattr(sound_module.subprocess, "Popen", lambda *args, **kwargs: process)
    notifier = SoundNotifier(sound_path)

    assert notifier.notify() is True
    assert started.wait(timeout=1)
    release.set()
    notifier.wait(timeout=1)

    assert notifier._threads == set()

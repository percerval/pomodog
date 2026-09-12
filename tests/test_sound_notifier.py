import subprocess
from types import SimpleNamespace

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


def configure_players(monkeypatch, available):
    monkeypatch.setattr(
        sound_module.shutil,
        "which",
        lambda player: f"/usr/bin/{player}" if player in available else None,
    )
    monkeypatch.setattr(sound_module.threading, "Thread", ImmediateThread)


def test_notifier_prefers_pw_play(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    calls = []
    configure_players(monkeypatch, {"pw-play", "paplay", "aplay"})

    def run(command, **options):
        calls.append((command, options))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(sound_module.subprocess, "run", run)

    assert SoundNotifier(sound_path).notify() is True
    assert calls == [
        (
            ["/usr/bin/pw-play", str(sound_path)],
            {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "timeout": 5,
                "check": False,
            },
        )
    ]


def test_notifier_falls_back_after_nonzero_exit(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    commands = []
    configure_players(monkeypatch, {"pw-play", "paplay"})

    def run(command, **options):
        commands.append(command)
        return SimpleNamespace(returncode=1 if command[0].endswith("pw-play") else 0)

    monkeypatch.setattr(sound_module.subprocess, "run", run)

    assert SoundNotifier(sound_path).notify() is True
    assert commands == [
        ["/usr/bin/pw-play", str(sound_path)],
        ["/usr/bin/paplay", str(sound_path)],
    ]


def test_notifier_falls_back_after_timeout(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    commands = []
    configure_players(monkeypatch, {"pw-play", "paplay"})

    def run(command, **options):
        commands.append(command)
        if command[0].endswith("pw-play"):
            raise subprocess.TimeoutExpired(command, timeout=5)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(sound_module.subprocess, "run", run)

    assert SoundNotifier(sound_path).notify() is True
    assert commands[-1][0] == "/usr/bin/paplay"


def test_aplay_uses_quiet_option(tmp_path, monkeypatch):
    sound_path = tmp_path / "sound.wav"
    sound_path.write_bytes(b"RIFF")
    commands = []
    configure_players(monkeypatch, {"aplay"})
    monkeypatch.setattr(
        sound_module.subprocess,
        "run",
        lambda command, **options: commands.append(command)
        or SimpleNamespace(returncode=0),
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
        "run",
        lambda command, **options: SimpleNamespace(returncode=1),
    )

    assert SoundNotifier(sound_path).notify(lambda: failures.append(True)) is True
    assert failures == [True]


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

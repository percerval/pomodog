import subprocess
from types import SimpleNamespace

import src.notifications.desktop_notifier as desktop_module
from src.notifications.desktop_notifier import DesktopNotifier


class ImmediateThread:
    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


class FailingThread(ImmediateThread):
    def start(self):
        raise RuntimeError("thread unavailable")


def configure_notify_send(monkeypatch, available=True):
    monkeypatch.setattr(
        desktop_module.shutil,
        "which",
        lambda name: "/usr/bin/notify-send" if available else None,
    )
    monkeypatch.setattr(desktop_module.threading, "Thread", ImmediateThread)


def test_focus_notification_includes_icon_and_messages(tmp_path, monkeypatch):
    icon = tmp_path / "pomodog.png"
    icon.write_bytes(b"PNG")
    calls = []
    configure_notify_send(monkeypatch)

    def run(command, **options):
        calls.append((command, options))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(desktop_module.subprocess, "run", run)

    assert DesktopNotifier(icon).notify("focus-complete") is True
    assert calls == [
        (
            [
                "/usr/bin/notify-send",
                "--app-name=Pomodog",
                "--urgency=normal",
                "--expire-time=5000",
                f"--icon={icon}",
                "Foco concluído",
                "Hora de fazer uma pausa.",
            ],
            {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "timeout": 5,
                "check": False,
            },
        )
    ]


def test_break_notification_uses_break_messages(tmp_path, monkeypatch):
    icon = tmp_path / "pomodog.png"
    icon.write_bytes(b"PNG")
    commands = []
    configure_notify_send(monkeypatch)
    monkeypatch.setattr(
        desktop_module.subprocess,
        "run",
        lambda command, **options: commands.append(command)
        or SimpleNamespace(returncode=0),
    )

    assert DesktopNotifier(icon).notify("break-complete") is True
    assert commands[0][-2:] == ["Pausa concluída", "Hora de voltar ao foco."]
    assert commands[0][:4] == [
        "/usr/bin/notify-send",
        "--app-name=Pomodog",
        "--urgency=normal",
        "--expire-time=5000",
    ]


def test_notification_omits_icon_when_file_is_missing(tmp_path, monkeypatch):
    commands = []
    configure_notify_send(monkeypatch)
    monkeypatch.setattr(
        desktop_module.subprocess,
        "run",
        lambda command, **options: commands.append(command)
        or SimpleNamespace(returncode=0),
    )

    assert DesktopNotifier(tmp_path / "missing.png").notify("focus-complete") is True
    assert not any(part.startswith("--icon=") for part in commands[0])


def test_notification_returns_false_without_notify_send(tmp_path, monkeypatch):
    icon = tmp_path / "pomodog.png"
    icon.write_bytes(b"PNG")
    configure_notify_send(monkeypatch, available=False)

    assert DesktopNotifier(icon).notify("focus-complete") is False


def test_notification_returns_false_when_thread_cannot_start(tmp_path, monkeypatch):
    icon = tmp_path / "pomodog.png"
    icon.write_bytes(b"PNG")
    monkeypatch.setattr(
        desktop_module.shutil, "which", lambda name: "/usr/bin/notify-send"
    )
    monkeypatch.setattr(desktop_module.threading, "Thread", FailingThread)

    assert DesktopNotifier(icon).notify("focus-complete") is False


def test_notification_failure_inside_thread_is_silent(tmp_path, monkeypatch):
    icon = tmp_path / "pomodog.png"
    icon.write_bytes(b"PNG")
    configure_notify_send(monkeypatch)

    def run(command, **options):
        raise OSError("dbus indisponível")

    monkeypatch.setattr(desktop_module.subprocess, "run", run)

    assert DesktopNotifier(icon).notify("focus-complete") is True

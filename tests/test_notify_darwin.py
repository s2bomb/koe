from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from koe import notify

if TYPE_CHECKING:
    from pathlib import Path

    from koe.types import TranscriptionError


@pytest.fixture(autouse=True)
def _isolate_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:  # pyright: ignore[reportUnusedFunction]
    """Keep test notifications out of the real /tmp/koe.log flight recorder."""
    monkeypatch.setattr(notify, "_DIAGNOSTIC_LOG_PATH", tmp_path / "koe.log")


@pytest.fixture(autouse=True)
def _pin_darwin_backend(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("KOE_BACKEND", "darwin")


def test_notification_uses_osascript_display_notification() -> None:
    with patch("subprocess.run") as run_mock:
        notify.send_notification("recording_started")

    command = run_mock.call_args.args[0]
    assert command[0] == "osascript"
    assert command[1] == "-e"
    assert command[2] == 'display notification "Recording…" with title "Koe"'


def test_notification_escapes_quotes_and_backslashes_in_error_messages() -> None:
    error: TranscriptionError = {
        "category": "transcription",
        "message": 'model said "no" \\ twice',
        "cuda_available": False,
    }
    with patch("subprocess.run") as run_mock:
        notify.send_notification("error_transcription", error)

    script = run_mock.call_args.args[0][2]
    assert '\\"no\\"' in script
    assert "\\\\ twice" in script


def test_notification_transport_failure_is_swallowed() -> None:
    with patch("subprocess.run", side_effect=RuntimeError("osascript missing")):
        notify.send_notification("completed")

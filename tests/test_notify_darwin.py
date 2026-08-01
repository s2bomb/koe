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


def test_recording_fires_bar_event_with_start_timestamp() -> None:
    with (
        patch.object(notify.shutil, "which", return_value="/opt/homebrew/bin/sketchybar"),
        patch("subprocess.run") as run_mock,
    ):
        notify.send_notification("recording_started")

    bar_calls = [c.args[0] for c in run_mock.call_args_list if c.args[0][0].endswith("sketchybar")]
    assert len(bar_calls) == 1
    command = bar_calls[0]
    assert command[1:3] == ["--trigger", "koe_state"]
    assert command[3] == "STATE=recording"
    assert command[4].startswith("STARTED=")
    assert command[4].removeprefix("STARTED=").isdigit()


def test_terminal_states_clear_the_bar_indicator() -> None:
    for kind in ("completed", "no_speech", "error_transcription"):
        with (
            patch.object(notify.shutil, "which", return_value="/opt/homebrew/bin/sketchybar"),
            patch("subprocess.run") as run_mock,
        ):
            notify.send_notification(kind)  # pyright: ignore[reportArgumentType]

        bar_calls = [
            c.args[0] for c in run_mock.call_args_list if c.args[0][0].endswith("sketchybar")
        ]
        assert bar_calls == [
            ["/opt/homebrew/bin/sketchybar", "--trigger", "koe_state", "STATE=off"]
        ]


def test_bar_event_skipped_when_sketchybar_absent() -> None:
    with (
        patch.object(notify.shutil, "which", return_value=None),
        patch("subprocess.run") as run_mock,
    ):
        notify.send_notification("recording_started")

    assert all(not c.args[0][0].endswith("sketchybar") for c in run_mock.call_args_list)

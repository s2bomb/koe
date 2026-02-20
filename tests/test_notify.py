from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest

from koe import notify

if TYPE_CHECKING:
    from koe.types import KoeError, NotificationKind


@pytest.mark.parametrize(
    ("kind", "title", "message"),
    [
        (
            cast("NotificationKind", "recording_started"),
            "Koe",
            "Recording…",
        ),
        (cast("NotificationKind", "processing"), "Koe", "Processing…"),
        (cast("NotificationKind", "completed"), "Koe", "Transcription complete"),
        (cast("NotificationKind", "no_speech"), "Koe", "No speech detected"),
    ],
)
def test_send_notification_lifecycle_payload_matrix_is_exact(
    kind: NotificationKind, title: str, message: str
) -> None:
    with patch("subprocess.run") as run_mock:
        notify.send_notification(kind)

    run_mock.assert_called_once_with(
        ["notify-send", title, message],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("kind", "error"),
    [
        (
            cast("NotificationKind", "already_running"),
            cast(
                "KoeError",
                {
                    "category": "already_running",
                    "message": "another koe instance is active",
                    "lock_file": "/tmp/koe.lock",
                    "conflicting_pid": 41,
                },
            ),
        ),
        (
            cast("NotificationKind", "error_focus"),
            cast("KoeError", {"category": "focus", "message": "no focused window"}),
        ),
        (
            cast("NotificationKind", "error_dependency"),
            cast(
                "KoeError",
                {
                    "category": "dependency",
                    "message": "required tool is missing: xdotool",
                    "missing_tool": "xdotool",
                },
            ),
        ),
        (
            cast("NotificationKind", "error_audio"),
            cast(
                "KoeError",
                {
                    "category": "audio",
                    "message": "mic not found",
                    "device": "default",
                },
            ),
        ),
        (
            cast("NotificationKind", "error_transcription"),
            cast(
                "KoeError",
                {
                    "category": "transcription",
                    "message": "CUDA not available",
                    "cuda_available": False,
                },
            ),
        ),
        (
            cast("NotificationKind", "error_insertion"),
            cast(
                "KoeError",
                {
                    "category": "insertion",
                    "message": "clipboard restore failed: xclip exited with 1",
                    "transcript_text": "hello",
                },
            ),
        ),
    ],
)
def test_send_notification_error_kinds_preserve_error_message(
    kind: NotificationKind, error: KoeError
) -> None:
    with patch("subprocess.run") as run_mock:
        notify.send_notification(kind, error)

    notify_send_args = run_mock.call_args.args[0]
    assert notify_send_args[2] == error["message"]


@pytest.mark.parametrize(
    ("kind", "title"),
    [
        (cast("NotificationKind", "already_running"), "Koe already running"),
        (cast("NotificationKind", "error_focus"), "Koe focus required"),
        (cast("NotificationKind", "error_dependency"), "Koe dependency issue"),
        (cast("NotificationKind", "error_audio"), "Koe audio error"),
        (cast("NotificationKind", "error_transcription"), "Koe transcription error"),
        (cast("NotificationKind", "error_insertion"), "Koe insertion error"),
    ],
)
def test_send_notification_error_title_matrix_is_exact(kind: NotificationKind, title: str) -> None:
    error = cast("KoeError", {"category": "focus", "message": "error context"})

    with patch("subprocess.run") as run_mock:
        notify.send_notification(kind, error)

    notify_send_args = run_mock.call_args.args[0]
    assert notify_send_args[1] == title
    assert notify_send_args[1] != "Koe"


@pytest.mark.parametrize(
    ("kind", "fallback_message"),
    [
        (cast("NotificationKind", "already_running"), "Another Koe invocation is active."),
        (cast("NotificationKind", "error_focus"), "No focused window is available."),
        (cast("NotificationKind", "error_dependency"), "A required dependency is missing."),
        (cast("NotificationKind", "error_audio"), "Microphone capture failed."),
        (cast("NotificationKind", "error_transcription"), "Transcription failed."),
        (cast("NotificationKind", "error_insertion"), "Text insertion failed."),
    ],
)
def test_send_notification_error_fallback_matrix_when_error_is_none(
    kind: NotificationKind, fallback_message: str
) -> None:
    with patch("subprocess.run") as run_mock:
        notify.send_notification(kind)

    notify_send_args = run_mock.call_args.args[0]
    assert notify_send_args[2] == fallback_message


@pytest.mark.parametrize(
    ("kind", "error"),
    [
        (cast("NotificationKind", "recording_started"), None),
        (cast("NotificationKind", "processing"), None),
        (cast("NotificationKind", "completed"), None),
        (cast("NotificationKind", "no_speech"), None),
        (
            cast("NotificationKind", "already_running"),
            cast(
                "KoeError",
                {
                    "category": "already_running",
                    "message": "another koe instance is active",
                    "lock_file": "/tmp/koe.lock",
                    "conflicting_pid": 41,
                },
            ),
        ),
        (
            cast("NotificationKind", "error_focus"),
            cast("KoeError", {"category": "focus", "message": "no focused window"}),
        ),
        (
            cast("NotificationKind", "error_dependency"),
            cast(
                "KoeError",
                {"category": "dependency", "message": "missing xdotool", "missing_tool": "xdotool"},
            ),
        ),
        (
            cast("NotificationKind", "error_audio"),
            cast("KoeError", {"category": "audio", "message": "mic not found", "device": None}),
        ),
        (
            cast("NotificationKind", "error_transcription"),
            cast(
                "KoeError",
                {
                    "category": "transcription",
                    "message": "model load failed: missing file",
                    "cuda_available": True,
                },
            ),
        ),
        (
            cast("NotificationKind", "error_insertion"),
            cast(
                "KoeError",
                {
                    "category": "insertion",
                    "message": "clipboard restore failed: xclip exited with 1",
                    "transcript_text": "hello",
                },
            ),
        ),
    ],
)
def test_send_notification_swallows_backend_failures(
    kind: NotificationKind, error: KoeError | None
) -> None:
    with patch("subprocess.run", side_effect=RuntimeError("backend down")):
        result = notify.send_notification(kind, error)

    assert result is None

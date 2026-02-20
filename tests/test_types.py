from __future__ import annotations

from pathlib import Path

import pytest
from typeguard import TypeCheckError, check_type

from koe import types as koe_types
from koe.types import (
    AudioArtifactPath,
    AudioError,
    ClipboardState,
    DependencyError,
    Err,
    FocusedWindow,
    FocusError,
    InsertionError,
    KoeError,
    Ok,
    TranscriptionError,
    TranscriptionFailure,
    TranscriptionNoSpeech,
    TranscriptionResult,
    TranscriptionText,
    WindowFocusResult,
    WindowId,
)


def test_ok_shape_accepts_success_arm() -> None:
    check_type({"ok": True, "value": "hello"}, Ok[str])


def test_ok_shape_rejects_false_discriminator() -> None:
    with pytest.raises(TypeCheckError):
        check_type({"ok": False, "value": "hello"}, Ok[str])


def test_err_shape_accepts_error_arm() -> None:
    check_type({"ok": False, "error": {"category": "focus", "message": "missing"}}, Err[FocusError])


def test_err_shape_rejects_missing_error_payload() -> None:
    with pytest.raises(TypeCheckError):
        check_type({"ok": False}, Err[FocusError])


def test_focused_window_requires_both_fields() -> None:
    check_type({"window_id": WindowId(42), "title": "Editor"}, FocusedWindow)


def test_focused_window_rejects_missing_title() -> None:
    with pytest.raises(TypeCheckError):
        check_type({"window_id": WindowId(42)}, FocusedWindow)


def test_window_focus_result_accepts_window_and_none() -> None:
    check_type({"window_id": WindowId(1), "title": "Terminal"}, WindowFocusResult)
    check_type(None, WindowFocusResult)


def test_transcription_text_enforces_schema() -> None:
    check_type({"kind": "text", "text": "hello"}, TranscriptionText)
    with pytest.raises(TypeCheckError):
        check_type({"kind": "text"}, TranscriptionText)


def test_transcription_no_speech_enforces_empty_kind() -> None:
    check_type({"kind": "empty"}, TranscriptionNoSpeech)
    with pytest.raises(TypeCheckError):
        check_type({"kind": "text"}, TranscriptionNoSpeech)


def test_transcription_failure_requires_transcription_error_payload() -> None:
    valid_error = {
        "category": "transcription",
        "message": "cuda missing",
        "cuda_available": False,
    }
    invalid_error = {
        "category": "audio",
        "message": "device missing",
        "device": None,
    }
    check_type({"kind": "error", "error": valid_error}, TranscriptionFailure)
    with pytest.raises(TypeCheckError):
        check_type({"kind": "error", "error": invalid_error}, TranscriptionFailure)


@pytest.mark.parametrize(
    ("value", "is_valid"),
    [
        ({"kind": "text", "text": "hello"}, True),
        ({"kind": "empty"}, True),
        (
            {
                "kind": "error",
                "error": {
                    "category": "transcription",
                    "message": "model load failed",
                    "cuda_available": True,
                },
            },
            True,
        ),
        ({"kind": "unexpected"}, False),
    ],
)
def test_transcription_result_is_exactly_three_armed(value: object, *, is_valid: bool) -> None:
    if is_valid:
        check_type(value, TranscriptionResult)
        return

    with pytest.raises(TypeCheckError):
        check_type(value, TranscriptionResult)


def test_clipboard_state_allows_text_or_none() -> None:
    check_type({"content": "existing clipboard"}, ClipboardState)
    check_type({"content": None}, ClipboardState)


@pytest.mark.parametrize(
    ("value", "type_hint"),
    [
        ({"category": "focus", "message": "no focus"}, FocusError),
        ({"category": "audio", "message": "mic busy", "device": None}, AudioError),
        (
            {
                "category": "transcription",
                "message": "cuda unavailable",
                "cuda_available": False,
            },
            TranscriptionError,
        ),
        (
            {
                "category": "insertion",
                "message": "xclip failed",
                "transcript_text": "hello",
            },
            InsertionError,
        ),
        (
            {
                "category": "dependency",
                "message": "missing tool",
                "missing_tool": "xdotool",
            },
            DependencyError,
        ),
    ],
)
def test_each_error_shape_accepts_required_fields(value: object, type_hint: object) -> None:
    check_type(value, type_hint)


@pytest.mark.parametrize(
    ("value", "type_hint"),
    [
        ({"category": "focus"}, FocusError),
        ({"category": "audio", "message": "mic busy"}, AudioError),
        ({"category": "transcription", "message": "cuda unavailable"}, TranscriptionError),
        ({"category": "insertion", "message": "xclip failed"}, InsertionError),
        ({"category": "dependency", "message": "missing tool"}, DependencyError),
    ],
)
def test_each_error_shape_rejects_missing_required_fields(value: object, type_hint: object) -> None:
    with pytest.raises(TypeCheckError):
        check_type(value, type_hint)


@pytest.mark.parametrize(
    "error",
    [
        {"category": "focus", "message": "no focus"},
        {"category": "audio", "message": "mic busy", "device": None},
        {"category": "transcription", "message": "cuda unavailable", "cuda_available": False},
        {"category": "insertion", "message": "xclip failed", "transcript_text": "hello"},
        {"category": "dependency", "message": "missing tool", "missing_tool": "xdotool"},
    ],
)
def test_koe_error_union_accepts_each_error_variant(error: object) -> None:
    check_type(error, KoeError)


def test_audio_artifact_alias_runtime_shape_accepts_wrapped_path() -> None:
    check_type(AudioArtifactPath(Path("/tmp/sample.wav")), AudioArtifactPath)


def test_audio_capture_requires_artifact_path() -> None:
    check_type(
        {"kind": "captured", "artifact_path": AudioArtifactPath(Path("/tmp/capture.wav"))},
        koe_types.AudioCapture,
    )
    with pytest.raises(TypeCheckError):
        check_type({"kind": "captured"}, koe_types.AudioCapture)


def test_audio_empty_requires_explicit_empty_kind() -> None:
    check_type({"kind": "empty"}, koe_types.AudioEmpty)
    with pytest.raises(TypeCheckError):
        check_type({"kind": "unexpected"}, koe_types.AudioEmpty)


def test_audio_capture_failed_requires_audio_error_payload() -> None:
    check_type(
        {
            "kind": "error",
            "error": {"category": "audio", "message": "microphone unavailable", "device": None},
        },
        koe_types.AudioCaptureFailed,
    )
    with pytest.raises(TypeCheckError):
        check_type(
            {
                "kind": "error",
                "error": {"category": "audio", "message": "microphone unavailable"},
            },
            koe_types.AudioCaptureFailed,
        )


@pytest.mark.parametrize(
    ("value", "is_valid"),
    [
        (
            {"kind": "captured", "artifact_path": AudioArtifactPath(Path("/tmp/captured.wav"))},
            True,
        ),
        ({"kind": "empty"}, True),
        (
            {
                "kind": "error",
                "error": {"category": "audio", "message": "wav write failed", "device": None},
            },
            True,
        ),
        ({"kind": "unexpected"}, False),
    ],
)
def test_audio_capture_result_is_exactly_three_armed(value: object, *, is_valid: bool) -> None:
    if is_valid:
        check_type(value, koe_types.AudioCaptureResult)
        return

    with pytest.raises(TypeCheckError):
        check_type(value, koe_types.AudioCaptureResult)


def test_already_running_error_accepts_pid_or_none() -> None:
    already_running_error = koe_types.AlreadyRunningError
    check_type(
        {
            "category": "already_running",
            "message": "another koe instance is active",
            "lock_file": "/tmp/koe.lock",
            "conflicting_pid": 1234,
        },
        already_running_error,
    )
    check_type(
        {
            "category": "already_running",
            "message": "another koe instance is active",
            "lock_file": "/tmp/koe.lock",
            "conflicting_pid": None,
        },
        already_running_error,
    )


def test_already_running_error_rejects_missing_fields_or_wrong_category() -> None:
    already_running_error = koe_types.AlreadyRunningError
    with pytest.raises(TypeCheckError):
        check_type(
            {
                "category": "already_running",
                "message": "another koe instance is active",
                "conflicting_pid": 1234,
            },
            already_running_error,
        )

    with pytest.raises(TypeCheckError):
        check_type(
            {
                "category": "dependency",
                "message": "another koe instance is active",
                "lock_file": "/tmp/koe.lock",
                "conflicting_pid": None,
            },
            already_running_error,
        )

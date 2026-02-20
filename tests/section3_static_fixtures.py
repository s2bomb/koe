from __future__ import annotations

from typing import assert_never, assert_type

from koe.types import AudioArtifactPath, AudioCaptureResult, AudioError, NotificationKind


def t04_audio_capture_result_is_closed(result: AudioCaptureResult) -> None:
    match result["kind"]:
        case "captured":
            assert_type(result["artifact_path"], AudioArtifactPath)
        case "empty":
            return
        case "error":
            assert_type(result["error"], AudioError)
        case _ as unreachable:
            assert_never(unreachable)


def t05_notification_kind_includes_no_speech(kind: NotificationKind) -> None:
    match kind:
        case (
            "recording_started"
            | "processing"
            | "completed"
            | "no_speech"
            | "error_focus"
            | "error_audio"
            | "error_transcription"
            | "error_insertion"
            | "error_dependency"
            | "already_running"
        ):
            return
        case _ as unreachable:
            assert_never(unreachable)

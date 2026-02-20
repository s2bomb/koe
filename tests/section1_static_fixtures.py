from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal, assert_never, assert_type

from koe.config import DEFAULT_CONFIG, KoeConfig
from koe.main import run_pipeline
from koe.types import (
    AudioArtifactPath,
    AudioError,
    DependencyError,
    ExitCode,
    FocusError,
    HotkeyAction,
    InsertionError,
    KoeError,
    NotificationKind,
    Ok,
    PipelineOutcome,
    Result,
    TranscriptionError,
    WindowId,
)


def t01_aliases_have_explicit_wrapper_construction() -> None:
    artifact = AudioArtifactPath(Path("/tmp/koe.wav"))
    window = WindowId(123)
    assert_type(artifact, AudioArtifactPath)
    assert_type(window, WindowId)


def t04_result_narrows_on_ok_discriminator(result: Result[str, FocusError]) -> None:
    if result["ok"] is True:
        assert_type(result, Ok[str])
        assert_type(result["value"], str)
        return

    assert_type(result["error"], FocusError)


def t05_hotkey_action_is_closed(action: HotkeyAction) -> None:
    match action:
        case "start" | "stop":
            return
        case _ as unreachable:
            assert_never(unreachable)


def t13_notification_kind_is_closed(kind: NotificationKind) -> None:
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


def t15_koe_error_narrows_by_category(error: KoeError) -> None:
    match error["category"]:
        case "focus":
            assert_type(error, FocusError)
        case "audio":
            assert_type(error, AudioError)
            assert_type(error["device"], str | None)
        case "transcription":
            assert_type(error, TranscriptionError)
            assert_type(error["cuda_available"], bool)
        case "insertion":
            assert_type(error, InsertionError)
            assert_type(error["transcript_text"], str)
        case "dependency":
            assert_type(error, DependencyError)
            assert_type(error["missing_tool"], str)
        case "already_running":
            assert_type(error["lock_file"], str)
            assert_type(error["conflicting_pid"], int | None)
        case _ as unreachable:
            assert_never(unreachable)


def t16_pipeline_outcome_is_closed(outcome: PipelineOutcome) -> None:
    match outcome:
        case (
            "success"
            | "no_focus"
            | "no_speech"
            | "error_dependency"
            | "error_audio"
            | "error_transcription"
            | "error_insertion"
            | "error_unexpected"
            | "already_running"
        ):
            return
        case _ as unreachable:
            assert_never(unreachable)


def t17_exit_code_is_closed(code: ExitCode) -> None:
    match code:
        case 0 | 1 | 2:
            return
        case _ as unreachable:
            assert_never(unreachable)


def t18_whisper_device_literal_is_preserved(config: KoeConfig) -> None:
    assert_type(config["whisper_device"], Literal["cuda"])
    assert_type(DEFAULT_CONFIG["whisper_device"], Literal["cuda"])


def t21_run_pipeline_signature_contract() -> None:
    signature: Callable[[KoeConfig], PipelineOutcome] = run_pipeline
    assert_type(signature, Callable[[KoeConfig], PipelineOutcome])

from __future__ import annotations

from pathlib import Path
from typing import assert_never, assert_type

from koe.types import (
    AlreadyRunningError,
    InstanceLockHandle,
    KoeError,
    NotificationKind,
    PipelineOutcome,
)


def t01_instance_lock_handle_requires_explicit_wrapper() -> None:
    wrapped = InstanceLockHandle(Path("/tmp/koe.lock"))
    assert_type(wrapped, InstanceLockHandle)


def t04_notification_kind_includes_already_running(kind: NotificationKind) -> None:
    match kind:
        case "recording_started" | "processing" | "completed":
            return
        case "no_speech":
            return
        case "error_focus" | "error_audio" | "error_transcription":
            return
        case "error_insertion" | "error_dependency" | "already_running":
            return
        case _ as unreachable:
            assert_never(unreachable)


def t05_koe_error_narrows_with_already_running(error: KoeError) -> None:
    match error["category"]:
        case "already_running":
            assert_type(error, AlreadyRunningError)
            assert_type(error["lock_file"], str)
            assert_type(error["conflicting_pid"], int | None)
        case "focus" | "audio" | "transcription" | "insertion" | "dependency":
            return
        case _ as unreachable:
            assert_never(unreachable)


def t06_pipeline_outcome_includes_already_running(outcome: PipelineOutcome) -> None:
    match outcome:
        case (
            "success"
            | "signaled_stop"
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

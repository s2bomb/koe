"""Shared pipeline type vocabulary for Koe M1."""

from __future__ import annotations

from pathlib import Path
from typing import Generic, Literal, NewType, TypeAlias, TypedDict, TypeVar

T = TypeVar("T")
E = TypeVar("E")

AudioArtifactPath = NewType("AudioArtifactPath", Path)
WindowId = NewType("WindowId", int)
InstanceLockHandle = NewType("InstanceLockHandle", Path)


class Ok(TypedDict, Generic[T]):  # noqa: UP046
    ok: Literal[True]
    value: T


class Err(TypedDict, Generic[E]):  # noqa: UP046
    ok: Literal[False]
    error: E


Result: TypeAlias = Ok[T] | Err[E]  # noqa: UP040

type HotkeyAction = Literal["start", "stop"]


class FocusedWindow(TypedDict):
    window_id: WindowId
    title: str


type WindowFocusResult = FocusedWindow | None


class AudioCapture(TypedDict):
    kind: Literal["captured"]
    artifact_path: AudioArtifactPath


class AudioEmpty(TypedDict):
    kind: Literal["empty"]


class AudioCaptureFailed(TypedDict):
    kind: Literal["error"]
    error: AudioError


type AudioCaptureResult = AudioCapture | AudioEmpty | AudioCaptureFailed


class TranscriptionText(TypedDict):
    kind: Literal["text"]
    text: str


class TranscriptionNoSpeech(TypedDict):
    kind: Literal["empty"]


class TranscriptionError(TypedDict):
    category: Literal["transcription"]
    message: str
    cuda_available: bool


class TranscriptionFailure(TypedDict):
    kind: Literal["error"]
    error: TranscriptionError


type TranscriptionResult = TranscriptionText | TranscriptionNoSpeech | TranscriptionFailure


class ClipboardState(TypedDict):
    content: str | None


type NotificationKind = Literal[
    "recording_started",
    "processing",
    "completed",
    "no_speech",
    "error_focus",
    "error_audio",
    "error_transcription",
    "error_insertion",
    "error_dependency",
    "already_running",
]


class FocusError(TypedDict):
    category: Literal["focus"]
    message: str


class AudioError(TypedDict):
    category: Literal["audio"]
    message: str
    device: str | None


class InsertionError(TypedDict):
    category: Literal["insertion"]
    message: str
    transcript_text: str


class DependencyError(TypedDict):
    category: Literal["dependency"]
    message: str
    missing_tool: str


class AlreadyRunningError(TypedDict):
    category: Literal["already_running"]
    message: str
    lock_file: str
    conflicting_pid: int | None


type KoeError = (
    FocusError
    | AudioError
    | TranscriptionError
    | InsertionError
    | DependencyError
    | AlreadyRunningError
)

type PipelineOutcome = Literal[
    "success",
    "signaled_stop",
    "no_focus",
    "no_speech",
    "error_dependency",
    "error_audio",
    "error_transcription",
    "error_insertion",
    "error_unexpected",
    "already_running",
]


class UsageLogRecord(TypedDict):
    run_id: str
    invoked_at: str
    outcome: PipelineOutcome
    duration_ms: int


type ExitCode = Literal[0, 1, 2]

"""Koe M1 CLI entrypoint contracts."""

from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import signal
import sys
import time
from datetime import UTC, datetime
from threading import Event, Thread
from typing import TYPE_CHECKING, Protocol, assert_never, cast

from koe.audio import capture_audio, remove_audio_artifact
from koe.backend import detect_backend
from koe.config import DEFAULT_CONFIG, KoeConfig
from koe.hotkey import (
    acquire_instance_lock,
    determine_hotkey_action,
    release_instance_lock,
    signal_running_instance,
)
from koe.insert import insert_transcript_text
from koe.notify import send_notification
from koe.textproc import strip_filler_words
from koe.usage_log import ensure_data_dir, write_transcription_record, write_usage_log_record
from koe.window import check_focused_window, check_x11_context

if TYPE_CHECKING:
    from types import FrameType

    from koe.types import (
        AudioArtifactPath,
        AudioCaptureResult,
        DependencyError,
        ExitCode,
        PipelineOutcome,
        Result,
        TranscriptionResult,
    )

# Module-level stop event set by SIGUSR1 handler during recording.
_stop_event = Event()

# First run may still be downloading the model when recording stops; the join
# gives up after this and lets the cold path (with its own download lock) win.
_PRELOAD_JOIN_TIMEOUT_SECONDS = 30.0


class _EngineLike(Protocol):
    """The transcription seam both platform engines expose."""

    def transcribe_audio(
        self, artifact_path: AudioArtifactPath, config: KoeConfig, /
    ) -> TranscriptionResult: ...


class _PreloadingEngineLike(Protocol):
    """Darwin extra: background model load + Metal warm-up during recording."""

    def preload_model(self, config: KoeConfig, /) -> None: ...


def _load_engine() -> _EngineLike:
    """Import the platform's engine lazily so hotkey start never pays for it.

    Press 1 must reach an open microphone fast; both engines drag in heavy
    native stacks (CTranslate2/CUDA on linux, MLX/Metal on darwin) that only
    the stop-press needs.
    """
    module_name = "koe.transcribe_darwin" if detect_backend() == "darwin" else "koe.transcribe"
    return cast("_EngineLike", importlib.import_module(module_name))


def transcribe_audio(artifact_path: AudioArtifactPath, config: KoeConfig, /) -> TranscriptionResult:
    """Engine dispatch seam: the backend picks the engine, imported on demand."""
    return _load_engine().transcribe_audio(artifact_path, config)


def _record_with_engine_preload(config: KoeConfig, /) -> AudioCaptureResult:
    """Capture audio while the platform engine preloads on a background thread.

    The join is bounded: recording time normally dwarfs the load+warm-up, so
    the join returns immediately; on a first run still downloading the model,
    the timeout hands the work to the cold path instead of hanging the press.
    """
    preload_thread = _start_engine_preload(config)
    send_notification("recording_started")
    capture_result = capture_audio(config, stop_event=_stop_event)
    if preload_thread is not None:
        preload_thread.join(timeout=_PRELOAD_JOIN_TIMEOUT_SECONDS)
    return capture_result


def _start_engine_preload(config: KoeConfig, /) -> Thread | None:
    """On darwin, load and warm the Metal engine while the user is still talking.

    Turns the stop-press cost from ~3.5 s (import + load + cold kernels) into
    ~0.3 s of pure inference. The thread swallows its own failures: an empty
    preload slot just means the main path loads cold and reports any genuine
    fault as typed data.
    """
    if detect_backend() != "darwin":
        return None

    def _preload() -> None:
        try:
            engine = cast("_PreloadingEngineLike", importlib.import_module("koe.transcribe_darwin"))
            engine.preload_model(config)
        except Exception:
            return

    thread = Thread(target=_preload, daemon=True, name="koe-engine-preload")
    thread.start()
    return thread


def _handle_stop_signal(_signum: int, _frame: FrameType | None) -> None:
    """SIGUSR1 handler: signal the recording loop to stop."""
    _stop_event.set()


def main() -> None:
    ensure_data_dir(DEFAULT_CONFIG)
    invoked_at = datetime.now(UTC).isoformat()
    started_at = time.monotonic()

    try:
        outcome = run_pipeline(DEFAULT_CONFIG)
    except Exception:
        outcome = "error_unexpected"

    duration_ms = int((time.monotonic() - started_at) * 1000)
    write_usage_log_record(
        DEFAULT_CONFIG,
        outcome,
        invoked_at=invoked_at,
        duration_ms=duration_ms,
    )
    sys.exit(outcome_to_exit_code(outcome))


def dependency_preflight(config: KoeConfig, /) -> Result[None, DependencyError]:  # noqa: PLR0911
    """Validate startup dependencies required before Section 3 handoff."""
    if detect_backend() == "darwin":
        return _dependency_preflight_darwin(config)

    required_tools = ["notify-send"]
    if _is_wayland_session():
        required_tools.extend(["hyprctl", "wl-copy", "wl-paste"])
        if shutil.which("wtype") is None and shutil.which("hyprctl") is None:
            return {
                "ok": False,
                "error": {
                    "category": "dependency",
                    "message": "wtype or hyprctl is required for Wayland paste",
                    "missing_tool": "wtype",
                },
            }
    else:
        required_tools.extend(["xdotool", "xclip"])

    for tool in required_tools:
        if shutil.which(tool) is None:
            return {
                "ok": False,
                "error": {
                    "category": "dependency",
                    "message": f"required tool is missing: {tool}",
                    "missing_tool": tool,
                },
            }

    if config["whisper_device"] != "cuda":
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": "whisper_device must be cuda",
                "missing_tool": "whisper_device",
            },
        }

    if importlib.util.find_spec("soundfile") is None:
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": "python package soundfile is required",
                "missing_tool": "soundfile",
            },
        }

    temp_dir = config["temp_dir"]
    lock_parent = config["lock_file_path"].parent
    if not os.access(temp_dir, os.W_OK):
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": f"temp directory is not writable: {temp_dir}",
                "missing_tool": "temp_dir",
            },
        }

    if not os.access(lock_parent, os.W_OK):
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": f"lock directory is not writable: {lock_parent}",
                "missing_tool": "lock_file_path",
            },
        }

    return {"ok": True, "value": None}


def _dependency_preflight_darwin(config: KoeConfig, /) -> Result[None, DependencyError]:
    """Darwin preflight: no external tools to probe.

    pbcopy and osascript ship with macOS, the paste path lives in-process
    behind Quartz, and there is no CUDA gate — the Metal engine has no
    device precondition. Only the python audio stack and writable paths
    remain to verify.
    """
    if importlib.util.find_spec("soundfile") is None:
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": "python package soundfile is required",
                "missing_tool": "soundfile",
            },
        }

    if not os.access(config["temp_dir"], os.W_OK):
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": f"temp directory is not writable: {config['temp_dir']}",
                "missing_tool": "temp_dir",
            },
        }

    if not os.access(config["lock_file_path"].parent, os.W_OK):
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": f"lock directory is not writable: {config['lock_file_path'].parent}",
                "missing_tool": "lock_file_path",
            },
        }

    return {"ok": True, "value": None}


def _is_wayland_session() -> bool:
    backend_override = os.environ.get("KOE_BACKEND")
    if backend_override == "wayland":
        return True
    if backend_override == "x11":
        return False

    return os.environ.get("XDG_SESSION_TYPE") == "wayland" and not bool(os.environ.get("DISPLAY"))


def run_pipeline(config: KoeConfig, /) -> PipelineOutcome:  # noqa: PLR0911
    preflight = dependency_preflight(config)
    if preflight["ok"] is False:
        send_notification("error_dependency", preflight["error"])
        return "error_dependency"

    # Toggle logic: if another instance is recording, signal it to stop.
    action, running_pid = determine_hotkey_action(config)
    if action == "stop" and running_pid is not None:
        signal_running_instance(running_pid)
        return "signaled_stop"

    lock_result = acquire_instance_lock(config)
    if lock_result["ok"] is False:
        send_notification("already_running", lock_result["error"])
        return "already_running"

    # Install SIGUSR1 handler so the second press can stop recording.
    signal.signal(signal.SIGUSR1, _handle_stop_signal)

    lock_handle = lock_result["value"]
    try:
        x11_context = check_x11_context()
        if x11_context["ok"] is False:
            send_notification("error_dependency", x11_context["error"])
            return "error_dependency"

        focused_window = check_focused_window()
        if focused_window["ok"] is False:
            send_notification("error_focus", focused_window["error"])
            return "no_focus"

        capture_result = _record_with_engine_preload(config)

        if capture_result["kind"] == "empty":
            send_notification("no_speech")
            return "no_speech"

        if capture_result["kind"] == "error":
            send_notification("error_audio", capture_result["error"])
            return "error_audio"

        artifact_path = capture_result["artifact_path"]
        try:
            return _transcribe_and_insert(artifact_path, config)
        finally:
            remove_audio_artifact(artifact_path)
    finally:
        release_instance_lock(lock_handle)


def _transcribe_and_insert(
    artifact_path: AudioArtifactPath, config: KoeConfig, /
) -> PipelineOutcome:
    """Post-capture stages: transcribe, archive verbatim, deliver cleaned text."""
    send_notification("processing")
    transcription_result = transcribe_audio(artifact_path, config)

    if transcription_result["kind"] == "empty":
        send_notification("no_speech")
        return "no_speech"

    if transcription_result["kind"] == "error":
        send_notification("error_transcription", transcription_result["error"])
        return "error_transcription"

    # Archive verbatim + delivered; deliver cleaned (D14).
    transcript_text = _deliverable_transcript(transcription_result["text"], config)
    write_transcription_record(config, transcription_result["text"], delivered=transcript_text)
    if transcript_text == "":
        send_notification("no_speech")
        return "no_speech"

    insertion_result = insert_transcript_text(transcript_text, config)
    if insertion_result["ok"] is False:
        send_notification("error_insertion", insertion_result["error"])
        return "error_insertion"

    send_notification("completed")
    return "success"


def _deliverable_transcript(transcript_text: str, config: KoeConfig, /) -> str:
    """Shape the verbatim transcript into the text actually delivered."""
    if not config["strip_filler_words"]:
        return transcript_text
    return strip_filler_words(transcript_text)


def outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode:
    match outcome:
        case "success" | "signaled_stop":
            return 0
        case (
            "no_focus"
            | "no_speech"
            | "error_dependency"
            | "error_audio"
            | "error_transcription"
            | "error_insertion"
            | "already_running"
        ):
            return 1
        case "error_unexpected":
            return 2
        case _ as unreachable:
            assert_never(unreachable)

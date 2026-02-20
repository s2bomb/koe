"""Koe M1 CLI entrypoint contracts."""

from __future__ import annotations

import importlib.util
import os
import shutil
import signal
import sys
import time
from datetime import UTC, datetime
from threading import Event
from typing import TYPE_CHECKING, assert_never

from koe.audio import capture_audio, remove_audio_artifact
from koe.config import DEFAULT_CONFIG, KoeConfig
from koe.hotkey import (
    acquire_instance_lock,
    determine_hotkey_action,
    release_instance_lock,
    signal_running_instance,
)
from koe.insert import insert_transcript_text
from koe.notify import send_notification
from koe.transcribe import transcribe_audio
from koe.usage_log import ensure_data_dir, write_transcription_record, write_usage_log_record
from koe.window import check_focused_window, check_x11_context

if TYPE_CHECKING:
    from types import FrameType

    from koe.types import DependencyError, ExitCode, PipelineOutcome, Result

# Module-level stop event set by SIGUSR1 handler during recording.
_stop_event = Event()


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

        send_notification("recording_started")
        capture_result = capture_audio(config, stop_event=_stop_event)

        if capture_result["kind"] == "empty":
            send_notification("no_speech")
            return "no_speech"

        if capture_result["kind"] == "error":
            send_notification("error_audio", capture_result["error"])
            return "error_audio"

        artifact_path = capture_result["artifact_path"]
        try:
            send_notification("processing")
            transcription_result = transcribe_audio(artifact_path, config)

            if transcription_result["kind"] == "empty":
                send_notification("no_speech")
                return "no_speech"

            if transcription_result["kind"] == "error":
                send_notification("error_transcription", transcription_result["error"])
                return "error_transcription"

            transcript_text = transcription_result["text"]
            write_transcription_record(config, transcript_text)

            insertion_result = insert_transcript_text(transcript_text, config)
            if insertion_result["ok"] is False:
                send_notification("error_insertion", insertion_result["error"])
                return "error_insertion"

            send_notification("completed")
            return "success"
        finally:
            remove_audio_artifact(artifact_path)
    finally:
        release_instance_lock(lock_handle)


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

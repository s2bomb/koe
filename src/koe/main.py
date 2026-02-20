"""Koe M1 CLI entrypoint contracts."""

from __future__ import annotations

import shutil
import sys
from typing import TYPE_CHECKING, assert_never

from koe.audio import capture_audio, remove_audio_artifact
from koe.config import DEFAULT_CONFIG, KoeConfig
from koe.hotkey import acquire_instance_lock, release_instance_lock
from koe.notify import send_notification
from koe.transcribe import transcribe_audio
from koe.window import check_focused_window, check_x11_context

if TYPE_CHECKING:
    from koe.types import DependencyError, ExitCode, PipelineOutcome, Result


def main() -> None:
    try:
        outcome = run_pipeline(DEFAULT_CONFIG)
        sys.exit(outcome_to_exit_code(outcome))
    except Exception:
        sys.exit(2)


def dependency_preflight(config: KoeConfig, /) -> Result[None, DependencyError]:
    """Validate startup dependencies required before Section 3 handoff."""
    required_tools = ("xdotool", "xclip", "notify-send")
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

    return {"ok": True, "value": None}


def run_pipeline(config: KoeConfig, /) -> PipelineOutcome:  # noqa: PLR0911
    preflight = dependency_preflight(config)
    if preflight["ok"] is False:
        send_notification("error_dependency", preflight["error"])
        return "error_dependency"

    lock_result = acquire_instance_lock(config)
    if lock_result["ok"] is False:
        send_notification("already_running", lock_result["error"])
        return "already_running"

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
        capture_result = capture_audio(config)

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

            raise NotImplementedError("Section 5 handoff: insertion")
        finally:
            remove_audio_artifact(artifact_path)
    finally:
        release_instance_lock(lock_handle)


def outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode:
    match outcome:
        case "success":
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

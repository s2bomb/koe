from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

from koe.config import DEFAULT_CONFIG
from koe.main import run_pipeline

if TYPE_CHECKING:
    from koe.config import KoeConfig
    from koe.types import InstanceLockHandle


def test_terminal_flow_integration_composes_pipeline_stages() -> None:
    events: list[str] = []
    transcript_text = "section 7 integration transcript"
    artifact_path = Path("/tmp/section7-integration.wav")
    lock_handle = cast("InstanceLockHandle", DEFAULT_CONFIG["lock_file_path"])

    def _notify(kind: str, *_args: object) -> None:
        events.append(f"notify:{kind}")

    def _insert_text(text: str, config: KoeConfig) -> object:
        assert text == transcript_text
        assert config == DEFAULT_CONFIG
        events.append("insert_transcript_text")
        return {"ok": True, "value": None}

    def _remove_artifact(path: Path) -> None:
        assert path == artifact_path
        events.append("remove_audio_artifact")

    def _release_lock(handle: InstanceLockHandle) -> None:
        assert handle == lock_handle
        events.append("release_instance_lock")

    with (
        patch("koe.main.shutil.which", return_value="/usr/bin/fake", create=True),
        patch(
            "koe.main.acquire_instance_lock",
            return_value={"ok": True, "value": lock_handle},
            create=True,
        ),
        patch("koe.main.check_x11_context", return_value={"ok": True, "value": None}, create=True),
        patch(
            "koe.main.check_focused_window",
            return_value={"ok": True, "value": {"window_id": 1, "title": "Terminal"}},
            create=True,
        ),
        patch(
            "koe.main.capture_audio",
            return_value={"kind": "captured", "artifact_path": artifact_path},
            create=True,
        ),
        patch(
            "koe.main.transcribe_audio",
            return_value={"kind": "text", "text": transcript_text},
            create=True,
        ),
        patch("koe.main.insert_transcript_text", side_effect=_insert_text, create=True),
        patch("koe.main.remove_audio_artifact", side_effect=_remove_artifact, create=True),
        patch("koe.main.release_instance_lock", side_effect=_release_lock, create=True),
        patch("koe.main.send_notification", side_effect=_notify, create=True),
    ):
        outcome = run_pipeline(DEFAULT_CONFIG)

    assert outcome == "success"
    assert [event for event in events if event.startswith("notify:")] == [
        "notify:recording_started",
        "notify:processing",
        "notify:completed",
    ]
    assert "insert_transcript_text" in events
    assert events[-2:] == ["remove_audio_artifact", "release_instance_lock"]

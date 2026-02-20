from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest

from koe import insert as koe_insert
from koe.config import DEFAULT_CONFIG

if TYPE_CHECKING:
    from koe.config import KoeConfig
    from koe.types import ClipboardState, InsertionError, Result


def _completed(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["xclip"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _insert_error(message: str, transcript_text: str) -> InsertionError:
    return {
        "category": "insertion",
        "message": message,
        "transcript_text": transcript_text,
    }


def _call_insert_transcript_text(
    transcript_text: str, config: KoeConfig
) -> Result[None, InsertionError]:
    return koe_insert.insert_transcript_text(transcript_text, config)  # type: ignore[attr-defined]


def _call_backup_clipboard_text(transcript_text: str) -> Result[ClipboardState, InsertionError]:
    return koe_insert.backup_clipboard_text(transcript_text)  # type: ignore[attr-defined]


def _call_write_clipboard_text(text: str, transcript_text: str) -> Result[None, InsertionError]:
    return koe_insert.write_clipboard_text(text, transcript_text)  # type: ignore[attr-defined]


def _call_simulate_paste(config: KoeConfig, transcript_text: str) -> Result[None, InsertionError]:
    return koe_insert.simulate_paste(config, transcript_text)  # type: ignore[attr-defined]


def _call_restore_clipboard_text(
    state: ClipboardState,
    transcript_text: str,
) -> Result[None, InsertionError]:
    return koe_insert.restore_clipboard_text(state, transcript_text)  # type: ignore[attr-defined]


def test_insert_transcript_text_returns_ok_only_when_all_stages_succeed() -> None:
    with (
        patch.object(
            koe_insert,
            "backup_clipboard_text",
            return_value={"ok": True, "value": {"content": "previous"}},
            create=True,
        ),
        patch.object(
            koe_insert,
            "write_clipboard_text",
            return_value={"ok": True, "value": None},
            create=True,
        ),
        patch.object(
            koe_insert, "simulate_paste", return_value={"ok": True, "value": None}, create=True
        ),
        patch.object(
            koe_insert,
            "restore_clipboard_text",
            return_value={"ok": True, "value": None},
            create=True,
        ),
    ):
        result = _call_insert_transcript_text("hello", DEFAULT_CONFIG)

    assert result == {"ok": True, "value": None}


@pytest.mark.parametrize("transcript_text", ["", "   ", "\n\t"])
def test_insert_transcript_text_rejects_empty_or_whitespace_input(transcript_text: str) -> None:
    with (
        patch.object(koe_insert, "backup_clipboard_text", create=True) as backup_mock,
        patch.object(koe_insert, "write_clipboard_text", create=True) as write_mock,
        patch.object(koe_insert, "simulate_paste", create=True) as paste_mock,
        patch.object(koe_insert, "restore_clipboard_text", create=True) as restore_mock,
    ):
        result = _call_insert_transcript_text(transcript_text, DEFAULT_CONFIG)

    assert result["ok"] is False
    assert result["error"]["category"] == "insertion"
    assert result["error"]["transcript_text"] == transcript_text
    assert result["error"]["message"]
    backup_mock.assert_not_called()
    write_mock.assert_not_called()
    paste_mock.assert_not_called()
    restore_mock.assert_not_called()


def test_insert_transcript_text_enforces_stage_order() -> None:
    events: list[str] = []

    def _backup(_transcript_text: str) -> object:
        events.append("backup_clipboard_text")
        return {"ok": True, "value": {"content": "previous"}}

    def _write(_text: str, _transcript_text: str) -> object:
        events.append("write_clipboard_text")
        return {"ok": True, "value": None}

    def _paste(_config: KoeConfig, _transcript_text: str) -> object:
        events.append("simulate_paste")
        return {"ok": True, "value": None}

    def _restore(_state: ClipboardState, _transcript_text: str) -> object:
        events.append("restore_clipboard_text")
        return {"ok": True, "value": None}

    with (
        patch.object(koe_insert, "backup_clipboard_text", side_effect=_backup, create=True),
        patch.object(koe_insert, "write_clipboard_text", side_effect=_write, create=True),
        patch.object(koe_insert, "simulate_paste", side_effect=_paste, create=True),
        patch.object(koe_insert, "restore_clipboard_text", side_effect=_restore, create=True),
    ):
        result = _call_insert_transcript_text("hello", DEFAULT_CONFIG)

    assert result == {"ok": True, "value": None}
    assert events == [
        "backup_clipboard_text",
        "write_clipboard_text",
        "simulate_paste",
        "restore_clipboard_text",
    ]


def test_insert_transcript_text_short_circuits_on_backup_failure() -> None:
    transcript_text = "hello"
    backup_error = _insert_error("clipboard backup failed: xclip exited with 1", transcript_text)

    with (
        patch.object(
            koe_insert,
            "backup_clipboard_text",
            return_value={"ok": False, "error": backup_error},
            create=True,
        ),
        patch.object(koe_insert, "write_clipboard_text", create=True) as write_mock,
        patch.object(koe_insert, "simulate_paste", create=True) as paste_mock,
        patch.object(koe_insert, "restore_clipboard_text", create=True) as restore_mock,
    ):
        result = _call_insert_transcript_text(transcript_text, DEFAULT_CONFIG)

    assert result == {"ok": False, "error": backup_error}
    write_mock.assert_not_called()
    paste_mock.assert_not_called()
    restore_mock.assert_not_called()


def test_insert_transcript_text_short_circuits_on_write_failure() -> None:
    transcript_text = "hello"
    write_error = _insert_error("clipboard write failed: xclip exited with 1", transcript_text)

    with (
        patch.object(
            koe_insert,
            "backup_clipboard_text",
            return_value={"ok": True, "value": {"content": "old"}},
            create=True,
        ),
        patch.object(
            koe_insert,
            "write_clipboard_text",
            return_value={"ok": False, "error": write_error},
            create=True,
        ),
        patch.object(koe_insert, "simulate_paste", create=True) as paste_mock,
        patch.object(koe_insert, "restore_clipboard_text", create=True) as restore_mock,
    ):
        result = _call_insert_transcript_text(transcript_text, DEFAULT_CONFIG)

    assert result == {"ok": False, "error": write_error}
    paste_mock.assert_not_called()
    restore_mock.assert_not_called()


def test_insert_transcript_text_short_circuits_on_paste_failure() -> None:
    transcript_text = "hello"
    paste_error = _insert_error("paste simulation failed: xdotool exited with 1", transcript_text)

    with (
        patch.object(
            koe_insert,
            "backup_clipboard_text",
            return_value={"ok": True, "value": {"content": "old"}},
            create=True,
        ),
        patch.object(
            koe_insert,
            "write_clipboard_text",
            return_value={"ok": True, "value": None},
            create=True,
        ),
        patch.object(
            koe_insert,
            "simulate_paste",
            return_value={"ok": False, "error": paste_error},
            create=True,
        ),
        patch.object(koe_insert, "restore_clipboard_text", create=True) as restore_mock,
    ):
        result = _call_insert_transcript_text(transcript_text, DEFAULT_CONFIG)

    assert result == {"ok": False, "error": paste_error}
    restore_mock.assert_not_called()


def test_insert_transcript_text_surfaces_restore_failure_after_successful_paste() -> None:
    transcript_text = "hello"
    restore_error = _insert_error("clipboard restore failed: xclip exited with 1", transcript_text)

    with (
        patch.object(
            koe_insert,
            "backup_clipboard_text",
            return_value={"ok": True, "value": {"content": "old"}},
            create=True,
        ),
        patch.object(
            koe_insert,
            "write_clipboard_text",
            return_value={"ok": True, "value": None},
            create=True,
        ),
        patch.object(
            koe_insert, "simulate_paste", return_value={"ok": True, "value": None}, create=True
        ),
        patch.object(
            koe_insert,
            "restore_clipboard_text",
            return_value={"ok": False, "error": restore_error},
            create=True,
        ),
    ):
        result = _call_insert_transcript_text(transcript_text, DEFAULT_CONFIG)

    assert result == {"ok": False, "error": restore_error}


def test_backup_clipboard_text_returns_existing_text_content() -> None:
    with patch("subprocess.run", return_value=_completed(stdout="existing text\n")):
        result = _call_backup_clipboard_text("spoken text")

    assert result == {"ok": True, "value": {"content": "existing text\n"}}


def test_backup_clipboard_text_maps_non_text_or_empty_clipboard_to_none() -> None:
    with patch(
        "subprocess.run", return_value=_completed(returncode=1, stderr="target has no text")
    ):
        result = _call_backup_clipboard_text("spoken text")

    assert result == {"ok": True, "value": {"content": None}}


def test_backup_clipboard_text_returns_prefixed_error_on_operational_failure() -> None:
    transcript_text = "spoken text"
    with patch("subprocess.run", side_effect=OSError("xclip missing")):
        result = _call_backup_clipboard_text(transcript_text)

    assert result["ok"] is False
    assert result["error"]["category"] == "insertion"
    assert result["error"]["transcript_text"] == transcript_text
    assert result["error"]["message"].startswith("clipboard backup failed:")


def test_backup_clipboard_text_is_read_only() -> None:
    with patch("subprocess.run", return_value=_completed(stdout="existing text")) as run_mock:
        result = _call_backup_clipboard_text("spoken text")

    assert result["ok"] is True
    for call in run_mock.call_args_list:
        args = call.args[0]
        command_text = " ".join(str(part) for part in args)
        assert "-i" not in command_text


def test_write_clipboard_text_writes_provided_text_to_clipboard() -> None:
    text_to_write = "clipboard payload"
    transcript_text = "original transcript"

    with patch("subprocess.run", return_value=_completed()) as run_mock:
        result = _call_write_clipboard_text(text_to_write, transcript_text)

    assert result == {"ok": True, "value": None}
    called_with_input = run_mock.call_args.kwargs.get("input")
    if called_with_input is not None:
        assert called_with_input == text_to_write
    else:
        command_text = " ".join(str(part) for part in run_mock.call_args.args[0])
        assert text_to_write in command_text
        assert transcript_text not in command_text


def test_write_clipboard_text_maps_write_failure_to_prefixed_error() -> None:
    transcript_text = "original transcript"

    with patch("subprocess.run", return_value=_completed(returncode=1, stderr="write failed")):
        result = _call_write_clipboard_text("clipboard payload", transcript_text)

    assert result["ok"] is False
    assert result["error"]["category"] == "insertion"
    assert result["error"]["transcript_text"] == transcript_text
    assert result["error"]["message"].startswith("clipboard write failed:")


def test_simulate_paste_uses_configured_modifier_and_key() -> None:
    config = cast(
        "KoeConfig", {**DEFAULT_CONFIG, "paste_key_modifier": "alt", "paste_key": "Insert"}
    )

    with patch("subprocess.run", return_value=_completed()) as run_mock:
        result = _call_simulate_paste(config, "spoken text")

    assert result == {"ok": True, "value": None}
    command_text = " ".join(str(part) for part in run_mock.call_args.args[0])
    assert "alt" in command_text
    assert "Insert" in command_text
    assert "ctrl+v" not in command_text


def test_simulate_paste_maps_xdotool_failure_to_prefixed_error() -> None:
    transcript_text = "spoken text"

    with patch(
        "subprocess.run", return_value=_completed(returncode=1, stderr="cannot connect to X server")
    ):
        result = _call_simulate_paste(DEFAULT_CONFIG, transcript_text)

    assert result["ok"] is False
    assert result["error"]["category"] == "insertion"
    assert result["error"]["transcript_text"] == transcript_text
    assert result["error"]["message"].startswith("paste simulation failed:")


def test_restore_clipboard_text_restores_exact_prior_text() -> None:
    state = cast("ClipboardState", {"content": "prior clipboard text"})
    transcript_text = "spoken text"

    with patch("subprocess.run", return_value=_completed()) as run_mock:
        result = _call_restore_clipboard_text(state, transcript_text)

    assert result == {"ok": True, "value": None}
    called_with_input = run_mock.call_args.kwargs.get("input")
    if called_with_input is not None:
        assert called_with_input == state["content"]
    else:
        command_text = " ".join(str(part) for part in run_mock.call_args.args[0])
        assert state["content"] is not None
        assert state["content"] in command_text


def test_restore_clipboard_text_noops_when_backup_content_is_none() -> None:
    with patch("subprocess.run") as run_mock:
        result = _call_restore_clipboard_text(
            cast("ClipboardState", {"content": None}), "spoken text"
        )

    assert result == {"ok": True, "value": None}
    run_mock.assert_not_called()


def test_restore_clipboard_text_maps_restore_failure_to_prefixed_error() -> None:
    transcript_text = "spoken text"

    with patch("subprocess.run", return_value=_completed(returncode=1, stderr="restore failed")):
        result = _call_restore_clipboard_text(
            cast("ClipboardState", {"content": "prior clipboard text"}),
            transcript_text,
        )

    assert result["ok"] is False
    assert result["error"]["category"] == "insertion"
    assert result["error"]["transcript_text"] == transcript_text
    assert result["error"]["message"].startswith("clipboard restore failed:")

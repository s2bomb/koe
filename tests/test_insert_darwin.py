# ruff: noqa: N802  — fake methods mirror CoreGraphics' CamelCase API names
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from koe import insert as koe_insert
from koe.config import DEFAULT_CONFIG

if TYPE_CHECKING:
    from koe.types import InsertionError, Result

_PRIVATE_SOURCE_STATE = -1
_SESSION_TAP = 1
_KEY_V = 0x09
_COMMAND_FLAG = 0x0010_0000
_DOWN_AND_UP = 2


@pytest.fixture(autouse=True)
def _pin_darwin_backend(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("KOE_BACKEND", "darwin")


class _FakeQuartz:
    """Records every CoreGraphics call so tests assert the exact event sequence."""

    def __init__(self, *, preflight: bool = True, request: bool = False) -> None:
        self.ops: list[tuple[object, ...]] = []
        self._preflight = preflight
        self._request = request
        self.post_error: Exception | None = None

    def CGPreflightPostEventAccess(self) -> bool:
        self.ops.append(("preflight",))
        return self._preflight

    def CGRequestPostEventAccess(self) -> bool:
        self.ops.append(("request",))
        return self._request

    def CGEventSourceCreate(self, state: int, /) -> object:
        self.ops.append(("source", state))
        return ("source-handle", state)

    def CGEventCreateKeyboardEvent(self, source: object, keycode: int, keydown: bool, /) -> object:
        self.ops.append(("create", source, keycode, keydown))
        return ("event", keycode, keydown)

    def CGEventSetFlags(self, event: object, flags: int, /) -> None:
        self.ops.append(("flags", event, flags))

    def CGEventPost(self, tap: int, event: object, /) -> None:
        if self.post_error is not None:
            raise self.post_error
        self.ops.append(("post", tap, event))


def _paste(fake: _FakeQuartz | None, *, secure_input: bool = False) -> Result[None, InsertionError]:
    with (
        patch.object(koe_insert, "_quartz", fake),
        patch.object(koe_insert, "_secure_input_enabled", return_value=secure_input),
    ):
        return koe_insert.simulate_paste(DEFAULT_CONFIG, "transcript")


def test_clipboard_write_uses_pbcopy() -> None:
    completed = subprocess.CompletedProcess(args=["pbcopy"], returncode=0, stdout="", stderr="")
    with patch.object(koe_insert.subprocess, "run", return_value=completed) as run_mock:
        result = koe_insert.write_clipboard_text("hello", "hello")

    assert result["ok"] is True
    assert run_mock.call_args.args[0] == ["pbcopy"]


def test_paste_posts_command_v_down_then_up_on_session_tap() -> None:
    fake = _FakeQuartz(preflight=True)

    result = _paste(fake)

    assert result["ok"] is True
    key_down = ("event", _KEY_V, True)
    key_up = ("event", _KEY_V, False)
    assert ("source", _PRIVATE_SOURCE_STATE) in fake.ops
    assert ("flags", key_down, _COMMAND_FLAG) in fake.ops
    assert ("flags", key_up, _COMMAND_FLAG) in fake.ops
    posts = [op for op in fake.ops if op[0] == "post"]
    assert posts == [("post", _SESSION_TAP, key_down), ("post", _SESSION_TAP, key_up)]


def test_paste_without_quartz_is_typed_error() -> None:
    result = _paste(None)

    assert result["ok"] is False
    assert "Quartz is unavailable" in result["error"]["message"]


def test_paste_blocked_by_secure_input_is_typed_error_with_no_posts() -> None:
    fake = _FakeQuartz(preflight=True)

    result = _paste(fake, secure_input=True)

    assert result["ok"] is False
    assert "secure input" in result["error"]["message"]
    assert [op for op in fake.ops if op[0] == "post"] == []


def test_paste_without_permission_requests_once_then_errors() -> None:
    fake = _FakeQuartz(preflight=False, request=False)

    result = _paste(fake)

    assert result["ok"] is False
    assert "post-event permission" in result["error"]["message"]
    assert ("request",) in fake.ops
    assert [op for op in fake.ops if op[0] == "post"] == []


def test_paste_proceeds_when_permission_granted_on_request() -> None:
    fake = _FakeQuartz(preflight=False, request=True)

    result = _paste(fake)

    assert result["ok"] is True
    assert len([op for op in fake.ops if op[0] == "post"]) == _DOWN_AND_UP


def test_paste_post_failure_is_typed_error_preserving_transcript() -> None:
    fake = _FakeQuartz(preflight=True)
    fake.post_error = RuntimeError("event tap rejected")

    result = _paste(fake)

    assert result["ok"] is False
    assert "event tap rejected" in result["error"]["message"]
    assert result["error"]["transcript_text"] == "transcript"

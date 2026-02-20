from __future__ import annotations

from pathlib import Path

from koe import hotkey
from koe.config import DEFAULT_CONFIG, KoeConfig


def _config_with_lock(lock_path: Path) -> KoeConfig:
    return {**DEFAULT_CONFIG, "lock_file_path": lock_path}


def test_acquire_instance_lock_returns_success_handle_on_first_acquire(tmp_path: Path) -> None:
    config = _config_with_lock(tmp_path / "koe.lock")
    result = hotkey.acquire_instance_lock(config)

    assert result["ok"] is True
    assert isinstance(result["value"], Path)


def test_acquire_instance_lock_returns_err_when_already_running(tmp_path: Path) -> None:
    config = _config_with_lock(tmp_path / "koe.lock")
    first = hotkey.acquire_instance_lock(config)

    try:
        second = hotkey.acquire_instance_lock(config)
        assert first["ok"] is True
        assert second["ok"] is False
        assert second["error"]["category"] == "already_running"
        assert second["error"]["lock_file"] == str(config["lock_file_path"])
        assert isinstance(second["error"]["conflicting_pid"], int | None)
    finally:
        if first["ok"] is True:
            hotkey.release_instance_lock(first["value"])


def test_acquire_instance_lock_returns_typed_err_for_unusable_lock_path(tmp_path: Path) -> None:
    parent_as_file = tmp_path / "not-a-dir"
    parent_as_file.write_text("occupied", encoding="utf-8")
    config = _config_with_lock(parent_as_file / "koe.lock")

    result = hotkey.acquire_instance_lock(config)

    assert result["ok"] is False
    assert result["error"]["category"] == "already_running"
    assert result["error"]["lock_file"] == str(config["lock_file_path"])
    assert isinstance(result["error"]["conflicting_pid"], int | None)


def test_release_instance_lock_is_idempotent_and_non_raising(tmp_path: Path) -> None:
    config = _config_with_lock(tmp_path / "koe.lock")
    result = hotkey.acquire_instance_lock(config)

    assert result["ok"] is True
    lock_handle = result["value"]

    hotkey.release_instance_lock(lock_handle)
    hotkey.release_instance_lock(lock_handle)

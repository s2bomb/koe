"""Single-instance invocation guard for the Section 2 pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from koe.types import AlreadyRunningError, InstanceLockHandle, Result

if TYPE_CHECKING:
    from koe.config import KoeConfig


def _already_running_error(lock_file: Path, message: str) -> AlreadyRunningError:
    return {
        "category": "already_running",
        "message": message,
        "lock_file": str(lock_file),
        "conflicting_pid": _read_lock_pid(lock_file),
    }


def _read_lock_pid(lock_file: Path) -> int | None:
    try:
        raw = lock_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    if not raw:
        return None

    try:
        return int(raw)
    except ValueError:
        return None


def _is_process_alive(pid: int, /) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _try_break_stale_lock(lock_file: Path, /) -> bool:
    pid = _read_lock_pid(lock_file)
    if pid is None:
        return False
    if _is_process_alive(pid):
        return False

    try:
        lock_file.unlink()
    except OSError:
        return False
    return True


def acquire_instance_lock(config: KoeConfig, /) -> Result[InstanceLockHandle, AlreadyRunningError]:
    """Acquire lockfile ownership token or return typed contention error."""
    lock_file = config["lock_file_path"]
    try:
        with lock_file.open("x", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
    except FileExistsError:
        if _try_break_stale_lock(lock_file):
            return acquire_instance_lock(config)
        return {
            "ok": False,
            "error": _already_running_error(
                lock_file,
                f"another koe instance is active; remove stale lock at {lock_file}"
                " if this is unexpected",
            ),
        }
    except OSError:
        return {
            "ok": False,
            "error": _already_running_error(lock_file, "unable to acquire instance lock"),
        }

    return {"ok": True, "value": InstanceLockHandle(lock_file)}


def release_instance_lock(handle: InstanceLockHandle, /) -> None:
    """Release a previously acquired lockfile token; swallow cleanup failures."""
    lock_file = Path(handle)
    try:
        lock_file.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return

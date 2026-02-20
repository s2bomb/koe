"""Single-instance invocation guard and toggle signalling for the pipeline."""

from __future__ import annotations

import os
import signal
from pathlib import Path
from typing import TYPE_CHECKING

from koe.types import AlreadyRunningError, HotkeyAction, InstanceLockHandle, Result

if TYPE_CHECKING:
    from koe.config import KoeConfig


def determine_hotkey_action(config: KoeConfig, /) -> tuple[HotkeyAction, int | None]:
    """Determine whether this invocation should start or stop recording.

    If no lock exists, this is a "start" (the caller should acquire the lock
    and begin recording). If a lock exists with a live PID, this is a "stop"
    (the caller should signal that PID and exit). Returns the action and the
    PID to signal (only set for "stop").
    """
    lock_file = config["lock_file_path"]
    pid = _read_lock_pid(lock_file)
    if pid is not None and _is_process_alive(pid):
        return ("stop", pid)
    return ("start", None)


def signal_running_instance(pid: int, /) -> bool:
    """Send SIGUSR1 to a running koe instance to stop recording.

    Returns True if the signal was delivered, False if the process no longer exists.
    """
    try:
        os.kill(pid, signal.SIGUSR1)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    return True


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

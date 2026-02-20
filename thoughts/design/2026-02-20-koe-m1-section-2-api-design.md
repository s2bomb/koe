# Koe M1 Section 2 API Design: Invocation, Focus Gate, and Concurrency Guard

---
date: 2026-02-20
author: opencode
status: approved-for-implementation
project: koe-m1
section: "Section 2: Invocation, Focus Gate, and Concurrency Guard"
source_spec: thoughts/projects/2026-02-20-koe-m1/spec.md
source_research: thoughts/projects/2026-02-20-koe-m1/working/section-2-research.md
scope: "hotkey.py, window.py, notify.py, and Section 2 portions of main.py"
---

## Core Principle

Section 2 owns all pre-record decisions. Before any audio API is called, the pipeline must deterministically answer:

1. Are required startup dependencies available?
2. Is another Koe invocation already active?
3. Is there a focused X11 window?

Every negative answer is an expected, typed error with explicit user feedback and controlled exit (`ExitCode` 1), never a silent skip.

## Section 2 Acceptance Mapping

| Acceptance Criterion | API owner | Contract |
|---|---|---|
| AC1: invocation is external global hotkey; no daemon | `main.py` + `hotkey.py` | `main()` remains one-shot; no background listener loop in-process |
| AC2: focus checked before recording | `window.py` + `main.py` | `check_focused_window()` runs before any Section 3 audio call |
| AC3: no focus -> notify + exit without recording | `window.py` + `notify.py` + `main.py` | `Err[FocusError]` -> `send_notification("error_focus", ...)` -> `"no_focus"` |
| AC4: single-instance guard | `hotkey.py` + `main.py` | atomic lock acquire before focus/audio stages |
| AC5: blocked guard gives explicit already-running feedback | `types.py` + `notify.py` + `main.py` | new typed category and notification literal for `already_running` |
| AC6: startup dependency failures explicit + safe exit | `main.py` + `window.py` + `notify.py` | `dependency_preflight()` returns `Err[DependencyError]` arm, no crash |

## Required Type Extensions (Section 2)

These changes are required to make AC5 compile-time enforceable.

```python
# src/koe/types.py
from pathlib import Path
from typing import Literal, NewType, TypedDict

InstanceLockHandle = NewType("InstanceLockHandle", Path)


class AlreadyRunningError(TypedDict):
    category: Literal["already_running"]
    message: str
    lock_file: str
    conflicting_pid: int | None


type NotificationKind = Literal[
    "recording_started",
    "processing",
    "completed",
    "error_focus",
    "error_audio",
    "error_transcription",
    "error_insertion",
    "error_dependency",
    "already_running",
]


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
    "no_focus",
    "no_speech",
    "error_dependency",
    "error_audio",
    "error_transcription",
    "error_insertion",
    "error_unexpected",
    "already_running",
]
```

## Module APIs

### `src/koe/hotkey.py`

`hotkey.py` in Section 2 is the invocation guard API, not a daemon listener.

```python
from koe.config import KoeConfig
from koe.types import AlreadyRunningError, InstanceLockHandle, Result


def acquire_instance_lock(config: KoeConfig, /) -> Result[InstanceLockHandle, AlreadyRunningError]:
    """Atomically acquire single-run lock using config['lock_file_path'].

    Ok: returns ownership handle for this process.
    Err: another instance is active or lock path is unusable.
    """


def release_instance_lock(handle: InstanceLockHandle, /) -> None:
    """Best-effort lock release. Idempotent and non-raising."""
```

Error behavior:
- `Err[AlreadyRunningError]` maps to notification `"already_running"` and outcome `"already_running"`.
- lock release failures are logged but never change pipeline outcome.

### `src/koe/window.py`

`window.py` owns X11 context checks and focused-window lookup.

```python
from koe.types import DependencyError, FocusError, FocusedWindow, Result


def check_x11_context() -> Result[None, DependencyError]:
    """Validate Section 2 X11 prerequisites (DISPLAY + xdotool)."""


def check_focused_window() -> Result[FocusedWindow, FocusError]:
    """Return focused window metadata or typed focus failure."""
```

Error behavior:
- `Err[DependencyError]` from `check_x11_context()` maps to `"error_dependency"`.
- `Err[FocusError]` from `check_focused_window()` maps to `"error_focus"` + outcome `"no_focus"`.

### `src/koe/notify.py`

`notify.py` is best-effort emission only; it never raises into orchestration.

```python
from koe.types import KoeError, NotificationKind


def send_notification(kind: NotificationKind, error: KoeError | None = None) -> None:
    """Emit desktop notification for lifecycle/error state.

    Notification delivery failure is swallowed after warning log.
    """
```

Section 2 required kind mappings:
- `"error_dependency"`
- `"error_focus"`
- `"already_running"`

### `src/koe/main.py` (Section 2-owned portions)

`run_pipeline()` keeps one-shot invocation semantics and adds only pre-record stages.

```python
from koe.config import KoeConfig
from koe.types import DependencyError, ExitCode, PipelineOutcome, Result


def dependency_preflight(config: KoeConfig, /) -> Result[None, DependencyError]:
    """Validate required startup dependencies for Section 2 (xdotool, xclip, notify-send, CUDA)."""


def run_pipeline(config: KoeConfig, /) -> PipelineOutcome:
    """Section 2 orchestration order:

    1) dependency_preflight(config)
    2) acquire_instance_lock(config)
    3) check_x11_context()
    4) check_focused_window()
    5) handoff to Section 3 capture stage (out of scope here)
    """


def outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode:
    """Map controlled outcomes (including 'already_running') to 1."""
```

Required ordering contract in `run_pipeline()`:
- no Section 3 function may be called until all Section 2 preconditions above are `Ok`.
- lock handle is released in `finally` on all exits after successful acquire.

## Error Mapping Table

| Source | Result arm | Notification | PipelineOutcome | ExitCode |
|---|---|---|---|---|
| `dependency_preflight()` | `Err[DependencyError]` | `error_dependency` | `error_dependency` | 1 |
| `acquire_instance_lock()` | `Err[AlreadyRunningError]` | `already_running` | `already_running` | 1 |
| `check_focused_window()` | `Err[FocusError]` | `error_focus` | `no_focus` | 1 |
| unexpected exception | raise | best-effort notify | `error_unexpected` | 2 |

## Concurrency Guard API Contract

- Acquire is atomic and non-blocking.
- Success returns `InstanceLockHandle` token; only that token can be released.
- Failure returns typed `AlreadyRunningError` with lock path and optional conflicting pid.
- Release is idempotent best-effort in `finally`.
- A second invocation never progresses to focus/audio stages.

## Out of Scope for Section 2

- Audio capture implementation details (Section 3)
- Recording stop semantics and waveform lifecycle (Section 3)
- Transcription/insertion behavior (Sections 4-5)
- Full lifecycle notification catalog beyond Section 2-required states (Section 6)

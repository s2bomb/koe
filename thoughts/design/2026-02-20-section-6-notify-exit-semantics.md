---
date: 2026-02-20
project: koe-m1
section: 6
status: approved-for-test-design
source_spec: thoughts/projects/2026-02-20-koe-m1/spec.md
source_research: thoughts/projects/2026-02-20-koe-m1/working/section-6-research.md
focus_modules:
  - src/koe/notify.py
  - src/koe/main.py (Section 6 notification dispatch and exit mapping)
---

# Section 6 API Design: User Feedback and Error Surfaces

## Core Principle

**`notify.py` converts typed pipeline events into deterministic, user-visible desktop notifications with swallowed transport failures; `main.py` is the exclusive dispatcher of all lifecycle notifications and maps every `PipelineOutcome` to a deterministic `ExitCode` via `outcome_to_exit_code`.**

---

## Scope

Strictly bounded to Section 6 acceptance criteria in `thoughts/projects/2026-02-20-koe-m1/spec.md:89`
through `thoughts/projects/2026-02-20-koe-m1/spec.md:99`.

**In scope:**
- Notification payload content contract for all 10 `NotificationKind` values (title + message strings)
- `send_notification` function contract and non-raising guarantee
- `_notification_payload` exhaustive handling specification, including the implementation gap found in research
- Pipeline-to-notification dispatch mapping in `run_pipeline` (which kind is emitted, when, with what error)
- `outcome_to_exit_code` complete mapping specification
- `main()` exception-to-exit-code contract
- Test evidence obligations tied to each Section 6 AC

**Out of scope:**
- Audio, transcription, and insertion internals beyond what `main.py` dispatches
- Notification UI styling beyond title and message strings
- Non-`notify-send` desktop notification backends
- Wayland or D-Bus alternatives (X11 / M1 only)

---

## Existing Contracts Reused

All types are already defined in `src/koe/types.py` and must not change:

| Type | Location | Value |
|---|---|---|
| `NotificationKind` | `types.py:83` | 10-value closed `Literal` |
| `KoeError` | `types.py:127` | 6-variant discriminated union |
| `PipelineOutcome` | `types.py:136` | 9-value closed `Literal` |
| `ExitCode` | `types.py:148` | `Literal[0, 1, 2]` |

No new type aliases are required for Section 6 M1.

---

## Module Responsibilities

### `src/koe/notify.py`

**Owns:**
1. `send_notification(kind, error)` — the sole public notification API; called only from `main.py`
2. `_notification_payload(kind, error)` — pure function: `NotificationKind × KoeError | None → (title, message)`
3. `_error_message(error, fallback)` — pure helper: extract `error["message"]` or return fallback
4. Non-raising transport wrapper: subprocess call with `except Exception: return`

**Does NOT own:**
- Pipeline dispatch decisions (which kind to emit at which phase — that belongs to `main.py`)
- Exit code mapping
- Any mutable state

### `src/koe/main.py` (Section 6 scope)

**Owns:**
1. `run_pipeline` notification dispatch — the exclusive site where each `NotificationKind` is emitted at each pipeline phase transition
2. `outcome_to_exit_code(outcome)` — total function: `PipelineOutcome → ExitCode`
3. `main()` exception-to-exit contract — uncaught exceptions from `run_pipeline` produce `sys.exit(2)` directly

**Does NOT own:**
- Notification payload content (what the title/message say)
- Transport failure handling

---

## API Surface

### `notify.py`

```python
def send_notification(kind: NotificationKind, error: KoeError | None = None) -> None:
    """Attempt to send a desktop notification via notify-send; swallow all transport failures."""
```

**Contract:**
- Return type is `None` unconditionally — this function never raises under any condition
- Lifecycle kinds (`recording_started`, `processing`, `completed`, `no_speech`): `error` MUST be `None`; callers omit the parameter
- Error kinds (`error_*`, `already_running`): `error` MUST be non-`None` with the matching error category
- Subprocess invocation: `["notify-send", title, message]` with `check=False`, `capture_output=True`, `text=True`
- All exceptions from subprocess (including `FileNotFoundError`, `OSError`, any `Exception` subclass) are caught and swallowed with bare `except Exception: return`

```python
def _notification_payload(kind: NotificationKind, error: KoeError | None) -> tuple[str, str]:
    """Map notification kind and optional error to (title, message) pair for notify-send."""
```

**Contract:**
- Pure function — zero side effects, no subprocess calls, no I/O
- MUST handle all 10 `NotificationKind` values explicitly
- MUST use an exhaustive match with `assert_never` on the wildcard case so Pyright enforces completeness when `NotificationKind` gains new values
- Returns `(title, message)` where both strings are non-empty
- For error kinds: message is `error["message"]` when `error` is non-`None`, else the defined static fallback
- For lifecycle kinds: returns static strings from the Notification Contract Matrix below — never `kind.replace("_", " ")`

```python
def _error_message(error: KoeError | None, fallback: str) -> str:
    """Extract error["message"] from KoeError or return fallback when error is None."""
```

**Contract:**
- Pure function — zero side effects
- `error is None` → returns `fallback` unchanged
- `error is not None` → returns `error["message"]`

### `main.py`

```python
def outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode:
    """Map every PipelineOutcome to its deterministic exit code; exhaustive over all variants."""
```

**Contract:**
- Total function — every `PipelineOutcome` value maps to exactly one `ExitCode`
- Uses exhaustive `match` with `assert_never` on wildcard — Pyright enforces completeness
- Must not raise under any input

```python
def main() -> None:
    """CLI entrypoint: run pipeline, map outcome to exit code, handle uncaught exceptions."""
```

**Contract:**
- Calls `run_pipeline(DEFAULT_CONFIG)` then `sys.exit(outcome_to_exit_code(outcome))`
- Wraps entire body in `try/except Exception` — any uncaught exception produces `sys.exit(2)` directly, bypassing `outcome_to_exit_code`
- Never returns to caller

```python
def run_pipeline(config: KoeConfig, /) -> PipelineOutcome:
    """Execute full M1 pipeline; dispatch lifecycle notifications at each phase transition."""
```

**Section 6 contract (notification dispatch only):**
- All 10 `NotificationKind` values are dispatched from `run_pipeline` at defined phase transitions (see Notification Dispatch Matrix)
- Each error dispatch passes the matching `KoeError` instance as `error` argument
- Each lifecycle dispatch omits the `error` argument
- `run_pipeline` never returns without having dispatched at least one `NotificationKind`

---

## Notification Contract Matrix

This is the normative payload specification. Downstream test design derives deterministic test cases from
this table. Any implementation that produces different strings fails Section 6.

### Lifecycle notifications (`error` parameter: omitted / `None`)

| `NotificationKind` | `notify-send` title | `notify-send` message |
|---|---|---|
| `"recording_started"` | `"Koe"` | `"Recording…"` |
| `"processing"` | `"Koe"` | `"Processing…"` |
| `"completed"` | `"Koe"` | `"Transcription complete"` |
| `"no_speech"` | `"Koe"` | `"No speech detected"` |

### Error notifications (`error` parameter: matching `KoeError` instance)

| `NotificationKind` | Expected error category | `notify-send` title | `notify-send` message |
|---|---|---|---|
| `"already_running"` | `"already_running"` | `"Koe already running"` | `error["message"]` or `"Another Koe invocation is active."` |
| `"error_focus"` | `"focus"` | `"Koe focus required"` | `error["message"]` or `"No focused window is available."` |
| `"error_dependency"` | `"dependency"` | `"Koe dependency issue"` | `error["message"]` or `"A required dependency is missing."` |
| `"error_audio"` | `"audio"` | `"Koe audio error"` | `error["message"]` or `"Microphone capture failed."` |
| `"error_transcription"` | `"transcription"` | `"Koe transcription error"` | `error["message"]` or `"Transcription failed."` |
| `"error_insertion"` | `"insertion"` | `"Koe insertion error"` | `error["message"]` or `"Text insertion failed."` |

**Matrix invariants:**
1. Lifecycle titles are always `"Koe"` — no subsystem label for success/progress states
2. Error titles always include a subsystem descriptor (e.g. `"Koe audio error"`) — never just `"Koe"`
3. Error messages MUST extract `error["message"]` when `error` is non-`None` — silently dropping it violates AC3
4. Fallback message strings are static and must never be the empty string
5. No kind uses `kind.replace("_", " ")` as its message — that is an implementation artifact, not a contract

---

## Notification Dispatch Matrix

Normative specification of which `NotificationKind` is dispatched at each pipeline phase, in order.

| Pipeline phase | Trigger condition | `NotificationKind` | `KoeError` type passed |
|---|---|---|---|
| Pre-record: dependency | `dependency_preflight` returns `Err` | `"error_dependency"` | `DependencyError` |
| Pre-record: lock contention | `acquire_instance_lock` returns `Err` | `"already_running"` | `AlreadyRunningError` |
| Pre-record: X11 context | `check_x11_context` returns `Err` | `"error_dependency"` | `DependencyError` |
| Pre-record: focus check | `check_focused_window` returns `Err` | `"error_focus"` | `FocusError` |
| Recording: capture start | After all pre-record gates pass | `"recording_started"` | _(omitted)_ |
| Recording: empty audio | `capture_audio` returns `kind="empty"` | `"no_speech"` | _(omitted)_ |
| Recording: capture failure | `capture_audio` returns `kind="error"` | `"error_audio"` | `AudioError` |
| Processing: transcription start | Before `transcribe_audio` is called | `"processing"` | _(omitted)_ |
| Processing: empty transcript | `transcribe_audio` returns `kind="empty"` | `"no_speech"` | _(omitted)_ |
| Processing: transcription failure | `transcribe_audio` returns `kind="error"` | `"error_transcription"` | `TranscriptionError` |
| Completion: insertion failure | `insert_transcript_text` returns `Err` | `"error_insertion"` | `InsertionError` |
| Completion: success | `insert_transcript_text` returns `Ok` | `"completed"` | _(omitted)_ |

**Dispatch ordering invariants (must hold under all test scenarios):**
1. `"recording_started"` MUST be dispatched before `capture_audio` is called
2. `"processing"` MUST be dispatched before `transcribe_audio` is called
3. On the success path, the full notification sequence is exactly: `["recording_started", "processing", "completed"]`
4. On the `no_speech` transcription path: `["recording_started", "processing", "no_speech"]`
5. Every pipeline exit dispatches exactly one terminal notification (the final notification before return)

---

## Outcome-to-Exit Semantics

### Full Mapping Table

| `PipelineOutcome` | `ExitCode` | Interpretation |
|---|---|---|
| `"success"` | `0` | Transcription inserted successfully; clean run |
| `"no_focus"` | `1` | Expected operational: no focused window at invocation time |
| `"no_speech"` | `1` | Expected operational: audio captured but no usable speech |
| `"already_running"` | `1` | Expected operational: concurrency guard blocked this invocation |
| `"error_dependency"` | `1` | Expected operational: missing X11 tool, DISPLAY, or CUDA policy |
| `"error_audio"` | `1` | Expected operational: microphone capture failure |
| `"error_transcription"` | `1` | Expected operational: Whisper/CUDA inference failure |
| `"error_insertion"` | `1` | Expected operational: clipboard or paste operation failure |
| `"error_unexpected"` | `2` | Programmer bug: uncaught exception — **never returned by `run_pipeline`** |

**Semantic distinction:**
- Exit `0`: run completed as designed
- Exit `1`: run did not complete, user received a failure notification, condition is diagnosable
- Exit `2`: programmer error or runtime corruption; user may NOT have received a failure notification

### The `"error_unexpected"` Special Case

`"error_unexpected"` exists in `PipelineOutcome` to keep `outcome_to_exit_code`'s exhaustive `match`
type-safe and to satisfy `assert_never`. However, `run_pipeline` never returns it.

The actual exit-code-2 path is:

```
main() try block
  → run_pipeline(DEFAULT_CONFIG) raises Exception (unhandled)
  → except Exception: sys.exit(2)   ← bypasses outcome_to_exit_code entirely
```

**Consequence:** When the exception path fires, `send_notification` has not been called for an error
kind. The user does NOT receive a failure notification on programmer-error exits. This is an accepted
M1 limitation.

---

## Invariants

These must hold after any implementation change to `notify.py` or the Section 6 paths in `main.py`:

| # | Invariant | Enforcement |
|---|---|---|
| I1 | `send_notification` never raises under any condition | `try/except Exception: return` in implementation; test T6N-05 |
| I2 | Every `NotificationKind` has a defined title and message | Exhaustive match + `assert_never` in `_notification_payload`; Pyright |
| I3 | Error kinds always extract `error["message"]` when error is non-`None` | `_error_message` used for all error kinds; tests T6N-02, T6N-03 |
| I4 | Lifecycle kinds return static strings from the matrix — never dynamic | Exhaustive match; tests T6N-01 |
| I5 | `outcome_to_exit_code` is total over all 9 `PipelineOutcome` values | Exhaustive match + `assert_never`; test T6M-01 |
| I6 | Every error pipeline branch dispatches exactly one `send_notification` call before return | Pipeline tests per branch; tests T6M-03 |
| I7 | `"recording_started"` precedes `capture_audio` | Ordering test T6M-04a |
| I8 | `"processing"` precedes `transcribe_audio` | Ordering test T6M-04b (exists as `test_run_pipeline_processing_notification_precedes_transcription_call`) |

---

## Implementation Gap: `_notification_payload`

Research found the current `src/koe/notify.py` implementation has a concrete gap.

**Current behavior** (`notify.py:26`):
```python
def _notification_payload(kind: NotificationKind, error: KoeError | None) -> tuple[str, str]:
    if kind == "already_running":
        return ("Koe already running", _error_message(error, "Another Koe invocation is active."))
    if kind == "error_focus":
        return ("Koe focus required", _error_message(error, "No focused window is available."))
    if kind == "error_dependency":
        return ("Koe dependency issue", _error_message(error, "A required dependency is missing."))

    return ("Koe", kind.replace("_", " "))  # ← fallthrough: 7 of 10 kinds land here
```

**What the fallthrough produces for error kinds:**
- `"error_audio"` → `("Koe", "error audio")` — `error["message"]` is silently dropped (**AC3 violation**)
- `"error_transcription"` → `("Koe", "error transcription")` — `error["message"]` is silently dropped (**AC3 violation**)
- `"error_insertion"` → `("Koe", "error insertion")` — `error["message"]` is silently dropped (**AC3 violation**)

**What the fallthrough produces for lifecycle kinds:**
- `"recording_started"` → `("Koe", "recording started")` — lowercase, no ellipsis, not the specified string
- `"processing"` → `("Koe", "processing")` — acceptable but not the specified "Processing…"
- `"completed"` → `("Koe", "completed")` — not the specified "Transcription complete"
- `"no_speech"` → `("Koe", "no speech")` — not the specified "No speech detected"

**Required behavior** (normative from this design):
```python
def _notification_payload(kind: NotificationKind, error: KoeError | None) -> tuple[str, str]:
    match kind:
        case "recording_started":
            return ("Koe", "Recording…")
        case "processing":
            return ("Koe", "Processing…")
        case "completed":
            return ("Koe", "Transcription complete")
        case "no_speech":
            return ("Koe", "No speech detected")
        case "already_running":
            return ("Koe already running", _error_message(error, "Another Koe invocation is active."))
        case "error_focus":
            return ("Koe focus required", _error_message(error, "No focused window is available."))
        case "error_dependency":
            return ("Koe dependency issue", _error_message(error, "A required dependency is missing."))
        case "error_audio":
            return ("Koe audio error", _error_message(error, "Microphone capture failed."))
        case "error_transcription":
            return ("Koe transcription error", _error_message(error, "Transcription failed."))
        case "error_insertion":
            return ("Koe insertion error", _error_message(error, "Text insertion failed."))
        case _ as unreachable:
            assert_never(unreachable)
```

---

## Acceptance Criteria Mapping

| Section 6 AC | `spec.md` line | Evidence required | Current gap |
|---|---|---|---|
| AC1: Lifecycle states user-visible | `:95` | All 4 lifecycle kinds dispatched in `run_pipeline`; payload strings verified by tests | ⚠️ payload strings unspecified until this design; T6N-01 needed |
| AC2: Notifications map to clear run phases | `:96` | Notification Dispatch Matrix; ordering invariants I7, I8 | ✅ dispatch is correct; ordering tests exist for processing→transcription |
| AC3: Error notifications identify subsystem | `:97` | Error titles are subsystem-labeled; `error["message"]` extracted for all 6 error kinds | ⚠️ implementation gap: `error_audio`, `error_transcription`, `error_insertion` drop `error["message"]`; T6N-02, T6N-03 needed |
| AC4: Emission failures don't crash runtime | `:99` | Non-raising invariant I1; test T6N-05 covers all 10 kinds | ⚠️ existing `test_notify.py` covers only 3 of 10 kinds; must extend to all 10 |

---

## Test Evidence Obligations

Obligations define what tests MUST prove for each Section 6 AC. Cases are derived directly from the
Notification Contract Matrix and the invariants above — each row in the matrix corresponds to one or
more parametrized test cases.

### `tests/test_notify.py`

**T6N-01 — Payload correctness for all 4 lifecycle kinds (AC1)**

Parametrized over all 4 lifecycle `NotificationKind` values. For each kind, patch `subprocess.run`,
call `send_notification(kind)`, assert subprocess was called with:
```
["notify-send", <expected_title>, <expected_message>]
```
Expected values from the Notification Contract Matrix:
- `"recording_started"` → `("Koe", "Recording…")`
- `"processing"` → `("Koe", "Processing…")`
- `"completed"` → `("Koe", "Transcription complete")`
- `"no_speech"` → `("Koe", "No speech detected")`

_These tests will fail against the current implementation — that is the intent._

**T6N-02 — Error message extraction for all 6 error kinds (AC3)**

Parametrized over all 6 error `NotificationKind` values with matching `KoeError` instances. Assert
that the message passed to subprocess equals `error["message"]`, NOT the fallback:
- `"error_audio"` + `AudioError(message="mic not found")` → subprocess message = `"mic not found"`
- `"error_transcription"` + `TranscriptionError(message="CUDA not available")` → `"CUDA not available"`
- `"error_insertion"` + `InsertionError(message="clipboard restore failed: xclip exited with 1")` → that exact message
- `"already_running"` + `AlreadyRunningError(message="another koe instance is active")` → that message
- `"error_focus"` + `FocusError(message="no focused window")` → `"no focused window"`
- `"error_dependency"` + `DependencyError(message="required tool is missing: xdotool")` → that message

_The first three will fail against the current implementation._

**T6N-03 — Error title uniqueness for all 6 error kinds (AC3)**

Parametrized over all 6 error kinds. Assert that the title passed to subprocess is NOT `"Koe"` — it
must contain a subsystem descriptor. Verify exact title strings from the matrix:
- `"error_audio"` → title `"Koe audio error"`
- `"error_transcription"` → title `"Koe transcription error"`
- `"error_insertion"` → title `"Koe insertion error"`
- `"already_running"` → title `"Koe already running"`
- `"error_focus"` → title `"Koe focus required"`
- `"error_dependency"` → title `"Koe dependency issue"`

**T6N-04 — Fallback message when error is `None` for error kinds**

Parametrized over all 6 error kinds with `error=None`. Assert subprocess message equals the static
fallback from the matrix (not the empty string, not `kind.replace("_", " ")`):
- `"error_audio"` → `"Microphone capture failed."`
- `"error_transcription"` → `"Transcription failed."`
- `"error_insertion"` → `"Text insertion failed."`
- `"already_running"` → `"Another Koe invocation is active."`
- `"error_focus"` → `"No focused window is available."`
- `"error_dependency"` → `"A required dependency is missing."`

**T6N-05 — Non-raising guarantee for all 10 `NotificationKind` values (AC4)**

Extend the existing parametrized swallow test to cover all 10 `NotificationKind` values. For each
kind, patch `subprocess.run` with `side_effect=RuntimeError("backend down")` and assert that
`send_notification(kind, ...)` returns `None` without raising.

Current coverage: 3 of 10 kinds (`error_dependency`, `error_focus`, `already_running`).
Required coverage: all 10 kinds.

### `tests/test_main.py`

**T6M-01 — `outcome_to_exit_code` is total (already exists)**

`test_outcome_to_exit_code_is_total` at `test_main.py:112` — parametrized over all 9 outcomes.
No new cases needed. Existing test satisfies this obligation. ✅

**T6M-02 — Uncaught exception exits with code 2 (already exists)**

`test_main_maps_unexpected_exception_to_exit_2` at `test_main.py:19`. ✅

**T6M-03 — Notification kind and error payload per pipeline branch**

One test per pipeline error branch, asserting the correct `(kind, error)` pair is passed to
`send_notification`. This must verify the `error` argument is passed (not dropped), not merely that
`send_notification` was called.

Required coverage (most exist; verify error payload assertion):
- `"error_dependency"` branch: `notify_mock.assert_called_once_with("error_dependency", dependency_error)` ✅ `test_main.py:136`
- `"already_running"` branch: `notify_mock.assert_called_once_with("already_running", already_running_error)` ✅ `test_main.py:165`
- `"error_focus"` branch: `notify_mock.assert_called_once_with("error_focus", focus_error)` ✅ `test_main.py:194`
- `"error_audio"` branch: `notify_mock.assert_any_call("error_audio", audio_error)` — ⚠️ verify error payload assertion exists
- `"error_transcription"` branch: `notify_mock.assert_any_call("error_transcription", transcription_error)` ✅ `test_main.py:436`
- `"error_insertion"` branch: `notify_mock.assert_any_call("error_insertion", insertion_error)` ✅ `test_main.py:631`
- `"no_speech"` (audio empty): `notify_mock.assert_any_call("no_speech")` — verify exists
- `"no_speech"` (transcription empty): `notify_mock.assert_called_with("no_speech")` ✅ `test_main.py:392`
- `"completed"` on success: `notify_mock.assert_any_call("completed")` ✅ `test_main.py:480`

**T6M-04a — `"recording_started"` precedes `capture_audio` (ordering invariant I7)**

Use an events list (pattern established in `test_main.py:199`) to assert that `"notify:recording_started"` appears before `"capture_audio"` in the event sequence.

**T6M-04b — `"processing"` precedes `transcribe_audio` (ordering invariant I8, already exists)**

`test_run_pipeline_processing_notification_precedes_transcription_call` at `test_main.py:538`. ✅

**T6M-05 — Success path notification sequence is exactly `["recording_started", "processing", "completed"]`**

Assert `[call.args[0] for call in notify_mock.call_args_list]` equals
`["recording_started", "processing", "completed"]` on the full success path.
Partial coverage exists at `test_main.py:307` (asserts first two); extend to assert `"completed"` is third and no others follow.

### `tests/section6_static_fixtures.py` (new file)

Static compile-time proof that public API signatures have not changed during implementation.

**T6SF-01 — `send_notification` signature**
```python
from collections.abc import Callable
from koe.notify import send_notification
from koe.types import KoeError, NotificationKind

sig: Callable[[NotificationKind], None] = send_notification
```

**T6SF-02 — `outcome_to_exit_code` signature**
```python
from collections.abc import Callable
from koe.main import outcome_to_exit_code
from koe.types import ExitCode, PipelineOutcome

sig: Callable[[PipelineOutcome], ExitCode] = outcome_to_exit_code
```

**T6SF-03 — `NotificationKind` exhaustiveness** (already covered in `section1_static_fixtures.py:51`)

No duplication needed. Reference only.

---

## Failure Handling Policy

| Failure scenario | Policy | Rationale |
|---|---|---|
| `notify-send` subprocess raises any `Exception` | Swallow; `send_notification` returns `None` | AC4: notification failures must not crash the core runtime path |
| `notify-send` exits with non-zero code | Ignored (`check=False`) | Best-effort transport; non-zero exit is not an error for user-facing notification |
| `_notification_payload` receives unrecognized kind | Pyright compile error via `assert_never` | Invalid states are impossible at the type level; this never reaches runtime |
| `error` is `None` for an error kind | Returns static fallback message; does not raise | Defensive; preferred over crashing the notification path |
| Uncaught exception in `run_pipeline` | `main()` exits with code `2`; no notification sent | Programmer bugs are not expected user-visible events for M1 |

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| `_notification_payload` uses exhaustive `match` + `assert_never` | Required | Pyright enforces completeness when `NotificationKind` gains new values; fallthrough is a correctness hazard proven by the implementation gap |
| Error titles include subsystem descriptor | `"Koe audio error"` not `"Koe"` | AC3 requires subsystem identification; distinct titles also prevent desktop notification deduplication from collapsing separate errors into one |
| Lifecycle kinds use static strings, not `kind.replace("_", " ")` | Required | Static strings are design-owned and testable; dynamic transformation is implementation leakage that bypasses the design contract |
| `error["message"]` always extracted for error kinds | Required | AC3 requires subsystem error context; silently dropping `error["message"]` makes error notifications useless for diagnosis |
| `"error_unexpected"` in `PipelineOutcome` but never returned by `run_pipeline` | Preserved as-is | Needed for `assert_never` exhaustiveness in `outcome_to_exit_code`; `main()` exception path exits `2` directly |
| No new `NotificationKind` values for M1 | Closed set | All M1 failure paths are already modeled in the 10-value set; additions require type + test + implementation changes |
| No logging/metrics sink for M1 | Desktop notification is the sole observability channel | Minimal-dependency posture; structured logging would require additional runtime dependencies not in the M1 brief |

---

## Integration Notes

- `notify.py` is the only module that invokes `subprocess.run(["notify-send", ...])` — other modules never emit notifications directly.
- `main.py` is the only module that calls `send_notification` — `notify.py` is never imported by `audio.py`, `transcribe.py`, `insert.py`, or `window.py`.
- `section6_static_fixtures.py` provides compile-time proof that the public API surface has not changed during Section 6 implementation. It follows the pattern established by `section1_static_fixtures.py` through `section5_static_fixtures.py`.
- The exhaustive `assert_never` in `_notification_payload` and `outcome_to_exit_code` means both functions become Pyright errors (not runtime errors) when new variants are added to their respective types without being handled.

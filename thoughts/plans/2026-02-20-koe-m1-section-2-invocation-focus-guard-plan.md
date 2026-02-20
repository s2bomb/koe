---
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 2: Invocation, Focus Gate, and Concurrency Guard"
research_source: thoughts/projects/2026-02-20-koe-m1/working/section-2-research.md
test_spec_source: thoughts/projects/2026-02-20-koe-m1/working/section-2-test-spec.md
design_source: thoughts/design/2026-02-20-koe-m1-section-2-api-design.md
---

# Koe M1 Section 2 Implementation Plan

## Overview

Implement Section 2 only: invocation preflight, single-instance lock semantics, X11 focus gate, and pre-record orchestration behavior.
This plan follows the approved Section 2 API design and test spec, and keeps all Section 3+ behavior explicitly out of scope.

## Current State Analysis

- Section 2 modules are still stubs (`src/koe/hotkey.py:1`, `src/koe/window.py:1`, `src/koe/notify.py:1`).
- `run_pipeline` is intentionally deferred (`src/koe/main.py:22`) and cannot satisfy Section 2 acceptance criteria yet.
- Shared vocabulary does not yet include concurrency-specific contracts (`src/koe/types.py:65`, `src/koe/types.py:100`, `src/koe/types.py:102`).
- Exit-code mapping is currently total for Section 1 outcomes only (`src/koe/main.py:27`).
- Type exhaustiveness fixtures from Section 1 are strict and will fail unless type extensions are done atomically (`tests/section1_static_fixtures.py:51`, `tests/section1_static_fixtures.py:68`, `tests/section1_static_fixtures.py:88`).

## Desired End State

Section 2 acceptance criteria from `thoughts/projects/2026-02-20-koe-m1/spec.md:45` through `thoughts/projects/2026-02-20-koe-m1/spec.md:50` are met:

1. Invocation remains one-shot external trigger with no daemon introduced.
2. X11 context and focus checks happen before any Section 3 handoff.
3. No-focus path emits explicit feedback and exits as controlled outcome.
4. Concurrent invocation is blocked by typed lock guard.
5. Already-running path emits explicit typed notification.
6. Startup dependency failures return typed dependency errors and controlled exit.

Verification bundle:

```bash
make lint && make typecheck && make test
```

## Traceability

| Requirement | Source | Test Spec ID | Planned Phase |
|-------------|--------|--------------|---------------|
| AC1: external invocation, no daemon | `thoughts/projects/2026-02-20-koe-m1/spec.md:45` | T-18, T-19, T-21 | Phase 3, Phase 6 |
| AC2: focus checked before recording | `thoughts/projects/2026-02-20-koe-m1/spec.md:46` | T-11, T-13, T-14, T-21 | Phase 3, Phase 5, Phase 6 |
| AC3: no focus -> notify + exit | `thoughts/projects/2026-02-20-koe-m1/spec.md:47` | T-14, T-20 | Phase 3, Phase 6 |
| AC4: single-instance guard blocks second run | `thoughts/projects/2026-02-20-koe-m1/spec.md:48` | T-07, T-08, T-10 | Phase 3, Phase 4 |
| AC5: explicit already-running feedback | `thoughts/projects/2026-02-20-koe-m1/spec.md:49` | T-02, T-04, T-06, T-19 | Phase 1, Phase 2, Phase 6 |
| AC6: startup dependency failures explicit + safe exit | `thoughts/projects/2026-02-20-koe-m1/spec.md:50` | T-11, T-12, T-16, T-18 | Phase 3, Phase 5, Phase 6 |

### Key Discoveries

- Section 2 behavior already has approved API design contract (`thoughts/design/2026-02-20-koe-m1-section-2-api-design.md:6`).
- Test contract is fully specified with 21 obligations and no blocking design gaps (`thoughts/projects/2026-02-20-koe-m1/working/section-2-test-spec.md:254`).
- Section 1 fixtures enforce closed unions and must be updated alongside type additions (`tests/section1_static_fixtures.py:51`, `tests/section1_static_fixtures.py:68`, `tests/section1_static_fixtures.py:88`).
- Current outcome mapping lacks the new Section 2 controlled outcome (`src/koe/main.py:31`).

## What We're NOT Doing

- No Section 3 audio capture behavior, waveform lifecycle, or recording-stop semantics.
- No Section 4 transcription work, Section 5 insertion/clipboard logic, or Section 6 full lifecycle notification catalog.
- No daemon mode, no Wayland work, no broadened milestone scope beyond Section 2.
- No redesign of approved Section 2 API surface; this plan implements the approved contract.

## Implementation Approach

Test-first at section scope:

1. `/test-implementer` writes Section 2 tests/spec fixtures in bounded groups.
2. `/implement-plan` makes each group pass in smallest validated increments.
3. Each implementation phase ends with explicit phase-level validation and full regression gates.

Design references applied from `thoughts/design/2026-02-20-koe-m1-section-2-api-design.md`:

- Required type extensions (`:35-88`)
- `hotkey.py` lock API (`:92-116`)
- `window.py` X11/focus API (`:117-136`)
- `notify.py` non-raising contract (`:137-156`)
- `main.py` stage ordering + mapping (`:157-197`)

## Perspectives Synthesis

**Alignment**

- Treat Section 2 type extension as an atomic change with all closed-union fixture updates.
- Keep leaf modules composable and side-effect boundaries explicit (`hotkey.py`, `window.py`, `notify.py`).
- Enforce `run_pipeline` stage order exactly as design contract before any Section 3 handoff.
- Keep all expected failures typed and user-visible, never silent.

**Divergence (resolved in this plan)**

- Stale-lock recovery depth: plan keeps approved signature and required tests unchanged; implementation may include safe stale-lock handling internally as long as T-07..T-10 contract is preserved.
- Additional orchestration test ideas beyond approved 21 tests are excluded from mandatory scope to keep strict section/test-spec alignment.

**Key perspective contributions**

- DX Advocate: enforce atomic type + fixture update and clear module docstrings to prevent misuse.
- Architecture Purist: preserve strict import direction and thin orchestrator style in `main.py`.
- Validation Strategist: phase by smallest red/green groups with explicit command gates.
- Security Auditor: require safe subprocess invocation patterns and non-raising cleanup boundaries.
- Correctness Guardian: keep total mappings and exhaustiveness guarantees green at every phase boundary.

## Phase Ownership

| Phase | Owner | Responsibility |
|-------|-------|---------------|
| Phase 1, Phase 3 | `/test-implementer` | Write Section 2 tests from approved spec in red-first sequence |
| Phase 2, Phase 4-6 | `/implement-plan` | Implement APIs and orchestration to make existing tests pass |

## Phase 1: Type-Surface Tests and Fixtures (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 2 type-surface proofs`

### Overview

Introduce Section 2 type-surface tests first, including static exhaustiveness fixtures and runtime schema checks for the new concurrency error payload.

### Changes Required

#### 1. Section 2 static type fixtures
**File**: `tests/section2_static_fixtures.py`
**Changes**: add static fixtures for T-01, T-04, T-05, T-06 using `assert_type` / `assert_never` patterns.

```python
from __future__ import annotations

from typing import assert_never

from koe.types import NotificationKind


def t04_notification_kind_includes_already_running(kind: NotificationKind) -> None:
    match kind:
        case "recording_started" | "processing" | "completed":
            return
        case "error_focus" | "error_audio" | "error_transcription":
            return
        case "error_insertion" | "error_dependency" | "already_running":
            return
        case _ as unreachable:
            assert_never(unreachable)
```

#### 2. Runtime schema tests for `AlreadyRunningError`
**File**: `tests/test_types.py`
**Changes**: add T-02 and T-03 using `check_type(...)` and `TypeCheckError` expectations.

```python
def test_already_running_error_accepts_pid_or_none() -> None:
    check_type(
        {
            "category": "already_running",
            "message": "another koe instance is active",
            "lock_file": "/tmp/koe.lock",
            "conflicting_pid": 1234,
        },
        AlreadyRunningError,
    )
```

#### 3. Extend outcome mapping proof
**File**: `tests/test_main.py`
**Changes**: update T-17 mapping table with `("already_running", 1)`.

```python
@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("success", 0),
        ("already_running", 1),
        ("error_unexpected", 2),
    ],
)
def test_outcome_to_exit_code_is_total(outcome: PipelineOutcome, expected: ExitCode) -> None:
    assert outcome_to_exit_code(outcome) == expected
```

### Success Criteria

#### Validation

- [x] T-01, T-04, T-05, T-06 fixtures exist and fail/red until type extensions are implemented.
- [x] T-02 and T-03 runtime schema tests exist and fail/red until type extensions are implemented.
- [x] T-17 includes `("already_running", 1)`.

#### Standard Checks

- [x] `uv run ruff check tests/`
- [x] `uv run pyright` (expected red for missing Section 2 type/runtime symbols)

**Implementation Note**: Proceed once tests are written and expected-red due to missing Section 2 type additions.

---

## Phase 2: Atomic Type Extension + Exit Mapping (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: extend section 2 type contracts and outcome mapping`

### Overview

Implement all Section 2 type and mapping extensions in one atomic change so Pyright closed-union checks remain green.

### Changes Required

#### 1. Extend shared vocabulary
**File**: `src/koe/types.py`
**Changes**: add `InstanceLockHandle`, `AlreadyRunningError`, and extend `NotificationKind`, `KoeError`, `PipelineOutcome`.

```python
InstanceLockHandle = NewType("InstanceLockHandle", Path)


class AlreadyRunningError(TypedDict):
    category: Literal["already_running"]
    message: str
    lock_file: str
    conflicting_pid: int | None
```

#### 2. Keep existing static fixtures exhaustive
**File**: `tests/section1_static_fixtures.py`
**Changes**: add `"already_running"` arms for notification, error-category, and outcome exhaustive matches.

```python
        case "error_insertion" | "error_dependency" | "already_running":
            return
```

#### 3. Update outcome mapping
**File**: `src/koe/main.py`
**Changes**: include `"already_running"` in controlled exit-code 1 path.

```python
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
```

### Success Criteria

#### Validation

- [x] T-01..T-06 and T-17 all pass.
- [x] Existing Section 1 static fixtures remain exhaustive under Pyright.

#### Standard Checks

- [ ] `uv run pyright`
- [x] `uv run pytest tests/test_types.py tests/test_main.py`
- [x] `uv run ruff check src/ tests/`

**Implementation Note**: Proceed only after atomic type/mapping update is fully green.

---

## Phase 3: Runtime Contract Tests for Modules and Orchestration (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 2 runtime contract suite`

### Overview

Write all remaining Section 2 runtime tests before implementation: lock semantics, X11/focus checks, notification non-raising behavior, dependency preflight mapping, and pipeline short-circuit ordering.

### Changes Required

#### 1. Lock contract tests
**File**: `tests/test_hotkey.py`
**Changes**: add T-07, T-08, T-09, T-10 with per-test `tmp_path` lock-path override.

```python
def test_acquire_instance_lock_returns_err_when_already_running(tmp_path: Path) -> None:
    config: KoeConfig = {**DEFAULT_CONFIG, "lock_file_path": tmp_path / "koe.lock"}
    first = acquire_instance_lock(config)
    second = acquire_instance_lock(config)
    assert first["ok"] is True
    assert second["ok"] is False
    assert second["error"]["category"] == "already_running"
```

#### 2. X11/focus boundary tests
**File**: `tests/test_window.py`
**Changes**: add T-11, T-12, T-13, T-14 with patched environment/subprocess probes.

#### 3. Notification contract test
**File**: `tests/test_notify.py`
**Changes**: add T-15 for `"error_dependency"`, `"error_focus"`, `"already_running"` non-raising behavior when backend errors.

#### 4. Main orchestration tests
**File**: `tests/test_main.py`
**Changes**: add T-16, T-18, T-19, T-20, T-21 and replace deferred placeholder test.

```python
def test_run_pipeline_short_circuits_on_lock_contention() -> None:
    with (
        patch("koe.main.dependency_preflight", return_value={"ok": True, "value": None}),
        patch("koe.main.acquire_instance_lock", return_value={"ok": False, "error": already_running_error}),
        patch("koe.main.send_notification") as notify_mock,
        patch("koe.main.check_focused_window") as focus_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "already_running"
    notify_mock.assert_called_once()
    focus_mock.assert_not_called()
```

### Success Criteria

#### Validation

- [x] T-07..T-21 tests exist and are expected-red before implementations.
- [x] Deferred `xfail` placeholder in `tests/test_main.py` is replaced by concrete Section 2 runtime tests.

#### Standard Checks

- [x] `uv run ruff check tests/`
- [x] `uv run pytest tests/test_hotkey.py tests/test_window.py tests/test_notify.py tests/test_main.py` (expected red for missing Section 2 runtime implementations)

**Implementation Note**: Proceed once tests are committed and failing for missing runtime implementations only.

---

## Phase 4: Implement Concurrency Guard API (`hotkey.py`)

**Owner**: `/implement-plan`
**Commit**: `feat: implement section 2 instance lock api`

### Overview

Implement non-blocking single-instance guard API returning typed `Result` values and idempotent release semantics.

### Changes Required

#### 1. Acquire/release lock functions
**File**: `src/koe/hotkey.py`
**Changes**: implement `acquire_instance_lock(config)` and `release_instance_lock(handle)`.

```python
def acquire_instance_lock(config: KoeConfig, /) -> Result[InstanceLockHandle, AlreadyRunningError]:
    lock_file = config["lock_file_path"]
    try:
        with lock_file.open("x", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
    except FileExistsError:
        return {
            "ok": False,
            "error": {
                "category": "already_running",
                "message": "koe is already running",
                "lock_file": str(lock_file),
                "conflicting_pid": _read_lock_pid(lock_file),
            },
        }
    return {"ok": True, "value": InstanceLockHandle(lock_file)}
```

#### 2. File-level docs for module role
**File**: `src/koe/hotkey.py`
**Changes**: replace stub docstring with Section 2 lock-guard ownership explanation.

### Success Criteria

#### Validation

- [x] T-07, T-08, T-09, T-10 pass.
- [x] Acquire path is non-raising and returns typed success/error arms.
- [x] Release path is idempotent and non-raising.

#### Standard Checks

- [x] `uv run pytest tests/test_hotkey.py`
- [ ] `uv run pyright`
- [x] `uv run ruff check src/ tests/`

**Implementation Note**: Proceed after lock guard API is green and isolated tests pass.

---

## Phase 5: Implement X11/Notification/Preflight Boundaries

**Owner**: `/implement-plan`
**Commit**: `feat: implement section 2 preflight focus and notification boundaries`

### Overview

Implement `window.py`, `notify.py`, and `dependency_preflight` in `main.py` so all typed pre-record checks are executable and non-silent.

### Changes Required

#### 1. X11 context and focus lookup
**File**: `src/koe/window.py`
**Changes**: implement `check_x11_context()` and `check_focused_window()` returning typed `Result` values.

```python
def check_x11_context() -> Result[None, DependencyError]:
    display = os.environ.get("DISPLAY")
    if not display:
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": "DISPLAY is not set",
                "missing_tool": "DISPLAY",
            },
        }
    if shutil.which("xdotool") is None:
        return {
            "ok": False,
            "error": {
                "category": "dependency",
                "message": "xdotool is required",
                "missing_tool": "xdotool",
            },
        }
    return {"ok": True, "value": None}
```

#### 2. Notification transport
**File**: `src/koe/notify.py`
**Changes**: implement `send_notification(kind, error=None)` with swallowed backend failures.

#### 3. Startup dependency preflight
**File**: `src/koe/main.py`
**Changes**: implement `dependency_preflight(config)` returning `Result[None, DependencyError]` for required startup checks.

### Success Criteria

#### Validation

- [ ] T-11, T-12, T-13, T-14 pass.
- [ ] T-15 passes and notification backend failures never raise.
- [ ] T-16 passes with all expected dependency permutations.

#### Standard Checks

- [ ] `uv run pytest tests/test_window.py tests/test_notify.py tests/test_main.py -k "dependency_preflight"`
- [ ] `uv run pyright`
- [ ] `uv run ruff check src/ tests/`

**Implementation Note**: Proceed to orchestration only after preflight/focus/notify boundaries are green.

---

## Phase 6: Implement Section 2 Orchestration in `run_pipeline`

**Owner**: `/implement-plan`
**Commit**: `feat: implement section 2 pipeline stage ordering and short-circuit mapping`

### Overview

Implement ordered pre-record orchestration in `run_pipeline` with explicit short-circuit mappings and guaranteed lock release in `finally` after successful acquire.

### Changes Required

#### 1. Stage orchestration
**File**: `src/koe/main.py`
**Changes**: implement Stage 1-4 ordering and outcome/notification mapping per design table.

```python
def run_pipeline(config: KoeConfig, /) -> PipelineOutcome:
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
        x11 = check_x11_context()
        if x11["ok"] is False:
            send_notification("error_dependency", x11["error"])
            return "error_dependency"

        focus = check_focused_window()
        if focus["ok"] is False:
            send_notification("error_focus", focus["error"])
            return "no_focus"

        raise NotImplementedError("Section 3 handoff implemented in later sections")
    finally:
        release_instance_lock(lock_handle)
```

### Success Criteria

#### Validation

- [ ] T-18 passes: preflight failure short-circuits and blocks downstream stages.
- [ ] T-19 passes: already-running short-circuits and blocks focus/audio progression.
- [ ] T-20 passes: focus failure maps to `no_focus` and releases lock exactly once.
- [ ] T-21 passes: stage order is exactly `dependency_preflight -> acquire_instance_lock -> check_x11_context -> check_focused_window -> Section 3 handoff`.

#### Standard Checks

- [ ] `uv run pytest tests/test_main.py`
- [ ] `make lint`
- [ ] `make typecheck`
- [ ] `make test`

**Implementation Note**: Section 2 complete after full suite and gate commands are green.

## Testing Strategy

Test phases come first. Implementation phases only make those tests pass.

### Tests (written by `/test-implementer`)

- `tests/section2_static_fixtures.py`: T-01, T-04, T-05, T-06
- `tests/test_types.py`: T-02, T-03
- `tests/test_hotkey.py`: T-07, T-08, T-09, T-10
- `tests/test_window.py`: T-11, T-12, T-13, T-14
- `tests/test_notify.py`: T-15
- `tests/test_main.py`: T-16, T-17, T-18, T-19, T-20, T-21

### Additional Validation

- `uv run pyright` for static exhaustiveness and narrowing contracts.
- `uv run ruff check src/ tests/` for lint/annotation policy.
- `make lint && make typecheck && make test` as final acceptance gate.

### Manual Testing Steps

None required for Section 2 completion. All success criteria are agent-self-verifiable through tests and static checks.

## Execution Graph

**Phase Dependencies:**

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> Phase 6
```

| Phase | Depends On | Can Parallelize With |
|-------|------------|---------------------|
| 1 | - | - |
| 2 | 1 | - |
| 3 | 2 | - |
| 4 | 3 | 5 (partial, if tests isolated by file) |
| 5 | 3 | 4 (partial, if no overlapping files under active edit) |
| 6 | 4, 5 | - |

**Parallel Execution Notes:**

- `hotkey.py` and `window.py`/`notify.py` can be implemented in parallel only after Phase 3 tests exist and if edits are split cleanly by file.
- `main.py` orchestration (Phase 6) stays sequential because it integrates all prior stage APIs.

## References

- Requirements: `thoughts/projects/2026-02-20-koe-m1/spec.md:39`
- Section 2 research: `thoughts/projects/2026-02-20-koe-m1/working/section-2-research.md:42`
- Section 2 API design: `thoughts/design/2026-02-20-koe-m1-section-2-api-design.md:35`
- Section 2 test spec: `thoughts/projects/2026-02-20-koe-m1/working/section-2-test-spec.md:33`

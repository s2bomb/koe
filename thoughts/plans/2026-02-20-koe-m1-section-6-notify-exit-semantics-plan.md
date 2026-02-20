---
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 6: User Feedback and Error Surfaces"
research_source: thoughts/projects/2026-02-20-koe-m1/working/section-6-research.md
test_spec_source: thoughts/projects/2026-02-20-koe-m1/working/section-6-test-spec.md
design_source: thoughts/design/2026-02-20-section-6-notify-exit-semantics.md
---

# Koe M1 Section 6 Implementation Plan

## Overview

Implement Section 6 only: make notification payload contracts deterministic and exhaustive, strengthen Section 6 test coverage to prove dispatch/ordering/exit semantics, and preserve the non-raising notification transport guarantee.
This plan is strictly bounded to Section 6 acceptance criteria in `thoughts/projects/2026-02-20-koe-m1/spec.md:95` through `thoughts/projects/2026-02-20-koe-m1/spec.md:99`.

## Current State Analysis

- `run_pipeline` already dispatches lifecycle and error notifications at the expected phase transitions (`src/koe/main.py:79`, `src/koe/main.py:92`, `src/koe/main.py:105`, `src/koe/main.py:108`).
- Exit semantics are already total and exhaustive in `outcome_to_exit_code` and exception-mapped in `main` (`src/koe/main.py:21`, `src/koe/main.py:116`).
- Notification transport already swallows backend failures (`src/koe/notify.py:12`, `src/koe/notify.py:22`).
- Section 6 gap is payload correctness and exhaustiveness: `_notification_payload` handles only 3 kinds explicitly and uses `kind.replace("_", " ")` fallback for the remaining 7 (`src/koe/notify.py:26`, `src/koe/notify.py:34`), which violates design matrix requirements (`thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:165`, `thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:190`).
- Current `tests/test_notify.py` only proves swallow behavior for 3 error kinds and does not prove lifecycle payload matrix, error-title matrix, or full 10-kind swallow guarantee (`tests/test_notify.py:14`, `tests/test_notify.py:42`).

## Desired End State

Section 6 acceptance criteria from `thoughts/projects/2026-02-20-koe-m1/spec.md:95` through `thoughts/projects/2026-02-20-koe-m1/spec.md:99` are fully and permanently proven by tests:

1. All lifecycle notifications are user-visible with exact matrix strings.
2. Error notifications are subsystem-specific and preserve `error["message"]` when present.
3. `run_pipeline` notification dispatch semantics and ordering invariants are explicitly tested.
4. Notification transport remains non-raising for all 10 `NotificationKind` values.
5. Exit mapping and exception-to-exit behavior remain deterministic and exhaustive.

Verification bundle:

```bash
make lint && make typecheck && make test
```

## Traceability

| Requirement | Source | Test Spec ID | Planned Phase |
|-------------|--------|--------------|---------------|
| AC1 lifecycle states visible | `thoughts/projects/2026-02-20-koe-m1/spec.md:95` | T6N-01, T6M-03g, T6M-03h, T6M-03i, T6M-05 | Phase 2, Phase 3, Phase 4 |
| AC2 notifications map to clear phases | `thoughts/projects/2026-02-20-koe-m1/spec.md:96` | T6M-03a..T6M-03i, T6M-04a, T6M-04b, T6M-05 | Phase 3, Phase 4 |
| AC3 subsystem-specific error notifications with context | `thoughts/projects/2026-02-20-koe-m1/spec.md:97` | T6N-02, T6N-03, T6N-04, T6M-03a..T6M-03f | Phase 2, Phase 3, Phase 4 |
| AC4 notification emission failures never crash runtime | `thoughts/projects/2026-02-20-koe-m1/spec.md:99` | T6N-05 | Phase 2, Phase 4 |
| Deterministic exit semantics | `thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:224` | T6M-01, T6M-02 | Phase 3 |

### Key Discoveries

- The design document provides a fully specified payload matrix and dispatch matrix; no API redesign is required (`thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:160`, `thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:194`).
- `notify.py` implementation currently deviates from matrix invariants I2-I4, specifically for `error_audio`, `error_transcription`, `error_insertion`, and lifecycle wording (`thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:279`, `src/koe/notify.py:34`).
- `main.py` dispatch shape mostly satisfies Section 6 design and should be defended by expanded tests rather than broad refactor (`src/koe/main.py:56`, `tests/test_main.py:538`).
- Section 6 static fixture file is missing and should be added to lock callable API surfaces (`thoughts/projects/2026-02-20-koe-m1/working/section-6-test-spec.md:217`).

## What We're NOT Doing

- No changes to Section 3/4/5 internals (`audio.py`, `transcribe.py`, `insert.py`) beyond Section 6 dispatch assertions.
- No new notification backend (no D-Bus/Wayland transport).
- No logging/metrics/tracing substrate introduction in M1.
- No changes to `NotificationKind`, `KoeError`, `PipelineOutcome`, or `ExitCode` type definitions.
- No UX redesign of desktop rendering beyond exact title/message contract strings.

## Implementation Approach

Test-first delivery with strict section scope:

1. `/test-implementer` lands Section 6 static fixture + test contract coverage from the approved test spec.
2. `/implement-plan` updates `notify.py` payload logic to exact design matrix values with exhaustive matching.
3. `/implement-plan` validates full suite and ensures no regressions in existing pipeline semantics.

Design references applied directly:

- Notification API contracts and non-raising behavior (`thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:90` through `thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:124`).
- Notification payload matrix and invariants (`thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:160` through `thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:191`).
- Dispatch matrix and ordering invariants (`thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:194` through `thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:219`).
- Outcome-to-exit semantics (`thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:224` through `thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:259`).

## Perspectives Synthesis

**Alignment**

- Keep Section 6 changes concentrated in `src/koe/notify.py`, `tests/test_notify.py`, `tests/test_main.py`, and `tests/section6_static_fixtures.py`.
- Treat dispatch semantics in `main.py` as stable; add/adjust tests to prove guarantees already described by design.
- Use exhaustive match + `assert_never` in `_notification_payload` to make future `NotificationKind` drift a type-time failure.
- Expand non-raising guarantee coverage to all 10 notification kinds.

**Divergence (resolved in this plan)**

- Whether to refactor `main.py` notification dispatch for style consistency: resolved to no broad orchestration refactor because current behavior already aligns with Section 6 contracts and risk is unnecessary.
- Whether to widen Section 6 into broader observability work: resolved to no; M1 observability remains desktop notifications only per approved design.

**Key perspective contributions**

- DX Advocate: exact static payload strings prevent confusing user-facing wording drift.
- Architecture Purist: exhaustive matching in payload function removes fragile fallback behavior.
- Validation Strategist: explicit matrix-driven parametrized tests become the primary proof artifact.
- Security Auditor: preserve subprocess list-arg invocation and non-raising boundary.
- Correctness Guardian: keep total/exhaustive mappings with `assert_never` and literal unions.

## Phase Ownership

| Phase | Owner | Responsibility |
|-------|-------|---------------|
| Phase 1-3 | `/test-implementer` | Add Section 6 static + runtime contract tests |
| Phase 4-5 | `/implement-plan` | Implement payload behavior and pass all Section 6 proofs |

## Phase 1: Section 6 Static Contract Fixtures (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 6 static contract fixtures`

### Overview

Create compile-time fixture coverage for Section 6 callable API stability.

### Changes Required

#### 1. Add static fixture file
**File**: `tests/section6_static_fixtures.py` (new)
**Changes**:
- add callable signature fixture for `send_notification`
- add callable signature fixture for `outcome_to_exit_code`
- avoid duplicating `NotificationKind` exhaustive fixture already covered in `tests/section1_static_fixtures.py`

```python
from collections.abc import Callable

from koe.main import outcome_to_exit_code
from koe.notify import send_notification
from koe.types import ExitCode, NotificationKind, PipelineOutcome

send_sig: Callable[[NotificationKind], None] = send_notification
exit_sig: Callable[[PipelineOutcome], ExitCode] = outcome_to_exit_code
```

### Success Criteria

#### Validation (required)

- [x] `tests/section6_static_fixtures.py` exists and is typechecked.
- [x] T6SF-01 and T6SF-02 contracts are represented exactly.

#### Standard Checks

- [x] `uv run ruff check tests/section6_static_fixtures.py`
- [x] `uv run pyright`

**Implementation Note**: Proceed when any red state is attributable only to not-yet-implemented runtime payload behavior.

---

## Phase 2: Notification Payload and Transport Tests (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 6 notification payload matrix tests`

### Overview

Expand `tests/test_notify.py` to fully encode T6N-01..T6N-05 matrix obligations.

### Changes Required

#### 1. Add lifecycle payload matrix tests
**File**: `tests/test_notify.py`
**Changes**:
- add parametrized assertions for exact title/message values for 4 lifecycle kinds (T6N-01)

#### 2. Add error payload matrix tests
**File**: `tests/test_notify.py`
**Changes**:
- add parametrized assertions for 6 error kinds preserving `error["message"]` (T6N-02)
- add exact subsystem-title assertions for 6 error kinds (T6N-03)
- add fallback matrix assertions when `error is None` (T6N-04)

#### 3. Extend swallow guarantee coverage to all 10 kinds
**File**: `tests/test_notify.py`
**Changes**:
- extend backend-failure swallow test from 3 kinds to all 10 `NotificationKind` values (T6N-05)

```python
@pytest.mark.parametrize(
    ("kind", "title", "message"),
    [
        ("recording_started", "Koe", "Recording..."),
        ("processing", "Koe", "Processing..."),
        ("completed", "Koe", "Transcription complete"),
        ("no_speech", "Koe", "No speech detected"),
    ],
)
def test_lifecycle_payload_matrix(kind: NotificationKind, title: str, message: str) -> None: ...
```

### Success Criteria

#### Validation (required)

- [x] T6N-01..T6N-05 are present and fail red against current `notify.py` fallback behavior.
- [x] Tests assert only observable contract outputs (`notify-send` args and non-raising behavior).

#### Standard Checks

- [x] `uv run ruff check tests/test_notify.py`
- [x] `uv run pytest tests/test_notify.py` (expected red pre-implementation)

**Implementation Note**: Keep matrix strings exactly aligned to design doc, including punctuation and capitalization.

---

## Phase 3: Pipeline Dispatch/Ordering and Exit-Semantics Tests (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 6 pipeline dispatch and ordering proofs`

### Overview

Add missing Section 6 proofs in `tests/test_main.py` while preserving existing passing coverage.

### Changes Required

#### 1. Add/adjust dispatch matrix branch tests
**File**: `tests/test_main.py`
**Changes**:
- ensure explicit error payload assertions exist for all error branches, including audio path (T6M-03d)
- ensure both no-speech branches are explicitly asserted (T6M-03g, T6M-03h)

#### 2. Add recording-before-capture ordering test
**File**: `tests/test_main.py`
**Changes**:
- add events-list ordering assertion for `recording_started` before `capture_audio` (T6M-04a)

#### 3. Tighten success sequence exactness
**File**: `tests/test_main.py`
**Changes**:
- assert exact success sequence `['recording_started', 'processing', 'completed']` (T6M-05)
- reuse existing T6M-01/T6M-02 coverage as-is

```python
kinds = [call.args[0] for call in notify_mock.call_args_list]
assert kinds == ["recording_started", "processing", "completed"]
```

### Success Criteria

#### Validation (required)

- [x] T6M-03a..T6M-03i, T6M-04a, T6M-04b, and T6M-05 are all represented and scoped to Section 6 behavior.
- [x] Existing total exit mapping and exception exit tests remain green and unweakened.

#### Standard Checks

- [x] `uv run ruff check tests/test_main.py`
- [x] `uv run pytest tests/test_main.py` (expected mixed red until Phase 4)

**Implementation Note**: Avoid over-asserting unrelated orchestration details; keep assertions scoped to notification dispatch and exit semantics.

---

## Phase 4: Implement Deterministic Notification Payload Matrix (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: implement section 6 notification payload matrix`

### Overview

Update `src/koe/notify.py` to satisfy Section 6 payload contracts and make T6N tests pass.

### Changes Required

#### 1. Replace fallback-based payload logic with exhaustive match
**File**: `src/koe/notify.py`
**Changes**:
- implement explicit branch for all 10 `NotificationKind` values
- preserve `_error_message` helper usage for all 6 error kinds
- return exact design-matrix title/message strings
- add `assert_never` wildcard branch for completeness checks

```python
def _notification_payload(kind: NotificationKind, error: KoeError | None) -> tuple[str, str]:
    match kind:
        case "recording_started":
            return ("Koe", "Recording...")
        case "processing":
            return ("Koe", "Processing...")
        # ... all remaining lifecycle and error kinds ...
        case _ as unreachable:
            assert_never(unreachable)
```

#### 2. Preserve transport non-raising boundary
**File**: `src/koe/notify.py`
**Changes**:
- keep subprocess invocation shape unchanged (`check=False`, `capture_output=True`, `text=True`)
- keep `except Exception: return` contract intact

### Success Criteria

#### Validation (required)

- [x] T6N-01..T6N-05 pass with exact matrix values.
- [x] `send_notification` remains non-raising across all simulated backend failures.
- [x] Payload function is exhaustive and type-safe under Pyright.

#### Standard Checks

- [x] `uv run pytest tests/test_notify.py`
- [x] `uv run pyright`
- [x] `uv run ruff check src/koe/notify.py tests/test_notify.py`

**Implementation Note**: Do not alter `NotificationKind` or `KoeError` types in Section 6.

---

## Phase 5: Section 6 Regression Gate (Green)

**Owner**: `/implement-plan`
**Commit**: `test: validate section 6 notification and exit semantics`

### Overview

Run focused and full project gates to confirm Section 6 completion and non-regression.

### Changes Required

#### 1. Execute Section 6 targeted validation
**Files**: none (validation phase)
**Changes**:

```bash
uv run pytest tests/test_notify.py tests/test_main.py
uv run pyright
uv run ruff check src/koe/notify.py src/koe/main.py tests/test_notify.py tests/test_main.py tests/section6_static_fixtures.py
```

#### 2. Execute full baseline gates
**Files**: none (validation phase)
**Changes**:

```bash
make lint && make typecheck && make test
```

### Success Criteria

#### Validation (required)

- [ ] All Section 6 tests from `section-6-test-spec.md` pass (T6N, T6M, T6SF groups).
- [ ] Full lint/typecheck/test gates pass with no regressions.

#### Standard Checks

- [ ] `make lint`
- [ ] `make typecheck`
- [ ] `make test`

**Implementation Note**: If non-Section-6 failures appear, apply minimal compatibility fixes without widening scope.

## Testing Strategy

Test phases land first. Implementation phases make those tests pass.

### Tests (written by `/test-implementer`)

- `tests/section6_static_fixtures.py` for callable contract stability (T6SF-01, T6SF-02).
- `tests/test_notify.py` for payload matrix + fallback + non-raising transport (T6N-01..T6N-05).
- `tests/test_main.py` additions/adjustments for dispatch matrix and ordering invariants (T6M-03..T6M-05).

### Additional Validation (implementation phases)

- `pyright` to enforce exhaustive matches and callable compatibility.
- `ruff` to enforce module hygiene.
- full pytest and make gates for regression confidence.

### Manual Testing Steps

1. Run `make run` in an X11 session and trigger a successful path; verify user sees recording, processing, completed notifications in order.
2. Trigger an error path (for example missing dependency in test environment) and verify subsystem-labeled notification title.

Reason manual verification is required: desktop notification compositor behavior cannot be fully proven via unit mocks even when subprocess arguments are correct.

## Execution Graph

**Phase Dependencies:**

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5
```

| Phase | Depends On | Can Parallelize With |
|-------|------------|---------------------|
| 1 | - | - |
| 2 | 1 | - |
| 3 | 1 | 2 (partial: different test files, both red before implementation) |
| 4 | 2, 3 | - |
| 5 | 4 | - |

**Parallel Execution Notes**

- Phase 2 and Phase 3 can run in parallel after Phase 1 because they modify different test surfaces.
- Phase 4 remains single-threaded to avoid coupling payload implementation with unrelated orchestration edits.
- Keep one validated commit per phase for clear rollback and review boundaries.

## References

- Section 6 requirements: `thoughts/projects/2026-02-20-koe-m1/spec.md:89`
- Section 6 research: `thoughts/projects/2026-02-20-koe-m1/working/section-6-research.md:36`
- Section 6 test specification: `thoughts/projects/2026-02-20-koe-m1/working/section-6-test-spec.md:51`
- Section 6 design: `thoughts/design/2026-02-20-section-6-notify-exit-semantics.md:160`
- Source brief notification context: `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:183`

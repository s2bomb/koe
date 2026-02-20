---
title: "Section 2 Invocation, Focus Gate, and Concurrency Guard Test Specification"
date: 2026-02-20
status: approved
design_source: "thoughts/design/2026-02-20-koe-m1-section-2-api-design.md"
spec_source: "thoughts/projects/2026-02-20-koe-m1/spec.md"
research_source: "thoughts/projects/2026-02-20-koe-m1/working/section-2-research.md"
project_section: "Section 2: Invocation, Focus Gate, and Concurrency Guard"
---

# Test Specification: Section 2 Invocation, Focus Gate, and Concurrency Guard

## Purpose

This document defines proof obligations for the Section 2 API surface only: invocation preflight, single-instance lock semantics, X11 focus gate, and orchestration error mapping before any Section 3 audio call. Each test maps to a specific design contract and includes explicit error-path proof.

## Test Infrastructure

**Framework**: `pytest` + `typeguard` runtime checks, plus Pyright static checks.
**Test location**: root `tests/` directory with `test_<module>.py` convention (`tests/test_main.py`, `tests/test_types.py`, `tests/test_config.py`).
**Patterns to follow**:
- Runtime shape validation with `check_type(...)` / `pytest.raises(TypeCheckError)` (`tests/test_types.py:29`, `tests/test_types.py:33`).
- Parametrized total-mapping tests for literal unions (`tests/test_main.py:32`).
- `unittest.mock.patch` stacked context managers for orchestration boundaries (`tests/test_main.py:14`).
- Deferred runtime-contract marker via `@pytest.mark.xfail(strict=True)` where implementation is intentionally pending (`tests/test_main.py:24`).
**Utilities available**: no shared `conftest.py`; tests should be self-contained.
**Run command**: `uv run pytest tests/` (with `uv run pyright` and `uv run ruff check src/ tests/` gates).

## API Surface

Contracts under test, extracted from the design doc:

| Contract | Signature / Type | Design Reference | Tests |
|----------|-------------------|------------------|-------|
| `InstanceLockHandle` | `NewType("InstanceLockHandle", Path)` | `...section-2-api-design.md:44` | T-01 |
| `AlreadyRunningError` | `TypedDict{category:"already_running", message:str, lock_file:str, conflicting_pid:int\|None}` | `...section-2-api-design.md:47-52` | T-02, T-03 |
| `NotificationKind` extension | includes literal `"already_running"` | `...section-2-api-design.md:54-64` | T-04 |
| `KoeError` extension | includes `AlreadyRunningError` arm | `...section-2-api-design.md:67-74` | T-05 |
| `PipelineOutcome` extension | includes `"already_running"` | `...section-2-api-design.md:77-87` | T-06, T-17 |
| `acquire_instance_lock` | `(config) -> Result[InstanceLockHandle, AlreadyRunningError]` | `...section-2-api-design.md:101-107` | T-07, T-08, T-09 |
| `release_instance_lock` | `(handle) -> None` idempotent, non-raising | `...section-2-api-design.md:109-110` | T-10 |
| `check_x11_context` | `() -> Result[None, DependencyError]` | `...section-2-api-design.md:125-127` | T-11, T-12 |
| `check_focused_window` | `() -> Result[FocusedWindow, FocusError]` | `...section-2-api-design.md:129-131` | T-13, T-14 |
| `send_notification` | `(kind, error=None) -> None`, best-effort non-raising | `...section-2-api-design.md:145-149` | T-15 |
| `dependency_preflight` | `(config) -> Result[None, DependencyError]` | `...section-2-api-design.md:166-168` | T-16 |
| `run_pipeline` ordering | pre-record stages 1-4 must pass before Section 3 | `...section-2-api-design.md:170-178`, `:185-188` | T-18, T-19, T-20, T-21 |
| `outcome_to_exit_code` | `("already_running" included) -> ExitCode` | `...section-2-api-design.md:181-183`, `:189-197` | T-17 |

## Proof Obligations

### `types.py` Section 2 extensions

#### T-01: `InstanceLockHandle` remains an opaque lock-ownership token

**Contract**: `InstanceLockHandle` is not interchangeable with bare `Path` at type boundary.
**Setup**: Pyright static fixture with positive wrapped assignment and negative bare `Path` assignment.
**Expected**: Wrapped value type-checks; bare `Path` to `InstanceLockHandle` fails.
**Discriminating power**: Catches accidental alias weakening that lets any path be released as a lock handle.
**Contract invariant**: Release accepts only ownership tokens returned by acquire.

#### T-02: `AlreadyRunningError` accepts full required schema including optional PID

**Contract**: Error payload requires `category`, `message`, `lock_file`, and `conflicting_pid` (`int | None`).
**Setup**: `check_type(...)` for one value with PID and one with `None` PID.
**Expected**: Both valid variants are accepted.
**Discriminating power**: Catches over-tightening of `conflicting_pid` to required `int` only.
**Contract invariant**: Lock conflict diagnostics remain structured and typed.

#### T-03: `AlreadyRunningError` rejects incomplete or wrong-category payloads

**Contract**: Category literal is fixed and all required fields must be present.
**Setup**: `check_type(...)` wrapped by `pytest.raises(TypeCheckError)` for missing `lock_file` and wrong `category` value.
**Expected**: Invalid payloads are rejected.
**Discriminating power**: Catches silent widening to generic dependency/focus-style errors.
**Contract invariant**: Concurrency guard errors are distinguishable from other failures.

#### T-04: `NotificationKind` includes Section 2 literal `"already_running"`

**Contract**: Notification vocabulary is closed and includes the new literal.
**Setup**: Pyright literal assignment checks for `"already_running"` and one invalid literal.
**Expected**: `"already_running"` passes; unknown literal fails.
**Discriminating power**: Catches omission of required explicit feedback channel for AC5.
**Contract invariant**: Orchestrator can emit typed already-running notification.

#### T-05: `KoeError` narrows correctly for the `already_running` category

**Contract**: `KoeError` union includes `AlreadyRunningError` and supports category narrowing.
**Setup**: Pyright `match error["category"]` fixture with `already_running` branch accessing `lock_file` and `conflicting_pid`.
**Expected**: Branch-specific fields type-check only in correct branch.
**Discriminating power**: Catches failure to include new error arm in shared union.
**Contract invariant**: Downstream error handling remains exhaustive and typed.

#### T-06: `PipelineOutcome` includes `"already_running"` and remains closed

**Contract**: Outcome literal set contains the Section 2 concurrency outcome.
**Setup**: Pyright assignment check with `"already_running"` and one invalid literal.
**Expected**: New literal accepted; unknown outcome rejected.
**Discriminating power**: Catches missing outcome vocabulary update.
**Contract invariant**: Concurrency block exits through explicit controlled outcome.

### `hotkey.py` contracts

#### T-07: `acquire_instance_lock` returns success handle on first acquire

**Contract**: Acquire is non-blocking and returns `Ok[InstanceLockHandle]` on success.
**Setup**: Use temporary lock path via config override; ensure lock does not exist before call.
**Expected**: Result is `ok=True` with `InstanceLockHandle`; no exception.
**Discriminating power**: Catches implementations that return bare `Path`, block indefinitely, or throw on success path.
**Contract invariant**: Successful invocation receives an ownership token.

#### T-08: second acquire returns typed `Err[AlreadyRunningError]` without progressing

**Contract**: Concurrent invocation fails atomically with `AlreadyRunningError` payload.
**Setup**: First acquire retains handle; second call with same lock path.
**Expected**: Second call returns `ok=False`, `category="already_running"`, includes `lock_file`, and `conflicting_pid` (`int|None`).
**Discriminating power**: Catches implementations that allow double-run or emit untyped generic errors.
**Contract invariant**: Single-instance guard blocks concurrent pipelines.

#### T-09: unusable lock path returns typed already-running style error (no raise)

**Contract**: Acquire failure due to lock path unusable is represented by `Err[AlreadyRunningError]` per API signature.
**Setup**: Config override points lock file under non-creatable location in isolated test sandbox.
**Expected**: Function returns `Err` typed payload and does not raise.
**Discriminating power**: Catches crash-on-I/O implementations that violate Result contract.
**Contract invariant**: Acquire path always communicates failure via typed error arm.

#### T-10: `release_instance_lock` is idempotent and non-raising

**Contract**: Release is best-effort and safe to call multiple times.
**Setup**: Acquire once, call release twice; additionally call release on already-removed path scenario.
**Expected**: No exception raised; second release is a no-op from caller perspective.
**Discriminating power**: Catches release implementations that raise on missing lock file.
**Contract invariant**: Cleanup cannot change pipeline outcome via release failure.

### `window.py` contracts

#### T-11: `check_x11_context` returns `Ok[None]` when DISPLAY and required tools are available

**Contract**: X11 preconditions are validated before focus lookup.
**Setup**: Patch environment/tool probes to simulate valid DISPLAY and tool availability.
**Expected**: `ok=True` with `value is None`.
**Discriminating power**: Catches implementations that skip checks or return untyped success payload.
**Contract invariant**: Context check is explicit and typed.

#### T-12: `check_x11_context` returns `Err[DependencyError]` on missing DISPLAY/tool

**Contract**: Context dependency failures are typed dependency errors.
**Setup**: Parameterized missing DISPLAY, missing `xdotool`, and other required tool failures.
**Expected**: `ok=False` with `DependencyError` shape and meaningful `missing_tool` field.
**Discriminating power**: Catches silent false-success or wrong error category.
**Contract invariant**: Dependency faults are surfaced prior to focus/audio work.

#### T-13: `check_focused_window` returns typed focused-window metadata on success

**Contract**: Focus lookup success yields `Ok[FocusedWindow]` with complete schema.
**Setup**: Patch X11 command interaction to return deterministic window id/title.
**Expected**: `ok=True` and `value` satisfies `FocusedWindow` (`window_id`, `title`).
**Discriminating power**: Catches partial metadata or weakly typed dict returns.
**Contract invariant**: Success path provides full focus context for later insertion stages.

#### T-14: `check_focused_window` returns `Err[FocusError]` when no focus is available

**Contract**: Missing focus path is explicit typed focus error.
**Setup**: Patch command results to represent no focused window / lookup failure.
**Expected**: `ok=False` with `FocusError` payload (category `focus`).
**Discriminating power**: Catches `None` returns or dependency-category mislabeling on focus failure.
**Contract invariant**: No-focus is never a silent or ambiguous state.

### `notify.py` contract

#### T-15: `send_notification` swallows emission failures for Section 2 kinds

**Contract**: Notification transport failure never raises into orchestration.
**Setup**: Patch notification backend call to raise for `"error_dependency"`, `"error_focus"`, and `"already_running"` invocations.
**Expected**: `send_notification(...)` returns `None` without exception in each case.
**Discriminating power**: Catches propagation of notification backend failures that would crash pipeline.
**Contract invariant**: Notification channel is best-effort only.

### `main.py` Section 2 contracts

#### T-16: `dependency_preflight` maps startup dependency checks to typed dependency errors

**Contract**: Required startup dependencies (`xdotool`, `xclip`, `notify-send`, CUDA policy) produce `Result[None, DependencyError]`.
**Setup**: Parametrized environment/tool availability permutations with patched probes.
**Expected**: all-present -> `Ok[None]`; any required dependency missing -> `Err[DependencyError]` with identifying field.
**Discriminating power**: Catches partial preflight checks and exception-based failure leakage.
**Contract invariant**: Startup dependency gate is deterministic and typed.

#### T-17: `outcome_to_exit_code` maps `"already_running"` to controlled exit code 1

**Contract**: Mapping table remains total and includes Section 2 outcome extension.
**Setup**: Extend existing parametrized mapping test with `("already_running", 1)`.
**Expected**: All outcomes map as specified; no missing branch.
**Discriminating power**: Catches omission or accidental mapping to exit 2.
**Contract invariant**: Controlled, expected failures exit with code 1.

#### T-18: `run_pipeline` short-circuits on preflight dependency error with explicit notification

**Contract**: `Err[DependencyError]` from preflight maps to notification `"error_dependency"` and outcome `"error_dependency"`.
**Setup**: Patch `dependency_preflight` -> `Err`; patch downstream stage functions (`acquire_instance_lock`, `check_x11_context`, `check_focused_window`) as spies; patch `send_notification`.
**Expected**: returns `"error_dependency"`; sends `"error_dependency"`; does not call lock/focus/audio stages.
**Discriminating power**: Catches continued progression after known-precondition failure.
**Contract invariant**: No Section 3 call before Section 2 preconditions succeed.

#### T-19: `run_pipeline` short-circuits on lock contention with `already_running` mapping

**Contract**: `Err[AlreadyRunningError]` maps to notification `"already_running"`, outcome `"already_running"`, and no focus/audio progression.
**Setup**: Patch preflight -> `Ok`; patch `acquire_instance_lock` -> `Err[AlreadyRunningError]`; patch focus/audio stage functions as spies.
**Expected**: returns `"already_running"`; notification kind is `"already_running"`; focus/audio stages are not invoked.
**Discriminating power**: Catches implementations that continue into focus checks after lock failure.
**Contract invariant**: Second invocation never progresses to focus/audio stages.

#### T-20: `run_pipeline` maps focus failure to `no_focus` and always releases acquired lock

**Contract**: After successful acquire, focus error path notifies `"error_focus"`, returns `"no_focus"`, and releases lock in `finally`.
**Setup**: Patch preflight/acquire/context -> `Ok`; patch `check_focused_window` -> `Err[FocusError]`; patch `release_instance_lock` spy.
**Expected**: outcome `"no_focus"`; notification `"error_focus"`; `release_instance_lock` called exactly once with acquired handle.
**Discriminating power**: Catches missing finally-release or incorrect error mapping on focus failure.
**Contract invariant**: Lock cleanup is guaranteed on all exits after successful acquire.

#### T-21: `run_pipeline` enforces stage ordering before Section 3 handoff

**Contract**: Call order is `dependency_preflight` -> `acquire_instance_lock` -> `check_x11_context` -> `check_focused_window` -> Section 3 handoff.
**Setup**: Instrument stage calls with ordered spy/side-effect log under all-`Ok` preconditions.
**Expected**: observed order matches contract exactly; no Section 3 call occurs before all preconditions are `Ok`.
**Discriminating power**: Catches reordered pipelines that record audio before focus/context validation.
**Contract invariant**: Focus gate occurs before any recording/transcription stage.

## Requirement Traceability

| Requirement | Source | Proved By Contract | Proved By Tests |
|-------------|--------|--------------------|-----------------|
| AC1: invocation remains one-shot external trigger, no in-process daemon | `spec.md:45` | `run_pipeline` stage contract and short-circuit behavior | T-18, T-19, T-21 |
| AC2: focus checked before audio capture | `spec.md:46` | `check_focused_window` + `run_pipeline` ordering contract | T-13, T-14, T-21 |
| AC3: no focus -> notify + exit without recording | `spec.md:47` | focus error mapping table (`error_focus` -> `no_focus`) | T-14, T-20 |
| AC4: single-instance guard blocks concurrent run | `spec.md:48` | `acquire_instance_lock` atomic/non-blocking contract | T-07, T-08 |
| AC5: blocked guard gives explicit already-running feedback | `spec.md:49` | `AlreadyRunningError`, notification literal, `run_pipeline` mapping | T-02, T-04, T-19 |
| AC6: startup dependency failures explicit + safe exit | `spec.md:50` | `dependency_preflight` + `check_x11_context` error contracts | T-11, T-12, T-16, T-18 |

## What Is NOT Tested (and Why)

- Section 3+ internals (audio recording, transcription output quality, insertion strategy): out of Section 2 API surface.
- Notification copy/content wording: not part of typed API contract; only kind/error-path emission is asserted.
- OS-specific lock primitive implementation details (fcntl/flock internals): internal mechanism is not contract; observable atomic behavior is.

## Test Execution Order

1. Type-surface extensions and static exhaustiveness (`T-01` to `T-06`) via `uv run pyright`.
2. Module boundary unit contracts (`T-07` to `T-16`) via `uv run pytest tests/`.
3. Orchestration/error-mapping and ordering (`T-17` to `T-21`) via `uv run pytest tests/`.

If group 1 fails, groups 2-3 are not trusted.

## Design Gaps

- No blocking design gaps for Section 2 testability were found in the current API design.
- Non-blocking precision note: `acquire_instance_lock` uses `AlreadyRunningError` for both active-conflict and unusable-lock-path cases; tests therefore assert typed failure shape rather than differentiating category subtypes.

Test specification complete.

**Location**: `thoughts/projects/2026-02-20-koe-m1/working/section-2-test-spec.md`
**Summary**: 21 tests across 14 API contracts
**Design gaps**: none blocking

Ready for planner.

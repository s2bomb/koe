---
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 8: Omarchy Hotkey Trigger and Per-Run Usage Logging Validation (Wayland)"
research_source: thoughts/projects/2026-02-20-koe-m1/working/section-8-research.md
test_spec_source: thoughts/projects/2026-02-20-koe-m1/working/section-8-test-spec.md
design_source: thoughts/design/2026-02-20-koe-m1-section-8-api-design.md
---

# Koe M1 Section 8 Implementation Plan

## Overview

Implement Section 8 only: add a per-invocation usage-log contract and `main()` logging boundary so every run attempt writes exactly one record, then wire Omarchy hotkey binding validation for one-activation-to-one-run semantics.

This plan stays strictly inside Section 8 (`thoughts/projects/2026-02-20-koe-m1/spec.md:152`) and does not implement Section 9 Wayland focus/insert backend behavior (`thoughts/projects/2026-02-20-koe-m1/spec.md:174`).

## Current State Analysis

- `main()` is single-shot and exits by mapped `PipelineOutcome`, but does not write any usage record (`src/koe/main.py:21`).
- `run_pipeline()` already produces one terminal outcome per invocation and handles `already_running` distinctly (`src/koe/main.py:56`, `src/koe/types.py:136`).
- Lock contention semantics are already typed and tested (`src/koe/hotkey.py:39`, `tests/test_hotkey.py:21`).
- No usage logging module, type, or config path exists (`src/koe/types.py:1`, `src/koe/config.py:9`).
- No active Omarchy user binding launches `koe`; existing dictation binding targets `voxtype` (`/home/brad/.config/hypr/bindings.conf:1`, `/home/brad/.local/share/omarchy/default/hypr/bindings/utilities.conf:55`).

## Desired End State

After Section 8:

1. Every `main()` invocation writes exactly one JSONL record with `run_id`, `invoked_at`, `outcome`, `duration_ms` before `sys.exit`.
2. Unexpected exceptions are coerced to `outcome="error_unexpected"`, logged once, then exited as code `2`.
3. `run_pipeline()` does not write usage records directly (logging boundary remains `main()`).
4. Omarchy binding contract is configured and validated for one key activation -> one `koe` process launch intent.
5. Manual Omarchy runtime check confirms one activation increments usage log by exactly one line.

Verification target:

```bash
make lint && make typecheck && make test
```

Plus Section 8 manual checks M-01/M-02 from the test spec (`thoughts/projects/2026-02-20-koe-m1/working/section-8-test-spec.md:232`).

## Traceability

| Requirement | Test Spec ID | Planned Phase |
|-------------|--------------|---------------|
| AC1 Omarchy trigger path without X11 hotkey daemon (`spec.md:163`) | C7, M-01, M-02 | Phase 5 |
| AC2 One activation -> one usage record (`spec.md:164`) | T-04, T-05, T-08, T-09, M-02 | Phases 1-4, 5 |
| AC3 Blocked attempts logged distinctly (`spec.md:165`) | T-02, T-06, T-09, M-02 | Existing + Phases 1, 3-5 |
| AC4 Missing deps/config still logged (`spec.md:166`) | T-06, T-09, T-10, T-12, M-02 | Phases 1, 3-5 |
| AC5 Automated + manual validation path (`spec.md:167`) | T-01..T-12, M-01, M-02 | Phases 1-5 |

### Key Discoveries

- Section 8 design already defines exact surfaces and event ordering; no new API design pass is required (`thoughts/design/2026-02-20-koe-m1-section-8-api-design.md:19`, `thoughts/design/2026-02-20-koe-m1-section-8-api-design.md:119`).
- Existing `test_main_maps_unexpected_exception_to_exit_2` will need updating when `main()` starts writing logs (`tests/test_main.py:19`).
- Current Section 8 C1/C2 contracts are already implemented in `hotkey.py`; plan focuses on logging surfaces and Omarchy validation deltas (`tests/test_hotkey.py:13`).
- Hyprland config sources Omarchy defaults first, then user overrides; user binding file is correct place for Section 8 bind (`/home/brad/.config/hypr/hyprland.conf:4`, `/home/brad/.config/hypr/hyprland.conf:18`).

## What We're NOT Doing

- No Section 9 Wayland-native focus detection or insertion backend (`spec.md:174`).
- No daemon/background listener redesign; process model remains single-shot (`spec.md:155`, `AGENTS.md:13`).
- No analytics dashboard or remote telemetry export (`spec.md:170`).
- No changes to lock semantics beyond existing tested behavior in `hotkey.py`.

## Implementation Approach

Follow the approved Section 8 design exactly:

- Surface A: keep `hotkey.py` lock API unchanged and add Omarchy binding contract (`design.md:23`, `design.md:37`).
- Surface B: add `UsageLogRecord` + `usage_log_path` + `usage_log.py` writer (`design.md:51`, `design.md:66`, `design.md:80`).
- Surface C: make `main()` the only logging boundary with strict event ordering (`design.md:113`, `design.md:121`).

The test spec is authoritative for proof obligations and phase-level validation (`thoughts/projects/2026-02-20-koe-m1/working/section-8-test-spec.md:49`).

## Perspectives Synthesis

**Alignment**

- Keep logging ownership in `main()` only; never in `run_pipeline()`.
- Add a dedicated `usage_log.py` concern rather than overloading `main.py`/`notify.py`.
- Preserve existing lock/outcome contracts and reuse current typed `PipelineOutcome` literals.
- Use event-ordering tests in `tests/test_main.py` to prove `write_usage_log_record` happens before `sys.exit`.
- Require manual Omarchy runtime check for real keypress semantics.

**Divergence (resolved in this plan)**

- Default `usage_log_path` hardening (`/tmp` vs XDG path) was raised by security perspective; this plan keeps the approved Section 8 design default (`/tmp/koe-usage.jsonl`) to stay contract-accurate for this section.
- C1/C2 tests exist already; this plan treats them as existing evidence and adds only delta checks where proof gaps matter.

**Key perspective contributions**

- DX Advocate: explicitly update existing `main()` tests to avoid hidden filesystem side effects.
- Architecture Purist: preserve strict module ownership and one-way imports.
- Validation Strategist: phase red/green around C3 then C4/C5 with exact test IDs.
- Security Auditor: enforce explicit Omarchy binding validation and duplicate-binding checks in manual phase.
- Correctness Guardian: keep exhaustive outcome semantics and non-raising writer contract explicit.

## Phase Ownership

| Phase | Owner | Responsibility |
|-------|-------|---------------|
| Test phases | `/test-implementer` | Add/adjust tests from Section 8 test spec before implementation changes |
| Implementation phases | `/implement-plan` | Implement `types/config/usage_log/main` changes to make Section 8 tests pass |

## Phase 1: Section 8 Test Surface (Red/Delta)

**Owner**: `/test-implementer`
**Commit**: `test: add section 8 logging boundary contracts`

### Overview

Add Section 8 tests and static fixtures that encode C3-C6 contracts and update existing `main()` test expectations for upcoming logging behavior.

### Changes Required

#### 1. Add new usage log tests
**File**: `tests/test_usage_log.py` (new)
**Changes**: implement T-04, T-05, T-06, T-07 from test spec.

```python
def test_write_usage_log_record_appends_one_jsonl_record_with_required_shape(...) -> None: ...
def test_write_usage_log_record_multiple_calls_append_and_generate_distinct_uuid4_run_ids(...) -> None: ...
@pytest.mark.parametrize("outcome", [...all PipelineOutcome literals...])
def test_write_usage_log_record_outcome_passthrough_is_total(outcome: PipelineOutcome) -> None: ...
def test_write_usage_log_record_is_non_raising_on_write_failure_emits_stderr(...) -> None: ...
```

#### 2. Add section static contract fixture
**File**: `tests/section8_static_fixtures.py` (new)
**Changes**: callable signature contract for `write_usage_log_record` and type-surface checks for `UsageLogRecord`/`KoeConfig` field.

```python
def t8sf_write_usage_log_record_signature_contract() -> None: ...
def t8sf_koe_config_includes_usage_log_path(config: KoeConfig) -> None: ...
```

#### 3. Extend `main()` boundary tests
**File**: `tests/test_main.py`
**Changes**: add T-08, T-09, T-10, T-11, T-12 and update existing `test_main_maps_unexpected_exception_to_exit_2` to patch writer.

```python
def test_main_logs_once_before_sys_exit_on_success() -> None: ...
def test_main_logs_once_for_all_non_unexpected_outcomes(...) -> None: ...
def test_main_exception_path_logs_error_unexpected_and_exits_2() -> None: ...
def test_main_passes_iso_invoked_at_and_non_negative_duration_ms() -> None: ...
def test_run_pipeline_never_calls_write_usage_log_record() -> None: ...
```

#### 4. Fill small existing proof gaps
**File**: `tests/test_hotkey.py`
**Changes**: add assertions/tests for lock-file existence/removal to align with T-01/T-03 expected side effects.

### Success Criteria

#### Validation (REQUIRED)
- [x] `tests/test_usage_log.py` exists with T-04..T-07.
- [x] `tests/test_main.py` includes T-08..T-12 and updated existing `main()` exception test.
- [x] `tests/section8_static_fixtures.py` exists and typechecks once Section 8 types/modules are implemented.
- [x] New tests are red only for missing Section 8 implementation code (not for broken harness assumptions).

#### Standard Checks
- [x] `uv run ruff check tests/`
- [x] `uv run pytest tests/test_usage_log.py tests/test_main.py` (expected red: missing `UsageLogRecord`/`koe.usage_log` implementation)
- [x] `uv run pyright` (expected red: missing Section 8 type/module surfaces)

**Implementation Note**: Proceed to implementation after red tests are attributable only to missing Section 8 code.

---

## Phase 2: Add Section 8 Types/Config/Writer (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: add section 8 usage log contracts and writer`

### Overview

Implement Surface B from design: new shared type, config path, and non-raising JSONL writer.

### Changes Required

#### 1. Extend shared types
**File**: `src/koe/types.py`
**Changes**: add `UsageLogRecord` TypedDict.

```python
class UsageLogRecord(TypedDict):
    run_id: str
    invoked_at: str
    outcome: PipelineOutcome
    duration_ms: int
```

#### 2. Extend runtime config
**File**: `src/koe/config.py`
**Changes**: add `usage_log_path: Path` to `KoeConfig` and default path in `DEFAULT_CONFIG`.

```python
"usage_log_path": Path("/tmp/koe-usage.jsonl")
```

#### 3. Add usage log module
**File**: `src/koe/usage_log.py` (new)
**Changes**: implement `write_usage_log_record(...) -> None` with append-only JSONL write and stderr diagnostic on failure.

```python
def write_usage_log_record(config: KoeConfig, outcome: PipelineOutcome, /, *, invoked_at: str, duration_ms: int) -> None:
    ...  # append one JSON line, never raise
```

### Success Criteria

#### Validation (REQUIRED)
- [x] T-04, T-05, T-06, T-07 pass.
- [x] Section 8 static fixture contracts pass under Pyright.
- [x] Writer failures are non-raising and produce stderr diagnostic token.

#### Standard Checks
- [x] `uv run pytest tests/test_usage_log.py tests/test_types.py tests/test_config.py`
- [x] `uv run pyright`
- [x] `uv run ruff check src/ tests/`

**Implementation Note**: Keep writer pure concern; do not call it from `run_pipeline()`.

---

## Phase 3: Add `main()` Logging Boundary (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: log one usage record per main invocation`

### Overview

Implement Surface C: `main()` captures invocation metadata, resolves outcome, writes exactly one log record, then exits using existing mapping.

### Changes Required

#### 1. Update `main()` orchestration ordering
**File**: `src/koe/main.py`
**Changes**: import time/date + writer, capture `invoked_at` and monotonic start, coerce exception path to `error_unexpected`, write usage record before `sys.exit`.

```python
invoked_at = datetime.now(timezone.utc).isoformat()
start = time.monotonic()
...
write_usage_log_record(DEFAULT_CONFIG, outcome, invoked_at=invoked_at, duration_ms=duration_ms)
sys.exit(outcome_to_exit_code(outcome))
```

#### 2. Preserve separation boundary
**File**: `src/koe/main.py`
**Changes**: do not add writer calls inside `run_pipeline()`.

### Success Criteria

#### Validation (REQUIRED)
- [x] T-08, T-09, T-10, T-11 pass in `tests/test_main.py`.
- [x] T-12 proves `run_pipeline()` never writes usage logs directly.
- [x] Existing outcome-to-exit total mapping remains green.

#### Standard Checks
- [x] `uv run pytest tests/test_main.py`
- [x] `uv run pyright`
- [x] `uv run ruff check src/ tests/`

**Implementation Note**: `main()` remains single-shot and exits exactly once.

---

## Phase 4: Section 8 Regression and Gate Validation

**Owner**: `/implement-plan`
**Commit**: `test: validate section 8 automated contracts`

### Overview

Run Section 8 targeted and full-project gates after implementation phases.

### Changes Required

#### 1. Run targeted suite
**Files**: none (validation phase)

```bash
uv run pytest tests/test_hotkey.py tests/test_usage_log.py tests/test_main.py tests/section8_static_fixtures.py
```

#### 2. Run full quality gates
**Files**: none (validation phase)

```bash
make lint && make typecheck && make test
```

### Success Criteria

#### Validation (REQUIRED)
- [x] All Section 8 automated contracts pass.
- [x] Full repository lint/typecheck/test gates pass with no regressions.

#### Standard Checks
- [x] `make lint`
- [x] `make typecheck`
- [x] `make test`

**Implementation Note**: If failures appear outside Section 8, apply minimal compatibility fixes only.

---

## Phase 5: Omarchy Binding and Manual Runtime Validation

**Owner**: `/implement-plan`
**Commit**: `docs: add section 8 omarchy binding validation runbook`

### Overview

Materialize C7 and complete M-01/M-02 manual checks for real compositor behavior.

### Changes Required

#### 1. Add/update Omarchy keybind
**File**: `/home/brad/.config/hypr/bindings.conf`
**Changes**: add one `bind` mapping that executes `koe` exactly once per activation.

```conf
bind = SUPER SHIFT, V, exec, koe
```

#### 2. Record manual validation artifact
**File**: `thoughts/projects/2026-02-20-koe-m1/working/section-8-validation-report.md` (new)
**Changes**: capture M-01 static config evidence and M-02 runtime delta-of-one evidence.

### Success Criteria

#### Validation (REQUIRED)
- [ ] M-01: exactly one active binding maps to `exec, koe`; no duplicate same-chord mapping across sourced Hyprland files.
- [ ] M-02: one key activation increments usage log by exactly one line; latest outcome matches observed run result.

#### Standard Checks
- [ ] `uv run pytest tests/test_usage_log.py tests/test_main.py`
- [ ] `make lint && make typecheck && make test`

#### Manual Verification (required)
- [ ] Press `SUPER+SHIFT+V` once in active Omarchy session and verify exactly one new JSONL record.
- [ ] Trigger contention scenario and verify `outcome="already_running"` is logged distinctly.

**Implementation Note**: Pause for human verification. Reason: compositor hotkey activation cannot be fully self-validated by the agent.

## Testing Strategy

Test phases come first; implementation phases make tests pass.

### Tests (written by `/test-implementer`)

- `tests/test_usage_log.py`: T-04, T-05, T-06, T-07.
- `tests/test_main.py`: T-08, T-09, T-10, T-11, T-12 plus existing `main()` exception test update.
- `tests/section8_static_fixtures.py`: Section 8 callable/type contracts.
- `tests/test_hotkey.py`: T-01/T-03 side-effect proof deltas if needed.

### Additional Validation (implementation phases)

- Pyright strict checks enforce TypedDict and signature contracts.
- Ruff checks enforce import/order/annotation hygiene.
- Full pytest and make gates prove no regressions across sections.

### Manual Testing Steps (only where agent cannot self-validate)

1. Verify Hyprland source chain and single binding active (`/home/brad/.config/hypr/hyprland.conf:4`, `/home/brad/.config/hypr/hyprland.conf:18`).
2. Record baseline line count for usage log file.
3. Press hotkey once; wait for run completion.
4. Verify line-count delta is exactly `+1` and latest record parses as valid JSON with expected outcome.

## Execution Graph

**Phase Dependencies:**

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5
```

| Phase | Depends On | Can Parallelize With |
|-------|------------|---------------------|
| 1 | - | - |
| 2 | 1 | - |
| 3 | 2 | - |
| 4 | 3 | - |
| 5 | 4 | - |

**Parallel Execution Notes:**

- Phase 2 and Phase 3 both modify `src/koe/main.py`-adjacent behavior through tests and orchestration, so run sequentially for low merge risk.
- Manual Omarchy checks (Phase 5) must run after all automated phases are green.

## References

- Section requirements: `thoughts/projects/2026-02-20-koe-m1/spec.md:152`
- Section 8 acceptance criteria: `thoughts/projects/2026-02-20-koe-m1/spec.md:163`
- Section 8 research: `thoughts/projects/2026-02-20-koe-m1/working/section-8-research.md:44`
- Section 8 test spec: `thoughts/projects/2026-02-20-koe-m1/working/section-8-test-spec.md:39`
- Section 8 API design (Surface A/B/C): `thoughts/design/2026-02-20-koe-m1-section-8-api-design.md:19`
- Omarchy user binding path: `/home/brad/.config/hypr/bindings.conf:1`

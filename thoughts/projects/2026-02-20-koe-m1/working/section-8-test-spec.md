---
title: "Section 8 Test Specification"
date: 2026-02-20
status: draft
design_source: "thoughts/design/2026-02-20-koe-m1-section-8-api-design.md"
spec_source: "thoughts/projects/2026-02-20-koe-m1/spec.md"
research_source: "thoughts/projects/2026-02-20-koe-m1/working/section-8-research.md"
project_section: "Section 8: Omarchy Hotkey Trigger and Per-Run Usage Logging Validation (Wayland)"
---

# Test Specification: Section 8 Omarchy Trigger and Usage Logging

## Purpose

This document specifies proof obligations for Section 8 API contracts. Each test/check maps to a contract in `thoughts/design/2026-02-20-koe-m1-section-8-api-design.md` and covers both happy and error paths where applicable. Passing these tests proves one-record-per-invocation semantics, including blocked and failure outcomes.

## Test Infrastructure

**Framework**: `pytest` + `typeguard`
**Test location**: `tests/` (flat module-aligned layout)
**Patterns to follow**:
- Result-arm assertions and error-category checks: `tests/test_window.py:21`, `tests/test_hotkey.py:21`, `tests/test_insert.py:278`
- Exhaustive `PipelineOutcome` parametrization: `tests/test_main.py:98`
- Orchestration ordering via `events` list: `tests/test_main.py:198`, `tests/test_main.py:602`
- Cleanup/invariant ordering checks: `tests/test_main.py:749`
- Runtime TypedDict shape checks: `tests/test_types.py:30`

**Utilities available**:
- Local `_completed()` subprocess helpers per module test file (`tests/test_window.py:12`, `tests/test_insert.py:17`)
- Config override pattern via spread (`tests/test_hotkey.py:9`, `tests/test_audio.py:12`)
- `unittest.mock.patch(..., create=True)` module boundary patching (`tests/test_main.py:116`)

**Run command**:
- `make test`
- Targeted: `uv run pytest tests/test_main.py tests/test_hotkey.py tests/test_usage_log.py`

## API Surface

| Contract | Signature | Design Reference | Tests/Checks |
|----------|-----------|------------------|--------------|
| C1: Hotkey lock acquire | `acquire_instance_lock(config: KoeConfig, /) -> Result[InstanceLockHandle, AlreadyRunningError]` | Surface A | T-01, T-02 |
| C2: Hotkey lock release | `release_instance_lock(handle: InstanceLockHandle, /) -> None` | Surface A | T-03 |
| C3: Usage log writer | `write_usage_log_record(config: KoeConfig, outcome: PipelineOutcome, /, *, invoked_at: str, duration_ms: int) -> None` | Surface B | T-04, T-05, T-06, T-07 |
| C4: Main logging boundary | `main() -> None` | Surface C | T-08, T-09, T-10, T-11 |
| C5: Pipeline/logging separation | `run_pipeline(config: KoeConfig, /) -> PipelineOutcome` does not write usage logs | Surface C | T-12 |
| C6: Exit mapping after logging | `outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode` used after write | Surface C event ordering | T-08, T-09, T-10 |
| C7: Omarchy trigger binding | `bind = SUPER SHIFT, V, exec, koe` (non-Python artifact) | Surface A binding contract | M-01, M-02 |

## Proof Obligations

### C1-C2: `hotkey.py` invocation guard contracts

Design reference: `thoughts/design/2026-02-20-koe-m1-section-8-api-design.md` (Surface A)
Depends on: none

#### T-01: First acquire succeeds and creates lock handle

**Contract**: Lock acquisition returns `Ok` for first invocation attempt.
**Setup**: Temp lock path in config; no pre-existing lock file.
**Expected**: `{"ok": True, "value": <InstanceLockHandle>}` and lock file exists.
**Discriminating power**: Fails if implementation silently no-ops, returns wrong union arm, or mis-types handle.
**Contract invariant**: One active process can establish ownership.
**Allowed variation**: Lock file contents may change, as long as exclusivity semantics stay intact.
**Assertion scope rationale**: Assert discriminant + handle existence, not incidental file payload text.
**Fragility check**: Should not fail if PID formatting changes.

---

#### T-02: Concurrent acquire returns typed `already_running` error

**Contract**: Contention maps to `Err[AlreadyRunningError]` and does not grant a second handle.
**Setup**: Acquire once; call `acquire_instance_lock` again with same lock path.
**Expected**: second call returns `{"ok": False, "error": {"category": "already_running", ...}}`.
**Discriminating power**: Catches broken locking that allows parallel execution or wrong error category.
**Contract invariant**: Blocked attempts are explicit and typed.
**Allowed variation**: Error message wording can vary if category and semantic meaning are preserved.
**Assertion scope rationale**: Category-level assertion is required by contract; full string equality is not.
**Fragility check**: Avoid asserting full OS error text.

---

#### T-03: Release removes held lock without raising

**Contract**: `release_instance_lock` cleans up lock artifact for a valid handle.
**Setup**: Acquire lock, then release returned handle.
**Expected**: lock file removed; function returns `None`.
**Discriminating power**: Catches leaked lock state causing false `already_running` on next run.
**Contract invariant**: Ownership cleanup is explicit and deterministic.
**Allowed variation**: Internal deletion mechanism can vary.
**Assertion scope rationale**: Verify observable side effect only.
**Fragility check**: Do not over-assert internal fs call sequence.

---

### C3: `usage_log.py` writer contract

Design reference: `thoughts/design/2026-02-20-koe-m1-section-8-api-design.md` (Surface B)
Depends on: none

#### T-04: One call appends exactly one JSONL record with required shape

**Contract**: Each writer call appends one line containing `run_id`, `invoked_at`, `outcome`, `duration_ms`.
**Setup**: Empty temp `usage_log_path`; call once with fixed `invoked_at`, outcome, duration.
**Expected**: file has one new line; JSON parses; `check_type(record, UsageLogRecord)` passes; outcome/duration/invoked_at match input.
**Discriminating power**: Catches missing fields, wrong keys, overwrite behavior, non-JSON output.
**Contract invariant**: Record schema is stable and machine-parseable.
**Allowed variation**: Key order in JSON object may vary.
**Assertion scope rationale**: Shape + semantic field equality is minimal sufficient proof.
**Fragility check**: Never assert raw JSON string ordering.

---

#### T-05: Multiple calls append (not overwrite) and produce distinct UUID4 `run_id`

**Contract**: Writer is append-only per invocation and generates run id internally.
**Setup**: Call writer N=3 times to same file with different outcomes.
**Expected**: exactly 3 lines; each record has unique `run_id`; each `run_id` parses as UUID4.
**Discriminating power**: Catches truncation/overwrite and non-unique or caller-provided run ids.
**Contract invariant**: one call -> one durable record with independent identity.
**Allowed variation**: UUID values themselves are nondeterministic.
**Assertion scope rationale**: Validate uniqueness + UUID format, not specific UUID values.
**Fragility check**: Do not seed or snapshot exact IDs.

---

#### T-06: Outcome passthrough is total for all `PipelineOutcome` variants

**Contract**: Writer accepts and persists every `PipelineOutcome` variant exactly.
**Setup**: `@pytest.mark.parametrize` over all literals: `success`, `already_running`, `no_focus`, `no_speech`, `error_dependency`, `error_audio`, `error_transcription`, `error_insertion`, `error_unexpected`.
**Expected**: persisted `record["outcome"] == input_outcome` for each case.
**Discriminating power**: Catches accidental remapping/collapsing of outcomes.
**Contract invariant**: Usage logging preserves outcome semantics.
**Allowed variation**: None on outcome value; literal is contract-bound.
**Assertion scope rationale**: Exact equality required because literals are semantic.
**Fragility check**: Parameter list must track future `PipelineOutcome` expansions.

---

#### T-07: Write/serialization failure is non-raising and emits stderr diagnostic

**Contract**: Writer must never raise; on failure it prints diagnostic to `sys.stderr` and returns.
**Setup**: Patch file open or JSON serialization to raise `OSError`/`TypeError`.
**Expected**: no exception escapes; stderr contains usage-log failure diagnostic.
**Discriminating power**: Catches silent failures and exception propagation that would alter process exit behavior.
**Contract invariant**: logging is best-effort, non-fatal, non-silent.
**Allowed variation**: Diagnostic wording may vary if it clearly indicates write failure.
**Assertion scope rationale**: Assert stderr intent token/prefix, not full sentence.
**Fragility check**: Avoid brittle exact punctuation checks.

---

### C4-C6: `main.py` logging hook and event ordering

Design reference: `thoughts/design/2026-02-20-koe-m1-section-8-api-design.md` (Surface C, event ordering)
Depends on: C3

#### T-08: Success path logs exactly once before `sys.exit`

**Contract**: `main()` writes one usage record before exiting with mapped code.
**Setup**: Patch `run_pipeline` to return `success`; patch `write_usage_log_record` and `sys.exit`; capture ordered events list.
**Expected**: exactly one writer call; writer event index < `sys.exit` event index; `sys.exit(0)`.
**Discriminating power**: Catches missing logging, duplicate logging, or incorrect ordering.
**Contract invariant**: logging is part of terminal path, not optional post-step.
**Allowed variation**: internal time-source implementation may vary.
**Assertion scope rationale**: Count + relative order are the minimal required semantics.
**Fragility check**: Do not assert absolute timing values in this test.

---

#### T-09: Expected non-success outcomes still log exactly once and preserve outcome literal

**Contract**: `main()` logs exactly once for every normal return outcome, including blocked/error outcomes.
**Setup**: Parametrize `run_pipeline` returns across all non-`error_unexpected` outcomes.
**Expected**: one writer call per invocation with `outcome` equal to pipeline return; `sys.exit` code equals `outcome_to_exit_code(outcome)`.
**Discriminating power**: Catches selective logging that only covers success path.
**Contract invariant**: one-record-per-invocation regardless of outcome class.
**Allowed variation**: Invocation timestamp and duration values vary per run.
**Assertion scope rationale**: outcome equality + single call are contract core.
**Fragility check**: avoid asserting notification internals from `run_pipeline` here.

---

#### T-10: Unexpected exception path coerces to `error_unexpected`, logs once, exits `2`

**Contract**: `main()` catches unexpected exception from `run_pipeline`, logs `error_unexpected`, exits with code `2`.
**Setup**: Patch `run_pipeline` to raise `RuntimeError`; patch writer and `sys.exit`.
**Expected**: writer called once with `outcome="error_unexpected"`; `sys.exit(2)`.
**Discriminating power**: Catches crash-through behavior and missing exception-path logging.
**Contract invariant**: exception path remains observable and typed at process boundary.
**Allowed variation**: raised exception message/type does not matter for this contract.
**Assertion scope rationale**: only mapped terminal outcome and exit code are contractual.
**Fragility check**: do not assert traceback formatting.

---

#### T-11: Logged metadata is structurally valid (`invoked_at` ISO-8601 text, `duration_ms` int >= 0)

**Contract**: `main()` passes invocation metadata expected by writer contract.
**Setup**: Patch clocks to deterministic values; intercept writer kwargs.
**Expected**: `invoked_at` is parseable ISO-8601 string; `duration_ms` is int and non-negative.
**Discriminating power**: Catches wrong time-source wiring and negative/non-int duration bugs.
**Contract invariant**: usage records are parseable and quantitatively valid.
**Allowed variation**: precise timestamp format offset (`Z` vs `+00:00`) if ISO-8601 parseable.
**Assertion scope rationale**: parser-based validation avoids overfitting exact rendering.
**Fragility check**: avoid exact timestamp string equality unless clock is fully frozen.

---

### C5: `run_pipeline` separation-of-concerns contract

Design reference: `thoughts/design/2026-02-20-koe-m1-section-8-api-design.md` (Surface C)
Depends on: existing pipeline tests

#### T-12: `run_pipeline()` never writes usage logs directly

**Contract**: Logging boundary is `main()`, not `run_pipeline()`.
**Setup**: Patch `koe.main.write_usage_log_record` spy; execute `run_pipeline` via representative branch matrix (success, already_running, dependency error).
**Expected**: writer spy is never called from `run_pipeline`.
**Discriminating power**: Catches accidental duplicate logging and boundary violations.
**Contract invariant**: one orchestration point controls invocation record emission.
**Allowed variation**: pipeline internals can change if terminal outcome contract remains unchanged.
**Assertion scope rationale**: direct non-call assertion is sufficient proof.
**Fragility check**: avoid coupling to full stage order here (covered elsewhere).

---

### C7: Omarchy binding contract checks (non-Python)

Design reference: `thoughts/design/2026-02-20-koe-m1-section-8-api-design.md` (Surface A binding)
Depends on: none

#### M-01: Static config check for one-keypress one-process trigger binding

**Contract**: Binding exists in committed/user-applied Hyprland config as `bind = SUPER SHIFT, V, exec, koe` (or project-approved equivalent key tuple -> `exec, koe`).
**Setup**: Validate effective Hyprland binding source for active profile.
**Expected**: exactly one active bind entry maps to `exec, koe`; no duplicate mappings for the same chord.
**Discriminating power**: Catches missing trigger and duplicate binding causing multi-launch risk.
**Contract invariant**: one activation -> one Koe process launch intent.
**Allowed variation**: key chord may change if spec/design is explicitly updated.
**Assertion scope rationale**: assert semantic mapping to `koe`, not whitespace/format trivia.
**Fragility check**: include source-chain awareness (included files may override).

---

#### M-02: Manual runtime check confirms one activation -> one usage record

**Contract**: Real Omarchy hotkey activation causes one run attempt and one new JSONL record.
**Setup**: note baseline line count in usage log; press hotkey once; wait for process completion.
**Expected**: line count increments by exactly one; latest record outcome matches observed run result (including `already_running` contention scenario).
**Discriminating power**: Catches compositor-level repeat firing and missed logging in real environment.
**Contract invariant**: AC2/AC3 runtime semantics hold outside unit-test harness.
**Allowed variation**: outcome value depends on environment state during run.
**Assertion scope rationale**: delta-of-one is minimal proof of one-record-per-activation.
**Fragility check**: ensure no concurrent external `koe` runs during validation.

---

## Requirement Traceability

| Requirement | Source | Proved By Contract | Proved By Test/Check |
|-------------|--------|--------------------|----------------------|
| AC1 Omarchy trigger path without X11 daemon path | `thoughts/projects/2026-02-20-koe-m1/spec.md:163` | C7 | M-01, M-02 |
| AC2 one activation -> one record | `thoughts/projects/2026-02-20-koe-m1/spec.md:164` | C3, C4 | T-04, T-05, T-08, T-09, M-02 |
| AC3 blocked attempts logged distinctly | `thoughts/projects/2026-02-20-koe-m1/spec.md:165` | C1, C3, C4 | T-02, T-06, T-09, M-02 |
| AC4 missing deps/config logged with failed-attempt record | `thoughts/projects/2026-02-20-koe-m1/spec.md:166` | C3, C4, C5 | T-06, T-09, T-12, M-02 |
| AC5 validation is testable (automated + manual) | `thoughts/projects/2026-02-20-koe-m1/spec.md:167` | C3-C7 | T-01..T-12, M-01, M-02 |

## What Is NOT Tested (and Why)

- Internal JSON serialization implementation details in `usage_log.py`: not part of API contract.
- Exact stderr message text punctuation: contract requires diagnostic emission, not fixed prose.
- Wayland focus/insert backend behavior: explicitly out of scope for Section 8 (owned by Section 9).
- Analytics/telemetry aggregation: out of scope; only per-run JSONL append semantics are in scope.

## Test Execution Order

1. Foundation lock and writer contracts: T-01, T-02, T-03, T-04, T-05, T-06, T-07
2. Main boundary and ordering contracts: T-08, T-09, T-10, T-11, T-12
3. Environment/manual Omarchy checks: M-01, M-02

If group 1 fails, group 2 results are not trustworthy; if groups 1-2 pass, manual checks validate compositor/runtime integration.

## Design Gaps

- None blocking automated test specification for the Python API surfaces.
- Operational note: C7 is compositor configuration, so final proof requires manual runtime check (M-01/M-02) in active Omarchy profile.

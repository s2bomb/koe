---
title: "Section 7 Quality Gates, Tests, and Onboarding Readiness Test Specification"
date: 2026-02-20
status: approved
design_source: "thoughts/design/2026-02-20-koe-m1-section-7-api-design.md"
spec_source: "thoughts/projects/2026-02-20-koe-m1/spec.md"
research_source: "thoughts/projects/2026-02-20-koe-m1/working/section-7-research.md"
project_section: "Section 7: Quality Gates, Tests, and Onboarding Readiness"
---

# Test Specification: Section 7 Quality Gates, Tests, and Onboarding Readiness

## Purpose

This document defines proof obligations for Section 7 delivery-gate contracts. The design surface here is a mixed API: runtime gate behavior in `main.py`, command-surface contracts in `Makefile`, and onboarding sufficiency in `README.md`. Tests/checks below are scoped to those contracts only and include explicit failure-path coverage for each gate.

## Test Infrastructure

**Framework**: `pytest` (`pyproject.toml:28`)
**Test location**: `tests/` (flat layout, one file per module boundary)
**Patterns to follow**:
- Exhaustive mapping via `pytest.mark.parametrize`: `tests/test_main.py:98`
- Pipeline branch isolation with `patch(..., create=True)`: `tests/test_main.py:116`
- Ordering assertions via `events` list and `side_effect`: `tests/test_main.py:198`
- Runtime TypedDict shape assertions with `typeguard.check_type`: `tests/test_types.py:31`
**Utilities available**:
- `tmp_path` fixture for lock/artifact lifecycle checks: `tests/test_main.py:311`
- Static fixture type-contract checks under `make typecheck`: `tests/section1_static_fixtures.py:27`
**Run command**:
- Automated: `make test`, `make lint`, `make typecheck`
- Target-runtime/manual gate: `make run` + timed onboarding validation

## API Surface

| Contract | Signature | Design Reference | Tests/Checks |
|----------|-----------|------------------|--------------|
| Dependency startup gate | `dependency_preflight(config: KoeConfig, /) -> Result[None, DependencyError]` | `2026-02-20-koe-m1-section-7-api-design.md:23` | T7A-01, T7A-02 |
| Pipeline lifecycle gate outcomes and cleanup | `run_pipeline(config: KoeConfig, /) -> PipelineOutcome` | `2026-02-20-koe-m1-section-7-api-design.md:24` | T7A-03, T7A-04, T7A-05, T7A-06 |
| Exit mapping totality | `outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode` | `2026-02-20-koe-m1-section-7-api-design.md:25` | T7A-07 |
| CLI exception boundary | `main() -> None` | `2026-02-20-koe-m1-section-7-api-design.md:22` | T7A-08 |
| Command gate: lint | `make lint` | `2026-02-20-koe-m1-section-7-api-design.md:60` | T7B-01, T7B-02 |
| Command gate: typecheck | `make typecheck` | `2026-02-20-koe-m1-section-7-api-design.md:61` | T7B-03, T7B-04 |
| Command gate: test | `make test` | `2026-02-20-koe-m1-section-7-api-design.md:62` | T7B-05, T7B-06 |
| Command gate: run | `make run` | `2026-02-20-koe-m1-section-7-api-design.md:63` | T7B-07, T7B-08 |
| Onboarding contract sufficiency | `README.md` content contract | `2026-02-20-koe-m1-section-7-api-design.md:99` | T7C-01, T7C-02 |
| AC1 integration artifact requirement | one dedicated terminal-flow integration source | `2026-02-20-koe-m1-section-7-api-design.md:118` | T7C-03 |

## Proof Obligations

### Surface A: `main.py` delivery-gate contracts

Design references: `2026-02-20-koe-m1-section-7-api-design.md:17`, `:28`, `:43`
Depends on: Section 2-6 module contracts already proven in their module tests

#### T7A-01: `dependency_preflight` accepts only fully compliant startup environment

**Contract**: Returns `Ok[None]` when all required tools are present and `whisper_device == "cuda"`.
**Setup**: Patch `shutil.which` for `xdotool`, `xclip`, `notify-send` to non-`None`; use default config.
**Expected**: `{"ok": True, "value": None}`.
**Discriminating power**: Fails permissive implementations that skip one tool or skip CUDA policy check.
**Invariant**: Startup gate is explicit and non-raising.
**Allowed variation**: Internal check order may vary.
**Assertion scope rationale**: Result arm + value are minimum sufficient proof.
**Fragility check**: Do not assert internal helper call count.

---

#### T7A-02: `dependency_preflight` returns typed dependency error for each missing prerequisite

**Contract**: Any missing required tool or non-CUDA device returns `Err[DependencyError]` with explicit category.
**Setup**: Parametrize missing tool cases (`xdotool`, `xclip`, `notify-send`) plus `whisper_device="cpu"`.
**Expected**: `result["ok"] is False`; `error["category"] == "dependency"`; `missing_tool` matches failing prerequisite.
**Discriminating power**: Fails implementations that raise, silently pass, or collapse all failures to generic error.
**Invariant**: One failing prerequisite is sufficient to block pipeline start.
**Allowed variation**: Message text tail can vary if category and missing_tool are preserved.
**Assertion scope rationale**: Category + missing_tool identify the contract behavior.
**Fragility check**: Avoid exact full-message string lock.

---

#### T7A-03: `run_pipeline` maps all expected branch states to controlled outcomes

**Contract**: Returns only controlled outcomes for expected states (`success`, `no_focus`, `no_speech`, `error_dependency`, `error_audio`, `error_transcription`, `error_insertion`, `already_running`).
**Setup**: Existing branch-isolated tests covering preflight failure, lock contention, no focus, audio failure, transcription failure/empty, insertion failure, and success.
**Expected**: Exact outcome literal per branch.
**Discriminating power**: Fails branch mis-wiring (for example mapping insertion failure to `error_audio`).
**Invariant**: Expected failures stay in controlled outcome set.
**Allowed variation**: Internal sequencing inside a branch may evolve if terminal outcome remains exact.
**Assertion scope rationale**: Outcome literal is the contract surface.
**Fragility check**: Do not assert unrelated side effects in this proof.

---

#### T7A-04: lock lifecycle cleanup runs on every lock-acquired path, including failures

**Contract**: Once lock acquisition succeeds, release is guaranteed for all terminal branches.
**Setup**: Parametrize branch outcomes after lock acquisition (focus fail, audio fail, transcription fail/empty, insertion fail, success) with patched lock handle/release function.
**Expected**: `release_instance_lock` called exactly once in each lock-acquired branch.
**Discriminating power**: Fails leaked-lock implementations on early-return branches.
**Invariant**: No branch may retain lock after `run_pipeline` returns.
**Allowed variation**: Exact release timing within `finally` can vary.
**Assertion scope rationale**: Single call with acquired handle is sufficient.
**Fragility check**: No assertions about unrelated notification ordering.

---

#### T7A-05: audio artifact cleanup runs on every artifact-created path, including no-speech/error branches

**Contract**: Once capture creates a WAV artifact, cleanup always runs regardless of downstream result.
**Setup**: Parametrize transcription results (`text`, `empty`, `error`) and insertion failure/success with known artifact path.
**Expected**: `cleanup_audio_artifact(artifact_path)` called once for each artifact-created branch.
**Discriminating power**: Fails implementations that clean up only success path.
**Invariant**: Artifact lifecycle is bounded to invocation.
**Allowed variation**: Cleanup call placement may differ if branch coverage remains complete.
**Assertion scope rationale**: One cleanup call per artifact-created run is minimal proof.
**Fragility check**: Avoid asserting exact event timeline beyond cleanup guarantee.

---

#### T7A-06: notification transport failure cannot mask pipeline cleanup or outcome

**Contract**: Notification emission exceptions do not change outcome mapping and do not block lock/artifact cleanup.
**Setup**: Patch `send_notification` to raise on representative branches where lock and artifact are already acquired.
**Expected**: Controlled branch outcome still returned; lock release and artifact cleanup still occur.
**Discriminating power**: Fails implementations where notify exception aborts cleanup path.
**Invariant**: Notification is best-effort and non-authoritative.
**Allowed variation**: Exact error logging behavior is not contractual.
**Assertion scope rationale**: Outcome + cleanup evidence proves non-masking.
**Fragility check**: Do not assert stderr content.

---

#### T7A-07: `outcome_to_exit_code` is exhaustive and total over `PipelineOutcome`

**Contract**: Mapping table is exact (`success->0`, controlled outcomes->1, `error_unexpected->2`).
**Setup**: Parametrize all outcome literals.
**Expected**: Exact mapped `ExitCode` per literal.
**Discriminating power**: Fails omissions and accidental remaps.
**Invariant**: Process exit code semantics are deterministic.
**Allowed variation**: Implementation style (`match` or lookup table) may vary.
**Assertion scope rationale**: Table equality is minimum totality proof.
**Fragility check**: No internal branch assertions.

---

#### T7A-08: `main()` catches uncaught exceptions and exits with code 2

**Contract**: `main` is exception boundary for unexpected exceptions.
**Setup**: Patch `run_pipeline` with `side_effect=Exception("boom")`; patch `sys.exit`.
**Expected**: `sys.exit(2)` called exactly once.
**Discriminating power**: Fails leak/crash behavior or incorrect mapping through normal outcome table.
**Invariant**: Unexpected exceptions are terminal exit code 2.
**Allowed variation**: Exception message text.
**Assertion scope rationale**: Exit code call is only observable contract output.
**Fragility check**: Avoid traceback string assertions.

---

### Surface B: command delivery gates (`Makefile`)

Design references: `2026-02-20-koe-m1-section-7-api-design.md:55`, `:66`, `:75`
Depends on: command definitions in `Makefile` and CLI entrypoint in `pyproject.toml`

#### T7B-01: `make lint` success gate proves ruff baseline integrity

**Contract**: `make lint` passes only when lint command exits `0` with no unmanaged suppressions.
**Setup**: Execute `make lint` in clean environment.
**Expected**: Exit status `0`.
**Discriminating power**: Fails on new lint violations or command wiring regressions.
**Invariant**: Lint gate is mandatory pre-delivery.
**Allowed variation**: Exact ruff output text can differ by tool version.
**Assertion scope rationale**: Exit status is contract output.
**Fragility check**: Do not assert exact line counts/messages.

---

#### T7B-02: `make lint` failure path is explicit and non-silent

**Contract**: On lint violations, command fails with non-zero exit and visible diagnostics.
**Setup**: Controlled mutation check in CI/pre-merge validation (introduce known lint violation in ephemeral branch/worktree).
**Expected**: Non-zero exit and printed lint error.
**Discriminating power**: Fails silent-success wrappers that hide ruff failures.
**Invariant**: Gate failures are explicit.
**Allowed variation**: Violation type used to trigger failure.
**Assertion scope rationale**: Non-zero + diagnostics are minimum failure proof.
**Fragility check**: No coupling to one exact lint rule code.

---

#### T7B-03: `make typecheck` success gate proves strict typing baseline

**Contract**: `make typecheck` passes only with `0 errors, 0 warnings`.
**Setup**: Execute `make typecheck` in clean environment.
**Expected**: Exit status `0`; summary indicates zero errors/warnings.
**Discriminating power**: Fails if strict-mode regresses or type contracts drift.
**Invariant**: strict Pyright remains hard gate.
**Allowed variation**: Runtime duration/output formatting.
**Assertion scope rationale**: Exit status plus zero-summary capture the contract.
**Fragility check**: Do not assert absolute file-count checked.

---

#### T7B-04: `make typecheck` failure path is explicit and non-silent

**Contract**: Type violations produce non-zero exit and visible diagnostic.
**Setup**: Controlled mutation check (introduce temporary signature/type mismatch).
**Expected**: Non-zero exit with error diagnostic.
**Discriminating power**: Fails wrappers that swallow Pyright failures.
**Invariant**: Type gate failure cannot be silent.
**Allowed variation**: Exact mismatch example.
**Assertion scope rationale**: Non-zero + surfaced error is minimum proof.
**Fragility check**: No assertion on exact error code text.

---

#### T7B-05: `make test` success gate proves whole-suite runtime pass

**Contract**: `make test` exits `0` when full `tests/` suite passes.
**Setup**: Execute `make test`.
**Expected**: Exit status `0` with no failures/errors.
**Discriminating power**: Fails on broken module behavior or test wiring regressions.
**Invariant**: Section pass requires full-suite pass.
**Allowed variation**: Exact count of passing tests may change as suite grows.
**Assertion scope rationale**: Exit status + no failures is contractually sufficient.
**Fragility check**: Do not pin to fixed total test count.

---

#### T7B-06: `make test` failure path is explicit and non-silent

**Contract**: Test regressions surface as non-zero exit with failing test diagnostics.
**Setup**: Controlled mutation check (inject temporary failing assertion in isolated branch).
**Expected**: Non-zero exit, failed-test report present.
**Discriminating power**: Fails silent green wrappers.
**Invariant**: Runtime regression cannot pass gate silently.
**Allowed variation**: Which test is intentionally failed.
**Assertion scope rationale**: Non-zero + failure report are minimum proof.
**Fragility check**: No hardcoded failure text beyond presence of pytest failure report.

---

#### T7B-07: `make run` in non-target environments fails explicitly, never by silent no-op

**Contract**: Non-target runtime path may fail, but failure must be explicit and controlled.
**Setup**: Execute `make run` in environment missing one or more runtime prerequisites.
**Expected**: Non-zero exit; actionable terminal output and/or notification path indicates dependency/runtime failure.
**Discriminating power**: Fails silent return-0 behavior when runtime cannot execute contract.
**Invariant**: Run gate communicates failure reason.
**Allowed variation**: Exact failing prerequisite.
**Assertion scope rationale**: Non-zero explicit failure evidence is required behavior in non-target env.
**Fragility check**: Do not require one specific message text if failure remains explicit and categorized.

---

#### T7B-08: `make run` in M1 target environment completes successful terminal insertion

**Contract**: In target Arch+X11+CUDA+mic environment, run exits `0` and inserts transcribed text into focused terminal.
**Setup**: Manual target-environment run with focused terminal and spoken utterance.
**Expected**: Exit `0`; visible lifecycle notifications; transcribed text appears in terminal input; clipboard restore intent observable.
**Discriminating power**: Fails pipelines that process but do not insert, or insert but fail cleanup semantics.
**Invariant**: End-user M1 happy path is real, not mocked.
**Allowed variation**: Exact transcript content depends on spoken phrase.
**Assertion scope rationale**: Exit + insertion + signal sequence are minimum user-visible success proof.
**Fragility check**: No strict word-for-word transcript assertion.

---

### Surface C: docs artifacts delivery gates (`README.md`)

Design references: `2026-02-20-koe-m1-section-7-api-design.md:90`, `:97`, `:109`
Depends on: command and runtime contracts above

#### T7C-01: README contains all required onboarding sections for first-run self-sufficiency

**Contract**: README includes prerequisites, hardware/X11 scope, install steps, verify/run flow, success signals, and troubleshooting categories.
**Setup**: Content checklist validation against required section matrix.
**Expected**: All required sections present in `README.md` without mandatory dependency on external docs for happy path.
**Discriminating power**: Fails minimal or partial README that omits one or more required gates.
**Invariant**: README is primary onboarding contract artifact.
**Allowed variation**: Section headings may vary if required content is clearly present.
**Assertion scope rationale**: Section-presence matrix is minimum contract proof.
**Fragility check**: Avoid exact prose matching.

---

#### T7C-02: Cold-start onboarding runbook reaches first successful transcription within 15 minutes using README only

**Contract**: New contributor can complete first success path in <=15 minutes from clean start.
**Setup**: Timed onboarding drill on target M1 environment with participant using only `README.md`.
**Expected**: Successful run (`make run` success behavior) completed in <=15 minutes; blockers and deviations logged.
**Discriminating power**: Fails docs that are technically complete but operationally unusable.
**Invariant**: Onboarding gate is outcome/time-bound, not just text-presence.
**Allowed variation**: Contributor identity and exact spoken phrase.
**Assertion scope rationale**: Timed first-success evidence is the direct contract statement.
**Fragility check**: Do not require identical click/command ordering when result and time bound hold.

---

#### T7C-03: Dedicated integration test artifact exists and proves terminal-flow composition (AC1)

**Contract**: At least one explicit end-to-end terminal-flow integration test source exists, separate from unit-only module tests.
**Setup**: Validate test inventory includes dedicated integration test file and that it executes under designated integration target.
**Expected**: Integration source present; test asserts cross-module terminal-flow composition rather than isolated mocks only.
**Discriminating power**: Fails repositories that only have unit tests and no explicit integration artifact.
**Invariant**: AC1 requires both module tests and one integration artifact.
**Allowed variation**: File naming convention and exact harness strategy.
**Assertion scope rationale**: Presence + execution of dedicated integration source is minimum AC1 proof.
**Fragility check**: Do not require substring `integration` in filename if artifact is explicit and scoped correctly.

## Requirement Traceability

| Requirement | Source | Proved By Contract | Proved By Test/Check |
|-------------|--------|--------------------|----------------------|
| AC1: unit tests per module boundary and one e2e integration test | `spec.md:106` | Surface A gate behavior + Surface C integration artifact contract | T7A-03, T7A-04, T7A-05, T7A-06, T7C-03 |
| AC2: error-path tests for no-focus/mic/CUDA-insertion/dependency failures | `spec.md:107` | `dependency_preflight` and controlled `run_pipeline` outcome mapping | T7A-02, T7A-03 |
| AC3: lint/typecheck/test/run commands execute successfully | `spec.md:108` | Surface B command contracts | T7B-01..T7B-08 |
| AC4: README onboarding sufficiency within 15 minutes | `spec.md:109` | Surface C onboarding docs contracts | T7C-01, T7C-02 |

## What Is NOT Tested (and Why)

- Internal implementation mechanics of module peers (`audio.py`, `transcribe.py`, `insert.py`) beyond their externally visible outcomes: these belong to Section 3-5 module test specs.
- Pixel-level desktop notification rendering differences by compositor/theme: not part of Section 7 delivery-gate API.
- Non-M1 platforms (Wayland/macOS/CPU-only): explicitly outside M1 scope.

## Test Execution Order

1. Surface A deterministic unit gates (`T7A-01`..`T7A-08`) for fastest contract regressions.
2. Surface B command success checks (`T7B-01`, `T7B-03`, `T7B-05`, `T7B-07`) in CI/dev shell.
3. Surface B controlled failure checks (`T7B-02`, `T7B-04`, `T7B-06`) in mutation/ephemeral validation workflow.
4. Surface C docs content gate (`T7C-01`) before expensive manual runs.
5. Surface C integration artifact and timed onboarding validation (`T7C-03`, `T7C-02`) as release-gate sign-off.

If group 1 fails, later gate checks are not trustworthy for Section 7 sign-off.

## Design Gaps

- **Missing dedicated integration source for AC1**: research indicates no explicit integration test file currently exists.
  - Design/reference: `2026-02-20-koe-m1-section-7-api-design.md:125`, `section-7-research.md:31`
  - Required change: add one dedicated terminal-flow integration test artifact and include it in command gate execution strategy.
  - Affected checks: T7C-03.

- **README onboarding contract currently unsatisfied (AC4)**: current README lacks required setup/run/troubleshooting content.
  - Design/reference: `2026-02-20-koe-m1-section-7-api-design.md:111`, `section-7-research.md:85`
  - Required change: expand `README.md` to complete required onboarding matrix and validate with timed cold-start run.
  - Affected checks: T7C-01, T7C-02.

**Planner note**: Section 7 can proceed to implementation planning for missing artifacts, but release sign-off remains blocked until both gaps are closed.

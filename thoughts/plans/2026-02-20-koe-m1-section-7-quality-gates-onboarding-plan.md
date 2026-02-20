---
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 7: Quality Gates, Tests, and Onboarding Readiness"
research_source: thoughts/projects/2026-02-20-koe-m1/working/section-7-research.md
test_spec_source: thoughts/projects/2026-02-20-koe-m1/working/section-7-test-spec.md
design_source: thoughts/design/2026-02-20-koe-m1-section-7-api-design.md
---

# Koe M1 Section 7 Implementation Plan

## Overview

Implement Section 7 only: close the two remaining delivery blockers by adding one dedicated terminal-flow integration test artifact and making `README.md` a self-sufficient onboarding contract for first-success in <=15 minutes.
This plan is strictly bounded to Section 7 acceptance criteria in `thoughts/projects/2026-02-20-koe-m1/spec.md:106` through `thoughts/projects/2026-02-20-koe-m1/spec.md:109` and the Section 7 design contracts in `thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:17`, `thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:55`, and `thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:90`.

## Current State Analysis

- Section 7 AC2 is already covered by existing tests across focus/audio/transcription/insertion/dependency error paths (`thoughts/projects/2026-02-20-koe-m1/working/section-7-research.md:36`).
- Section 7 AC3 command surface exists and is wired (`Makefile:1`, `Makefile:4`, `Makefile:7`, `Makefile:10`, `Makefile:13`, `pyproject.toml:17`), with `lint/typecheck/test` passing in this environment (`thoughts/projects/2026-02-20-koe-m1/working/section-7-research.md:67`).
- AC1 is only partially satisfied because no dedicated integration test source exists yet (`thoughts/projects/2026-02-20-koe-m1/working/section-7-research.md:31`, `thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:125`).
- AC4 is currently unsatisfied because `README.md` is minimal and not onboarding-complete (`README.md:1`, `thoughts/projects/2026-02-20-koe-m1/working/section-7-research.md:79`).

## Desired End State

Section 7 passes with durable proof artifacts:

1. A dedicated integration test file exists and proves terminal-flow composition across stage boundaries (not module-isolated checks only).
2. README contains all required onboarding contract sections and supports first successful transcription workflow without mandatory external docs.
3. Command gates remain explicit and verifiable (`make lint`, `make typecheck`, `make test`, `make run`) with non-silent failures in non-target environments.
4. Release sign-off includes explicit human-run target-environment checks for `make run` success and the <=15 minute cold-start onboarding drill.

Verification bundle:

```bash
make lint && make typecheck && make test
make run   # non-target env: explicit controlled failure; target env: success path
```

## Traceability

| Requirement | Source | Test Spec ID | Planned Phase |
|-------------|--------|--------------|---------------|
| AC1: module unit + dedicated integration artifact | `thoughts/projects/2026-02-20-koe-m1/spec.md:106` | T7C-03 | Phase 1, Phase 2 |
| AC2: error-path coverage for focus/mic/CUDA-insertion/dependency | `thoughts/projects/2026-02-20-koe-m1/spec.md:107` | T7A-02, T7A-03 | Phase 4 (regression defense) |
| AC3: lint/typecheck/test/run command gates | `thoughts/projects/2026-02-20-koe-m1/spec.md:108` | T7B-01..T7B-08 | Phase 4 |
| AC4: README onboarding sufficiency <=15 minutes | `thoughts/projects/2026-02-20-koe-m1/spec.md:109` | T7C-01, T7C-02 | Phase 1, Phase 3, Phase 4 |

### Key Discoveries

- `tests/test_main.py` already provides rich branch-level pipeline proofs but is not an explicit integration artifact (`tests/test_main.py:267`).
- Section 7 design already defines the exact docs contract matrix and command gate intent, so no API redesign is required (`thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:97`, `thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:66`).
- Project brief provides the concrete onboarding prerequisites to encode into README (system deps, hardware, run flow) (`docs/project-brief.md:198`, `docs/project-brief.md:202`, `docs/project-brief.md:221`, `docs/project-brief.md:267`).

## What We're NOT Doing

- No runtime behavior changes for Sections 2-6 (`src/koe/hotkey.py`, `src/koe/window.py`, `src/koe/audio.py`, `src/koe/transcribe.py`, `src/koe/insert.py`, `src/koe/notify.py`).
- No new platform scope (Wayland/macOS/CPU-only), consistent with M1 boundary (`thoughts/projects/2026-02-20-koe-m1/spec.md:13`).
- No new daemon/state model, consistent with single-run process model.
- No CI platform redesign; this section adds proofs/artifacts, not infrastructure migration.

## Implementation Approach

Test-first and evidence-first:

1. Add Section 7 red tests/artifacts that encode missing contracts (integration artifact presence and README content contract).
2. Implement only the minimum code/docs needed to satisfy those tests (`README.md` plus integration test file).
3. Re-run full command gates and produce explicit manual sign-off steps for target-runtime checks that cannot be self-validated in this environment.

Design references applied directly:

- Main gate surface remains authoritative and unchanged (`thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:17`).
- Command delivery gates and explicit failure behavior (`thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:55`, `thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:66`).
- Docs onboarding matrix and timed first-success criterion (`thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:99`, `thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:111`).

## Perspectives Synthesis

**Alignment**

- Keep Section 7 concentrated in `tests/` plus `README.md`; avoid runtime refactors.
- Prefer permanent automated checks for artifact/content contracts over one-off manual assertions.
- Preserve explicit failure semantics for command gates; no silent pass conditions.
- Keep manual-only checks narrowly scoped to target hardware/runtime outcomes.

**Divergence (resolved in this plan)**

- Whether integration proof should be folded into `tests/test_main.py` or isolated: resolved to a dedicated file to satisfy AC1/T7C-03 unambiguously.
- Whether README sufficiency is validated manually only: resolved to dual proof (automated content-contract test + manual timed onboarding drill).

**Key perspective contributions**

- DX Advocate: README must be executable as a runbook, not a pointer list.
- Architecture Purist: dedicated integration artifact avoids ambiguous interpretation of unit-vs-integration coverage.
- Validation Strategist: pair automated contract tests with clearly bounded manual target-runtime checks.
- Security Auditor: command failure paths must remain explicit and non-silent; no hidden wrapper behavior.
- Correctness Guardian: keep scope to contract proofs and avoid widening into unrelated runtime edits.

## Phase Ownership

| Phase | Owner | Responsibility |
|-------|-------|---------------|
| Phase 1-2 | `/test-implementer` | Add failing Section 7 contract tests/artifacts |
| Phase 3-4 | `/implement-plan` | Implement README/integration artifact and run gate validation |

## Phase 1: Add Section 7 Contract Tests (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 7 docs and integration contract tests`

### Overview

Create explicit tests that fail until the missing Section 7 artifacts are present and complete.

### Changes Required

#### 1. Add README onboarding content-contract test
**File**: `tests/test_readme.py` (new)
**Changes**:

- parse `README.md` as plain text and assert required onboarding contract sections/content tokens exist.
- map checks to T7C-01 required matrix categories from design.

```python
def test_readme_contains_m1_onboarding_contract_sections() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    required_tokens = [
        "System prerequisites",
        "X11",
        "make lint",
        "make typecheck",
        "make test",
        "make run",
        "Troubleshooting",
    ]
    for token in required_tokens:
        assert token in readme
```

#### 2. Add dedicated integration artifact test file
**File**: `tests/test_integration_terminal_flow.py` (new)
**Changes**:

- add one explicit integration-style test that exercises `run_pipeline` composition with minimal patching around OS boundaries.
- assert cross-module flow signals (lifecycle notifications, insertion call with transcript text, artifact + lock cleanup ordering).
- keep deterministic; avoid real device/X11 dependencies.

```python
def test_terminal_flow_integration_composes_pipeline_stages() -> None:
    # Patch only side-effect boundaries, keep orchestration real.
    outcome = run_pipeline(DEFAULT_CONFIG)
    assert outcome == "success"
```

### Success Criteria

#### Validation (required)

- [x] `tests/test_readme.py` exists and encodes T7C-01 contract checks.
- [x] `tests/test_integration_terminal_flow.py` exists and encodes T7C-03 dedicated integration proof.
- [x] New tests are red against current repo state (README currently incomplete; integration artifact absent).

#### Standard Checks

- [x] `uv run ruff check tests/test_readme.py tests/test_integration_terminal_flow.py`
- [x] `uv run pytest tests/test_readme.py tests/test_integration_terminal_flow.py` (expected red)

**Implementation Note**: Keep assertions on externally visible contracts; avoid coupling to private helper internals.

---

## Phase 2: Strengthen Integration Contract Semantics (Red)

**Owner**: `/test-implementer`
**Commit**: `test: enforce section 7 integration artifact semantics`

### Overview

Ensure the new integration artifact proves composition obligations beyond simple file presence.

### Changes Required

#### 1. Extend integration test with discriminating assertions
**File**: `tests/test_integration_terminal_flow.py`
**Changes**:

- assert notification sequence includes `recording_started -> processing -> completed`.
- assert transcription text is handed to insertion unchanged.
- assert cleanup guarantees execute (`remove_audio_artifact` and `release_instance_lock`).

#### 2. Keep branch isolation for expected failure contracts
**File**: `tests/test_main.py` (optional, only if needed)
**Changes**:

- only add assertions if integration test reveals contract ambiguity for T7A/T7B surfaces.
- avoid broad refactor; Section 7 scope is gate proof, not runtime redesign.

### Success Criteria

#### Validation (required)

- [x] Integration test fails for real contract regressions (mis-ordered notifications, missing cleanup, skipped insertion).
- [x] AC1 dedicated artifact requirement is unambiguous and durable.

#### Standard Checks

- [ ] `uv run pytest tests/test_integration_terminal_flow.py` (red until implementation phase)
- [x] `uv run pyright`

Observed result: `uv run pytest tests/test_integration_terminal_flow.py` is green with current pipeline behavior; red state remains represented by `tests/test_readme.py` until README implementation lands.

**Implementation Note**: Do not duplicate every unit assertion; integration test should prove cross-module composition signal.

---

## Phase 3: Implement Onboarding Artifact and Integration Source (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: complete section 7 onboarding docs and integration artifact`

### Overview

Implement missing artifacts so Phase 1-2 tests pass and Section 7 blockers close.

### Changes Required

#### 1. Expand README to full onboarding contract
**File**: `README.md`
**Changes**:

- add target scope and platform section (Arch Linux, X11, CUDA-only).
- add system prerequisites and hardware checklist.
- add install and verification workflow with `make lint`, `make typecheck`, `make test`, `make run`.
- add first-run success signals and troubleshooting categories required by design.
- keep README self-sufficient for first success; allow optional deep-dive links only.

#### 2. Add/finish dedicated integration test artifact
**File**: `tests/test_integration_terminal_flow.py`
**Changes**:

- finalize the integration test harness introduced in red phases so it passes reliably.
- ensure it remains explicitly integration-scoped and distinguishable from module-boundary unit tests.

### Success Criteria

#### Validation (required)

- [x] T7C-01 passes via `tests/test_readme.py`.
- [x] T7C-03 passes via `tests/test_integration_terminal_flow.py`.
- [x] Existing AC2/Surface A tests remain green.

#### Standard Checks

- [x] `uv run pytest tests/test_readme.py tests/test_integration_terminal_flow.py tests/test_main.py`
- [x] `uv run ruff check README.md tests/test_readme.py tests/test_integration_terminal_flow.py`
- [x] `uv run pyright`

**Implementation Note**: Keep README concise but complete; prioritize first-run execution clarity over narrative depth.

---

## Phase 4: Section 7 Delivery-Gate Validation and Sign-Off

**Owner**: `/implement-plan`
**Commit**: `test: validate section 7 quality gates and onboarding readiness`

### Overview

Run the full Section 7 validation bundle and explicitly separate autonomous vs human-required evidence.

### Changes Required

#### 1. Run automated gate proofs
**Files**: none (validation phase)
**Changes**:

```bash
make lint
make typecheck
make test
```

#### 2. Capture run-gate behavior in non-target environment
**Files**: none (validation phase)
**Changes**:

- run `make run` and verify explicit controlled failure behavior when prerequisites are unavailable (T7B-07).

#### 3. Define human sign-off checklist for target environment
**Files**: `README.md` (if checklist needs tightening)
**Changes**:

- include a short release-gate checklist for:
  - target-environment successful run path (`make run` exits 0 with insertion) (T7B-08)
  - timed cold-start onboarding drill <=15 minutes using only README (T7C-02)

### Success Criteria

#### Validation (required)

- [x] T7B-01, T7B-03, T7B-05 pass in automated environment.
- [x] T7B-07 demonstrates explicit non-silent behavior in non-target environment.
- [x] T7C-01 and T7C-03 pass in automated environment.

#### Manual Verification (required)

- [ ] T7B-08 target-runtime success verified by human on Arch+X11+CUDA+mic host.
- [ ] T7C-02 timed onboarding drill (<=15 minutes) completed using `README.md` only.

Reason human verification is required: this agent cannot access a real X11 desktop, microphone, or target CUDA runtime to prove physical input/output path timing.

Observed non-target run result: `make run` returned non-zero with explicit shell failure (`make: *** [Makefile:13: run] Error 1`), satisfying the non-silent failure expectation for T7B-07.

**Implementation Note**: Pause for human verification before final Section 7 release sign-off.

## Testing Strategy

Test phases land first. Implementation phases make those tests pass.

### Tests (written by `/test-implementer`)

- `tests/test_readme.py` for docs-contract matrix obligations (T7C-01).
- `tests/test_integration_terminal_flow.py` for dedicated integration artifact and composition proof (T7C-03).
- Optional targeted `tests/test_main.py` additions only when needed to eliminate contract ambiguity.

### Additional Validation (implementation phases)

- `make lint`, `make typecheck`, `make test` for Section 7 command gate continuity.
- `make run` explicit-failure validation in non-target env for T7B-07.

### Manual Testing Steps

1. On target host, follow README from clean shell and time to first successful transcription.
2. Confirm `make run` happy path: notifications sequence visible, transcript appears in focused terminal input, clipboard restore intent preserved.

## Execution Graph

**Phase Dependencies:**

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4
```

| Phase | Depends On | Can Parallelize With |
|-------|------------|---------------------|
| 1 | - | - |
| 2 | 1 | - |
| 3 | 2 | - |
| 4 | 3 | - |

**Parallel Execution Notes**

- Keep Section 7 linear to reduce merge friction in shared files (`README.md`, integration test).
- Preserve one validated commit per phase for clear rollback and review.

## References

- Section 7 requirements: `thoughts/projects/2026-02-20-koe-m1/spec.md:100`
- Section 7 research: `thoughts/projects/2026-02-20-koe-m1/working/section-7-research.md:88`
- Section 7 test spec: `thoughts/projects/2026-02-20-koe-m1/working/section-7-test-spec.md:299`
- Section 7 design: `thoughts/design/2026-02-20-koe-m1-section-7-api-design.md:114`
- M1 onboarding prerequisites and runbook context: `docs/project-brief.md:198`

---
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 4: Local CUDA Transcription"
research_source: thoughts/projects/2026-02-20-koe-m1/working/section-4-research.md
test_spec_source: thoughts/projects/2026-02-20-koe-m1/working/section-4-test-spec.md
design_source: thoughts/design/2026-02-20-section-4-transcription-api.md
---

# Koe M1 Section 4 Implementation Plan

## Overview

Implement Section 4 only: convert captured WAV artefacts into a typed transcription union (`text | empty | error`) using CUDA-local inference, then wire `run_pipeline` to branch exhaustively on that union.
This plan is test-first and bounded to Section 4 acceptance criteria in `thoughts/projects/2026-02-20-koe-m1/spec.md:64` through `thoughts/projects/2026-02-20-koe-m1/spec.md:74`, with Section 5 kept as a handoff placeholder.

## Current State Analysis

- `src/koe/transcribe.py` is still a stub (`src/koe/transcribe.py:1`).
- `run_pipeline` still raises a Section 4 placeholder at captured-audio handoff (`src/koe/main.py:89` through `src/koe/main.py:93`).
- Section 4 type surface already exists and is closed (`src/koe/types.py:56` through `src/koe/types.py:76`).
- CUDA-only policy already exists in config and startup preflight (`src/koe/config.py:15`, `src/koe/main.py:41`).
- Section 4 test specification is approved with 15 concrete obligations (`thoughts/projects/2026-02-20-koe-m1/working/section-4-test-spec.md:194`).
- Approved Section 4 API design fully defines contracts, noise-token set, orchestration branch rules, and cleanup invariants (`thoughts/design/2026-02-20-section-4-transcription-api.md:76`, `thoughts/design/2026-02-20-section-4-transcription-api.md:148`, `thoughts/design/2026-02-20-section-4-transcription-api.md:215`, `thoughts/design/2026-02-20-section-4-transcription-api.md:243`).

## Desired End State

Section 4 acceptance criteria from `thoughts/projects/2026-02-20-koe-m1/spec.md:70` through `thoughts/projects/2026-02-20-koe-m1/spec.md:74` are fully satisfied:

1. Transcription runs only on CUDA configuration and never falls back to CPU (`spec.md:70`).
2. CUDA/backend failures return typed transcription errors and route to explicit user-visible error notifications (`spec.md:71`).
3. Empty/whitespace transcripts route to `no_speech` and do not proceed to insertion (`spec.md:72`).
4. Known non-useful noise tokens are filtered and treated as non-pasteable `empty` outputs (`spec.md:73`).
5. Successful transcripts produce insertion-ready, non-empty text and proceed to Section 5 handoff (`spec.md:74`).

Verification bundle:

```bash
make lint && make typecheck && make test
```

## Traceability

| Requirement | Source | Test Spec ID | Planned Phase |
|-------------|--------|--------------|---------------|
| AC1: CUDA-required policy, no CPU fallback | `thoughts/projects/2026-02-20-koe-m1/spec.md:70` | T-06, T-10 | Phase 2, Phase 4, Phase 5 |
| AC2: CUDA/backend unavailable are explicit user-visible errors | `thoughts/projects/2026-02-20-koe-m1/spec.md:71` | T-06, T-07, T-08, T-12 | Phase 2, Phase 3, Phase 4, Phase 6 |
| AC3: Empty/whitespace does not paste and maps to no-speech feedback | `thoughts/projects/2026-02-20-koe-m1/spec.md:72` | T-03, T-11 | Phase 2, Phase 3, Phase 4, Phase 6 |
| AC4: Noise-only outputs are non-pasteable and follow no-speech path | `thoughts/projects/2026-02-20-koe-m1/spec.md:73` | T-04, T-05 | Phase 2, Phase 4 |
| AC5: Success yields insertion-ready text for downstream consumption | `thoughts/projects/2026-02-20-koe-m1/spec.md:74` | T-01, T-02, T-05, T-13 | Phase 2, Phase 3, Phase 4, Phase 6 |

### Key Discoveries

- Section 4 is currently contract-only and requires net-new runtime implementation (`src/koe/transcribe.py:1`, `src/koe/main.py:91`).
- Existing orchestration already preserves captured-branch artifact cleanup in `finally`; Section 4 must preserve this invariant (`src/koe/main.py:88` through `src/koe/main.py:95`).
- Notification and outcome enums already include `no_speech` and `error_transcription`, so Section 4 can wire behavior without extending union surfaces (`src/koe/types.py:83`, `src/koe/types.py:136`).
- The approved design resolves the research open question about noise token classification by specifying the canonical token set (`thoughts/design/2026-02-20-section-4-transcription-api.md:148`).

## What We're NOT Doing

- No Section 5 insertion implementation beyond preserving the Section 5 handoff marker.
- No changes to clipboard mechanics, `insert.py`, or paste-key behavior (Section 5 scope).
- No notification wording redesign (Section 6 scope); Section 4 only routes notification kinds and payloads.
- No model caching/persistent process behavior; per-invocation load stays consistent with single-shot runtime.
- No expansion of transcription type unions beyond the existing three-arm contract.

## Implementation Approach

Test-first, section-bounded delivery:

1. `/test-implementer` adds failing tests for Section 4 contracts from the approved test spec.
2. `/implement-plan` implements `transcribe_audio` in `src/koe/transcribe.py` and wires Section 4 branching in `src/koe/main.py`.
3. Expected failures are return-valued `TranscriptionFailure`, never silent and never CPU fallback.
4. `run_pipeline` keeps explicit orchestration and existing cleanup/lock invariants.

Design references applied directly:

- Public API and return-arm guarantees (`thoughts/design/2026-02-20-section-4-transcription-api.md:76` through `thoughts/design/2026-02-20-section-4-transcription-api.md:104`)
- Internal behavior and error shaping rules (`thoughts/design/2026-02-20-section-4-transcription-api.md:117` through `thoughts/design/2026-02-20-section-4-transcription-api.md:183`)
- Canonical M1 noise token set (`thoughts/design/2026-02-20-section-4-transcription-api.md:148` through `thoughts/design/2026-02-20-section-4-transcription-api.md:169`)
- `main.py` Section 4 branch replacement and cleanup invariants (`thoughts/design/2026-02-20-section-4-transcription-api.md:215` through `thoughts/design/2026-02-20-section-4-transcription-api.md:249`)

## Perspectives Synthesis

**Alignment**

- Keep Section 4 as a strict three-arm union with exhaustive branch handling in orchestration.
- Put noise filtering inside `transcribe_audio` so downstream stages consume already-safe text.
- Keep expected failures as typed return values to prevent exception leakage and silent failure.
- Preserve existing cleanup ordering and lock release invariants while replacing only the Section 4 placeholder.

**Divergence (resolved in this plan)**

- CUDA detection can be prechecked or inferred via model-load exceptions; resolved to outcome-based classification defined by design (`cuda_available` + message prefixes) rather than backend-specific exception identity.
- Token normalization strictness could drift by implementation; resolved by pinning exact canonical token set from design and parametrized tests.

**Key perspective contributions**

- DX Advocate: one public function in `transcribe.py` with explicit, self-documenting union outcomes.
- Architecture Purist: keep Section 4 changes isolated to `transcribe.py`, `main.py`, and tests; no unnecessary cross-module expansion.
- Validation Strategist: make all 15 Section 4 tests concrete and red-first before implementation.
- Security Auditor: no silent fallback behavior; all backend failures carry explicit typed diagnostics.
- Correctness Guardian: enforce branch-total narrowing in `run_pipeline` and invariant that text arm is insertion-ready.

## Phase Ownership

| Phase | Owner | Responsibility |
|-------|-------|---------------|
| Phase 1-3 | `/test-implementer` | Write Section 4 test contracts from approved test spec |
| Phase 4-6 | `/implement-plan` | Implement code that makes Section 4 tests pass |

## Phase 1: Section 4 Type/Static Contract Tests (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 4 type and static narrowing proofs`

### Overview

Add static and runtime coverage for Section 4 contract closure and narrowing so implementation has a strict typed target.

### Changes Required

#### 1. Add Section 4 static fixture file
**File**: `tests/section4_static_fixtures.py` (new)
**Changes**: add exhaustive narrowing and text-arm assertions matching design obligations.

```python
def t06_transcription_result_is_closed(result: TranscriptionResult) -> None:
    match result["kind"]:
        case "text":
            assert_type(result["text"], str)
        case "empty":
            return
        case "error":
            assert_type(result["error"], TranscriptionError)
        case _ as unreachable:
            assert_never(unreachable)
```

#### 2. Add/adjust runtime union shape tests only if needed
**File**: `tests/test_types.py`
**Changes**: confirm existing Section 4 arm-shape tests remain exhaustive and aligned to `TranscriptionResult` three-arm closure.

### Success Criteria

#### Validation (required)

- [x] Section 4 static fixture file exists and is discovered by `pyright`.
- [x] Transcription union closure and narrowing checks are red/green meaningful for Section 4 changes.

#### Standard Checks

- [x] `uv run ruff check tests/section4_static_fixtures.py`
- [x] `uv run pyright` (expected red before implementation phases)

**Implementation Note**: Proceed when the static/type harness is in place and failures are attributable to missing Section 4 runtime behavior.

---

## Phase 2: `transcribe_audio` Contract Tests (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 4 transcribe_audio contract tests`

### Overview

Create `tests/test_transcribe.py` with T-01..T-10 from the approved test spec, including error classification and noise filtering obligations.

### Changes Required

#### 1. Add `transcribe_audio` behavior test file
**File**: `tests/test_transcribe.py` (new)
**Changes**: implement T-01..T-10 with deterministic patches for model load/transcribe boundaries.

```python
def test_transcribe_audio_whitespace_only_returns_empty() -> None:
    # patched inference returns whitespace-only segments
    result = transcribe_audio(AudioArtifactPath(Path("/tmp/sample.wav")), DEFAULT_CONFIG)
    assert result == {"kind": "empty"}
```

#### 2. Add canonical noise-token parametrization
**File**: `tests/test_transcribe.py`
**Changes**: parametrize T-04 over exact token set from design doc.

#### 3. Add constructor-argument contract checks
**File**: `tests/test_transcribe.py`
**Changes**: T-10 verifies model constructor uses `whisper_model`, `whisper_device`, `whisper_compute_type` from config.

### Success Criteria

#### Validation (required)

- [x] T-01..T-10 are present and fail red before implementation.
- [x] T-04 token set matches design canonical values exactly.
- [x] Failure tests assert returned error arms, not raised exceptions.

#### Standard Checks

- [x] `uv run ruff check tests/test_transcribe.py`
- [x] `uv run pytest tests/test_transcribe.py` (expected red before Phase 4)

**Implementation Note**: Keep this phase strictly test-only; do not add `transcribe.py` runtime code here.

---

## Phase 3: Section 4 Orchestration Tests in `main.py` (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 4 run_pipeline orchestration tests`

### Overview

Add T-11..T-15 to `tests/test_main.py` validating Section 4 branch mapping, notification ordering, and captured-branch cleanup invariants.

### Changes Required

#### 1. Add Section 4 branch mapping tests
**File**: `tests/test_main.py`
**Changes**: add tests for `empty -> no_speech`, `error -> error_transcription`, `text -> Section 5 handoff placeholder`.

```python
with patch("koe.main.transcribe_audio", return_value={"kind": "error", "error": transcription_error}, create=True):
    assert run_pipeline(DEFAULT_CONFIG) == "error_transcription"
```

#### 2. Add ordering and cleanup-invariant tests
**File**: `tests/test_main.py`
**Changes**: add processing-before-transcription event-order assertion and parametric cleanup-on-all-transcription-outcomes assertion.

### Success Criteria

#### Validation (required)

- [x] T-11..T-15 exist and are red before implementation.
- [x] Tests prove `remove_audio_artifact` runs once for all transcription outcomes on captured path.
- [x] Tests prove `processing` notification occurs before `transcribe_audio` call.

#### Standard Checks

- [x] `uv run ruff check tests/test_main.py`
- [x] `uv run pytest tests/test_main.py` (expected red before Phase 6)

**Implementation Note**: Keep pre-existing Section 1-3 behavior assertions intact; Section 4 tests should be additive and scoped.

---

## Phase 4: Implement `src/koe/transcribe.py` API (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: implement section 4 transcription result shaping`

### Overview

Implement `transcribe_audio(artifact_path, config, /) -> TranscriptionResult` exactly per approved design and make T-01..T-10 pass.

### Changes Required

#### 1. Replace module stub with full Section 4 implementation
**File**: `src/koe/transcribe.py`
**Changes**:
- add `transcribe_audio` public function with positional-only signature
- load model from config values (`whisper_model`, `whisper_device`, `whisper_compute_type`)
- classify model-load/inference failures into typed error arms
- aggregate segments with single-space join and boundary strip
- filter exact-match canonical noise tokens
- return `{"kind": "empty"}` when normalized output is unusable
- return `{"kind": "text", "text": ...}` only when non-empty and insertion-ready

```python
def transcribe_audio(artifact_path: AudioArtifactPath, config: KoeConfig, /) -> TranscriptionResult:
    # load model on CUDA
    # map expected failures to {"kind": "error", "error": {...}}
    # normalize and filter segments
    # return empty or text arm
```

#### 2. Keep noise token set internal but contractual
**File**: `src/koe/transcribe.py`
**Changes**: define private `_NOISE_TOKENS: frozenset[str]` matching design values.

### Success Criteria

#### Validation (required)

- [x] T-01..T-10 pass in `tests/test_transcribe.py`.
- [x] Expected failure paths return `kind="error"` and do not raise.
- [x] Text-arm outputs satisfy `len(text.strip()) > 0` invariant.

#### Standard Checks

- [x] `uv run pytest tests/test_transcribe.py`
- [x] `uv run pyright`
- [x] `uv run ruff check src/ tests/`

**Implementation Note**: keep one public API (`transcribe_audio`); helper functions may be private and local to transcription concern.

---

## Phase 5: Wire Section 4 into `run_pipeline` (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: wire section 4 transcription orchestration`

### Overview

Replace the Section 4 handoff placeholder in `main.py` with actual transcription branching while preserving cleanup and lock-release invariants.

### Changes Required

#### 1. Import and call `transcribe_audio`
**File**: `src/koe/main.py`
**Changes**: add `from koe.transcribe import transcribe_audio` and call it after `send_notification("processing")` on captured path.

#### 2. Replace placeholder with exhaustive branch routing
**File**: `src/koe/main.py`
**Changes**:
- `empty` arm => send `no_speech`, return `no_speech`
- `error` arm => send `error_transcription` with payload, return `error_transcription`
- `text` arm => proceed to existing Section 5 placeholder (`NotImplementedError("Section 5 handoff: insertion")`)

```python
send_notification("processing")
transcription_result = transcribe_audio(artifact_path, config)
if transcription_result["kind"] == "empty":
    send_notification("no_speech")
    return "no_speech"
if transcription_result["kind"] == "error":
    send_notification("error_transcription", transcription_result["error"])
    return "error_transcription"
raise NotImplementedError("Section 5 handoff: insertion")
```

#### 3. Preserve existing `finally` cleanup block
**File**: `src/koe/main.py`
**Changes**: keep `remove_audio_artifact(artifact_path)` in `finally` for all captured-path transcription outcomes.

### Success Criteria

#### Validation (required)

- [x] T-11..T-15 pass in `tests/test_main.py`.
- [x] Cleanup remains guaranteed for `empty`, `error`, and `text` transcription outcomes.
- [x] Processing notification is emitted before transcription call.

#### Standard Checks

- [x] `uv run pytest tests/test_main.py`
- [x] `uv run pyright`
- [x] `uv run ruff check src/ tests/`

**Implementation Note**: keep changes scoped to Section 4 branch only; do not implement Section 5 behavior in this phase.

---

## Phase 6: Section 4 Regression Gate and Integration Proof (Green)

**Owner**: `/implement-plan`
**Commit**: `test: verify section 4 contracts and regression gates`

### Overview

Run full quality gates and ensure Section 4 changes integrate without regressing prior sections.

### Changes Required

#### 1. Execute full Section 4 + suite checks
**Files**: none (validation phase)
**Changes**: run all required commands and ensure deterministic green state.

```bash
uv run pytest tests/test_transcribe.py tests/test_main.py tests/test_types.py
uv run pyright
uv run ruff check src/ tests/
make test
```

### Success Criteria

#### Validation (required)

- [x] Section 4 test groups are green (`T-01`..`T-15`).
- [x] Full test suite remains green (Sections 1-3 unaffected).
- [x] Typecheck/lint gates remain green with no suppression creep.

#### Standard Checks

- [x] `make lint`
- [x] `make typecheck`
- [x] `make test`

**Implementation Note**: If regressions appear outside Section 4, fix only what is needed to restore existing contracts; do not widen Section 4 scope.

## Testing Strategy

Test phases are written first; implementation phases then make them pass.

### Tests (written by `/test-implementer`)

- `tests/section4_static_fixtures.py`: static closure and narrowing proofs.
- `tests/test_transcribe.py`: `T-01`..`T-10` transcription API contract coverage.
- `tests/test_main.py`: `T-11`..`T-15` orchestration branch and cleanup/ordering coverage.

### Additional Validation (implementation phases)

- `pyright` checks union narrowing and signature contract adherence.
- `ruff` keeps imports/style consistent in new module and tests.
- Full suite run ensures Section 4 wiring does not regress Section 1-3 behavior.

### Manual Testing Steps

None required for Section 4 completion. Section 4 obligations are self-verifiable through deterministic tests and quality gates.

## Execution Graph

**Phase Dependencies:**

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> Phase 6
```

| Phase | Depends On | Can Parallelize With |
|-------|------------|---------------------|
| 1 | - | - |
| 2 | 1 | - |
| 3 | 1 | 2 (partial; different test files) |
| 4 | 1,2,3 | - |
| 5 | 4 | - |
| 6 | 4,5 | - |

**Parallel Execution Notes**

- Phase 2 and Phase 3 can be authored in parallel after Phase 1 because they target different contracts/files.
- Phase 4 and Phase 5 are sequential integration steps and should not be split.
- Keep one validated commit per phase to preserve rollback clarity.

## References

- Section 4 requirements: `thoughts/projects/2026-02-20-koe-m1/spec.md:64`
- Section 4 research: `thoughts/projects/2026-02-20-koe-m1/working/section-4-research.md:38`
- Section 4 test specification: `thoughts/projects/2026-02-20-koe-m1/working/section-4-test-spec.md:33`
- Section 4 API design: `thoughts/design/2026-02-20-section-4-transcription-api.md:76`
- M1 source brief (GPU/transcription intent): `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:56`

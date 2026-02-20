---
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 3: Audio Capture and Temporary Artefact Lifecycle"
research_source: thoughts/projects/2026-02-20-koe-m1/working/section-3-research.md
test_spec_source: thoughts/projects/2026-02-20-koe-m1/working/section-3-test-spec.md
design_source: thoughts/design/2026-02-20-koe-m1-section-3-api-design.md
---

# Koe M1 Section 3 Implementation Plan

## Overview

Implement Section 3 only: microphone capture, temporary WAV artefact creation, typed capture outcomes, and artefact cleanup lifecycle.
This plan follows the approved Section 3 API design and Section 3 test spec, and keeps transcription/insertion/notification-copy polish out of scope.

## Current State Analysis

- `src/koe/audio.py` is a stub with no runtime logic (`src/koe/audio.py:1`).
- `run_pipeline` still stops at a Section 3 placeholder (`src/koe/main.py:76`).
- `types.py` lacks Section 3 capture union contracts (`src/koe/types.py:39`, `src/koe/types.py:84`).
- `NotificationKind` does not include `"no_speech"` (`src/koe/types.py:66`).
- Existing Pyright static fixtures are exhaustive over `NotificationKind` and will break unless updated atomically (`tests/section1_static_fixtures.py:51`, `tests/section2_static_fixtures.py:20`).
- `tests/test_audio.py` and `tests/section3_static_fixtures.py` do not exist.

## Desired End State

Section 3 acceptance criteria from `thoughts/projects/2026-02-20-koe-m1/spec.md:58` through `thoughts/projects/2026-02-20-koe-m1/spec.md:62` are met:

1. Capture path uses configured Whisper-compatible defaults (16kHz, mono, float32 intent) and writes a temporary WAV artefact.
2. Microphone unavailable/inaccessible failures are typed audio errors and route to explicit user-visible `error_audio` outcome.
3. WAV write failures are typed audio errors and do not continue to Section 4 handoff.
4. Temporary artefacts are cleaned up on captured-branch completion and downstream failures.
5. Zero-duration/near-empty capture returns explicit `no_speech` behavior.

Verification bundle:

```bash
make lint && make typecheck && make test
```

## Traceability

| Requirement | Source | Test Spec ID | Planned Phase |
|-------------|--------|--------------|---------------|
| AC1: 16kHz/float32 capture defaults + temp WAV artefact | `thoughts/projects/2026-02-20-koe-m1/spec.md:58` | T-06 | Phase 2, Phase 5 |
| AC2: mic unavailable/inaccessible => explicit error + safe exit | `thoughts/projects/2026-02-20-koe-m1/spec.md:59` | T-08, T-13 | Phase 2, Phase 3, Phase 5, Phase 6 |
| AC3: WAV creation/write failure => typed error + no continuation | `thoughts/projects/2026-02-20-koe-m1/spec.md:60` | T-09, T-13 | Phase 2, Phase 3, Phase 5, Phase 6 |
| AC4: artefacts removed on success and handled error exits | `thoughts/projects/2026-02-20-koe-m1/spec.md:61` | T-10, T-11, T-14, T-15, T-16 | Phase 2, Phase 3, Phase 5, Phase 6 |
| AC5: zero-duration/near-empty => no-speech behavior | `thoughts/projects/2026-02-20-koe-m1/spec.md:62` | T-02, T-04, T-07, T-12 | Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, Phase 6 |

### Key Discoveries

- Section 3 runtime is fully unimplemented and therefore must be introduced as net-new code (`src/koe/audio.py:1`, `src/koe/main.py:76`).
- Section 3 design contracts are approved and sufficient; no blocking API design gap remains (`thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:67`, `thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:97`).
- Existing fixture exhaustiveness means `NotificationKind` updates require atomic fixture updates to keep `pyright` green (`tests/section1_static_fixtures.py:51`, `tests/section2_static_fixtures.py:20`).
- Cleanup safety pattern already exists in lock lifecycle and should be mirrored for audio artefacts (`src/koe/hotkey.py:59`, `src/koe/main.py:77`).

## What We're NOT Doing

- No Section 4 transcription implementation beyond preserving a handoff marker.
- No Section 5 insertion/clipboard logic.
- No Section 6 notification copy redesign; Section 3 only adds notification kinds/outcomes required for flow control.
- No daemon/background process or multi-invocation recorder loop.
- No Wayland or non-X11 behavior.

## Implementation Approach

Test-first, section-bounded delivery:

1. `/test-implementer` writes Section 3 tests in three focused groups (types/static, audio module, orchestration).
2. `/implement-plan` makes each group pass in smallest validated increments.
3. All expected failures are represented as typed return unions, not raised runtime exceptions.
4. `main.py` keeps explicit orchestration and ownership boundaries:
   - `audio.py` owns capture + artefact creation + best-effort artefact deletion helper.
   - `main.py` owns captured-branch cleanup timing via inner `finally` around downstream handoff.

Design references applied directly:

- Type additions (`thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:37` through `thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:63`)
- `audio.py` API contracts (`thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:67` through `thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:92`)
- `main.py` branching and cleanup ownership (`thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:97` through `thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:129`)

## Perspectives Synthesis

**Alignment**

- Keep Section 3 as a closed three-arm discriminated union at both audio and orchestration boundaries.
- Treat `NotificationKind` extension plus static fixture updates as an atomic change set.
- Keep cleanup non-raising and branch-exact (cleanup iff captured arm).
- Preserve smallest testable increments: type surface first, then module behavior, then orchestration.

**Divergence (resolved in this plan)**

- Recording-stop semantics are broader milestone behavior; Section 3 implementation here is bounded to deterministic single-call capture behavior that satisfies AC and test-spec contracts, without adding daemon-like control flow.
- Notification text specificity is deferred to Section 6; Section 3 validates notification routing and kind usage only.

**Key perspective contributions**

- DX Advocate: atomic `NotificationKind` + fixture updates and strict phase boundaries to avoid red/green thrash.
- Architecture Purist: preserve explicit ownership split (`audio.py` create/helper, `main.py` cleanup timing).
- Validation Strategist: enforce red-first sequencing and explicit command gates per phase.
- Security Auditor: require safe temp artefact lifecycle handling and non-leaking cleanup behavior via tests.
- Correctness Guardian: maintain discriminated unions, exhaustive narrowing, and nested `finally` layout invariants.

## Phase Ownership

| Phase | Owner | Responsibility |
|-------|-------|---------------|
| Phase 1-3 | `/test-implementer` | Write Section 3 test contracts from approved spec |
| Phase 4-6 | `/implement-plan` | Implement code to satisfy existing Section 3 tests |

## Phase 1: Section 3 Type and Static Contract Tests (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 3 type-surface proofs`

### Overview

Add runtime shape tests and Pyright static fixtures proving Section 3 type vocabulary and narrowing contracts.

### Changes Required

#### 1. Add runtime type-shape tests
**File**: `tests/test_types.py`
**Changes**: add T-01, T-02, T-03, T-04 runtime checks for new `AudioCapture*` contracts.

```python
check_type({"kind": "captured", "artifact_path": AudioArtifactPath(Path("/tmp/a.wav"))}, AudioCapture)
check_type({"kind": "empty"}, AudioEmpty)
check_type(
    {"kind": "error", "error": {"category": "audio", "message": "mic busy", "device": None}},
    AudioCaptureFailed,
)
```

#### 2. Add Section 3 static fixture file
**File**: `tests/section3_static_fixtures.py` (new)
**Changes**: add T-04 exhaustive narrowing on `AudioCaptureResult` and T-05 literal acceptance for `"no_speech"`.

```python
def t04_audio_capture_result_is_closed(result: AudioCaptureResult) -> None:
    match result["kind"]:
        case "captured":
            assert_type(result["artifact_path"], AudioArtifactPath)
        case "empty":
            return
        case "error":
            assert_type(result["error"], AudioError)
        case _ as unreachable:
            assert_never(unreachable)
```

### Success Criteria

#### Validation (required)

- [x] T-01..T-05 test code exists and fails for missing Section 3 type symbols before implementation.
- [x] Static fixture file `tests/section3_static_fixtures.py` is discovered by `pyright` and participates in typecheck.

#### Standard Checks

- [x] `uv run ruff check tests/`
- [x] `uv run pyright` (expected red before Phase 4)

**Implementation Note**: Proceed once tests are written and failing only due to unimplemented Section 3 contracts.

---

## Phase 2: Audio Module Contract Tests (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 3 audio module contract tests`

### Overview

Create `audio.py` contract tests for capture success, empty branch, microphone errors, WAV write errors, and cleanup helper behavior.

### Changes Required

#### 1. Add audio test file
**File**: `tests/test_audio.py` (new)
**Changes**: add T-06..T-11 with patched dependencies and temp-path isolation.

```python
def test_capture_audio_maps_microphone_unavailable_to_audio_error() -> None:
    with patch("koe.audio.sounddevice.rec", side_effect=sounddevice.PortAudioError("no input")):
        result = capture_audio(DEFAULT_CONFIG)
    assert result["kind"] == "error"
    assert result["error"]["category"] == "audio"
```

#### 2. Add WAV-write-failure cleanup proof
**File**: `tests/test_audio.py`
**Changes**: extend T-09 assertion to verify no lingering artefact path is left on WAV write failure.

### Success Criteria

#### Validation (required)

- [x] T-06..T-11 test code exists and is red before implementation.
- [x] T-09 proves write-failure path returns typed error and leaves no persisted artefact.

#### Standard Checks

- [x] `uv run ruff check tests/test_audio.py`
- [x] `uv run pytest tests/test_audio.py` (expected red before Phase 5)

**Implementation Note**: Proceed once tests are committed and failing only for missing `audio.py` implementation.

---

## Phase 3: Section 3 Orchestration Tests (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 3 pipeline orchestration tests`

### Overview

Add `run_pipeline` tests for empty/error/captured branches, notification ordering, and captured-branch-only cleanup ownership.

### Changes Required

#### 1. Add orchestration branch tests
**File**: `tests/test_main.py`
**Changes**: add T-12..T-16.

```python
def test_run_pipeline_maps_empty_capture_to_no_speech() -> None:
    with (
        patch("koe.main.capture_audio", return_value={"kind": "empty"}, create=True),
        patch("koe.main.send_notification", create=True) as notify_mock,
    ):
        assert run_pipeline(DEFAULT_CONFIG) == "no_speech"
    notify_mock.assert_any_call("recording_started")
    notify_mock.assert_any_call("no_speech")
```

#### 2. Preserve deterministic stage-order test behavior
**File**: `tests/test_main.py`
**Changes**: patch `capture_audio` in existing stage-order test so Section 2 order assertions remain isolated from real audio side effects.

### Success Criteria

#### Validation (required)

- [x] T-12..T-16 tests exist and are red before implementation.
- [x] Stage-order test remains deterministic and does not touch real audio backends.

#### Standard Checks

- [x] `uv run ruff check tests/test_main.py`
- [x] `uv run pytest tests/test_main.py` (expected red before Phase 6)

**Implementation Note**: Proceed once orchestration tests are present and failing only for missing Section 3 runtime behavior.

---

## Phase 4: Atomic Type + Fixture Integration (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: add section 3 capture type contracts`

### Overview

Implement Section 3 type vocabulary and `NotificationKind` extension as one atomic change with static fixture updates to keep `pyright` green.

### Changes Required

#### 1. Add Section 3 capture contracts
**File**: `src/koe/types.py`
**Changes**: add `AudioCapture`, `AudioEmpty`, `AudioCaptureFailed`, and `AudioCaptureResult`; extend `NotificationKind` with `"no_speech"`.

#### 2. Keep static fixtures exhaustive
**Files**:
- `tests/section1_static_fixtures.py`
- `tests/section2_static_fixtures.py`
**Changes**: add `"no_speech"` match arms for existing exhaustive `NotificationKind` checks.

### Success Criteria

#### Validation (required)

- [x] T-01..T-05 pass.
- [x] No Pyright regressions from `NotificationKind` literal extension.

#### Standard Checks

- [x] `uv run pyright`
- [x] `uv run pytest tests/test_types.py`
- [x] `uv run ruff check src/ tests/`

**Implementation Note**: This phase is atomic; do not split type update and fixture update across commits.

---

## Phase 5: Implement `audio.py` Capture + Cleanup API (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: implement section 3 audio capture lifecycle`

### Overview

Implement capture and artefact lifecycle behavior in `audio.py` to satisfy T-06..T-11.

### Changes Required

#### 1. Implement `capture_audio`
**File**: `src/koe/audio.py`
**Changes**: implement capture happy/empty/error arms using `KoeConfig` capture defaults and typed `AudioError` shaping.

```python
def capture_audio(config: KoeConfig, /) -> AudioCaptureResult:
    # success -> {"kind": "captured", "artifact_path": AudioArtifactPath(...)}
    # near-empty -> {"kind": "empty"}
    # expected failure -> {"kind": "error", "error": AudioError}
```

#### 2. Implement `remove_audio_artifact`
**File**: `src/koe/audio.py`
**Changes**: non-raising, idempotent best-effort deletion helper safe for missing artefacts and non-fatal OS errors.

### Success Criteria

#### Validation (required)

- [x] T-06..T-11 pass.
- [x] WAV write failure path returns typed error and does not leak temp artefacts.

#### Standard Checks

- [x] `uv run pytest tests/test_audio.py`
- [x] `uv run pyright`
- [x] `uv run ruff check src/ tests/`

**Implementation Note**: keep capture failures as `AudioCaptureFailed` return arms, not raised exceptions.

---

## Phase 6: Implement Section 3 Orchestration in `run_pipeline` (Green)

**Owner**: `/implement-plan`
**Commit**: `feat: wire section 3 capture orchestration`

### Overview

Replace the Section 3 placeholder in `run_pipeline` with branch-exact capture handling and captured-branch cleanup `finally`.

### Changes Required

#### 1. Wire capture branching and cleanup ownership
**File**: `src/koe/main.py`
**Changes**:
- import `capture_audio` and `remove_audio_artifact`
- send `recording_started`
- branch on `capture_result["kind"]`
- `empty` => notify `no_speech`, return `no_speech`
- `error` => notify `error_audio`, return `error_audio`
- `captured` => send `processing`, then Section 4 handoff marker in inner `try/finally` with `remove_audio_artifact(artifact_path)`

```python
send_notification("recording_started")
capture_result = capture_audio(config)

if capture_result["kind"] == "empty":
    send_notification("no_speech")
    return "no_speech"

if capture_result["kind"] == "error":
    send_notification("error_audio", capture_result["error"])
    return "error_audio"

artifact_path = capture_result["artifact_path"]
try:
    send_notification("processing")
    raise NotImplementedError("Section 4 handoff: transcription")
finally:
    remove_audio_artifact(artifact_path)
```

### Success Criteria

#### Validation (required)

- [x] T-12..T-16 pass.
- [x] Captured-branch cleanup always runs in `finally` and only for captured branch.
- [x] Empty and error branches never call artefact cleanup.

#### Standard Checks

- [x] `uv run pytest tests/test_main.py`
- [x] `make lint`
- [x] `make typecheck`
- [x] `make test`

**Implementation Note**: preserve nested `finally` layout so lock release remains outermost cleanup and audio artefact cleanup remains captured-branch scoped.

## Testing Strategy

Test phases come first. Implementation phases only make those tests pass.

### Tests (written by `/test-implementer`)

- `tests/test_types.py`: T-01, T-02, T-03, T-04
- `tests/section3_static_fixtures.py`: T-04 static narrowing, T-05 literal inclusion
- `tests/test_audio.py`: T-06, T-07, T-08, T-09, T-10, T-11
- `tests/test_main.py`: T-12, T-13, T-14, T-15, T-16

### Additional Validation (implementation phases)

- Typecheck and lint on every phase boundary.
- `tests/section1_static_fixtures.py` and `tests/section2_static_fixtures.py` stay exhaustive after `NotificationKind` extension.
- Full-suite regression gate at end of Phase 6.

### Manual Testing Steps

None required for Section 3 completion. All contracts are self-verifiable through unit/static tests and quality gates.

## Execution Graph

**Phase Dependencies:**

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> Phase 6
```

| Phase | Depends On | Can Parallelize With |
|-------|------------|---------------------|
| 1 | - | - |
| 2 | 1 | - |
| 3 | 1 | 2 (partial, different files) |
| 4 | 1,2,3 | - |
| 5 | 4 | - |
| 6 | 4,5 | - |

**Parallel Execution Notes**

- Phase 2 and Phase 3 test-writing can run in parallel after Phase 1 because they target different files.
- Phase 4 must remain sequential and atomic due to cross-file `NotificationKind` exhaustiveness coupling.
- Phase 6 is sequential because it integrates all prior API surfaces.

## References

- Section 3 requirements: `thoughts/projects/2026-02-20-koe-m1/spec.md:52`
- Section 3 research: `thoughts/projects/2026-02-20-koe-m1/working/section-3-research.md:42`
- Section 3 API design: `thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:34`
- Section 3 test spec: `thoughts/projects/2026-02-20-koe-m1/working/section-3-test-spec.md:33`
- M1 source brief (audio/temp lifecycle context): `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:70`

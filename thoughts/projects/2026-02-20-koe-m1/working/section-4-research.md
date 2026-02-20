---
date: 2026-02-20T15:21:58+11:00
researcher: opencode
git_commit: f49ce20
branch: master
repository: s2bomb/koe
topic: "Section 4 of thoughts/projects/2026-02-20-koe-m1/spec.md. Focus: Local Transcription on GPU"
tags: [research, codebase, koe, transcription, cuda, section-4]
status: complete
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 4: Local CUDA Transcription"
last_updated: 2026-02-20
last_updated_by: opencode
---

# Research: Section 4 Local Transcription on GPU

**Date**: 2026-02-20T15:21:58+11:00
**Researcher**: opencode
**Git Commit**: f49ce20
**Branch**: master
**Repository**: s2bomb/koe

## Research Question

Section 4 of `thoughts/projects/2026-02-20-koe-m1/spec.md` with focus on Local CUDA Transcription, including full acceptance-criteria coverage and concrete file:line references.

## Summary

Section 4 runtime logic is not implemented yet: `src/koe/transcribe.py:1` is a module stub with no functions.

The codebase does already define and test the Section 4 contracts around:
- CUDA-required configuration and preflight rejection of non-CUDA (`src/koe/config.py:15`, `src/koe/main.py:41`)
- Transcription result/error type shapes (`src/koe/types.py:56`, `src/koe/types.py:65`, `src/koe/types.py:76`)
- Notification and outcome vocabulary for transcription/no-speech paths (`src/koe/types.py:83`, `src/koe/types.py:136`)
- Pipeline handoff boundary where Section 4 will be wired (`src/koe/main.py:89`)

## Acceptance Criteria Coverage (Section 4)

### AC1: Transcription executes with CUDA-required policy; CPU fallback is treated as error

**What exists now**
- CUDA-only type contract is enforced in config schema: `whisper_device: Literal["cuda"]` (`src/koe/config.py:15`).
- Default config value is CUDA (`src/koe/config.py:29`).
- Startup preflight rejects non-CUDA config before pipeline proceeds (`src/koe/main.py:41`, `src/koe/main.py:47`).
- Transcription runtime itself is not implemented (`src/koe/transcribe.py:1`).

**Test evidence**
- Dependency preflight test passes `{"whisper_device": "cpu"}` and expects dependency failure (`tests/test_main.py:63`, `tests/test_main.py:89`).
- Static type fixture asserts whisper device remains `Literal["cuda"]` (`tests/section1_static_fixtures.py:119`).

### AC2: CUDA unavailable or transcription backend unavailable states are explicit, user-visible errors

**What exists now**
- Transcription error contract includes CUDA availability flag (`src/koe/types.py:65`, `src/koe/types.py:68`).
- Error notification kind for transcription exists (`src/koe/types.py:90`).
- Pipeline outcome includes transcription error (`src/koe/types.py:142`) and maps to exit code 1 (`src/koe/main.py:107`, `src/koe/main.py:111`).
- Notification transport path exists and does not raise (`src/koe/notify.py:12`, `src/koe/notify.py:22`).
- Runtime detection/emission of transcription backend failures is not implemented because `transcribe.py` is a stub (`src/koe/transcribe.py:1`).

**Test evidence**
- Transcription failure shape requires nested `TranscriptionError` including `cuda_available` (`tests/test_types.py:74`, `tests/test_types.py:78`).
- Exit mapping includes `error_transcription -> 1` (`tests/test_main.py:107`, `tests/test_main.py:113`).

### AC3: Empty/whitespace transcription does not paste; user receives "no speech detected" feedback

**What exists now**
- No-speech transcription arm exists: `TranscriptionNoSpeech(kind="empty")` (`src/koe/types.py:61`).
- Transcription union is explicit three-arm contract (`src/koe/types.py:76`).
- No-speech notification kind and outcome exist (`src/koe/types.py:87`, `src/koe/types.py:139`).
- Exit mapping already handles no-speech as non-success (`src/koe/main.py:104`, `src/koe/main.py:111`).
- Section 4 no-speech runtime branch is not yet wired in `run_pipeline`; handoff currently raises NotImplementedError (`src/koe/main.py:91`).

**Adjacent implemented behavior**
- Audio-stage empty capture already uses the same feedback path: notify `no_speech` and return `no_speech` (`src/koe/main.py:80`, `src/koe/main.py:82`).

**Test evidence**
- `TranscriptionNoSpeech` shape and `TranscriptionResult` membership are tested (`tests/test_types.py:68`, `tests/test_types.py:94`).
- Audio-stage no-speech notification path is tested (`tests/test_main.py:267`, `tests/test_main.py:292`).

### AC4: Non-useful transcription tokens from silence/noise are non-pasteable and follow same feedback path

**What exists now**
- Section requirement is explicitly stated in project spec (`thoughts/projects/2026-02-20-koe-m1/spec.md:73`).
- Transcription domain model has no separate "noise token" arm; only `text | empty | error` (`src/koe/types.py:76`).
- Therefore, current type contract implies non-useful tokens map to the existing `empty` arm (`src/koe/types.py:61`).
- Token filtering/normalization logic is not implemented because `transcribe.py` has no runtime code (`src/koe/transcribe.py:1`).

### AC5: Successful transcription returns text suitable for insertion step consumption

**What exists now**
- Success transcription payload is plain string text (`src/koe/types.py:56`, `src/koe/types.py:58`).
- Downstream insertion error includes `transcript_text: str`, which is the value insertion operates on (`src/koe/types.py:108`, `src/koe/types.py:111`).
- Section 4 handoff point in pipeline is present but unimplemented (`src/koe/main.py:89`, `src/koe/main.py:91`).

**Test evidence**
- `TranscriptionText` shape enforced (`tests/test_types.py:62`, `tests/test_types.py:63`).
- Insertion error requires transcript text (`tests/test_types.py:139`, `tests/test_types.py:179`).

## Runtime Flow and Section 4 Handoff

- `run_pipeline` proceeds through preflight, lock, X11 checks, focus checks, and audio capture before Section 4 (`src/koe/main.py:55`, `src/koe/main.py:78`).
- On captured audio, pipeline sends processing notification and reaches Section 4 handoff (`src/koe/main.py:90`, `src/koe/main.py:91`).
- Audio artefact cleanup is guaranteed in `finally` around handoff (`src/koe/main.py:92`, `src/koe/main.py:93`).

```python
# src/koe/main.py:88-93
artifact_path = capture_result["artifact_path"]
try:
    send_notification("processing")
    raise NotImplementedError("Section 4 handoff: transcription")
finally:
    remove_audio_artifact(artifact_path)
```

## Code References & Examples

- `src/koe/transcribe.py:1` - Section 4 module is currently a one-line stub.
- `src/koe/config.py:15` - CUDA-only config type (`Literal["cuda"]`).
- `src/koe/main.py:41` - Runtime preflight enforcement for non-CUDA config.
- `src/koe/types.py:65` - `TranscriptionError` with `cuda_available` signal.
- `src/koe/types.py:76` - Three-armed `TranscriptionResult` contract.
- `tests/test_types.py:74` - Runtime shape test for transcription failure payload.
- `tests/test_main.py:67` - Runtime test for startup dependency/cuda preflight behavior.

## Architecture Documentation (Current State)

- Section 4 behavior is currently contract-first: types + orchestration boundary + tests for schema/exit mapping, with implementation deferred.
- Pipeline-wide outcome and notification enums are already closed sets used by match/assert-never style handling (`src/koe/main.py:98`, `tests/section1_static_fixtures.py:51`).
- Transcription integrates into an existing linear, single-shot pipeline structure that already enforces lock lifecycle and temp artefact cleanup (`src/koe/main.py:60`, `src/koe/main.py:95`).

## Historical Context (from thoughts/)

- Section 4 acceptance criteria are defined in project spec (`thoughts/projects/2026-02-20-koe-m1/spec.md:64`).
- Decision register marks CUDA-required policy for M1 (`thoughts/specs/2026-02-20-koe-m1-spec.md:62`).
- Spec also states empty/whitespace output should route to no-speech behavior (`thoughts/specs/2026-02-20-koe-m1-spec.md:108`).
- Prior project research document records that transcription runtime was not yet implemented at that time (`thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md:40`).

## Related Research

- `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-3-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-4-historical-context.md`

## Open Questions

- Which exact token set/rules classify "non-useful transcription tokens" for M1 normalization in Section 4 implementation (`thoughts/projects/2026-02-20-koe-m1/spec.md:73`).

## Assumptions & Risks

- **Assumption**: `hack/spec_metadata.sh` is unavailable in this branch, so document metadata was gathered from git/date commands.
  - **Why**: command returned `No such file or directory`.
  - **Validation approach**: add/restore script if metadata automation is required for this project workspace.
  - **Risk if wrong**: metadata field values may differ from expected script-generated formatting.

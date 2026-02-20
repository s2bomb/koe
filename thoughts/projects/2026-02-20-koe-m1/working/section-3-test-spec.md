---
title: "Section 3 Audio Capture and Temporary Artefact Lifecycle Test Specification"
date: 2026-02-20
status: approved
design_source: "thoughts/design/2026-02-20-koe-m1-section-3-api-design.md"
spec_source: "thoughts/projects/2026-02-20-koe-m1/spec.md"
research_source: "thoughts/projects/2026-02-20-koe-m1/working/section-3-research.md"
project_section: "Section 3: Audio Capture and Temporary Artefact Lifecycle"
---

# Test Specification: Section 3 Audio Capture and Temporary Artefact Lifecycle

## Purpose

This document defines proof obligations for the Section 3 API surface only: `audio.py` capture/cleanup contracts, `types.py` Section 3 capture-result vocabulary, and `main.py` orchestration behavior at the Section 3 boundary. Every test maps to an explicit Section 3 design contract, with explicit error-path coverage.

## Test Infrastructure

**Framework**: `pytest` + `typeguard` runtime checks, plus Pyright static checks.
**Test location**: root `tests/` directory using `test_<module>.py` naming (`tests/test_audio.py`, `tests/test_main.py`, `tests/test_types.py`, and static fixture files for Pyright checks).
**Patterns to follow**:
- Runtime shape checks: `check_type(...)` and `pytest.raises(TypeCheckError)` (`tests/test_types.py:30-55`, `tests/test_types.py:123-170`).
- Exhaustive literal/union mapping with `pytest.mark.parametrize` (`tests/test_main.py:97-112`, `tests/test_types.py:90-115`).
- Orchestration boundary isolation via stacked `unittest.mock.patch` and `assert_not_called` (`tests/test_main.py:115-138`).
- Call-order assertions via event-log side effects (`tests/test_main.py:197-254`).
**Utilities available**: no shared `conftest.py`; local helpers per file (`tests/test_window.py:12-18`, `tests/test_hotkey.py:9-10`).
**Run command**: `uv run pytest tests/` with quality gates `uv run pyright` and `uv run ruff check src/ tests/`.

## API Surface

Contracts under test, extracted from the design doc:

| Contract | Signature / Type | Design Reference | Tests |
|----------|-------------------|------------------|-------|
| `AudioCapture` | `TypedDict{kind:"captured", artifact_path: AudioArtifactPath}` | `...section-3-api-design.md:37-40` | T-01 |
| `AudioEmpty` | `TypedDict{kind:"empty"}` | `...section-3-api-design.md:42-44` | T-02 |
| `AudioCaptureFailed` | `TypedDict{kind:"error", error: AudioError}` | `...section-3-api-design.md:46-49` | T-03 |
| `AudioCaptureResult` | `AudioCapture | AudioEmpty | AudioCaptureFailed` | `...section-3-api-design.md:51` | T-04 |
| `NotificationKind` extension | includes literal `"no_speech"` | `...section-3-api-design.md:54-63` | T-05 |
| `capture_audio` | `(config: KoeConfig, /) -> AudioCaptureResult` | `...section-3-api-design.md:67-75` | T-06, T-07, T-08, T-09 |
| `capture_audio` error shaping | mic unavailable / wav write failed map to typed `AudioError` | `...section-3-api-design.md:84-92` | T-08, T-09 |
| `remove_audio_artifact` | `(artifact_path: AudioArtifactPath, /) -> None`, non-raising, safe if missing | `...section-3-api-design.md:77-81` | T-10, T-11 |
| `run_pipeline` Section 3 branching | `empty -> no_speech`, `error -> error_audio`, `captured -> processing handoff` | `...section-3-api-design.md:97-115` | T-12, T-13, T-14 |
| `run_pipeline` cleanup ownership invariant | cleanup called iff captured, in `finally`, non-masking | `...section-3-api-design.md:117-129` | T-14, T-15, T-16 |
| `run_pipeline` notification ordering | `recording_started` then `processing` on captured path | `...section-3-api-design.md:98-112`, `:165-169` | T-14 |

## Proof Obligations

### `types.py` Section 3 contracts

#### T-01: `AudioCapture` enforces captured-arm shape with required artefact path

**Contract**: Captured arm is represented only by `kind="captured"` plus `artifact_path: AudioArtifactPath`.
**Setup**: Runtime `check_type` with valid captured value and invalid value missing `artifact_path`.
**Expected**: Valid captured value accepted; missing-field shape rejected.
**Discriminating power**: Catches implementations returning untyped captured dicts or path as free-form string.

#### T-02: `AudioEmpty` enforces explicit empty-arm shape

**Contract**: Near-empty branch is a first-class `{"kind": "empty"}` variant.
**Setup**: Runtime `check_type` for `{"kind": "empty"}` and invalid wrong-literal variant.
**Expected**: Empty arm accepted; unknown kind rejected.
**Discriminating power**: Catches collapsing no-speech into generic error/None paths.

#### T-03: `AudioCaptureFailed` enforces typed audio-error payload

**Contract**: Error arm requires `kind="error"` and `error: AudioError`.
**Setup**: Runtime `check_type` with valid audio error and invalid payload missing `device`.
**Expected**: Valid error arm accepted; incomplete payload rejected.
**Discriminating power**: Catches weakening to opaque string errors that break notification category routing.

#### T-04: `AudioCaptureResult` is exactly three-armed and exhaustively narrowable

**Contract**: Union accepts only `captured | empty | error`.
**Setup**: Parametrized runtime `check_type` for three valid variants plus invalid `{"kind": "unexpected"}`; Pyright static fixture with exhaustive `match` + `assert_never`.
**Expected**: Three valid variants accepted; unknown variant rejected; static exhaustiveness holds.
**Discriminating power**: Catches accidental widening to generic dict or dropped union arm.

#### T-05: `NotificationKind` includes Section 3 literal `"no_speech"`

**Contract**: Notification vocabulary is closed and now includes no-speech feedback.
**Setup**: Pyright literal assignment checks for `"no_speech"` and one invalid literal.
**Expected**: `"no_speech"` type-checks; invalid literal fails.
**Discriminating power**: Catches omission of required explicit no-speech feedback channel.

### `audio.py` contracts

#### T-06: `capture_audio` returns captured variant with temporary WAV artefact on happy path

**Contract**: Successful capture returns `{"kind": "captured", "artifact_path": AudioArtifactPath}`.
**Setup**: Patch microphone and WAV-writing dependencies for deterministic success; use config defaults (`sample_rate=16000`, `audio_format="float32"`, mono channel) and isolated temp dir.
**Expected**: Returned result is captured arm with path under configured temp dir; WAV writer invoked with configured capture parameters.
**Discriminating power**: Catches implementations that do not persist artefact, ignore config defaults, or return untyped success payload.

#### T-07: `capture_audio` routes zero-duration/near-empty capture to empty variant

**Contract**: No usable recorded signal returns `{"kind": "empty"}` and not an error.
**Setup**: Patch capture backend to produce zero-length (and one near-empty representative) sample buffer.
**Expected**: Function returns empty arm; no WAV artefact is reported.
**Discriminating power**: Catches implementations that try to transcribe silence or misclassify no-speech as audio failure.

#### T-08: `capture_audio` maps microphone unavailable/inaccessible to typed audio error

**Contract**: Mic failure returns `{"kind": "error", "error": {"category": "audio", "message": "microphone unavailable: ...", "device": <str|None>}}`.
**Setup**: Patch capture backend to raise microphone/device-unavailable failure.
**Expected**: Error arm returned with `category="audio"`, message prefixed with microphone-unavailable context, and `device` preserved or `None`.
**Discriminating power**: Catches exception leakage and wrong-category error shaping.

#### T-09: `capture_audio` maps WAV creation/write failure to typed audio error

**Contract**: WAV persistence failure returns `{"kind": "error", "error": {"category": "audio", "message": "wav write failed: ...", "device": None}}`.
**Setup**: Patch WAV creation/write call to raise I/O failure after successful capture acquisition.
**Expected**: Error arm returned with category `audio`, message prefixed `wav write failed:`, and `device is None`.
**Discriminating power**: Catches partial-write crashes and failure to distinguish capture failure from persistence failure.

#### T-10: `remove_audio_artifact` deletes existing temporary artefact without raising

**Contract**: Cleanup removes existing file and returns `None`.
**Setup**: Create temp WAV file path wrapped as `AudioArtifactPath`, call `remove_audio_artifact`.
**Expected**: Function returns `None`; file is removed.
**Discriminating power**: Catches no-op cleanup implementations that leak artefacts.

#### T-11: `remove_audio_artifact` is non-raising and safe for missing file

**Contract**: Cleanup is best-effort and idempotent when path no longer exists.
**Setup**: Call `remove_audio_artifact` on absent path; optionally call twice on same path.
**Expected**: No exception in any call.
**Discriminating power**: Catches cleanup exceptions that would mask pipeline outcomes in `finally`.

### `main.py` Section 3 orchestration contracts

#### T-12: `run_pipeline` maps empty capture to `no_speech` with explicit notification and no cleanup

**Contract**: Empty capture path sends `no_speech`, returns `"no_speech"`, and does not call artefact cleanup.
**Setup**: Patch Section 2 preconditions to pass; patch `capture_audio` to return `{"kind": "empty"}`; patch `send_notification` and `remove_audio_artifact` spies.
**Expected**: Notification sequence includes `recording_started` then `no_speech`; outcome is `"no_speech"`; `remove_audio_artifact` not called.
**Discriminating power**: Catches silent no-speech exits and accidental cleanup call without artefact ownership.

#### T-13: `run_pipeline` maps audio capture error to `error_audio` and does not continue to processing

**Contract**: Error capture path sends `error_audio` with payload, returns `"error_audio"`, and skips processing handoff.
**Setup**: Patch preconditions to pass; patch `capture_audio` to return `{"kind": "error", "error": AudioError}`; patch notification/cleanup spies.
**Expected**: `send_notification("error_audio", error)` is called; outcome is `"error_audio"`; no `processing` notification; no cleanup call.
**Discriminating power**: Catches continued execution into downstream stages after capture failure.

#### T-14: `run_pipeline` captured path emits ordered lifecycle notifications and always runs cleanup in `finally`

**Contract**: Captured path sends `recording_started` then `processing`, and cleanup runs even when downstream handoff raises.
**Setup**: Patch preconditions to pass; patch `capture_audio` to return captured artefact; keep Section 4 handoff marker raising (`NotImplementedError`) or inject equivalent downstream exception; patch notification and cleanup spies.
**Expected**: Ordered notifications are observed (`recording_started`, then `processing`); `remove_audio_artifact(artifact_path)` called exactly once despite downstream error.
**Discriminating power**: Catches missing `finally`, wrong notification sequencing, or cleanup not bound to captured artefact.

#### T-15: cleanup ownership is branch-exact (`remove_audio_artifact` called iff captured)

**Contract**: Cleanup call occurs only for captured branch and never for empty/error branches.
**Setup**: Parametrize `capture_audio` return across `captured`, `empty`, and `error` with identical preconditions.
**Expected**: Cleanup call count is `1` only for captured, `0` otherwise.
**Discriminating power**: Catches branch bleed where cleanup is called unconditionally or skipped on captured path.

#### T-16: cleanup failures must not mask primary pipeline outcome or downstream failure

**Contract**: Section 3 invariant states cleanup is non-raising and cannot change outcome classification.
**Setup**: Patch captured flow and force cleanup helper to encounter missing path/non-fatal internal issue using real `remove_audio_artifact` behavior; run with downstream failure marker.
**Expected**: Pipeline still reports the primary path outcome/error classification (for current boundary, downstream Section 4 marker) without replacement by cleanup exception.
**Discriminating power**: Catches cleanup exception propagation that hides true failure source.

## Requirement Traceability

| Requirement | Source | Proved By Contract | Proved By Tests |
|-------------|--------|--------------------|-----------------|
| AC1: 16 kHz float32 capture defaults and temp WAV artefact | `spec.md:58` | `capture_audio(config) -> AudioCaptureResult` captured arm + config-consumption contract | T-06 |
| AC2: microphone unavailable/inaccessible gives explicit error and safe exit | `spec.md:59` | `capture_audio` mic error shaping + `run_pipeline` `error_audio` mapping | T-08, T-13 |
| AC3: WAV creation failure yields I/O-class error and blocks transcription continuation | `spec.md:60` | `capture_audio` wav-write failure shaping + orchestration no-processing-on-error branch | T-09, T-13 |
| AC4: temporary artefacts are removed on success and handled error exits | `spec.md:61` | `remove_audio_artifact` non-raising contract + `run_pipeline` captured-branch `finally` cleanup ownership | T-10, T-11, T-14, T-15, T-16 |
| AC5: zero-duration/near-empty routes to explicit no-speech behavior | `spec.md:62` | `AudioEmpty`/`AudioCaptureResult` union + `run_pipeline` no-speech mapping | T-02, T-04, T-07, T-12 |

## What Is NOT Tested (and Why)

- Section 4 transcription internals and model inference quality: out of Section 3 API surface (handoff boundary only).
- Terminal insertion/clipboard behavior (Section 5) and notification copy wording (Section 6): separate section contracts.
- Exact numeric threshold for "near-empty" classification: design contract requires explicit routing but does not define threshold constant; tests prove branch behavior, not threshold calibration.

## Test Execution Order

1. Type-surface and static narrowing proofs (`T-01` to `T-05`) via `uv run pyright` plus runtime shape checks in `tests/test_types.py`.
2. Audio module contract tests (`T-06` to `T-11`) via `uv run pytest tests/test_audio.py`.
3. Section 3 orchestration and error-path mapping (`T-12` to `T-16`) via `uv run pytest tests/test_main.py`.

If group 1 fails, groups 2-3 results are not trusted.

## Design Gaps

- No blocking design gaps were found for Section 3 API-surface testability.
- Non-blocking precision note: the design specifies "near-empty" routing but does not expose a threshold contract; tests should assert explicit branch behavior without hard-coding incidental threshold internals.

Test specification complete.

**Location**: `thoughts/projects/2026-02-20-koe-m1/working/section-3-test-spec.md`
**Summary**: 16 tests across 11 API contracts
**Design gaps**: none blocking

Ready for planner.

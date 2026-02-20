---
title: "Section 4 Local CUDA Transcription Test Specification"
date: 2026-02-20
status: approved
design_source: "thoughts/design/2026-02-20-section-4-transcription-api.md"
spec_source: "thoughts/projects/2026-02-20-koe-m1/spec.md"
research_source: "thoughts/projects/2026-02-20-koe-m1/working/section-4-research.md"
project_section: "Section 4: Local CUDA Transcription"
---

# Test Specification: Section 4 Local CUDA Transcription

## Purpose

This document defines proof obligations for Section 4 contracts only: `transcribe.py` transcription result shaping and `main.py` Section 4 orchestration branching. Every test maps to an explicit Section 4 API contract, with explicit error-path coverage.

## Test Infrastructure

**Framework**: `pytest` + `typeguard` runtime checks, plus Pyright static checks.
**Test location**: root `tests/` directory (`tests/test_transcribe.py` new; additions to `tests/test_main.py`; optional static narrowing fixture in `tests/section4_static_fixtures.py`).
**Patterns to follow**:
- Subprocess/library boundary patching with deterministic side effects (`tests/test_audio.py:16`, `tests/test_main.py:116`).
- Closed union runtime checks with `check_type(...)` and negative invalid-arm assertions (`tests/test_types.py:90`).
- Parametrized exhaustive branch checks (`tests/test_main.py:98`, `tests/test_types.py:123`).
- Orchestration call-order/event assertions using side-effect event list (`tests/test_main.py:198`).
**Utilities available**: no shared `conftest.py`; local helper factories are the existing style (`tests/test_window.py:12`, `tests/test_hotkey.py:9`).
**Run command**: `uv run pytest tests/` with quality gates `uv run pyright` and `uv run ruff check src/ tests/`.

## API Surface

Contracts under test, extracted from the Section 4 design:

| Contract | Signature / Type | Design Reference | Tests |
|----------|-------------------|------------------|-------|
| `transcribe_audio` public API | `(artifact_path: AudioArtifactPath, config: KoeConfig, /) -> TranscriptionResult` | `...section-4-transcription-api.md:76` | T-01..T-10 |
| CUDA unavailable shaping | returns `kind="error"` with `cuda_available=False`, message `"CUDA not available: ..."` | `...section-4-transcription-api.md:117`, `:180` | T-06 |
| Model-load failure shaping | returns `kind="error"` with `cuda_available=True`, message `"model load failed: ..."` | `...section-4-transcription-api.md:122`, `:181` | T-07 |
| Inference failure shaping | returns `kind="error"` with `cuda_available=True`, message `"inference failed: ..."` | `...section-4-transcription-api.md:126`, `:182` | T-08 |
| Segment aggregation + stripping | join segment texts with single spaces, strip output | `...section-4-transcription-api.md:129` | T-02 |
| Noise filtering contract | exact-match filtering against canonical token set | `...section-4-transcription-api.md:132`, `:148` | T-04, T-05 |
| Empty/no-speech contract | empty/whitespace/noise-only returns `{"kind":"empty"}` | `...section-4-transcription-api.md:136` | T-03, T-04 |
| Text-arm guarantee | `kind="text"` implies non-empty/non-whitespace usable text | `...section-4-transcription-api.md:139` | T-02, T-05 |
| `run_pipeline` Section 4 branch | `empty -> no_speech`, `error -> error_transcription`, `text -> Section 5 handoff` | `...section-4-transcription-api.md:215` | T-11, T-12, T-13 |
| Cleanup invariant | `remove_audio_artifact` runs in `finally` for all transcription outcomes | `...section-4-transcription-api.md:243` | T-14 |
| Notification ordering | `processing` emitted before transcription call on captured path | `...section-4-transcription-api.md:252` | T-15 |

## Proof Obligations

### `transcribe_audio(artifact_path, config, /) -> TranscriptionResult`

#### T-01: happy path returns text arm for usable speech

**Contract**: Successful inference yields `{"kind":"text","text":...}`.
**Setup**: Patch model load and `.transcribe()` to return speech segments with non-empty content.
**Expected**: Returned arm is `kind="text"`; text is `str` and passes `len(text.strip()) > 0`.
**Discriminating power**: Catches implementations that return raw segment arrays, unstripped content, or wrong union arm.

#### T-02: segment aggregation joins with single spaces and strips boundaries

**Contract**: Segment texts are aggregated by single-space join, then outer strip.
**Setup**: Return multi-segment transcript with leading/trailing whitespace per segment and around joined output.
**Expected**: Output text equals canonical normalized join string, not preserving incidental spacing.
**Discriminating power**: Catches newline joins, double-space joins, and failure to trim boundaries.

#### T-03: whitespace-only inference maps to no-speech arm

**Contract**: Empty/whitespace post-normalization returns `{"kind":"empty"}`.
**Setup**: Return one or more segments containing only whitespace.
**Expected**: Result arm is exactly `kind="empty"`.
**Discriminating power**: Catches implementations that emit blank `"text"` values or route to generic error.

#### T-04: noise-only token outputs map to no-speech (parametrized canonical set)

**Contract**: Each canonical noise token is excluded and noise-only output yields empty arm.
**Setup**: Parametrize over the full token set from design (`[BLANK_AUDIO]`, `(silence)`, `[MUSIC]`, `(noise)`, `[inaudible]`, etc. exactly as listed).
**Expected**: For each token as sole segment, result is `kind="empty"`.
**Discriminating power**: Catches incomplete token filtering or case-sensitive omissions.

#### T-05: mixed noise + speech strips noise and returns only usable speech text

**Contract**: Noise-token segments are dropped, non-noise segments preserved.
**Setup**: Return segment sequence mixing canonical noise tokens and real words.
**Expected**: Result is `kind="text"` with only non-noise content in normalized order.
**Discriminating power**: Catches over-aggressive filters that drop valid speech, or under-filtering that leaks noise tokens into insertion text.

#### T-06: CUDA-unavailable model load failure returns typed error with `cuda_available=False`

**Contract**: CUDA absence is surfaced as `TranscriptionFailure` with `cuda_available=False` and prefixed message.
**Setup**: Patch model constructor to raise a CUDA-unavailable representative exception.
**Expected**: `kind="error"`, `error.category="transcription"`, `error.cuda_available is False`, and message starts with `"CUDA not available:"` and includes original exception text.
**Discriminating power**: Catches silent fallback-to-CPU behavior and loss of CUDA diagnostics.

#### T-07: non-CUDA model load failure returns typed error with `cuda_available=True`

**Contract**: Non-CUDA load faults are classified as model-load failure with `cuda_available=True`.
**Setup**: Patch model constructor to raise non-CUDA exception (e.g., model file/runtime init error).
**Expected**: `kind="error"`, `error.cuda_available is True`, message starts `"model load failed:"` and embeds original text.
**Discriminating power**: Catches conflation of all load errors into CUDA-unavailable class.

#### T-08: post-load inference exception returns typed error with `cuda_available=True`

**Contract**: `.transcribe()` exceptions after successful load are inference failures.
**Setup**: Patch constructor success; patch `.transcribe()` to raise.
**Expected**: `kind="error"`, `error.cuda_available is True`, message starts `"inference failed:"` and embeds original text.
**Discriminating power**: Catches crashes/exception leakage and misclassification as model-load errors.

#### T-09: expected failures never raise and always return error arm

**Contract**: Known failure modes are return-valued, not thrown.
**Setup**: Reuse failure scenarios from T-06..T-08; assert call returns value without exception.
**Expected**: All scenarios return `kind="error"`; no expected-failure path raises.
**Discriminating power**: Catches implementations that let backend exceptions bubble and bypass pipeline routing.

#### T-10: model is constructed with config-specified CUDA settings

**Contract**: `whisper_model`, `whisper_device` (`"cuda"`), and `whisper_compute_type` are consumed as constructor args.
**Setup**: Use config override values; spy constructor call args.
**Expected**: Constructor receives exact config values; no implicit CPU substitution.
**Discriminating power**: Catches hard-coded defaults and ignored config that break AC1.

### `run_pipeline(config, /) -> PipelineOutcome` Section 4 branch

#### T-11: empty transcription maps to `no_speech` with no Section 5 handoff

**Contract**: `kind="empty"` branch sends `no_speech` and returns `"no_speech"`.
**Setup**: Patch preconditions and audio capture to captured; patch `koe.main.transcribe_audio` to return `{"kind":"empty"}`.
**Expected**: Outcome `"no_speech"`; `send_notification("no_speech")` emitted after `"processing"`; Section 5 handoff marker not reached.
**Discriminating power**: Catches accidental progression to insertion and missing user feedback.

#### T-12: transcription error maps to `error_transcription` with payload forwarding

**Contract**: `kind="error"` branch forwards typed error to notification and returns `"error_transcription"`.
**Setup**: Patch transcription result to error arm with full `TranscriptionError` payload.
**Expected**: Outcome `"error_transcription"`; notification called as `send_notification("error_transcription", error)`.
**Discriminating power**: Catches payload loss, wrong notification kind, and wrong pipeline outcome mapping.

#### T-13: text transcription proceeds to Section 5 handoff placeholder

**Contract**: `kind="text"` bypasses empty/error returns and reaches Section 5 marker.
**Setup**: Patch transcription result to `{"kind":"text","text":"hello"}`.
**Expected**: Current boundary raises `NotImplementedError("Section 5 handoff: insertion")`.
**Discriminating power**: Catches regressions where text is mistakenly treated as empty/error.

#### T-14: cleanup runs exactly once for all transcription outcomes

**Contract**: `remove_audio_artifact(artifact_path)` executes in `finally` regardless of transcription arm.
**Setup**: Parametrize transcription result across `empty`, `error`, `text` (text case expecting Section 5 handoff exception).
**Expected**: Cleanup called once in every variant.
**Discriminating power**: Catches missing `finally` coverage and branch-dependent cleanup leaks.

#### T-15: processing notification precedes transcription invocation

**Contract**: On captured path, `send_notification("processing")` occurs before `transcribe_audio(...)`.
**Setup**: Use side-effect event log across notification and transcription mock calls.
**Expected**: Event order shows `processing` before `transcribe_audio` entry.
**Discriminating power**: Catches sequencing regressions where user sees delayed/incorrect lifecycle feedback.

## Requirement Traceability

| Requirement | Source | Proved By Contract | Proved By Tests |
|-------------|--------|--------------------|-----------------|
| AC1: CUDA-required policy, CPU fallback treated as error | `spec.md:70` | `transcribe_audio` constructor arg contract + CUDA failure shaping | T-06, T-10 |
| AC2: CUDA/backend unavailable are explicit user-visible errors | `spec.md:71` | `TranscriptionFailure` shaping + `run_pipeline` error branch notification | T-06, T-07, T-08, T-12 |
| AC3: empty/whitespace output does not paste; user gets no-speech feedback | `spec.md:72` | empty mapping in `transcribe_audio` + `run_pipeline` `no_speech` branch | T-03, T-11 |
| AC4: non-useful silence/noise tokens are non-pasteable and follow no-speech path | `spec.md:73` | canonical noise filtering contract in `transcribe_audio` | T-04, T-05 |
| AC5: successful transcription yields insertion-ready text | `spec.md:74` | text-arm non-empty guarantee + text branch handoff | T-01, T-02, T-05, T-13 |

## What Is NOT Tested (and Why)

- Actual GPU throughput/latency and model quality metrics: performance/quality benchmarking is outside Section 4 API contracts.
- Faster-whisper internal implementation details (beam search internals, tokenizer internals): not part of observable API surface.
- Clipboard paste mechanics and terminal insertion: Section 5 scope.
- Notification rendering/look-and-feel text copy: Section 6 scope; only kind/payload routing is verified here.

## Test Execution Order

1. `transcribe_audio` value-shaping happy/error contracts (T-01..T-10) in `tests/test_transcribe.py`.
2. Orchestration branch mapping and cleanup/ordering contracts (T-11..T-15) in `tests/test_main.py`.
3. Optional static narrowing fixture (`tests/section4_static_fixtures.py`) during `uv run pyright`.

If group 1 fails, group 2 outcomes are not trusted.

## Design Gaps

- No blocking Section 4 testability gaps detected.
- Non-blocking precision note: CUDA-unavailable detection predicate is contractually outcome-based (T-06) rather than tied to a specific backend exception class, so tests should assert returned classification and message prefix, not backend exception type identity.

Test specification complete.

**Location**: `thoughts/projects/2026-02-20-koe-m1/working/section-4-test-spec.md`
**Summary**: 15 tests across 11 API contracts
**Design gaps**: none blocking

Ready for planner.

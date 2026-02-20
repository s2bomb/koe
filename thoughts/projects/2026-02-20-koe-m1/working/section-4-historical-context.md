---
date: 2026-02-20
author: opencode
project: koe-m1
section: "Section 4: Local CUDA Transcription"
purpose: "Concrete historical context references for Section 4 research stage"
topics: [cuda-policy, no-speech, non-useful-tokens, transcribe-insert-interface]
---

# Historical Context: Section 4 Local CUDA Transcription

Concrete references only. File:line citations are verified against the current
working tree on `master` at commit `6725071` (post-Section-3 validation).

---

## 1. CUDA-Only Policy

### Decision origin

- `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:20`
  — Acceptance criterion: "Transcription for M1 runs on CUDA only; CPU fallback
  is treated as an error path for this milestone."

- `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:180`
  — M1 milestone acceptance: "GPU utilised (not CPU fallback)" is a named
  acceptance condition for the Whisper transcription deliverable.

- `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:250`
  — Risk register: CUDA unavailability is classed High; mitigation is "detect
  GPU availability at startup; warn user loudly."

### Resolved in the spec decision register

- `thoughts/specs/2026-02-20-koe-m1-spec.md:62`
  — "GPU policy: M1 requires CUDA transcription; if CUDA is not available, run
  fails with notification (no CPU fallback in this milestone)."

- `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md:244`
  — Confirms: "CUDA-required fail-fast transcription policy" recorded as a
  resolved M1 default.

### Section 4 acceptance criteria (canonical)

- `thoughts/projects/2026-02-20-koe-m1/spec.md:70`
  — "Transcription executes with CUDA-required policy for M1; CPU fallback is
  treated as error."

- `thoughts/projects/2026-02-20-koe-m1/spec.md:71`
  — "CUDA unavailable or transcription backend unavailable states are explicit,
  user-visible errors."

### Enforcement already in code (pre-Section 4)

- `src/koe/config.py:15`
  — `whisper_device: Literal["cuda"]` — the type itself makes CPU a Pyright
  error; widening to `Literal["cuda", "cpu"]` is named as a future-milestone
  change in the design doc.

- `src/koe/config.py:29`
  — `"whisper_device": "cuda"` in `DEFAULT_CONFIG`.

- `src/koe/main.py:41-49`
  — `dependency_preflight` enforces `config["whisper_device"] != "cuda"` at
  runtime and returns a `DependencyError` if the check fails. This happens
  before the lock is acquired and before any audio capture. Section 4 therefore
  arrives guaranteed to have `whisper_device == "cuda"` in config.

- `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:365-368`
  — Design doc docstring on `whisper_device`: "Literal['cuda'] makes CPU
  fallback a Pyright type error for M1. Future milestone: widen to
  Literal['cuda', 'cpu']."

### TranscriptionError carries cuda_available flag

- `src/koe/types.py:65-68`
  — `TranscriptionError(TypedDict)` fields: `category: Literal["transcription"]`,
  `message: str`, `cuda_available: bool`. The `cuda_available` field explicitly
  supports distinguishing CUDA-absent failure from other inference errors.

- `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:235-240`
  — Design doc for `TranscriptionError`: "`cuda_available: bool` — False when
  CUDA was not available — the primary expected failure mode for M1."

---

## 2. No-Speech Handling

### Spec requirement

- `thoughts/projects/2026-02-20-koe-m1/spec.md:72`
  — "Empty/whitespace transcription does not paste; user receives 'no speech
  detected' feedback."

- `thoughts/specs/2026-02-20-koe-m1-spec.md:108`
  — Same requirement in the draft spec: "Empty or whitespace transcription output
  produces user-visible 'no speech detected' feedback and does not paste empty
  content."

### Type already defined in types.py

- `src/koe/types.py:61-63`
  — `TranscriptionNoSpeech(TypedDict)` with discriminant `kind: Literal["empty"]`.
  This is the arm Section 4 must return for empty or whitespace-only output.

- `src/koe/types.py:76`
  — `type TranscriptionResult = TranscriptionText | TranscriptionNoSpeech | TranscriptionFailure`
  — Three-armed discriminated union. No-speech is a first-class arm, not an
  error.

### Design intent documented

- `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:156-163`
  — `TranscriptionNoSpeech` docstring: "Audio contained no usable speech (empty
  or whitespace-only output). The pipeline must emit a 'no speech detected'
  notification and exit cleanly without attempting insertion."

- `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:175-186`
  — Union docstring: "NOT wrapped in Result[T, E] because there are three
  distinct arms, not two."

### Pipeline outcome and notification kind already present

- `src/koe/types.py:139`
  — `PipelineOutcome` includes `"no_speech"`.

- `src/koe/types.py:87`
  — `NotificationKind` includes `"no_speech"`.

### Exit mapping already implemented

- `src/koe/main.py:98-113`
  — `outcome_to_exit_code` maps `"no_speech"` → exit code `1` (controlled
  failure, user notified).

### Tests already covering the type surface

- `tests/test_types.py:68-71`
  — `test_transcription_no_speech_enforces_empty_kind` verifies
  `{"kind": "empty"}` accepted and `{"kind": "text"}` rejected as
  `TranscriptionNoSpeech`.

- `tests/test_types.py:90-115`
  — Parametrized `test_transcription_result_is_exactly_three_armed` proves the
  union accepts exactly text/empty/error and rejects any other kind.

---

## 3. Non-Useful Token Handling

### Spec requirement (the only explicit statement)

- `thoughts/projects/2026-02-20-koe-m1/spec.md:73`
  — "Non-useful transcription tokens from silence/noise are treated as
  non-pasteable output for M1 and follow the same feedback path."

  **What this means in context**: the spec explicitly groups hallucinated tokens
  (e.g. `[BLANK_AUDIO]`, `(background noise)`, whitespace-only segments) with
  the no-speech path, not the error path. The phrase "same feedback path" refers
  to the `TranscriptionNoSpeech` → `no_speech` → notification flow.

### No token filter list is defined anywhere

  No document in `thoughts/` defines a specific list of Whisper hallucination
  tokens to strip or reject. The only characterisation is "non-useful tokens
  from silence/noise." Section 4 research and API design must define this
  concretely. This is an open specification gap.

### The receiving type is already decided

- `src/koe/types.py:61-63`
  — Non-useful token output routes to `TranscriptionNoSpeech(kind="empty")`,
  the same type as genuine silence. There is no separate type for
  "filtered-token" outcomes.

- `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:156-163`
  — `TranscriptionNoSpeech` covers "empty or whitespace-only output" per
  its docstring. The spec's addition of "non-useful tokens" extends this
  scope but shares the type.

---

## 4. Interfaces and Types Between Transcribe and Insert

### Input to Section 4: what transcribe.py receives

- `thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:176`
  — "Section 4 should consume `artifact_path: AudioArtifactPath` from the
  captured branch only."

- `src/koe/main.py:88`
  — `artifact_path = capture_result["artifact_path"]` — this is the exact
  handoff value Section 4 receives.

- `src/koe/types.py:11`
  — `AudioArtifactPath = NewType("AudioArtifactPath", Path)` — the opaque
  type Section 4 consumes as its sole input from Section 3.

### The Section 4 handoff point in main.py

- `src/koe/main.py:89-93`
  — Current pipeline at the Section 4 boundary:

  ```python
  artifact_path = capture_result["artifact_path"]
  try:
      send_notification("processing")
      raise NotImplementedError("Section 4 handoff: transcription")
  finally:
      remove_audio_artifact(artifact_path)
  ```

  Section 4 replaces the `NotImplementedError` with a real `transcribe_audio`
  call. The outer `finally` at `src/koe/main.py:92-93` already guarantees
  artefact cleanup regardless of transcription outcome.

- `thoughts/design/2026-02-20-koe-m1-section-3-api-design.md:176`
  — "The Section 3 cleanup `finally` must remain wrapped around downstream
  stages so artefact deletion is guaranteed regardless of transcription/insertion
  success."

### Output of Section 4: what transcribe.py returns to main.py

- `src/koe/types.py:56-76`
  — `TranscriptionResult = TranscriptionText | TranscriptionNoSpeech | TranscriptionFailure`

  Full arm definitions:

  | Arm | Fields |
  |-----|--------|
  | `TranscriptionText` | `kind: Literal["text"]`, `text: str` |
  | `TranscriptionNoSpeech` | `kind: Literal["empty"]` |
  | `TranscriptionFailure` | `kind: Literal["error"]`, `error: TranscriptionError` |

  `TranscriptionError` fields: `category: Literal["transcription"]`,
  `message: str`, `cuda_available: bool`.

### What main.py does with TranscriptionResult (not yet implemented)

  The Section 4 design has not been written yet. The following can be inferred
  from the type/pipeline shape:

  - `"text"` arm → proceeds to Section 5 insertion with `result["text"]`
  - `"empty"` arm → `send_notification("no_speech")`, return `"no_speech"`
  - `"error"` arm → `send_notification("error_transcription", result["error"])`,
    return `"error_transcription"`

  These mappings are consistent with `outcome_to_exit_code` at
  `src/koe/main.py:98-113` which already covers `"no_speech"` and
  `"error_transcription"`.

### Interface from transcribe.py output to insert.py input

- `src/koe/types.py:56-58`
  — `TranscriptionText(TypedDict)`: `kind: Literal["text"]`, `text: str`.
  The `text` field is the sole value Section 5 (`insert.py`) consumes.

- `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:148-153`
  — `TranscriptionText` docstring: "`text` is non-empty and non-whitespace.
  The insert stage can consume it directly."

  This establishes the contract: `transcribe.py` must guarantee that any value
  it returns in the `"text"` arm is non-empty and non-whitespace. Whitespace-only
  output must route to the `"empty"` arm, not the `"text"` arm.

### InsertionError carries transcript_text for recovery

- `src/koe/types.py:108-111`
  — `InsertionError(TypedDict)`: `category: Literal["insertion"]`,
  `message: str`, `transcript_text: str`.

- `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:247-252`
  — Design docstring: "`transcript_text` is preserved so the user can manually
  paste the result. The pipeline must surface this in the error notification."

  This means Section 5 (`insert.py`) must receive the raw text string from
  Section 4 so it can include it in the `InsertionError` payload on failure.
  Section 4's `transcribe.py` return value (`TranscriptionText.text`) flows
  directly into that field.

### KoeConfig fields consumed by Section 4

- `src/koe/config.py:14-16`
  — `whisper_model: str`, `whisper_device: Literal["cuda"]`,
  `whisper_compute_type: str` — the three fields `transcribe.py` consumes
  from the config passed in by `main.py`.

- `src/koe/config.py:26-30`
  — Default values: `whisper_model = "base.en"`, `whisper_device = "cuda"`,
  `whisper_compute_type = "float16"`.

---

## Summary of Open Areas for Section 4 to Define

1. **Concrete function signature for `transcribe_audio`** in `transcribe.py` —
   not yet specified in any design document.

2. **Non-useful token list** — spec says to treat them as non-pasteable on the
   no-speech path but names no specific tokens. Section 4 API design must
   decide: which Whisper hallucination tokens are filtered, and whether filtering
   happens inside `transcribe.py` or is the caller's responsibility.

3. **`main.py` orchestration for the three `TranscriptionResult` arms** — not
   yet written. The type vocab, outcome labels, and notification kinds are all
   defined, but the `match` / `if` branching in `run_pipeline` must be added.

4. **`faster-whisper` model load strategy** — when the model is loaded (per-
   invocation vs. cached), how model load failure is surfaced, and whether
   `cuda_available` is checked before model load or reported from a model-load
   exception.

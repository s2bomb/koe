---
date: 2026-02-20
author: opencode (design-clone)
status: approved-for-test-design
project: koe-m1
section: "Section 4: Local CUDA Transcription"
spec_reference: thoughts/projects/2026-02-20-koe-m1/spec.md
research_reference: thoughts/projects/2026-02-20-koe-m1/working/section-4-research.md
historical_context: thoughts/projects/2026-02-20-koe-m1/working/section-4-historical-context.md
---

# Section 4 API Design: transcribe.py + main.py orchestration branch

## Scope

Strictly Section 4 acceptance criteria:

- convert `AudioArtifactPath` to `TranscriptionResult` via local CUDA Whisper inference
- enforce CUDA-required policy; surface backend unavailability as typed error
- map empty/whitespace output and known noise tokens to `TranscriptionNoSpeech`
- guarantee non-empty, non-whitespace text in the `"text"` arm
- wire the three-armed `TranscriptionResult` into `run_pipeline` in `main.py`

Out of scope: Section 5 insertion internals, clipboard handling, xdotool paste mechanics, notification copy quality (Section 6).

---

## The Core Principle

**`transcribe_audio` converts a raw WAV path into a three-armed discriminated union — text, no-speech, or error — and `main.py` branches exhaustively on that union so no transcription outcome is ever silent.**

Everything in this module traces to one responsibility: make the Whisper inference outcome a first-class typed value. The three-armed union (`TranscriptionText | TranscriptionNoSpeech | TranscriptionFailure`) is not wrapped in `Result[T, E]` because there are three distinct outcomes, not two. Callers narrow by `kind`. The `"text"` arm carries a compile-time guarantee that its `text` field is non-empty and non-whitespace — the insert stage can consume it directly. The `"empty"` arm covers both genuine silence and known noise-only hallucinations; callers do not distinguish these two sub-cases.

---

## Type contract additions

None required. All types are already defined in `src/koe/types.py`:

```python
# types.py (existing — shown for reference only, not net-new)

class TranscriptionText(TypedDict):
    kind: Literal["text"]
    text: str                           # non-empty, non-whitespace (invariant)

class TranscriptionNoSpeech(TypedDict):
    kind: Literal["empty"]

class TranscriptionError(TypedDict):
    category: Literal["transcription"]
    message: str
    cuda_available: bool                # False = CUDA absent; True = inference fault

class TranscriptionFailure(TypedDict):
    kind: Literal["error"]
    error: TranscriptionError

type TranscriptionResult = TranscriptionText | TranscriptionNoSpeech | TranscriptionFailure
```

`KoeConfig` fields consumed by Section 4 (already in `config.py`):

```python
whisper_model: str          # default "base.en"
whisper_device: Literal["cuda"]  # compile-time enforcement; CPU is a type error
whisper_compute_type: str   # default "float16"
```

No changes to `types.py` or `config.py` are needed for Section 4.

---

## `transcribe.py` public API

```python
def transcribe_audio(
    artifact_path: AudioArtifactPath,
    config: KoeConfig,
    /,
) -> TranscriptionResult:
    """Transcribe a recorded WAV artefact using local CUDA Whisper inference.

    Returns a three-armed discriminated union; narrow on result["kind"]:

    - {"kind": "text",  "text": "<non-empty, stripped transcript>"}
      Successful inference with usable speech detected. The text field is
      guaranteed non-empty and non-whitespace. Suitable for direct insertion.

    - {"kind": "empty"}
      No usable speech: Whisper output was empty, whitespace-only, or composed
      entirely of known noise-hallucination tokens. The pipeline must emit a
      "no_speech" notification and exit without attempting insertion.

    - {"kind": "error", "error": TranscriptionError}
      Inference could not complete. Covers: CUDA unavailable (cuda_available=False),
      model load failure, and CTranslate2 runtime fault (cuda_available=True).
      The pipeline must emit an "error_transcription" notification and exit.

    Never raises. All expected failures are returned as TranscriptionFailure.
    Truly exceptional programmer errors (corrupted state, wrong argument type)
    propagate as unhandled exceptions to main()'s outer try/except.
    """
```

### Parameter order rationale

`artifact_path` is the data being processed; `config` is the configuration.
Data-first ordering mirrors `remove_audio_artifact(artifact_path, /)` and is
consistent with positional-only (`/`) parameters established in Sections 1–3.

### `transcribe_audio` internal behaviour contract

These are the observable invariants the implementation must satisfy. They define
what tests can and must verify:

1. **CUDA detection**: If CUDA hardware or libraries are unavailable at model
   load time, return `TranscriptionFailure` with `cuda_available=False`. Detection
   happens before or during model load — not before the function is called (that
   is `dependency_preflight`'s concern, which already validates `whisper_device`).

2. **Model load failure (CUDA present)**: If model load raises for any reason
   other than CUDA absence, return `TranscriptionFailure` with `cuda_available=True`
   and a message containing the original exception string.

3. **Inference failure**: If `.transcribe()` raises after a successful model load,
   return `TranscriptionFailure` with `cuda_available=True`.

4. **Segment aggregation**: Join all segment texts with a single space. Strip
   leading and trailing whitespace from the aggregated result.

5. **Noise token filtering**: Each segment text is stripped individually before
   being tested against the noise token set. Segments that match a noise token
   exactly (after strip) are excluded from the aggregated result.

6. **Empty/whitespace detection**: If the aggregated, stripped, noise-filtered
   result is empty or whitespace-only, return `TranscriptionNoSpeech`.

7. **Text arm guarantee**: Any value returned in the `"text"` arm satisfies
   `len(text.strip()) > 0` and is not solely noise tokens.

### Noise token set (M1)

The following tokens are treated as non-pasteable noise for M1. They are the
canonical set `transcribe_audio` filters internally. Test writers must
parametrize against exactly this set:

```python
_NOISE_TOKENS: frozenset[str] = frozenset({
    "[BLANK_AUDIO]",
    "[blank_audio]",
    "(background noise)",
    "(Background Noise)",
    "(silence)",
    "(Silence)",
    "[MUSIC]",
    "(music)",
    "(Music)",
    "(noise)",
    "(Noise)",
    "(beep)",
    "(Beep)",
    "[beep]",
    "[noise]",
    "[inaudible]",
    "(inaudible)",
    "(Inaudible)",
})
```

These tokens cover the well-known faster-whisper hallucination patterns for
silence, background noise, and music. The set is the single source of truth —
the `_NOISE_TOKENS` name is internal to `transcribe.py`, but the values are
contractual for tests.

### Error shaping rules

| Failure scenario | `cuda_available` | `message` shape |
|---|---|---|
| CUDA hardware/libs absent at model load | `False` | `"CUDA not available: {original}"` |
| Model load raised (CUDA present) | `True` | `"model load failed: {original}"` |
| Inference raised after model load | `True` | `"inference failed: {original}"` |

All three return `TranscriptionFailure(kind="error", error=TranscriptionError(...))`.

---

## Section 4 orchestration in `main.py`

### Import addition

```python
# Add to existing main.py imports:
from koe.transcribe import transcribe_audio
```

This top-level import enables `patch("koe.main.transcribe_audio")` in tests,
consistent with how existing imports (`capture_audio`, `remove_audio_artifact`,
`send_notification`) are patched throughout `test_main.py`.

### Replace the `NotImplementedError` placeholder

Current stub at `src/koe/main.py:89-91`:

```python
try:
    send_notification("processing")
    raise NotImplementedError("Section 4 handoff: transcription")
finally:
    remove_audio_artifact(artifact_path)
```

Replace with:

```python
try:
    send_notification("processing")
    transcription_result = transcribe_audio(artifact_path, config)

    if transcription_result["kind"] == "empty":
        send_notification("no_speech")
        return "no_speech"

    if transcription_result["kind"] == "error":
        send_notification("error_transcription", transcription_result["error"])
        return "error_transcription"

    # Pyright narrows transcription_result to TranscriptionText here.
    # transcription_result["text"] is non-empty and non-whitespace (guaranteed by
    # transcribe_audio contract). Forwarded to Section 5 insertion.
    raise NotImplementedError("Section 5 handoff: insertion")
finally:
    remove_audio_artifact(artifact_path)
```

### Exhaustive narrowing guarantee

After the two `if`-guards return, Pyright statically narrows `transcription_result`
to `TranscriptionText`. Accessing `transcription_result["text"]` past those guards
is type-safe with no cast. The `assert_never` pattern is not needed here because
the two guards already exhaust the non-text arms by returning.

### Cleanup invariant (unchanged from Section 3 design)

The `finally: remove_audio_artifact(artifact_path)` block remains in place and
wraps the entire transcription stage (and the future Section 5 insertion stage).
Artefact cleanup is guaranteed regardless of transcription outcome, including
raised exceptions. This invariant is not changed by Section 4.

### Notification sequence on the captured path

The full notification sequence after Section 4 is wired:

| Event | `NotificationKind` emitted |
|---|---|
| Focus validated | _(none)_ |
| Recording begins | `"recording_started"` |
| Transcription begins | `"processing"` |
| Transcription returns empty/noise | `"no_speech"` |
| Transcription returns error | `"error_transcription"` |
| Transcription returns text | _(Section 5 will emit `"completed"`)_ |

### Pipeline outcome routing

| `transcription_result["kind"]` | `PipelineOutcome` returned | Exit code |
|---|---|---|
| `"empty"` | `"no_speech"` | 1 |
| `"error"` | `"error_transcription"` | 1 |
| `"text"` | _(proceeds to Section 5)_ | _(Section 5 determines)_ |

Both `"no_speech"` and `"error_transcription"` are already in `outcome_to_exit_code`
at `src/koe/main.py:98-113` and map to exit code 1. No changes to that function.

---

## Error handling strategy

**Returns `TranscriptionResult` (three-armed union, never raises):**

- All expected Whisper inference outcomes (text, empty, CUDA error, model error,
  runtime error) are captured inside `transcribe_audio` and returned as typed arms.

**Propagates as unhandled exception (caught by `main()`'s outer `try/except`):**

- `TypeError` / `AttributeError` from passing wrong argument types (programmer bug).
- Any exception that escapes the internal error-capture boundary inside
  `transcribe_audio` due to an unexpected library fault not in the known failure
  surface. These map to `ExitCode` 2 via `main()`'s existing handler.

**Never raises inside the `try/finally` block in `run_pipeline`:**

- `transcribe_audio` is the only new call that can fail. Its contract is
  "never raises for expected failures." Unexpected failures propagate to the
  outer `try/except Exception` in `main()`, which exits with code 2.

---

## Observability design

`transcribe_audio` has no structured tracing in M1 (no logfire/OpenTelemetry
dependency). Observability is via the `TranscriptionError.message` field, which
must carry the original exception string for every error arm. This ensures a
developer can read the error notification or log to diagnose failures at 2am.

**Attributes present on every failure arm:**

- `cuda_available: bool` — distinguishes CUDA-absent failures from inference faults.
- `message: str` — original exception string embedded. Must not be generic.

**Silent failure is unacceptable**: every code path inside `transcribe_audio`
must return one of the three arms. There must be no `pass`, no unchecked bare
`except`, and no suppressed exceptions.

---

## Acceptance criteria mapping

### AC1: Transcription executes with CUDA-required policy; CPU fallback is treated as error

- `config["whisper_device"]` is `Literal["cuda"]` — type system enforces this.
- `dependency_preflight` (already implemented) rejects CPU config before the
  pipeline reaches Section 4.
- `transcribe_audio` loads the model with `device=config["whisper_device"]`
  (which is always `"cuda"`). No CPU code path exists.

### AC2: CUDA unavailable or transcription backend unavailable are explicit, user-visible errors

- `TranscriptionFailure` with `cuda_available=False` → `send_notification("error_transcription", error)` → user sees notification.
- `TranscriptionFailure` with `cuda_available=True` (model/runtime fault) → same notification path.
- `send_notification` is already proven non-raising by Section 6 design.

### AC3: Empty/whitespace transcription does not paste; user receives "no speech detected" feedback

- `transcribe_audio` returns `TranscriptionNoSpeech` for empty/whitespace output.
- `run_pipeline` branches: `send_notification("no_speech")` then `return "no_speech"`.
- Section 5 insertion is never reached.

### AC4: Non-useful tokens treated as non-pasteable; follow same feedback path as AC3

- `transcribe_audio` filters the `_NOISE_TOKENS` set per segment before aggregation.
- Noise-only output produces `TranscriptionNoSpeech`.
- Same `"no_speech"` notification path. No separate type or outcome needed.

### AC5: Successful transcription returns text suitable for insertion step consumption

- `TranscriptionText.text` is contractually non-empty, non-whitespace.
- Available as `transcription_result["text"]` after the two `if`-guards in
  `run_pipeline`. Section 5 consumes this string directly.

---

## Test design obligations

### `tests/test_transcribe.py` (new file)

**Happy path:**
- Given a valid WAV with speech, returns `{"kind": "text", "text": <non-empty-str>}`.

**Empty/whitespace path:**
- Given a valid WAV that produces whitespace-only Whisper output, returns `{"kind": "empty"}`.

**Noise token path (parametrized over `_NOISE_TOKENS`):**
- Each token in the noise set, presented as the sole Whisper output, returns `{"kind": "empty"}`.
- Noise tokens mixed with real speech are stripped; the remaining text is returned in the `"text"` arm.

**CUDA unavailable path:**
- When model load raises an exception that indicates CUDA absence, returns
  `{"kind": "error", "error": {"category": "transcription", "message": ..., "cuda_available": False}}`.

**Model load failure path (CUDA present):**
- When model load raises for a non-CUDA reason, returns `TranscriptionFailure`
  with `cuda_available=True`.

**Inference failure path:**
- When `.transcribe()` raises after model load succeeds, returns `TranscriptionFailure`
  with `cuda_available=True`.

**Non-raising guarantee:**
- All of the above paths are verified to not raise; they return the `"error"` arm.

### `tests/test_main.py` additions (Section 4 orchestration)

**`test_run_pipeline_transcription_empty_returns_no_speech`:**
- Patch `koe.main.transcribe_audio` → `{"kind": "empty"}`.
- Assert `run_pipeline(config) == "no_speech"`.
- Assert `send_notification` called with `"no_speech"` (after `"processing"`).
- Assert `remove_audio_artifact` called once (cleanup still runs).

**`test_run_pipeline_transcription_error_returns_error_transcription`:**
- Patch `koe.main.transcribe_audio` → `{"kind": "error", "error": {...}}`.
- Assert `run_pipeline(config) == "error_transcription"`.
- Assert `send_notification("error_transcription", <error>)`.
- Assert `remove_audio_artifact` called once.

**`test_run_pipeline_transcription_text_proceeds_to_section5`:**
- Patch `koe.main.transcribe_audio` → `{"kind": "text", "text": "hello"}`.
- Assert pipeline raises `NotImplementedError` matching `"Section 5 handoff"`.
- Assert `remove_audio_artifact` still called (cleanup in `finally`).

**`test_run_pipeline_transcription_cleanup_runs_on_all_transcription_outcomes`:**
- Parametrize over all three `TranscriptionResult` arms.
- Assert `remove_audio_artifact` call count is always 1 regardless of arm.

**`test_run_pipeline_processing_notification_precedes_transcription`:**
- Track call ordering via side-effect-based event list.
- Assert `"processing"` notification is emitted before `transcribe_audio` is called.

### `tests/section4_static_fixtures.py` (new file)

```python
from koe.types import TranscriptionError, TranscriptionResult, TranscriptionText
from koe.transcribe import transcribe_audio  # noqa: F401 — import existence check


def t06_transcription_result_is_closed(result: TranscriptionResult) -> None:
    """Pyright must accept exactly three arms and reject any fourth."""
    match result["kind"]:
        case "text":
            assert_type(result["text"], str)
        case "empty":
            return
        case "error":
            assert_type(result["error"], TranscriptionError)
        case _ as unreachable:
            assert_never(unreachable)


def t07_transcription_text_arm_carries_str(result: TranscriptionText) -> None:
    """Pyright narrows text field to str after kind check."""
    if result["kind"] == "text":
        assert_type(result["text"], str)
```

---

## Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Public function count | 1: `transcribe_audio` | Module owns exactly one pipeline concern; no secondary entry points |
| Parameter order | `artifact_path` first, `config` second | Data-first ordering; consistent with existing positional-only pattern |
| Model load timing | Per-invocation inside `transcribe_audio` | Koe is single-shot; no persistent state survives invocations |
| CUDA detection | Attempt load; populate `cuda_available` from the exception | Detection at load time is accurate; avoids a separate pre-check that could race |
| Noise filtering location | Internal to `transcribe_audio` | The `"text"` arm contract (non-empty, non-noise) is enforced at source, not by callers |
| Noise token set exposure | Defined in design doc; private `_NOISE_TOKENS` frozenset | Test writers need the concrete set; callers do not need to see it |
| Text normalization | Strip whitespace from each segment and from joined result | Minimal and safe; spec says "empty/whitespace" routes to no-speech |
| `main.py` branching style | `if`-chain (not `match`) | Consistent with all existing `run_pipeline` branching; Pyright narrows correctly via `is False` / `kind ==` guards |
| Section 5 placeholder | `raise NotImplementedError("Section 5 handoff: insertion")` | Preserves the established placeholder contract; test `test_run_pipeline_transcription_text_proceeds_to_section5` can assert on it |
| Import placement | Top-level in `main.py` | Enables `patch("koe.main.transcribe_audio")` without `create=True` |

---

## Integration notes

**Upstream (Section 3 → Section 4):**
- Section 4 receives `artifact_path: AudioArtifactPath` from `capture_result["artifact_path"]`.
- The Section 3 cleanup `finally: remove_audio_artifact(artifact_path)` wraps Section 4.
- This invariant is preserved — do not restructure the `try/finally` block.

**Downstream (Section 4 → Section 5):**
- `transcription_result["text"]` is the sole value Section 5 needs from Section 4.
- It is in scope at the `raise NotImplementedError("Section 5 handoff")` line.
- `focused_window["value"]` (from the earlier focus check) is also in scope and
  available for Section 5's window-targeted paste operation.

**No changes required to:**
- `types.py` — all transcription types exist.
- `config.py` — all three consumed fields exist.
- `outcome_to_exit_code` — `"no_speech"` and `"error_transcription"` are already handled.
- `NotificationKind` — `"error_transcription"` and `"no_speech"` are already present.

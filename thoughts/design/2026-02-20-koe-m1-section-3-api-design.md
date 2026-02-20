---
date: 2026-02-20
author: opencode
project: koe-m1
section: "Section 3: Audio Capture and Temporary Artefact Lifecycle"
status: approved-for-test-design
spec_reference: thoughts/projects/2026-02-20-koe-m1/spec.md
research_reference: thoughts/projects/2026-02-20-koe-m1/working/section-3-research.md
---

# Section 3 API Design: audio.py + main.py orchestration boundary

## Scope

This design is strictly limited to Section 3 acceptance criteria:

- capture audio with M1 defaults (16 kHz, float32 intent) into a temporary WAV
- surface microphone and WAV I/O failures as typed audio errors
- guarantee temporary artefact cleanup ownership and lifecycle
- define near-empty capture routing into explicit no-speech behavior

Out of scope: Section 4 transcription internals, Section 5 insertion, Section 6 notification copy quality.

## Design principle

`audio.py` owns capture and artefact creation. `main.py` owns artefact cleanup timing.

This keeps data flow explicit:

1. `capture_audio(config)` returns a discriminated union (captured | empty | error).
2. `main.py` branches exhaustively on `kind`.
3. Cleanup runs in `finally` only for the captured branch via `remove_audio_artifact(artifact_path)`.

## Type contract additions (`src/koe/types.py`)

```python
class AudioCapture(TypedDict):
    kind: Literal["captured"]
    artifact_path: AudioArtifactPath


class AudioEmpty(TypedDict):
    kind: Literal["empty"]


class AudioCaptureFailed(TypedDict):
    kind: Literal["error"]
    error: AudioError


type AudioCaptureResult = AudioCapture | AudioEmpty | AudioCaptureFailed
```

### Notification kind extension

Section 3 requires explicit no-speech feedback, so add:

```python
"no_speech"
```

to `NotificationKind`.

## `audio.py` public API

```python
def capture_audio(config: KoeConfig, /) -> AudioCaptureResult:
    """Capture microphone audio and persist a temporary WAV artefact.

    Returns:
    - {"kind": "captured", "artifact_path": AudioArtifactPath}
    - {"kind": "empty"} when capture duration is near-empty
    - {"kind": "error", "error": AudioError} for expected failures
    """


def remove_audio_artifact(artifact_path: AudioArtifactPath, /) -> None:
    """Best-effort removal of temporary WAV artefact.

    Must not raise. Safe when file is already missing.
    """
```

### Error shaping rules

- Microphone unavailable/inaccessible:
  - return `{"kind": "error", "error": {"category": "audio", "message": "microphone unavailable: ...", "device": <str|None>}}`
- WAV creation/write failure:
  - return `{"kind": "error", "error": {"category": "audio", "message": "wav write failed: ...", "device": None}}`
- Near-empty capture:
  - return `{"kind": "empty"}`

## Section 3 orchestration contract in `main.py`

Replace Section 3 placeholder handoff with:

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

## Cleanup ownership and invariants

Ownership model:

- `audio.py` creates artefact paths and files.
- `main.py` owns lifetime completion and calls `remove_audio_artifact`.

Invariants:

1. `remove_audio_artifact` is called iff `capture_result.kind == "captured"`.
2. Cleanup call is in a `finally` block so it runs on success and downstream errors.
3. Cleanup never raises and never masks pipeline outcomes.
4. Empty/error capture variants never create an artefact and therefore never require cleanup.

## Acceptance criteria mapping

### AC1: 16 kHz float32 capture and temporary WAV

- `capture_audio(config)` consumes `sample_rate`, `audio_channels`, `audio_format`, `temp_dir`
- returns captured artefact path as `AudioArtifactPath`

### AC2: microphone unavailable/inaccessible -> explicit error + safe exit

- audio layer returns `AudioCaptureFailed`
- orchestration sends `error_audio` notification and returns `error_audio`

### AC3: WAV creation failure -> I/O class error and no transcription continuation

- audio layer returns `AudioCaptureFailed` with WAV write message
- orchestration returns before Section 4 handoff

### AC4: temporary artefacts removed on success and handled error exits

- `finally: remove_audio_artifact(artifact_path)` encloses downstream handoff

### AC5: zero-duration/near-empty -> no-speech behavior

- audio layer returns `AudioEmpty`
- orchestration sends `no_speech` notification and returns `no_speech`

## Test design obligations for downstream phase

- `tests/test_audio.py`
  - captured branch (happy path)
  - empty branch (zero/near-empty)
  - mic unavailable branch
  - wav write I/O failure branch
  - non-raising cleanup behavior
- `tests/test_main.py`
  - Section 3 branching outcomes (`no_speech`, `error_audio`)
  - Section 3 notification ordering (`recording_started` then `processing` on captured path)
  - cleanup invocation in `finally` for captured path
  - no cleanup call for empty/error capture branches
- static type fixtures
  - exhaustive narrowing over `AudioCaptureResult`
  - `NotificationKind` includes `"no_speech"`

## Integration handoff note

Section 4 should consume `artifact_path: AudioArtifactPath` from the captured branch only.
The Section 3 cleanup `finally` must remain wrapped around downstream stages so artefact deletion is guaranteed regardless of transcription/insertion success.

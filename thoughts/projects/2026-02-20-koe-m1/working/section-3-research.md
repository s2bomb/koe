---
date: 2026-02-20T13:42:29+11:00
researcher: opencode
git_commit: 6725071
branch: master
repository: s2bomb/koe
topic: "Section 3 of thoughts/projects/2026-02-20-koe-m1/spec.md: Audio Capture and Temporary Artefact Lifecycle"
tags: [research, codebase, koe, section-3, audio-capture, temp-artifacts]
status: complete
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 3: Audio Capture and Temporary Artefact Lifecycle"
last_updated: 2026-02-20
last_updated_by: opencode
---

# Research: Section 3 (Audio Capture and Temporary Artefact Lifecycle)

**Date**: 2026-02-20T13:42:29+11:00
**Researcher**: opencode
**Git Commit**: 6725071
**Branch**: master
**Repository**: s2bomb/koe

## Research Question

Document the current codebase state for Section 3 of `thoughts/projects/2026-02-20-koe-m1/spec.md` with full acceptance-criteria coverage for:
- Whisper-compatible audio capture defaults
- temporary WAV artefact creation/lifecycle
- microphone-unavailable error handling
- temporary artefact cleanup behavior
- zero-duration/near-empty capture routing

## Summary

Section 3 runtime behavior is not implemented yet in the live code path. `audio.py` remains a stub, and `run_pipeline` stops at a Section 3 handoff marker before any capture/transcription steps execute. The codebase currently contains type/config contracts that define intended audio and error vocabulary, but there is no executable microphone capture, temporary WAV creation, artefact cleanup, or zero-duration handling logic.

## Source Grounding

- Canonical Section 3 acceptance criteria are defined in `thoughts/projects/2026-02-20-koe-m1/spec.md:58`, `thoughts/projects/2026-02-20-koe-m1/spec.md:59`, `thoughts/projects/2026-02-20-koe-m1/spec.md:60`, `thoughts/projects/2026-02-20-koe-m1/spec.md:61`, and `thoughts/projects/2026-02-20-koe-m1/spec.md:62`.
- M1 brief audio expectations are documented in `docs/project-brief.md:75`, `docs/project-brief.md:77`, `docs/project-brief.md:98`, `docs/project-brief.md:179`, `docs/project-brief.md:234`, and `docs/project-brief.md:235`.

## Acceptance Criteria Coverage (Section 3)

### AC1: 16 kHz float32 capture with temporary WAV artefact

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:58`

What exists today:
- Audio capture settings are present in config contracts/defaults: `src/koe/config.py:11`, `src/koe/config.py:13`, `src/koe/config.py:25`, `src/koe/config.py:27`.
- Temp directory setting exists in config/defaults: `src/koe/config.py:20` and `src/koe/config.py:34`.
- Runtime type for an audio artefact path exists: `src/koe/types.py:11`.
- `audio.py` has no implementation beyond module stub: `src/koe/audio.py:1`.
- Pipeline does not reach capture stage: `src/koe/main.py:76`.

Status vs AC:
- Configuration/type intent exists.
- No implemented capture-to-WAV behavior exists in runtime code.

### AC2: Microphone unavailable/inaccessible gives explicit error and safe exit

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:59`

What exists today:
- Typed audio error schema exists: `src/koe/types.py:84` through `src/koe/types.py:88`.
- Notification kind includes audio failures: `src/koe/types.py:71`.
- Pipeline outcome includes audio error outcome: `src/koe/types.py:123`.
- Exit mapping for `"error_audio"` is implemented: `src/koe/main.py:89` and `src/koe/main.py:94`.
- Notification transport is implemented and non-raising: `src/koe/notify.py:12` through `src/koe/notify.py:23`.
- No microphone probing/capture logic exists in `audio.py`: `src/koe/audio.py:1`.

Status vs AC:
- Error vocabulary, notification transport, and exit mapping are present.
- No executable microphone-unavailable detection path is implemented.

### AC3: Temporary WAV creation failure triggers I/O-class notification and blocks transcription

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:60`

What exists today:
- No WAV creation logic exists: `src/koe/audio.py:1`.
- No transcription handoff from recorded artefact exists in pipeline; execution halts at Section 3 boundary: `src/koe/main.py:76`.
- `transcribe.py` is also a stub: `src/koe/transcribe.py:1`.

Status vs AC:
- No implemented temp-file creation failure branch exists.
- No implemented notification mapping specific to WAV creation I/O failure exists.

### AC4: Temporary audio artefacts removed on success and handled error exits

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:61`

What exists today:
- No temp audio creation exists, so no audio artefact cleanup logic exists in `audio.py`: `src/koe/audio.py:1`.
- Existing `run_pipeline` `finally` cleanup currently covers only lockfile release: `src/koe/main.py:77` through `src/koe/main.py:78`.

Status vs AC:
- No section-owned temp artefact lifecycle implementation exists.

### AC5: Zero-duration/near-empty capture routes to no-speech behavior

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:62`

What exists today:
- `TranscriptionResult` includes explicit empty/no-speech variant: `src/koe/types.py:44` through `src/koe/types.py:46` and `src/koe/types.py:59`.
- Pipeline outcome includes `"no_speech"`: `src/koe/types.py:121`.
- Exit mapping for `"no_speech"` is implemented: `src/koe/main.py:87` and `src/koe/main.py:94`.
- Type tests verify the three-armed transcription result union including empty: `tests/test_types.py:68` through `tests/test_types.py:71` and `tests/test_types.py:90` through `tests/test_types.py:116`.
- No capture-duration logic exists in runtime audio module: `src/koe/audio.py:1`.

Status vs AC:
- Type-level route vocabulary for no-speech exists.
- No runtime zero-duration/near-empty capture detection and routing logic is implemented.

## Current Implementation Map (Section 3-owned surface)

- `src/koe/audio.py:1` - Section 3 module is currently a stub.
- `src/koe/main.py:76` - pipeline explicitly raises Section 3 handoff marker before capture/transcribe/insert stages.
- `src/koe/transcribe.py:1` - downstream transcription module is currently a stub.

## Contract Surfaces Already Enforced by Code/Test

- Audio capture defaults in immutable config: `src/koe/config.py:11`, `src/koe/config.py:13`, `src/koe/config.py:25`, `src/koe/config.py:27`.
- Temp directory config contract: `src/koe/config.py:20` and `src/koe/config.py:34`.
- Audio artefact and audio/transcription error vocabulary: `src/koe/types.py:11`, `src/koe/types.py:84` through `src/koe/types.py:88`, `src/koe/types.py:44` through `src/koe/types.py:59`.
- No-speech and audio-error outcomes represented in pipeline outcomes: `src/koe/types.py:121` and `src/koe/types.py:123`.
- Exit mapping for no-speech/audio error outcomes: `src/koe/main.py:87`, `src/koe/main.py:89`, `src/koe/main.py:94`.
- Runtime shape checks for transcription empty/error variants: `tests/test_types.py:68` through `tests/test_types.py:71` and `tests/test_types.py:90` through `tests/test_types.py:116`.

## Code References & Examples

- `src/koe/main.py:53` through `src/koe/main.py:78` - current pipeline ends at Section 3 handoff marker.

```python
def run_pipeline(config: KoeConfig, /) -> PipelineOutcome:
    preflight = dependency_preflight(config)
    if preflight["ok"] is False:
        send_notification("error_dependency", preflight["error"])
        return "error_dependency"

    lock_result = acquire_instance_lock(config)
    if lock_result["ok"] is False:
        send_notification("already_running", lock_result["error"])
        return "already_running"

    lock_handle = lock_result["value"]
    try:
        x11_context = check_x11_context()
        if x11_context["ok"] is False:
            send_notification("error_dependency", x11_context["error"])
            return "error_dependency"

        focused_window = check_focused_window()
        if focused_window["ok"] is False:
            send_notification("error_focus", focused_window["error"])
            return "no_focus"

        raise NotImplementedError("Section 3 handoff implemented in later sections")
    finally:
        release_instance_lock(lock_handle)
```

- `src/koe/audio.py:1` - current Section 3 module body.

```python
"""Section-owned module stub for later implementation."""
```

- `src/koe/config.py:23` through `src/koe/config.py:35` - capture-related defaults already encoded.

```python
DEFAULT_CONFIG: Final[KoeConfig] = {
    "hotkey_combo": "<super>+<shift>+v",
    "sample_rate": 16_000,
    "audio_channels": 1,
    "audio_format": "float32",
    "whisper_model": "base.en",
    "whisper_device": "cuda",
    "whisper_compute_type": "float16",
    "paste_key_modifier": "ctrl",
    "paste_key": "v",
    "lock_file_path": Path("/tmp/koe.lock"),
    "temp_dir": Path("/tmp"),
}
```

## Architecture Documentation (As Implemented)

- Section 3 is currently represented by typed contracts and configuration defaults, not executable audio runtime logic.
- The live orchestrator currently implements Section 2 preconditions and lock cleanup, then intentionally stops at a Section 3 boundary marker.
- No temporary-audio artefact lifecycle exists yet in runtime code paths.

## Historical Context (from thoughts/)

- Section 3 requirements are specified at `thoughts/projects/2026-02-20-koe-m1/spec.md:52` through `thoughts/projects/2026-02-20-koe-m1/spec.md:63`.
- Prior project-level research listed Section 3 as a planned module concern (`thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md:162` through `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md:163`).
- Draft spec similarly defines Section 3 capture + temp artefact obligations (`thoughts/specs/2026-02-20-koe-m1-spec.md:90` through `thoughts/specs/2026-02-20-koe-m1-spec.md:99`).

## Related Research

- `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-1-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-2-research.md`

## Open Questions

- Which concrete function signatures in `src/koe/audio.py` will own capture start/stop, WAV persistence, and cleanup boundaries in Section 3 implementation.
- Where the audio artefact cleanup ownership boundary will sit between `src/koe/audio.py` and `src/koe/main.py` orchestration.

## Assumptions & Risks

- **Assumption**: `docs/project-brief.md` is the effective source brief for Section 3 grounding.
  - **Why**: `thoughts/projects/2026-02-20-koe-m1/spec.md:14` points to `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md`, but that file is not present in `thoughts/projects/2026-02-20-koe-m1/sources/`.
  - **Validation approach**: confirm canonical brief path in project source maintenance flow.
  - **Risk if wrong**: Section 3 planning can be anchored to a non-canonical brief copy.

- **Assumption**: No `hack/spec_metadata.sh` script exists for metadata generation in this repository state.
  - **Why**: repository glob search for `**/spec_metadata.sh` returned no matches.
  - **Validation approach**: confirm whether metadata helper script is expected to be added in a different path.
  - **Risk if wrong**: metadata collection process can drift across section research artifacts.

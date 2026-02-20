---
date: 2026-02-20T17:03:25+11:00
researcher: opencode
git_commit: 22748b8
branch: master
repository: koe
topic: "Section 6 of thoughts/projects/2026-02-20-koe-m1/spec.md. Focus: User Feedback, Exit Semantics, and Observability"
tags: [research, codebase, section-6, notifications, exit-semantics, observability]
status: complete
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 6: User Feedback and Error Surfaces"
last_updated: 2026-02-20
last_updated_by: opencode
---

# Research: Section 6 User Feedback, Exit Semantics, and Observability

**Date**: 2026-02-20T17:03:25+11:00
**Researcher**: opencode
**Git Commit**: 22748b8
**Branch**: master
**Repository**: koe

## Research Question

Document the current as-is implementation status for Section 6 of `thoughts/projects/2026-02-20-koe-m1/spec.md`, with full acceptance-criteria coverage, plus focused documentation of runtime exit semantics and observability behavior.

## Summary

Section 6 behavior is implemented in the runtime orchestration and notification transport layers. `run_pipeline()` emits lifecycle notifications at each major state (`src/koe/main.py:79`, `src/koe/main.py:92`, `src/koe/main.py:108`) and emits explicit failure notifications by subsystem path (`src/koe/main.py:59`, `src/koe/main.py:76`, `src/koe/main.py:87`, `src/koe/main.py:100`, `src/koe/main.py:105`).

Exit semantics are centralized through `PipelineOutcome -> ExitCode` mapping (`src/koe/main.py:116`) and applied by `main()` (`src/koe/main.py:23`). Notification transport is best-effort and non-raising (`src/koe/notify.py:12`, `src/koe/notify.py:22`), with test coverage confirming backend failures are swallowed (`tests/test_notify.py:42`).

Current observability surface is user-facing desktop notifications; no additional logging/metrics/tracing runtime sink is present in the pipeline modules (`src/koe/main.py:59`, `src/koe/notify.py:16`).

## Acceptance Criteria Coverage (Section 6)

Canonical criteria source: `thoughts/projects/2026-02-20-koe-m1/spec.md:95`.

### AC1: Lifecycle states are user-visible (recording started, processing, completed, error)

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:95`
- **Status**: implemented
- **Evidence**:
  - Recording started: `send_notification("recording_started")` in pipeline flow (`src/koe/main.py:79`).
  - Processing: `send_notification("processing")` before transcription call (`src/koe/main.py:92`, `src/koe/main.py:93`).
  - Completed: success notification after insertion success (`src/koe/main.py:108`).
  - Error notifications are emitted on dependency/focus/audio/transcription/insertion paths (`src/koe/main.py:59`, `src/koe/main.py:76`, `src/koe/main.py:87`, `src/koe/main.py:100`, `src/koe/main.py:105`).
  - Tests assert lifecycle ordering and completion/error emission (`tests/test_main.py:307`, `tests/test_main.py:480`, `tests/test_main.py:631`).

### AC2: Notifications map to clear run phases

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:96`
- **Status**: implemented
- **Evidence**:
  - Pre-record failure phase: dependency and lock/focus checks notify and return before capture (`src/koe/main.py:57`, `src/koe/main.py:64`, `src/koe/main.py:76`).
  - Recording phase notification emitted immediately before capture (`src/koe/main.py:79`, `src/koe/main.py:80`).
  - Processing phase notification emitted immediately before transcription (`src/koe/main.py:92`, `src/koe/main.py:93`).
  - Completion and failure phases terminate with explicit notification + outcome (`src/koe/main.py:105`, `src/koe/main.py:106`, `src/koe/main.py:108`, `src/koe/main.py:109`).
  - Tests verify processing notification precedes transcription invocation (`tests/test_main.py:538`, `tests/test_main.py:583`).

### AC3: Error notifications identify subsystem category (focus, audio, transcription/CUDA, insertion, dependency/preflight)

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:97`
- **Status**: implemented
- **Evidence**:
  - Typed subsystem categories are explicit in error contracts: focus/audio/transcription/insertion/dependency (`src/koe/types.py:97`, `src/koe/types.py:102`, `src/koe/types.py:65`, `src/koe/types.py:108`, `src/koe/types.py:114`).
  - Pipeline routes each category to matching notification kind (`src/koe/main.py:76`, `src/koe/main.py:87`, `src/koe/main.py:100`, `src/koe/main.py:105`, `src/koe/main.py:59`).
  - CUDA-specific transcription details are preserved in typed payload (`src/koe/types.py:68`) and set by transcribe logic (`src/koe/transcribe.py:54`, `src/koe/transcribe.py:93`).
  - Runtime tests cover each category-shaped error through pipeline branches (`tests/test_main.py:116`, `tests/test_main.py:170`, `tests/test_main.py:396`, `tests/test_main.py:586`, `tests/test_main.py:311`).

### AC4: Notification emission failures do not crash core runtime path

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:99`
- **Status**: implemented
- **Evidence**:
  - Notification transport wraps `notify-send` in `try/except Exception` and returns on failure (`src/koe/notify.py:15`, `src/koe/notify.py:22`).
  - Unit test verifies backend failure is swallowed (`tests/test_notify.py:42`, `tests/test_notify.py:45`).
  - `main()` still has global unexpected-exception exit mapping (`src/koe/main.py:25`, `src/koe/main.py:26`) and test coverage (`tests/test_main.py:19`, `tests/test_main.py:26`).

## Exit Semantics (as implemented)

- `run_pipeline()` returns closed `PipelineOutcome` variants (`src/koe/types.py:136`, `src/koe/main.py:56`).
- `outcome_to_exit_code()` maps success to `0`, expected operational outcomes to `1`, and unexpected to `2` (`src/koe/main.py:118`, `src/koe/main.py:129`, `src/koe/main.py:131`).
- `main()` calls `sys.exit(outcome_to_exit_code(outcome))` on normal path (`src/koe/main.py:23`, `src/koe/main.py:24`).
- Any uncaught exception in `main()` exits with code `2` (`src/koe/main.py:25`, `src/koe/main.py:26`).
- Tests validate total mapping and unexpected-exception behavior (`tests/test_main.py:98`, `tests/test_main.py:113`, `tests/test_main.py:19`, `tests/test_main.py:26`).

## Observability Surface (as implemented)

- User-facing observability channel is desktop notification emission via `notify-send` subprocess (`src/koe/notify.py:16`, `src/koe/notify.py:17`).
- Pipeline observability events are lifecycle and failure notification kinds dispatched from orchestration (`src/koe/main.py:79`, `src/koe/main.py:92`, `src/koe/main.py:108`, `src/koe/main.py:105`).
- Notification vocabulary is a closed literal set (`src/koe/types.py:83`) and static fixtures assert exhaustive handling (`tests/section1_static_fixtures.py:51`).
- Error payload observability includes typed category/message fields plus subsystem-specific fields (`src/koe/types.py:97`, `src/koe/types.py:105`, `src/koe/types.py:68`, `src/koe/types.py:111`, `src/koe/types.py:117`).

## Code References & Examples

- `src/koe/main.py:79` / `src/koe/main.py:92` / `src/koe/main.py:108` - lifecycle notification emission in order.
- `src/koe/main.py:116` - exit code mapping function.
- `src/koe/notify.py:12` - notification transport wrapper with non-raising behavior.

```python
def run_pipeline(config: KoeConfig, /) -> PipelineOutcome:
    ...
    send_notification("recording_started")
    ...
    send_notification("processing")
    ...
    if insertion_result["ok"] is False:
        send_notification("error_insertion", insertion_result["error"])
        return "error_insertion"
    send_notification("completed")
    return "success"
```

```python
def send_notification(kind: NotificationKind, error: KoeError | None = None) -> None:
    title, message = _notification_payload(kind, error)
    try:
        subprocess.run(["notify-send", title, message], check=False, capture_output=True, text=True)
    except Exception:
        return
```

## Historical Context (thoughts/)

- Section 6 acceptance criteria baseline: `thoughts/projects/2026-02-20-koe-m1/spec.md:89`.
- Prior spec mirror for Section 6 user stories/criteria: `thoughts/specs/2026-02-20-koe-m1-spec.md:120`.
- Section 4 and Section 5 working docs consistently treated notification copy/rendering as Section 6 scope while validating kind/payload routing in runtime (`thoughts/projects/2026-02-20-koe-m1/working/section-4-research.md:129`, `thoughts/projects/2026-02-20-koe-m1/working/section-5-research.md:119`).

## Related Research

- `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-4-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-5-research.md`

## Open Questions

- None identified from the current Section 6 runtime implementation surface.

## Assumptions & Risks

- **Assumption**: metadata helper script `hack/spec_metadata.sh` is not available in this working tree.
  - **Why**: `hack/` script path is absent in repository glob results.
  - **Validation approach**: add or restore metadata helper if required by process automation.
  - **Risk if wrong**: metadata field generation could diverge from automated conventions.

# Placeholder Spec

No approved spec was provided at project creation time.

Required next step: create or provide an approved spec that includes an explicit `## Section Breakdown`.

---

# Koe M1 Requirements Specification

## Scope and Source of Truth

- Scope is strictly **Milestone 1** (terminal proof of concept on X11 only).
- Primary source brief: `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md`.
- Codebase grounding reference: `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md`.
- Existing completed draft used for continuity: `thoughts/specs/2026-02-20-koe-m1-spec.md`.

## Milestone 1 Outcome

- A user triggers Koe from a global hotkey while a terminal is focused, speaks, stops recording, and receives pasted transcription in the active terminal input.
- Runtime is on-demand and single-run: start, capture, transcribe, insert, clean up, exit.
- Failures are explicit via notifications and never fail silently.
- Temporary artefacts are removed and clipboard safety guarantees are upheld on defined exit paths.

## Section Breakdown

### Section 1: Foundations and Delivery Baseline

Boundary:
- Establish repository-level prerequisites required before runtime sections can pass acceptance.

Acceptance criteria:
- `src/koe/` contains the M1 module surface (`main.py`, `hotkey.py`, `audio.py`, `transcribe.py`, `window.py`, `insert.py`, `notify.py`, `config.py`, `types.py`).
- Shared pipeline types are defined in one place with explicit contracts for: hotkey action, window focus result, audio artefact path, transcription result, clipboard state, and notification kind.
- `pyproject.toml` declares required M1 runtime libraries from the brief (`faster-whisper`, `sounddevice`, `numpy`, `pynput`) plus test/developer libraries (`pytest`, `typeguard`) and a runnable CLI entrypoint.
- A `Makefile` (or equivalent committed command surface) provides executable `lint`, `typecheck`, `test`, and `run` commands.
- Type/lint baseline aligns with repository policy (`pyproject.toml:24`, `pyproject.toml:37`) and is runnable.

### Section 2: Invocation, Focus Gate, and Concurrency Guard

Boundary:
- Define run invocation semantics and pre-recording guards only.

Acceptance criteria:
- Invocation path is explicitly defined for M1: external global hotkey launches Koe; no persistent daemon is introduced.
- Before audio capture begins, Koe validates focused-window presence using X11 tooling.
- If no focused window exists, Koe shows a notification and exits without recording.
- Single-instance protection is enforced: a second invocation during an active run does not start a concurrent pipeline.
- When blocked by the concurrency guard, user receives explicit "already running" feedback (not silent ignore).
- Startup dependency failures (missing X11 tools, missing display context, unavailable CUDA per M1 policy) surface as explicit error notifications and safe exit.

### Section 3: Audio Capture and Temporary Artefact Lifecycle

Boundary:
- Capture microphone audio and manage temporary recording artefacts only.

Acceptance criteria:
- Recording uses Whisper-compatible capture defaults from M1 config (16 kHz, float32 intent) and produces a temporary WAV artefact for transcription input.
- Microphone unavailable/inaccessible states produce explicit error notifications and exit safely.
- If temporary WAV creation fails, Koe exits safely with an I/O-class error notification and does not continue to transcription.
- Temporary audio artefacts are removed on success exits and handled error exits.
- Zero-duration/near-empty capture path is defined and routes cleanly into "no speech detected" behaviour (not silent failure).

### Section 4: Local CUDA Transcription

Boundary:
- Convert recorded artefact to transcript text using local GPU path only.

Acceptance criteria:
- Transcription executes with CUDA-required policy for M1; CPU fallback is treated as error.
- CUDA unavailable or transcription backend unavailable states are explicit, user-visible errors.
- Empty/whitespace transcription does not paste; user receives "no speech detected" feedback.
- Non-useful transcription tokens from silence/noise are treated as non-pasteable output for M1 and follow the same feedback path.
- Successful transcription returns text suitable for insertion step consumption.

### Section 5: Insertion and Clipboard Safety

Boundary:
- Insert transcript into focused terminal input and preserve user clipboard behaviour.

Acceptance criteria:
- Insertion uses clipboard-write plus simulated paste strategy aligned with X11 approach in the brief.
- M1 acceptance validates text insertion into terminal input in the target environment.
- Clipboard backup is attempted before write/paste sequence, and successful runs restore original clipboard content after paste.
- Insertion failure path is explicit: user receives actionable recovery feedback and cleanup still runs.
- Clipboard restore failure after paste is surfaced explicitly so clipboard side effects are never silent.
- Text-only clipboard guarantee and non-text limitation are documented for M1.

### Section 6: User Feedback and Error Surfaces

Boundary:
- Define notification contract and failure-category clarity across the run lifecycle.

Acceptance criteria:
- Lifecycle states are user-visible: recording started, processing, completed, and error.
- Notifications map to clear run phases (pre-record failure, recording, processing, completion, failure).
- Error notifications identify subsystem category at minimum: focus/context, audio, transcription/CUDA, insertion/clipboard, dependency/preflight.
- Notification emission failures do not crash the core runtime path.

### Section 7: Quality Gates, Tests, and Onboarding Readiness

Boundary:
- Define verification obligations for M1 completion.

Acceptance criteria:
- Unit tests exist for each module boundary plus one end-to-end terminal flow integration test.
- Error-path tests cover at least: no focused window, missing microphone, transcription/CUDA unavailable, insertion/dependency failure.
- Project commands for lint/typecheck/test/run execute successfully in a clean environment.
- README setup/run documentation is sufficient for a new contributor to achieve first successful transcription within 15 minutes.

## Developer Notes

- Codebase is currently scaffold-only (`src/koe/__init__.py`, `src/koe/py.typed`), so M1 runtime behaviour is net-new and must be specified explicitly.
- Repo enforcement is Pyright strict and Ruff, so acceptance criteria are aligned to configured tooling rather than introducing a separate mypy gate.
- `thoughts/projects/2026-02-20-koe-m1/index.md` expects this file to contain explicit section breakdown before downstream section execution.
- Existing draft spec at `thoughts/specs/2026-02-20-koe-m1-spec.md` confirms M1 defaults and informed bounded section structure.

## Technical Discovery

### Existing Patterns

- Strict typing/linting baseline already exists in `pyproject.toml:24` and `pyproject.toml:37`.
- Typed package marker exists at `src/koe/py.typed`.
- Runtime integration patterns (hotkey, audio, clipboard, notify, orchestration) are currently absent and must be introduced in M1 scope.

### Integration Points

- System tools from source brief (`xdotool`, `xclip`, `notify-send`, PortAudio, CUDA stack) are hard integration dependencies for M1 behaviour.
- Project command surface (`lint`, `typecheck`, `test`, `run`) is required for acceptance and onboarding.

## Perspective Analysis Summary

Alignment:
- Section decomposition into foundations, invocation, capture, transcription, insertion, feedback, and quality gates is high-confidence and matches brief plus research.
- Concurrency guard, explicit error surfaces, and clipboard safety are mandatory for trustworthy M1 behaviour.
- M1 must resolve invocation semantics and dependency preflight clearly to avoid silent or ambiguous runtime failure.

Divergence requiring explicit treatment in M1 criteria (captured above):
- Terminal paste keystroke behaviour differs by terminal; acceptance is framed as observed terminal insertion with config-backed key path.
- `pydantic` role versus minimal-dependency posture remains undecided; this is treated as an open design question, not a blocker for section indexing.

## Open Questions

- [ ] Should `pydantic` remain in M1 runtime for config validation, or be removed to match minimal-dependency intent?
- [ ] Should M1 explicitly standardise default paste keystroke for terminal-first environments (for example `Ctrl+Shift+V`) versus relying on per-terminal configuration?
- [ ] Should binary/non-text clipboard restoration be handled in M1, or documented as accepted text-only limitation?

---

## Addendum: Wayland and Omarchy Implementation Sections

### Section 8: Omarchy Hotkey Trigger and Per-Run Usage Logging Validation (Wayland)

Boundary:
- Add a Wayland/Omarchy invocation path that launches one single-shot Koe run per hotkey activation and validates per-run usage logging behaviour.
- Preserve M1 process model (invoke, run, exit) and concurrency guarantees; no daemon/background service is introduced.

Section ordering and dependency:
- Depends on Section 2 invocation/concurrency contracts and Section 6 notification/error-surface contracts.
- Must be implemented before Section 9 end-to-end Wayland runtime validation, because Section 9 relies on a functioning Omarchy trigger path.

Acceptance criteria:
- Omarchy hotkey integration can trigger Koe from a focused Wayland session without requiring the X11 hotkey path.
- Each hotkey activation produces exactly one run attempt and exactly one usage-log record suitable for validation (success or failure outcome included).
- Concurrent invocations remain blocked by the existing single-instance guard; blocked attempts are still represented in usage logging with a distinct outcome.
- If Omarchy trigger dependencies/configuration are missing, Koe exits safely with explicit feedback and emits a failed-attempt usage-log record.
- Per-run logging validation is testable: automated tests verify one-record-per-run semantics and manual validation confirms record emission on real Omarchy runtime.

Out of scope for Section 8:
- Historical analytics dashboards, long-term telemetry pipelines, or remote metrics export.
- Runtime redesign into a persistent listener/daemon.
- Wayland focus detection or text insertion mechanics (owned by Section 9).

### Section 9: Wayland-Native Focus and Insert Backend (Omarchy End-to-End Runtime)

Boundary:
- Add a Wayland-native focus-detection and insertion backend so the full Koe run (trigger -> capture -> transcribe -> insert) completes under Omarchy.
- Keep architecture composable: define backend interfaces and provide adapters for both X11 and Wayland, without rewriting shared pipeline stages.

Section ordering and dependency:
- Depends on Section 8 trigger/logging completion.
- Depends on Sections 3-5 for shared audio/transcription/clipboard-stage contracts and on Section 6 for consistent user-visible error handling.
- Must preserve existing X11 behaviour as the reference adapter while adding Wayland adapter coverage.

Acceptance criteria:
- Runtime selects focus/insert backend by environment/context and routes through a common backend interface used by `main.py` orchestration.
- X11 adapter remains functional and behaviourally unchanged for existing M1 acceptance criteria.
- Wayland adapter provides focused-target validation before recording and insertion behaviour sufficient for end-to-end Omarchy terminal dictation.
- Wayland focus/insert failures are explicit and category-aligned (focus/context or insertion/backend), with no silent degradation.
- End-to-end validation on Omarchy confirms: hotkey trigger, recording, local CUDA transcription, Wayland insertion, cleanup, and terminal-visible output.

Out of scope for Section 9:
- Universal compositor support beyond Omarchy-targeted Wayland runtime.
- Rich input-semantic detection beyond focused-target gate required for run safety.
- Replacing the linear single-shot pipeline with a new architecture.

## Addendum Developer Notes (Traceability)

- M1 currently constrains platform scope to X11-only (`thoughts/projects/2026-02-20-koe-m1/spec.md:13`, `AGENTS.md:35`), so this addendum explicitly extends scope with ordered sections rather than mutating existing M1 requirements.
- Original source brief marks Wayland as future/out-of-scope for initial milestone (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:54`, `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:192`), which is why this appears as a post-M1 addendum.
- Composable backend requirement is grounded in prior architectural intent that `window.py` and `insert.py` are the swap points for platform-specific logic (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:251`, `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:271`).
- Single-shot/no-daemon behaviour remains invariant across X11 and Wayland extensions (`thoughts/projects/2026-02-20-koe-m1/spec.md:21`, `AGENTS.md:13`).

---
date: 2026-02-20T21:19:39+11:00
researcher: bradkk-safer
git_commit: d1319abf895c767df685f8fe6a1168310341aa4d
branch: master
repository: koe
topic: "Koe M1 + Section 8/9 Runtime Hardening Handoff"
tags: [handoff, koe, wayland, omarchy, hotkey, logging, whisper, audio, integration]
status: complete
last_updated: 2026-02-20
last_updated_by: bradkk-safer
type: handoff
---

# Handoff: Koe M1 orchestration complete, real-runtime gaps found, Wayland hardening in-progress

## Task(s)

### 1) Full architect pipeline orchestration from scaffold to validated sections (completed)
- Completed end-to-end orchestrated workflow for original M1 sections 1-7 using delegated command agents:
  - `/spec-writer` -> `/research-codebase` -> `/api-designer` -> `/test-designer` -> `/create-plan` -> `/test-implementer` -> `/implement-plan` -> `/validate-plan`
- Produced complete artifacts under `thoughts/projects/2026-02-20-koe-m1/` and `thoughts/design/`, `thoughts/plans/`.
- Section-level validation reports exist for sections 1-7; Section 8 was later added and also has research/test-spec/plan/validation docs.

### 2) Omarchy hotkey + usage logging objective (Section 8) (partially complete + manually validated)
- Implemented and manually validated hotkey trigger path and usage log append behavior.
- Hyprland keybinding was updated to invoke repo-local command via uv.
- Manual verification proved:
  - hotkey triggers process
  - notification appears
  - `/tmp/koe-usage.jsonl` appends one line per invocation
- At this point outcomes were all `no_focus` (before Wayland backend work).

### 3) Real integration audit after CEO escalation (critical findings surfaced)
- Ran real (not mocked) checks and discovered major truth:
  - tests were strong for contracts but weak for live runtime integration
  - real microphone call failed (`frames must be specified`)
  - real whisper smoke run failed due to missing CUDA runtime lib (`libcublas.so.12`)
  - Wayland focus under xdotool path was not viable in this environment

### 4) Addendum scope extension for Wayland (Section 8 + Section 9) (completed at spec/artifact level)
- `thoughts/projects/2026-02-20-koe-m1/spec.md` now includes addendum sections:
  - Section 8: Omarchy hotkey + per-run usage logging
  - Section 9: Wayland-native focus/insert backend with composable adapters

### 5) Runtime hardening implementation pass started after stakeholder council output (IN PROGRESS, NOT RE-VALIDATED)
- I started code changes directly in core runtime modules to close hard blockers.
- This pass is **not finalized** and **full test/validation has not been rerun after the latest edits**.
- Current git state is dirty with many modified files and untracked artifacts.

## Critical References

- `thoughts/projects/2026-02-20-koe-m1/spec.md` (especially addendum Section 8/9 at `:150+`)
- `thoughts/plans/2026-02-20-koe-m1-section-8-omarchy-usage-logging-plan.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-8-validation-report.md`

## Recent Changes

### Core runtime hardening edits (latest WIP pass)
- `src/koe/main.py:45` - Expanded `dependency_preflight` for backend-aware dependencies, soundfile presence check, writable temp/lock path checks.
- `src/koe/main.py:118` - Added `KOE_BACKEND` override-aware `_is_wayland_session()` logic (x11/wayland explicit override).
- `src/koe/window.py:13` - Added Wayland branch in `check_x11_context()` requiring `hyprctl` when in wayland mode.
- `src/koe/window.py:51` - `check_focused_window()` now routes to `_check_wayland_focused_window()` under wayland mode.
- `src/koe/window.py:139` - Added Hyprland active-window JSON parser (`hyprctl activewindow -j`) to build `FocusedWindow` for Wayland.
- `src/koe/insert.py:117` - Added Wayland-aware paste path selection.
- `src/koe/insert.py:224` - Added Wayland clipboard command selection (`wl-paste`/`wl-copy` fallback logic).
- `src/koe/insert.py:236` - Added `_simulate_wayland_paste()` split into `_simulate_wtype_paste()` and `_simulate_hyprctl_paste()`.
- `src/koe/insert.py:214` - Added `KOE_BACKEND` override-aware session detection.
- `src/koe/audio.py:62` - Added `_CAPTURE_SECONDS = 8`.
- `src/koe/audio.py:68` - Added explicit `frames` argument to `sounddevice.rec(...)` to avoid runtime error.
- `src/koe/transcribe.py:57` - Moved segment normalization into guarded try block so generator-time failures map to typed error.
- `src/koe/hotkey.py:39` - Added stale-lock liveness detection (`os.kill(pid, 0)` via `_is_process_alive`).
- `src/koe/hotkey.py:49` - Added `_try_break_stale_lock()` and auto-reacquire behavior.
- `src/koe/hotkey.py:76` - Improved already-running message with stale-lock remediation path.
- `src/koe/usage_log.py:33` - Switched usage log writing to `os.open(..., mode=0o600)` for privacy-hardening.
- `src/koe/notify.py:62` - Insertion error notifications now append transcript text for manual recovery (`Transcript: ...`).
- `pyproject.toml:13` - Added runtime dependency `soundfile>=0.12.1`.
- `README.md:7` - Updated scope line to mention Omarchy Wayland support intent.
- `README.md:57` - Added usage log section documenting `/tmp/koe-usage.jsonl` behavior.

### External system config change (outside repo)
- `~/.config/hypr/bindings.conf:9` - Keybinding updated to:
  - `bindd = SUPER SHIFT, V, Koe, exec, bash -lc "cd /home/brad/Code/s2bomb/koe && KOE_BACKEND=wayland uv run koe"`
- Note: this was edited directly in user config; ensure `hyprctl reload` is run after edits.

### Test edits in WIP pass (also not revalidated yet)
- `tests/test_audio.py:31` - Added assertion for `frames == sample_rate * 8`.
- `tests/test_transcribe.py:30` - Added generator-failure fake model and assertion that lazy generator errors map to typed transcription error.
- `tests/test_hotkey.py:64` - Added stale-lock recovery test for `acquire_instance_lock`.
- `tests/test_window.py:77` - Added Wayland context/focus tests for `hyprctl` path.
- `tests/test_main.py:245` - Updated dependency preflight test to patch `find_spec` and `os.access`.
- `tests/test_main.py:264` - Added tests for soundfile dependency and writable runtime paths.
- `tests/test_notify.py:106` - Updated insertion-error message expectations to allow transcript suffix.

## Learnings

### What was proven true (hard evidence)
- Hotkey trigger and usage logging are real and observable on the machine:
  - `/tmp/koe-usage.jsonl` appends one record per invocation.
- The earlier binding `exec, koe` failed because `koe` was not on Hypr exec PATH; repo-local `uv run` invocation is required.
- Live `run_pipeline` in this Omarchy wayland environment repeatedly returned `no_focus` before Wayland routing.

### Root causes found during live runtime tests
- `audio.py` missing `frames` caused microphone capture to fail at runtime (`frames must be specified`).
  - Fixed in code at `src/koe/audio.py:68`.
- Real whisper CUDA smoke test hit missing runtime library (`libcublas.so.12`) during inference path.
  - This is an environment/runtime dependency issue, not just unit-test logic.
- Transcription error catching initially missed generator-time segment iteration errors.
  - Guarding normalization inside try catches this now (`src/koe/transcribe.py:57`).

### Architectural implications
- “All tests green” was insufficient because most tests were mocked contract tests.
- Required additional gates must include:
  - real mic capture smoke
  - real whisper GPU inference smoke
  - compositor-native focus + insertion runtime tests

### Session/tooling note
- Requested metadata script `hack/spec_metadata.sh` is not present in this repository (`hack/` missing). Frontmatter metadata in this handoff used fallback git/date commands.

## Artifacts

### Project/index/spec artifacts
- `thoughts/projects/2026-02-20-koe-m1/index.md`
- `thoughts/projects/2026-02-20-koe-m1/spec.md`
- `thoughts/projects/2026-02-20-koe-m1/sources/original-request.md`

### Design docs created/updated
- `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md`
- `thoughts/design/2026-02-20-koe-m1-section-2-api-design.md`
- `thoughts/design/2026-02-20-koe-m1-section-3-api-design.md`
- `thoughts/design/2026-02-20-section-4-transcription-api.md`
- `thoughts/design/2026-02-20-koe-m1-section-5-api-design.md`
- `thoughts/design/2026-02-20-section-6-notify-exit-semantics.md`
- `thoughts/design/2026-02-20-section-7-delivery-gates.md`
- `thoughts/design/2026-02-20-koe-m1-section-7-api-design.md`
- `thoughts/design/2026-02-20-koe-m1-section-8-api-design.md`

### Plans created/updated
- `thoughts/plans/2026-02-20-koe-m1-section-1-foundations-plan.md`
- `thoughts/plans/2026-02-20-koe-m1-section-2-invocation-focus-guard-plan.md`
- `thoughts/plans/2026-02-20-koe-m1-section-3-audio-capture-artifact-lifecycle-plan.md`
- `thoughts/plans/2026-02-20-koe-m1-section-4-local-cuda-transcription-plan.md`
- `thoughts/plans/2026-02-20-koe-m1-section-5-insertion-clipboard-safety-plan.md`
- `thoughts/plans/2026-02-20-koe-m1-section-6-notify-exit-semantics-plan.md`
- `thoughts/plans/2026-02-20-koe-m1-section-7-quality-gates-onboarding-plan.md`
- `thoughts/plans/2026-02-20-koe-m1-section-8-omarchy-usage-logging-plan.md`

### Working research/test-spec/validation docs
- `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-1-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-1-test-spec.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-1-validation-report.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-2-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-2-test-spec.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-2-validation-report.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-3-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-3-test-spec.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-3-validation-report.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-4-historical-context.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-4-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-4-test-spec.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-4-validation-report.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-5-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-5-test-spec.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-5-validation-report.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-6-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-6-test-spec.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-6-validation-report.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-7-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-7-test-spec.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-7-validation-report.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-8-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-8-test-spec.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-8-validation-report.md`

### Spec snapshot artifact
- `thoughts/specs/2026-02-20-koe-m1-spec.md`

### Code/test files changed in latest unfinished hardening pass
- `README.md`
- `pyproject.toml`
- `src/koe/audio.py`
- `src/koe/hotkey.py`
- `src/koe/insert.py`
- `src/koe/main.py`
- `src/koe/notify.py`
- `src/koe/transcribe.py`
- `src/koe/usage_log.py`
- `src/koe/window.py`
- `tests/test_audio.py`
- `tests/test_hotkey.py`
- `tests/test_main.py`
- `tests/test_notify.py`
- `tests/test_transcribe.py`
- `tests/test_window.py`

## Action Items & Next Steps

1. [ ] **Do not assume current branch is releasable**. Re-run full validation now that latest runtime-hardening edits are in place:
   - `make lint`
   - `make typecheck`
   - `make test`
2. [ ] Run targeted tests for newly touched behavior and fix regressions:
   - `uv run pytest tests/test_audio.py tests/test_transcribe.py tests/test_hotkey.py tests/test_window.py tests/test_notify.py tests/test_main.py`
3. [ ] Validate Wayland runtime path end-to-end using new binding and backend override:
   - ensure `hyprctl reload` after binding edit
   - trigger hotkey (`SUPER+SHIFT+V`)
   - verify `/tmp/koe-usage.jsonl` increments
   - verify focus no longer fails due to xdotool-only path
4. [ ] Validate real audio capture now that `frames` is set and `soundfile` dependency added.
5. [ ] Validate real whisper path and decide whether to add explicit CUDA library preflight checks (or stronger troubleshooting fallback) if `libcublas.so.12` still fails.
6. [ ] Decide whether README scope line should be finalized as Wayland supported now, or reverted until Section 9 acceptance is proven.
7. [ ] Reconcile docs/plan/validation statuses with actual code after latest changes (Section 8 currently marked pass-with-issues in prior report; this may change).
8. [ ] Commit strategy:
   - separate commit for runtime code hardening
   - separate commit for test updates
   - separate commit for docs/spec changes
9. [ ] Produce final validation report for Section 8/9 runtime integration with explicit evidence:
   - one successful `outcome: success` run log
   - one controlled failure outcome
   - one contention outcome
10. [ ] Only then resume any remaining roadmap work.

## Other Notes

- Current key external context from user/CEO:
  - They are on Omarchy Wayland and expect product to work there; they explicitly rejected terminal command-only validation as representative.
  - They requested nonstop progress until complete and strong integration realism.
  - They strongly emphasized composability and stakeholder-style truthfulness over green mocked tests.

- Known command outputs observed before latest hardening pass:
  - Earlier full suite pass: `make lint && make typecheck && make test` -> 201 passed.
  - Real whisper smoke failed with `libcublas.so.12` load/runtime error.
  - Real audio capture failed with `frames must be specified` before fix.

- Important caveat:
  - Latest edits were made rapidly in response to stakeholder escalation and handoff request interrupted completion.
  - **No post-edit full test pass was executed in this session after the final batch of code changes.**

- Useful runtime check commands for next agent:
  - `uv run python -c "from koe.main import run_pipeline; from koe.config import DEFAULT_CONFIG; print(run_pipeline(DEFAULT_CONFIG))"`
  - `uv run koe; echo EXIT:$?`
  - `hyprctl binds` (confirm bind exists)
  - `hyprctl reload`
  - `python -c "from pathlib import Path; p=Path('/tmp/koe-usage.jsonl'); print(p.exists(), sum(1 for _ in p.open()) if p.exists() else 0)"`

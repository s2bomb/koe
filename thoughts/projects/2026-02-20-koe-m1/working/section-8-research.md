---
date: 2026-02-20T19:46:37+11:00
researcher: opencode
git_commit: 97279fe
branch: master
repository: s2bomb/koe
topic: "Section 8 of thoughts/projects/2026-02-20-koe-m1/spec.md. Focus: Omarchy hotkey trigger and per-run usage logging validation on Wayland"
tags: [research, codebase, section-8, omarchy, wayland, hotkey, usage-logging]
status: complete
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 8: Omarchy Hotkey Trigger and Per-Run Usage Logging Validation (Wayland)"
last_updated: 2026-02-20
last_updated_by: opencode
---

# Research: Section 8 Omarchy Trigger and Per-Run Usage Logging Validation

**Date**: 2026-02-20T19:46:37+11:00
**Researcher**: opencode
**Git Commit**: 97279fe
**Branch**: master
**Repository**: s2bomb/koe

## Research Question

Document the current as-is implementation for Section 8 of `thoughts/projects/2026-02-20-koe-m1/spec.md`, with full acceptance-criteria coverage and concrete code/config integration surfaces for Omarchy hotkey trigger behavior and per-run usage logging validation on Wayland.

## Summary

Section 8 is specified in the project spec addendum (`thoughts/projects/2026-02-20-koe-m1/spec.md:152`) but is not implemented as a section deliverable in this repository at the time of research.

What exists today:

- Koe runtime is single-shot per invocation (`src/koe/main.py:21`, `src/koe/main.py:23`).
- Concurrent invocations are blocked by lockfile contention and mapped to a distinct outcome (`src/koe/hotkey.py:39`, `src/koe/main.py:62`, `src/koe/types.py:136`).
- Dependency/context failures produce explicit notification outcomes (`src/koe/main.py:57`, `src/koe/main.py:69`, `src/koe/notify.py:43`).

What does not exist today:

- No Wayland/Omarchy backend or integration code under `src/koe/` (no matches for Wayland/Omarchy symbols in source tree).
- No usage logging module, record type, or write path in runtime modules (no matches for usage-log constructs in `src/koe/*.py`).
- No Section 8 working artifacts (`thoughts/projects/2026-02-20-koe-m1/working/section-8*` does not exist).

## Acceptance Criteria Coverage (Section 8)

Canonical criteria source: `thoughts/projects/2026-02-20-koe-m1/spec.md:163`.

### AC1: Omarchy hotkey integration triggers Koe from focused Wayland session without X11 hotkey path

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:163`
- **Status**: not implemented in repository runtime
- **Evidence**:
  - `pyproject.toml:18` defines CLI entrypoint `koe = "koe.main:main"`; no compositor-specific trigger wiring in repo.
  - `src/koe/window.py:12` requires `DISPLAY`; on Wayland this gate returns dependency error if unset (`src/koe/window.py:15`, `src/koe/window.py:20`).
  - `README.md:10` still marks Wayland out of scope.
  - Omarchy user keybind file currently has no Koe binding (`/home/brad/.config/hypr/bindings.conf:1`).
  - Omarchy default dictation binding targets `voxtype`, not `koe` (`/home/brad/.local/share/omarchy/default/hypr/bindings/utilities.conf:55`).

### AC2: Each hotkey activation yields exactly one run attempt and exactly one usage-log record

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:164`
- **Status**: partially satisfied (one run attempt per invocation exists; usage log record does not)
- **Evidence**:
  - One-shot invocation shape: `main()` calls `run_pipeline()` once then exits (`src/koe/main.py:21`, `src/koe/main.py:24`).
  - `PipelineOutcome` models one terminal outcome per run (`src/koe/types.py:136`).
  - No runtime usage-log write path in main orchestration (`src/koe/main.py:56` to `src/koe/main.py:113`).
  - No usage-log schema type in shared contracts (`src/koe/types.py:1` to `src/koe/types.py:148`).

### AC3: Concurrent invocations blocked; blocked attempts represented in usage logging with distinct outcome

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:165`
- **Status**: partially satisfied (blocking + distinct outcome exists; usage-log representation missing)
- **Evidence**:
  - Single-instance lock acquisition via exclusive create (`src/koe/hotkey.py:43`) returns typed `already_running` error on contention (`src/koe/hotkey.py:45`, `src/koe/types.py:120`).
  - Pipeline maps contention to distinct terminal outcome (`src/koe/main.py:63`, `src/koe/main.py:65`, `src/koe/types.py:145`).
  - Tests validate contention short-circuit behavior (`tests/test_hotkey.py:21`, `tests/test_main.py:142`).
  - No log sink exists to persist blocked-attempt records in runtime modules.

### AC4: Missing Omarchy trigger dependencies/config emit explicit feedback and failed-attempt usage-log record

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:166`
- **Status**: partially satisfied (explicit feedback exists; failed-attempt usage-log record missing)
- **Evidence**:
  - Dependency preflight emits typed dependency errors (`src/koe/main.py:29`, `src/koe/main.py:37`) and sends explicit notification (`src/koe/main.py:59`, `src/koe/notify.py:44`).
  - X11 context missing (`DISPLAY`) maps to dependency error path (`src/koe/window.py:15`, `src/koe/main.py:70`, `src/koe/main.py:72`).
  - Tests cover dependency gate variants (`tests/test_main.py:29`) and preflight short-circuit (`tests/test_main.py:116`).
  - No per-run usage-log write for dependency/config failure outcomes.

### AC5: Per-run logging validation is testable (automated one-record-per-run + manual Omarchy runtime confirmation)

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:167`
- **Status**: not implemented
- **Evidence**:
  - Existing automated tests cover lock/dependency/outcomes but do not assert usage-log record semantics (`tests/test_main.py:98`, `tests/test_hotkey.py:21`).
  - Existing docs and validation report remain X11-focused and do not define Omarchy runbook validation for usage logs (`README.md:7`, `README.md:10`, `thoughts/projects/2026-02-20-koe-m1/working/section-7-validation-report.md:61`).
  - No Section 8 test spec or validation report artifact is present under `thoughts/projects/2026-02-20-koe-m1/working/`.

## Omarchy Integration Surfaces (As-Is)

### Hyprland binding and source chain

- Omarchy defaults and user overrides are sourced by Hyprland root config (`/home/brad/.config/hypr/hyprland.conf:4`, `/home/brad/.config/hypr/hyprland.conf:18`).
- User override bindings live in `/home/brad/.config/hypr/bindings.conf` (`/home/brad/.config/hypr/bindings.conf:1`).
- Current dictation hotkeys in Omarchy defaults execute `voxtype` commands (`/home/brad/.local/share/omarchy/default/hypr/bindings/utilities.conf:55`).

### Omarchy dictation tooling currently integrated

- Dictation install path uses `omarchy-voxtype-install` via Omarchy menu (`/home/brad/.local/share/omarchy/bin/omarchy-menu:335`, `/home/brad/.local/share/omarchy/bin/omarchy-menu:336`).
- Voxtype installer installs/configures daemonized dictation workflow (`/home/brad/.local/share/omarchy/bin/omarchy-voxtype-install:13`, `/home/brad/.local/share/omarchy/bin/omarchy-voxtype-install:14`).
- Voxtype config documents daemon state file behavior (`/home/brad/.local/share/omarchy/default/voxtype/config.toml:6`, `/home/brad/.local/share/omarchy/default/voxtype/config.toml:11`).
- Waybar includes `custom/voxtype` status module (`/home/brad/.local/share/omarchy/config/waybar/config.jsonc:8`, `/home/brad/.local/share/omarchy/config/waybar/config.jsonc:144`).

### Koe entrypoint surface available to a compositor command

- CLI entrypoint is present and runnable as `koe` (`pyproject.toml:18`).
- Current repository does not provide an Omarchy binding/config artifact that connects a Hyprland hotkey to this command.

## Runtime Outcome and Feedback Surfaces Relevant to Section 8

- Startup dependency gate: `dependency_preflight()` (`src/koe/main.py:29`).
- Lock contention distinct branch: `already_running` (`src/koe/main.py:64`, `src/koe/main.py:65`).
- X11 context dependency failure includes missing `DISPLAY` (`src/koe/window.py:20`, `src/koe/window.py:21`).
- Notification transport is best-effort and non-raising (`src/koe/notify.py:12`, `src/koe/notify.py:22`).
- Process-level terminal status remains `PipelineOutcome` + `ExitCode` mapping (`src/koe/main.py:116`, `src/koe/types.py:148`).

## Code References & Examples

- `src/koe/main.py:56` - single-run orchestration with early-return outcomes and cleanup

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
```

- `src/koe/hotkey.py:39` - lockfile-based single-instance guard

```python
with lock_file.open("x", encoding="utf-8") as handle:
    handle.write(str(os.getpid()))
```

- `/home/brad/.local/share/omarchy/default/hypr/bindings/utilities.conf:55` - existing Omarchy dictation binding target

```conf
bindd  = SUPER CTRL, X, Start dictation, exec, voxtype record start
binddr = SUPER CTRL, X, Stop dictation, exec, voxtype record stop
```

## Historical Context (from thoughts/)

- Section 8 requirements were added as post-M1 addendum (`thoughts/projects/2026-02-20-koe-m1/spec.md:150`).
- M1 base scope remains X11-focused in earlier docs (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:54`).
- Section 6 research documented notifications as the current observability surface with no additional runtime logging sink (`thoughts/projects/2026-02-20-koe-m1/working/section-6-research.md:34`).

## Related Research

- `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-6-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-7-validation-report.md`

## Open Questions

- None added in this research document. This document records only currently observable implementation and configuration state.

## Assumptions & Risks

- **Assumption**: Omarchy integration surfaces referenced under `/home/brad/.config/hypr/` and `/home/brad/.local/share/omarchy/` are the active runtime config on the target machine.
  - **Why**: Section 8 scope explicitly targets Omarchy trigger validation and these paths are present on host.
  - **Validation approach**: Confirm active Hyprland profile and sourced files during Section 8 manual runtime validation.
  - **Risk if wrong**: Trigger/config evidence could differ from the active compositor profile used for execution.

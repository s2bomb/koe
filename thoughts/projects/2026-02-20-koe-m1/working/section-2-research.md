---
date: 2026-02-20T11:48:29+11:00
researcher: opencode
git_commit: cbdf399
branch: master
repository: s2bomb/koe
topic: "Section 2 of thoughts/projects/2026-02-20-koe-m1/spec.md: Invocation, Focus Gate, and Concurrency Guard"
tags: [research, codebase, koe, section-2, invocation, focus-gate, concurrency-guard]
status: complete
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 2: Invocation, Focus Gate, and Concurrency Guard"
last_updated: 2026-02-20
last_updated_by: opencode
---

# Research: Section 2 (Invocation, Focus Gate, Concurrency Guard)

**Date**: 2026-02-20T11:48:29+11:00
**Researcher**: opencode
**Git Commit**: cbdf399
**Branch**: master
**Repository**: s2bomb/koe

## Research Question

Document the current codebase state for Section 2 of `thoughts/projects/2026-02-20-koe-m1/spec.md`, with full acceptance-criteria coverage for:
- invocation path
- focus gate before recording
- single-instance/concurrency guard
- startup dependency failures and explicit feedback

## Summary

Section 2 behavior is specified in project docs and type contracts, but not implemented in runtime modules yet. The invocation entrypoint exists (`koe.main:main`), `run_pipeline` is intentionally deferred, and Section 2-owned modules remain stubs. Acceptance criteria are represented today by type/config contracts, pipeline outcome vocabulary, and tests that validate those contracts, not by executable hotkey/focus/guard logic.

## Source Grounding

- Canonical Section 2 acceptance criteria are in `thoughts/projects/2026-02-20-koe-m1/spec.md:45` through `thoughts/projects/2026-02-20-koe-m1/spec.md:50`.
- The immutable brief text used for M1 behavior is present at `docs/project-brief.md:14`, `docs/project-brief.md:72`, `docs/project-brief.md:88`, `docs/project-brief.md:99`, `docs/project-brief.md:100`, and `docs/project-brief.md:178`.
- Project source pointer currently references `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md` (`thoughts/projects/2026-02-20-koe-m1/spec.md:14`), but that file is not present; only `thoughts/projects/2026-02-20-koe-m1/sources/original-request.md:1` exists in `sources/`.

## Acceptance Criteria Coverage (Section 2)

### AC1: Invocation path is external global hotkey; no daemon

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:45`

What exists today:
- CLI entrypoint is declared: `pyproject.toml:17` and `pyproject.toml:18`.
- Runtime command surface invokes the entrypoint: `Makefile:12` and `Makefile:13`.
- `main()` calls `run_pipeline(DEFAULT_CONFIG)`: `src/koe/main.py:14` through `src/koe/main.py:17`.
- `run_pipeline` is deferred: `src/koe/main.py:22` through `src/koe/main.py:24`.
- Hotkey module has no implementation yet: `src/koe/hotkey.py:1`.

Status vs AC:
- Invocation entrypoint wiring exists.
- External hotkey launch semantics are documented but not yet implemented in code.

### AC2: Focus check occurs before audio capture using X11 tooling

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:46`

What exists today:
- Focus data contract exists: `src/koe/types.py:30` through `src/koe/types.py:35`.
- Focus error contract exists: `src/koe/types.py:77` through `src/koe/types.py:79`.
- Focus module has no implementation yet: `src/koe/window.py:1`.
- API design documents Stage 3 ordering and X11 check intent: `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:473` through `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:477`.

Status vs AC:
- Type-level contract and stage ordering documentation exist.
- No executable X11 focus check is present yet.

### AC3: No focused window -> notify and exit without recording

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:47`

What exists today:
- Notification kind for focus failure exists: `src/koe/types.py:69`.
- Pipeline outcome includes `"no_focus"`: `src/koe/types.py:104`.
- Exit code mapping for `"no_focus"` is implemented: `src/koe/main.py:31` through `src/koe/main.py:39`.
- `notify.py` is a stub: `src/koe/notify.py:1`.

Status vs AC:
- Outcome vocabulary and exit code behavior are defined.
- Notification emission and focus-gate runtime behavior are not implemented yet.

### AC4: Single-instance protection blocks concurrent second invocation

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:48`

What exists today:
- Lockfile config field exists: `src/koe/config.py:19`.
- Lockfile default is defined: `src/koe/config.py:33`.
- Config shape tests include this field/default indirectly via full config checks: `tests/test_config.py:13` through `tests/test_config.py:15`, and `tests/test_config.py:27`.
- API design assigns Stage 2 guard and lockfile check semantics: `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:467` through `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:470`.

Status vs AC:
- Concurrency guard contract exists in config and design docs.
- No runtime lock acquisition/check/release implementation exists.

### AC5: Blocked concurrency guard must provide explicit "already running" feedback

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:49`

What exists today:
- Design doc describes explicit message on Stage 2 failure: `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:471`.
- Current `NotificationKind` closed set has no explicit `"already_running"` literal: `src/koe/types.py:65` through `src/koe/types.py:74`.
- `notify.py` remains unimplemented: `src/koe/notify.py:1`.

Status vs AC:
- Requirement is documented.
- No runtime feedback path for this condition is implemented.

### AC6: Startup dependency failures are explicit and exit safely

Requirement:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:50`

What exists today:
- Dependency error contract exists: `src/koe/types.py:94` through `src/koe/types.py:97`.
- Notification kind includes `"error_dependency"`: `src/koe/types.py:73`.
- Pipeline outcome includes `"error_dependency"`: `src/koe/types.py:106`.
- Exit code mapping for `"error_dependency"` is implemented: `src/koe/main.py:34` through `src/koe/main.py:39`.
- Config enforces CUDA-only device literal: `src/koe/config.py:15` and `src/koe/config.py:29`.
- Design doc lists startup checks for `xdotool`, `xclip`, `notify-send`, and CUDA: `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:462` through `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:465`.

Status vs AC:
- Dependency/CUDA failure vocabulary and exit mapping exist.
- No executable preflight check implementation exists.

## Current Implementation Map (Section 2-owned modules)

- `src/koe/hotkey.py:1` - module stub only.
- `src/koe/window.py:1` - module stub only.
- `src/koe/notify.py:1` - module stub only (relevant to Section 2 feedback paths).
- `src/koe/main.py:22` through `src/koe/main.py:24` - pipeline orchestration intentionally deferred for Sections 2-6.

## Contract Surfaces Already Enforced by Code/Test

- Hotkey action vocabulary: `src/koe/types.py:27`; exhaustiveness fixture: `tests/section1_static_fixtures.py:43` through `tests/section1_static_fixtures.py:48`.
- Focused window and optional result: `src/koe/types.py:30` through `src/koe/types.py:35`; runtime type tests: `tests/test_types.py:47` through `tests/test_types.py:58`.
- Focus/dependency error schemas: `src/koe/types.py:77` through `src/koe/types.py:79`, `src/koe/types.py:94` through `src/koe/types.py:97`; runtime type tests: `tests/test_types.py:125` through `tests/test_types.py:150`.
- Pipeline outcomes and exit code mapping: `src/koe/types.py:102` through `src/koe/types.py:111`, `src/koe/main.py:27` through `src/koe/main.py:43`; mapping tests: `tests/test_main.py:32` through `tests/test_main.py:46`.
- Lock file and CUDA defaults in config: `src/koe/config.py:15`, `src/koe/config.py:19`, `src/koe/config.py:29`, `src/koe/config.py:33`; config validation tests: `tests/test_config.py:13` through `tests/test_config.py:15` and `tests/test_config.py:35` through `tests/test_config.py:41`.

## Code References & Examples

- `src/koe/main.py:22` through `src/koe/main.py:24` - Section 2 runtime still deferred.

```python
def run_pipeline(config: KoeConfig, /) -> PipelineOutcome:
    _ = config
    raise NotImplementedError("Implemented in Sections 2-6")
```

- `src/koe/types.py:27` - invocation toggle contract.

```python
type HotkeyAction = Literal["start", "stop"]
```

- `src/koe/types.py:30` through `src/koe/types.py:35` - focus gate data shape.

```python
class FocusedWindow(TypedDict):
    window_id: WindowId
    title: str

type WindowFocusResult = FocusedWindow | None
```

- `src/koe/config.py:15` and `src/koe/config.py:29` - CUDA-only policy encoded in config type/default.

```python
whisper_device: Literal["cuda"]
...
"whisper_device": "cuda",
```

- `pyproject.toml:17` through `pyproject.toml:18` - invocation entrypoint.

```toml
[project.scripts]
koe = "koe.main:main"
```

## Architecture Documentation (As Implemented)

- Invocation surface is CLI-based and typed (`pyproject.toml:17`, `src/koe/main.py:14`), with deferred pipeline execution (`src/koe/main.py:24`).
- Section 2 runtime capabilities (hotkey listener, focus check, lock guard, startup preflight) are currently represented as type/config and design contracts, not implemented functions.
- Error/outcome pathways for focus/dependency are pre-modeled in shared types and mapped to process exit semantics.

## Historical Context (from thoughts/)

- Section 2 requirements are explicitly articulated in project spec: `thoughts/projects/2026-02-20-koe-m1/spec.md:39` through `thoughts/projects/2026-02-20-koe-m1/spec.md:50`.
- M1 draft spec records same domain and resolves `pynput` backend decision for M1: `thoughts/specs/2026-02-20-koe-m1-spec.md:61`, `thoughts/specs/2026-02-20-koe-m1-spec.md:80` through `thoughts/specs/2026-02-20-koe-m1-spec.md:89`.
- Section 1 API design assigns concrete stage contracts owned by Section 2: `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:462` through `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:477`.
- Project-level research previously documented Section 2 as unimplemented and contract-driven: `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md:160` through `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md:161`.

## Related Research

- `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-1-research.md`

## Open Questions

- Which concrete runtime API/function signatures will be exposed by `src/koe/hotkey.py` and `src/koe/window.py` for Section 2 implementation (not yet committed in code).
- Whether explicit "already running" feedback is expressed via an existing `NotificationKind` value or requires vocabulary expansion beyond `src/koe/types.py:65` through `src/koe/types.py:74`.

## Assumptions & Risks

- **Assumption**: `docs/project-brief.md` is the effective source brief referenced by Section 2 specs.
  - **Why**: `thoughts/projects/2026-02-20-koe-m1/spec.md:14` points to `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md`, but that file is absent while `docs/project-brief.md` contains the complete brief text.
  - **Validation approach**: confirm authoritative brief path in project index/spec maintenance workflow.
  - **Risk if wrong**: Section 2 implementation planning could be grounded on an unintended brief version.

- **Assumption**: Missing `hack/spec_metadata.sh` indicates metadata must be collected directly from git/system state for this research artifact.
  - **Why**: no `spec_metadata.sh` file exists under repository paths.
  - **Validation approach**: add or document canonical metadata script location if required by workflow.
  - **Risk if wrong**: metadata format drift across research artifacts.

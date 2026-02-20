---
date: 2026-02-20T10:15:24+11:00
researcher: opencode
git_commit: 8b5b90d
branch: master
repository: s2bomb/koe
topic: "Broad architectural discovery for Koe Milestone 1 global hotkey voice-to-text on Linux/X11"
tags: [research, codebase, koe, milestone-1, typing, tooling]
status: complete
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Project-level discovery"
last_updated: 2026-02-20
last_updated_by: opencode
last_updated_note: "Added follow-up project-level discovery for M1 integration points, thoughts context, and section-breakdown readiness"
---

# Research: Broad architectural discovery for Koe Milestone 1 global hotkey voice-to-text on Linux/X11

**Date**: 2026-02-20T10:15:24+11:00
**Researcher**: opencode
**Git Commit**: 8b5b90d
**Branch**: master
**Repository**: s2bomb/koe

## Research Question

Broad project-level discovery for Koe M1, with focus on reusable patterns and integration points for:
- hotkeys
- subprocess wrappers and CLI pipelines
- notifications
- clipboard interactions
- temporary file handling
- typed config and schemas
- orchestration, error handling, strict typing
- tests/tooling workflow
- prior decisions in `thoughts/`

## Summary

The repository is currently a scaffold, not an implemented application. There are no runtime modules yet for hotkeys, audio capture, subprocess orchestration, clipboard handling, notifications, or temp-file lifecycle. The strongest architectural signals today come from:

1. `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md` (the source brief)
2. `pyproject.toml` (actual enforced tooling and typing)
3. project scaffolding in `thoughts/projects/2026-02-20-koe-m1/`

This means M1 requirements can be grounded in existing project constraints and tooling conventions, but implementation patterns must still be introduced (no in-repo examples yet).

## Detailed Findings

### 1) Existing implementation patterns in this repo

- `src/koe/__init__.py` exists and is empty (`src/koe/__init__.py`)
- `src/koe/py.typed` exists as a package typing marker (`src/koe/py.typed`)
- No other Python implementation modules exist under `src/koe/` (`src/koe/__init__.py` only)
- No `tests/` Python files exist
- No in-repo code currently demonstrates:
  - subprocess wrappers
  - hotkey listeners
  - notifications
  - clipboard save/restore
  - temp WAV create/cleanup
  - CLI pipeline orchestration

### 2) Typed configuration and strict typing conventions already present

- Package metadata and dependency constraints are defined in `pyproject.toml:1`
- Python floor is 3.12+ (`pyproject.toml:9`)
- Runtime dependency list currently includes only `pydantic` (`pyproject.toml:10`)
- Strict typing is enforced via Pyright strict mode (`pyproject.toml:24`)
- Pyright is configured against `.venv` (`pyproject.toml:27`)
- Ruff is configured with broad lint selection including annotation, return typing, and pytest-style rules (`pyproject.toml:37`)
- `known-first-party = ["koe"]` is defined for import hygiene (`pyproject.toml:58`)

### 3) Project brief architecture signals (source requirements)

From `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md`:

- M1 architecture is specified as an on-demand linear pipeline (no daemon) (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:14`)
- Functional/procedural-first coding constraints are explicit (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:16`)
- Core M1 sequence includes focused window check, recording, temp WAV write, Whisper inference, paste, cleanup (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:70`)
- Text insertion strategy is clipboard + simulated paste, with clipboard restoration (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:84`)
- M1 scope is terminal proof-of-concept on X11 (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:170`)
- Planned flat module map is explicitly listed (main/hotkey/audio/transcribe/window/insert/notify/config/types) (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:112`)

### 4) Reusable services/utilities available now

Current reusable assets in-repo are primarily configuration/tooling-level:

- `pyproject.toml` strict typing and linting policy can be reused across all new modules (`pyproject.toml:24`, `pyproject.toml:37`)
- `src/koe/py.typed` establishes typed package intent for future module additions (`src/koe/py.typed`)
- `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md` provides architecture contract and acceptance criteria (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:176`)

No process orchestration, result/error wrappers, subprocess helpers, or OS integration utilities are currently implemented.

### 5) Integration points with tests, tooling, and workflow

- Tooling currently installed/declared:
  - `pyright` strict (`pyproject.toml:20`, `pyproject.toml:24`)
  - `ruff` with extensive rules (`pyproject.toml:21`, `pyproject.toml:37`)
- Test stack mentioned in source brief (`pytest` + `typeguard`) is not yet present in `pyproject.toml` (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:104`)
- `README.md` is currently a short stub and does not yet contain dev workflow commands (`README.md:1`)
- `thoughts/projects/2026-02-20-koe-m1/index.md` indicates section execution is blocked until approved section breakdown exists in `spec.md` (`thoughts/projects/2026-02-20-koe-m1/index.md:15`)

### 6) Historical context in thoughts/

- `thoughts/projects/2026-02-20-koe-m1/sources/original-request.md:1` records initial ask as a skeleton project request
- `thoughts/projects/2026-02-20-koe-m1/spec.md:1` is still a placeholder
- `thoughts/projects/2026-02-20-koe-m1/index.md:31` confirms no sections defined yet

There is no prior implemented-research history in `thoughts/` beyond this scaffold and source brief.

## Code References & Examples

- `pyproject.toml:24` - strict type-checking baseline

```toml
[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "strict"
venvPath = "."
venv = ".venv"
reportMissingTypeStubs = false
reportUnknownMemberType = false
```

- `pyproject.toml:37` - lint policy that will shape module/test style

```toml
[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "N", "UP", "B", "SIM", "TCH", "RUF", "ANN", "C4", "PT", "RET", "ARG", "PL",
]
ignore = []
```

- `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:70` - the intended M1 procedural pipeline contract

```markdown
| Step | Operation | Side Effect |
|---|---|---|
| 1 | User presses global hotkey | Input event (external) |
| ...
| 9 | Clean up temp files and exit | File delete (cleanup) |
```

## Architecture Documentation

Current architecture is specification-driven rather than implementation-driven:

- **Implemented architecture today**: package scaffold + strict lint/type tooling
- **Specified architecture for M1**: flat procedural modules, explicit side-effect boundaries, on-demand lifecycle, X11-focused insertion/detection, terminal-first acceptance
- **Typed boundary posture**: strict Pyright + typed package marker, ready for strongly-typed module additions

## Section Breakdown Inputs (for implementation-ready spec drafting)

The following section candidates are directly grounded in existing source brief deliverables (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:176`) and current repository structure:

1. **Section 1: Runtime + Typed Foundations**
   - `config.py`, `types.py`, package entry conventions, strict typing guardrails
2. **Section 2: X11 Context + Hotkey Trigger**
   - focused window check + global hotkey capture flow
3. **Section 3: Audio Capture + Temp Artifact Lifecycle**
   - microphone capture, temp WAV creation, cleanup boundaries
4. **Section 4: Whisper Transcription Pipeline**
   - local GPU inference path and typed result flow
5. **Section 5: Insertion + Clipboard Preservation**
   - xclip/xdotool interaction, clipboard backup/restore behavior
6. **Section 6: User Feedback + Error Surfaces**
   - notify-send lifecycle messages and failure handling
7. **Section 7: Test + Tooling Completion Gate**
   - module tests + integration test + lint/type/test workflows

## Historical Context (from thoughts/)

- `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md` contains the architecture and milestone contract used as source of truth
- `thoughts/projects/2026-02-20-koe-m1/index.md` records workflow status and section-block condition
- `thoughts/projects/2026-02-20-koe-m1/spec.md` indicates the approved section breakdown has not been written yet

## Related Research

- None currently present in `thoughts/research/` or project `working/` beyond this document.

## Open Questions

- Whether M1 typecheck gate is pyright-only (current toolchain) or must include mypy as brief language suggests
- Whether `pydantic` is intentionally required for runtime config/schema modeling in M1 or is scaffold carry-over
- Which hotkey backend is selected first for M1 (`pynput` vs `evdev`) as both are listed in source brief

## Assumptions & Risks

- **Assumption**: Current repo state is intentionally pre-implementation (scaffold only)
  - **Why**: no feature modules/tests are present under `src/koe/` or `tests/`
  - **Validation approach**: confirm with stakeholder that implementation has not started in another branch
  - **Risk if wrong**: this discovery could miss existing implementation patterns outside current branch

## Follow-up Research 2026-02-20T10:31:30+11:00

### Scope of this follow-up

- Project-level architectural discovery for Milestone 1 (terminal proof of concept)
- Explicit focus on reusable patterns/services, integration points, and prior decisions in `thoughts/`
- Source-of-truth alignment against `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md`

### Verified codebase state (current branch)

- `src/koe/__init__.py` is the only Python implementation file in this repository (`src/koe/__init__.py`)
- `src/koe/py.typed` exists as the typed package marker (`src/koe/py.typed`)
- No runtime modules yet for hotkeys/audio/transcription/window/insert/notify/config/types
- No `tests/` directory exists at present
- `README.md` remains a 3-line project stub (`README.md:1`)

### Existing patterns for similar features

- In-repo implementation patterns for global hotkeys, audio capture, transcription, clipboard restore, and notifications are currently absent (greenfield)
- The active patterns available to reuse today are specification and tooling patterns:
  - strict static typing baseline in `pyproject.toml:24`
  - lint/style constraints in `pyproject.toml:37`
  - flat module contract and linear runtime pipeline in `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:112` and `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:70`

### Related modules/scripts/configs/schema/types

- `pyproject.toml` currently defines runtime dependency set as only `pydantic` (`pyproject.toml:10`)
- `pyproject.toml` enforces Pyright strict (`pyproject.toml:24`) and Ruff rule set (`pyproject.toml:37`)
- `thoughts/specs/2026-02-20-koe-m1-spec.md` contains explicit M1 section breakdown and acceptance criteria (`thoughts/specs/2026-02-20-koe-m1-spec.md:68`)
- `thoughts/projects/2026-02-20-koe-m1/spec.md` remains placeholder and does not yet contain the section breakdown (`thoughts/projects/2026-02-20-koe-m1/spec.md:1`)

### Reusable services/utilities currently available

- Strict type/lint toolchain configuration is productionized and immediately reusable for new modules
- Typed package marker is already in place (`src/koe/py.typed`)
- No reusable runtime service wrappers (subprocess helper, notifier helper, clipboard helper, temporary-file helper) are implemented yet

### Integration points with existing CLI/workflows

- No CLI command entrypoint is declared yet in `pyproject.toml` (no `[project.scripts]` section)
- Milestone runtime flow is documented as a linear on-demand process contract in source brief (`thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:70`)
- Project workflow index still reports section execution blocked until project `spec.md` contains an explicit section breakdown (`thoughts/projects/2026-02-20-koe-m1/index.md:15`)

### Historical context and decisions in thoughts/

- `thoughts/specs/2026-02-20-koe-m1-spec.md` records resolved M1 defaults:
  - Pyright strict as canonical type gate (`thoughts/specs/2026-02-20-koe-m1-spec.md:60`)
  - `pynput` selected as M1 hotkey backend (`thoughts/specs/2026-02-20-koe-m1-spec.md:61`)
  - CUDA-required fail-fast transcription policy (`thoughts/specs/2026-02-20-koe-m1-spec.md:62`)
  - explicit success notification requirement (`thoughts/specs/2026-02-20-koe-m1-spec.md:63`)
  - single-instance guard requirement (`thoughts/specs/2026-02-20-koe-m1-spec.md:64`)
- Open M1 questions remain documented in `thoughts/specs/2026-02-20-koe-m1-spec.md:206`

### Assumptions

- **No new assumptions added in this follow-up.**
- The prior scaffold-only assumption is now directly corroborated by current repository file inventory on `master`.

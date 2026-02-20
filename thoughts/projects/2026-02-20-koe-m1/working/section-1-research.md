---
date: 2026-02-20T10:39:29+11:00
researcher: opencode
git_commit: 8b5b90d
branch: master
repository: s2bomb/koe
topic: "Section 1 Foundations and Delivery Baseline"
tags: [research, codebase, koe, milestone-1, section-1]
status: complete
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 1: Foundations and Delivery Baseline"
last_updated: 2026-02-20
last_updated_by: opencode
---

# Research: Section 1 Foundations and Delivery Baseline

**Date**: 2026-02-20T10:39:29+11:00
**Researcher**: opencode
**Git Commit**: 8b5b90d
**Branch**: master
**Repository**: s2bomb/koe

## Research Question

Document the current codebase state for Section 1 of `thoughts/projects/2026-02-20-koe-m1/spec.md`, with full acceptance-criteria coverage, concrete file:line evidence, and existing code patterns only.

## Section 1 Acceptance Criteria Coverage

Section 1 acceptance criteria are defined at `thoughts/projects/2026-02-20-koe-m1/spec.md:32` through `thoughts/projects/2026-02-20-koe-m1/spec.md:37`.

### Criterion 1: M1 module surface exists under `src/koe/`

- Requirement: `main.py`, `hotkey.py`, `audio.py`, `transcribe.py`, `window.py`, `insert.py`, `notify.py`, `config.py`, `types.py` (`thoughts/projects/2026-02-20-koe-m1/spec.md:33`).
- Present files in `src/koe/`:
  - `src/koe/__init__.py`
  - `src/koe/py.typed`
- Expected Section 1 module files are not present in the repository tree.

Evidence:
- `src/koe/__init__.py`
- `src/koe/py.typed`

### Criterion 2: Shared pipeline types defined in one place with explicit contracts

- Requirement references contracts for hotkey action, window focus result, audio artifact path, transcription result, clipboard state, notification kind (`thoughts/projects/2026-02-20-koe-m1/spec.md:34`).
- `src/koe/types.py` is not present.
- No other file currently defines these shared pipeline type contracts.

Evidence:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:34`
- `src/koe/__init__.py`
- `src/koe/py.typed`

### Criterion 3: `pyproject.toml` declares required M1 runtime libs + test/dev libs + runnable CLI entrypoint

- Requirement names: runtime (`faster-whisper`, `sounddevice`, `numpy`, `pynput`), test/developer (`pytest`, `typeguard`), and runnable CLI entrypoint (`thoughts/projects/2026-02-20-koe-m1/spec.md:35`).
- Current `dependencies` only declare `pydantic>=2.12.5` (`pyproject.toml:10`, `pyproject.toml:11`).
- Current `dependency-groups.dev` includes `pyright` and `ruff` (`pyproject.toml:18`, `pyproject.toml:20`, `pyproject.toml:21`).
- No `[project.scripts]` section is present in `pyproject.toml`.
- Observed command behavior: `uv run koe` fails with `No such file or directory (os error 2)`.

Evidence:
- `pyproject.toml:10`
- `pyproject.toml:11`
- `pyproject.toml:18`
- `pyproject.toml:20`
- `pyproject.toml:21`

### Criterion 4: `Makefile` (or equivalent committed command surface) provides `lint`, `typecheck`, `test`, `run`

- Requirement is at `thoughts/projects/2026-02-20-koe-m1/spec.md:36`.
- No `Makefile` is present at repository root.
- No alternate task runner file was found (`makefile`, `Justfile`, `justfile`, `Taskfile.yml`, `taskfile.yml`, `tox.ini`, `noxfile.py`).
- Observed command behavior: `make lint` returns `No rule to make target 'lint'.`

Evidence:
- `thoughts/projects/2026-02-20-koe-m1/spec.md:36`

### Criterion 5: Type/lint baseline aligns with repository policy and is runnable

- Requirement cites repository policy lines (`thoughts/projects/2026-02-20-koe-m1/spec.md:37`).
- Strict Pyright config exists (`pyproject.toml:24` through `pyproject.toml:30`).
- Ruff lint baseline exists (`pyproject.toml:37` through `pyproject.toml:56`).
- Baseline commands run successfully in this environment:
  - `uv run pyright` -> `0 errors, 0 warnings, 0 informations`
  - `uv run ruff check` -> `All checks passed!`

Evidence:
- `pyproject.toml:24`
- `pyproject.toml:37`

## Existing Patterns (Code Snippets)

### Pattern: strict type-check baseline in `pyproject.toml`

Source: `pyproject.toml:24`

```toml
[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "strict"
venvPath = "."
venv = ".venv"
reportMissingTypeStubs = false
reportUnknownMemberType = false
```

### Pattern: lint policy baseline in `pyproject.toml`

Source: `pyproject.toml:37`

```toml
[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "W",     # pycodestyle warnings
    "F",     # pyflakes
    "I",     # isort
    "N",     # pep8-naming
    "UP",    # pyupgrade
    "B",     # flake8-bugbear
    "SIM",   # flake8-simplify
    "TCH",   # flake8-type-checking
    "RUF",   # ruff-specific
    "ANN",   # flake8-annotations
    "C4",    # flake8-comprehensions
    "PT",    # flake8-pytest-style
    "RET",   # flake8-return
    "ARG",   # flake8-unused-arguments
    "PL",    # pylint
]
ignore = []
```

### Pattern: current package/runtime dependency declaration

Source: `pyproject.toml:1`

```toml
[project]
name = "koe"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.12.5",
]
```

## Related Project Context Files

- Project index scaffold state: `thoughts/projects/2026-02-20-koe-m1/index.md:31`
- Section 1 requirements source: `thoughts/projects/2026-02-20-koe-m1/spec.md:27`
- Brief module/command contract reference: `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:112`

## Assumptions & Verification Notes

- No unresolved assumptions were needed for Section 1 coverage.
- File presence/absence evidence is from direct repository file discovery at research time on commit `8b5b90d`.

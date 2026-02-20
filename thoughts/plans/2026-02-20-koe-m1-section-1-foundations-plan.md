---
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 1: Foundations and Delivery Baseline"
research_source: thoughts/projects/2026-02-20-koe-m1/working/section-1-research.md
test_spec_source: thoughts/projects/2026-02-20-koe-m1/working/section-1-test-spec.md
design_source: thoughts/design/2026-02-20-koe-m1-section-1-api-design.md
---

# Koe M1 Section 1 Implementation Plan

## Overview

Implement Section 1 only: repository foundations required for later runtime sections.
This plan delivers the Section 1 file surface, shared type contracts, typed defaults, CLI contract wiring, and quality command surface while keeping runtime behavior for Sections 2-6 out of scope.

## Current State Analysis

- `src/koe/` only contains `__init__.py` and `py.typed` (`thoughts/projects/2026-02-20-koe-m1/working/section-1-research.md:35`).
- `pyproject.toml` has only `pydantic` runtime dep, no Section 1 runtime/test deps, and no `[project.scripts]` (`pyproject.toml:10`).
- No `Makefile` exists and `make lint` currently fails (`thoughts/projects/2026-02-20-koe-m1/working/section-1-research.md:75`).
- Type/lint policy is already enforced and passing (`pyproject.toml:24`, `pyproject.toml:37`).

## Desired End State

Section 1 ACs are all met:

1. `src/koe/` contains required module surface from `spec.md:33`.
2. Shared pipeline contracts are centralized in `src/koe/types.py`.
3. `pyproject.toml` declares required M1 runtime/test deps and `koe` CLI entrypoint.
4. `Makefile` exposes `lint`, `typecheck`, `test`, `run`.
5. `uv run pyright`, `uv run ruff check src/ tests/`, and `uv run pytest tests/` succeed.

Verification command bundle:

```bash
make lint && make typecheck && make test
```

## Traceability

| Requirement | Source | Test Spec ID | Planned Phase |
|-------------|--------|--------------|---------------|
| AC-1: module surface in `src/koe/` | `thoughts/projects/2026-02-20-koe-m1/spec.md:33` | T-20, T-21, T-22 + file-presence gate | Phase 2, Phase 4 |
| AC-2: centralized shared types | `thoughts/projects/2026-02-20-koe-m1/spec.md:34` | T-01..T-17 | Phase 1, Phase 3 |
| AC-3: deps + CLI entrypoint | `thoughts/projects/2026-02-20-koe-m1/spec.md:35` | T-18, T-19, T-20 | Phase 2, Phase 3 |
| AC-4: command surface (`lint/typecheck/test/run`) | `thoughts/projects/2026-02-20-koe-m1/spec.md:36` | command validation suite | Phase 2 |
| AC-5: type/lint baseline runnable | `thoughts/projects/2026-02-20-koe-m1/spec.md:37` | T-01, T-04, T-05, T-13, T-15, T-16, T-17, T-18, T-21 | Phase 1, Phase 4 |

### Key Discoveries

- Section 1 is greenfield; contracts must be net-new (`thoughts/projects/2026-02-20-koe-m1/working/section-1-research.md:38`).
- Design contract for all Section 1 APIs already exists and is approved (`thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:6`).
- Test obligations are explicit and bounded to `types.py`, `config.py`, `main.py` (`thoughts/projects/2026-02-20-koe-m1/working/section-1-test-spec.md:15`).

## What We're NOT Doing

- No runtime behavior for hotkey/focus/audio/transcribe/insert/notify logic (Sections 2-6 ownership).
- No Wayland work, no daemon mode, no integration of external system tools.
- No Section 7 onboarding/docs completion work beyond command surface needed by Section 1 AC-4.

## Implementation Approach

Test-first at section scope:

1. `/test-implementer` writes Section 1 test suite and static type fixtures from T-01..T-22.
2. `/implement-plan` delivers infra + modules to make those tests pass.
3. End on strict quality gate command bundle.

Design references incorporated directly from `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md`:

- Type contracts block (`:35-304`)
- Config schema/defaults block (`:310-415`)
- Main invocation contracts (`:419-535`)
- Infra additions for `pyproject.toml` and `Makefile` (`:671-707`)

## Perspectives Synthesis

**Alignment**

- Keep Section 1 as contract-only foundation with no stage business logic.
- Implement `outcome_to_exit_code` as a total mapping and keep `run_pipeline` deferred.
- Keep tests explicit about deferred cleanup behavior for T-21 (`xfail`).

**Divergence (resolved in this plan)**

- Generic `TypedDict` style: use `TypeVar` + `Generic` for `Ok`/`Err` to avoid runtime checker compatibility risk while preserving Pyright strict narrowing.
- `Result` narrowing examples: standardize on `result["ok"] is True` / `match result["ok"]` patterns in code/tests for deterministic narrowing.
- Runtime dependency hygiene: remove unused `pydantic` when adding Section 1 runtime deps (keeps minimal-dependency posture).

**Key perspective contributions**

- DX Advocate: avoid misleading narrowing examples; keep test structure predictable.
- Architecture Purist: preserve flat modules and strict boundaries; no cross-module coupling in `types.py`/`config.py`.
- Validation Strategist: define phase-by-phase command-level proof, including expected `xfail` in T-21.
- Security Auditor: keep dependency surface intentional; avoid silent dependency drift.
- Correctness Guardian: mandate total exit-code mapping and explicit narrowing-safe patterns.

## Phase Ownership

| Phase | Owner | Responsibility |
|-------|-------|---------------|
| Phase 1 | `/test-implementer` | Write Section 1 tests/spec fixtures from T-01..T-22 |
| Phase 2-4 | `/implement-plan` | Implement code/infrastructure until all written tests pass |

## Phase 1: Section 1 Test Suite (Red)

**Owner**: `/test-implementer`
**Commit**: `test: add section 1 contract test suite`

### Overview

Create all Section 1 tests first, including static typing fixtures and runtime contract assertions.

### Changes Required

#### 1. Type contract tests
**File**: `tests/test_types.py`
**Changes**: implement T-02..T-17 runtime/static-friendly assertions.

```python
from __future__ import annotations

import pytest
from typeguard import TypeCheckError, check_type

from koe.types import FocusError, Ok


def test_ok_shape_accepts_success_arm() -> None:
    check_type({"ok": True, "value": "hello"}, Ok[str])


def test_ok_shape_rejects_false_discriminator() -> None:
    with pytest.raises(TypeCheckError):
        check_type({"ok": False, "value": "hello"}, Ok[str])
```

#### 2. Config tests
**File**: `tests/test_config.py`
**Changes**: implement T-18/T-19.

```python
from __future__ import annotations

from typeguard import check_type

from koe.config import DEFAULT_CONFIG, KoeConfig


def test_default_config_matches_contract() -> None:
    check_type(DEFAULT_CONFIG, KoeConfig)
    assert DEFAULT_CONFIG["sample_rate"] == 16_000
    assert DEFAULT_CONFIG["audio_format"] == "float32"
    assert DEFAULT_CONFIG["whisper_device"] == "cuda"
```

#### 3. Main invocation tests
**File**: `tests/test_main.py`
**Changes**: implement T-20/T-21/T-22.

```python
from __future__ import annotations

from unittest.mock import patch

from koe.main import main, outcome_to_exit_code


def test_main_maps_unexpected_exception_to_exit_2() -> None:
    with patch("koe.main.run_pipeline", side_effect=Exception("boom")):
        with patch("sys.exit") as exit_mock:
            main()
    exit_mock.assert_called_once_with(2)
```

### Success Criteria

#### Validation

- [x] Tests are written and import-clean.
- [x] Static fixture strategy for Pyright-only cases (T-01, T-04, T-05, T-13, T-15, T-16, T-17) is present.

#### Standard Checks

- [x] `uv run ruff check tests/`
- [x] `uv run pyright`

**Implementation Note**: Proceed to implementation phases after tests are committed (expected to fail initially due missing implementation).

---

## Phase 2: Infrastructure + Module Surface (Green foundation)

**Owner**: `/implement-plan`
**Commit**: `feat: add section 1 dependency and command surface`

### Overview

Deliver AC-1/AC-3/AC-4 foundation: module files, pyproject entries, Makefile targets.

### Changes Required

#### 1. Project metadata and deps
**File**: `pyproject.toml`
**Changes**: add runtime deps, dev deps, CLI script.

```toml
[project]
dependencies = [
    "faster-whisper>=1.0.0",
    "sounddevice>=0.4.6",
    "numpy>=1.26.0",
    "pynput>=1.7.6",
]

[project.scripts]
koe = "koe.main:main"

[dependency-groups]
dev = [
    "pyright>=1.1.408",
    "ruff>=0.15.2",
    "pytest>=8.0.0",
    "typeguard>=4.3.0",
]
```

#### 2. Command surface
**File**: `Makefile`
**Changes**: add required targets.

```makefile
.PHONY: lint typecheck test run

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run pyright

test:
	uv run pytest tests/

run:
	uv run koe
```

#### 3. Required module files
**Files**: `src/koe/hotkey.py`, `src/koe/audio.py`, `src/koe/transcribe.py`, `src/koe/window.py`, `src/koe/insert.py`, `src/koe/notify.py`
**Changes**: add minimal stubs to satisfy AC-1 file surface.

```python
"""Section-owned module stub for later implementation."""
```

### Success Criteria

#### Validation

- [x] `ls src/koe/{main,hotkey,audio,transcribe,window,insert,notify,config,types}.py`
- [x] `make lint`
- [x] `make typecheck`

#### Standard Checks

- [x] `uv run pyright`
- [x] `uv run ruff check src/ tests/`

**Implementation Note**: Proceed to Phase 3 once infra is passing and module surface exists.

---

## Phase 3: Shared Contracts (`types.py`, `config.py`, `main.py`)

**Owner**: `/implement-plan`
**Commit**: `feat: implement section 1 shared contracts and cli mapping`

### Overview

Implement contract-bearing modules per design and test spec, keeping runtime stages deferred.

### Changes Required

#### 1. Shared pipeline types
**File**: `src/koe/types.py`
**Changes**: implement all types required by `section-1-test-spec.md:33-57`.

```python
from __future__ import annotations

from pathlib import Path
from typing import Generic, Literal, NewType, TypeVar, TypedDict

T = TypeVar("T")
E = TypeVar("E")

AudioArtifactPath = NewType("AudioArtifactPath", Path)
WindowId = NewType("WindowId", int)


class Ok(TypedDict, Generic[T]):
    ok: Literal[True]
    value: T


class Err(TypedDict, Generic[E]):
    ok: Literal[False]
    error: E


type Result[TValue, TError] = Ok[TValue] | Err[TError]
```

#### 2. Typed defaults
**File**: `src/koe/config.py`
**Changes**: implement `KoeConfig` + `DEFAULT_CONFIG` (`api-design.md:332-408`).

```python
from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, TypedDict


class KoeConfig(TypedDict, total=True):
    sample_rate: int
    audio_channels: int
    audio_format: Literal["float32"]
    whisper_device: Literal["cuda"]
    lock_file_path: Path
    temp_dir: Path


DEFAULT_CONFIG: Final[KoeConfig] = {
    "sample_rate": 16_000,
    "audio_channels": 1,
    "audio_format": "float32",
    "whisper_device": "cuda",
    "lock_file_path": Path("/tmp/koe.lock"),
    "temp_dir": Path("/tmp"),
}
```

#### 3. Invocation contract
**File**: `src/koe/main.py`
**Changes**: implement `main()` and total `outcome_to_exit_code`; keep `run_pipeline` deferred.

```python
from __future__ import annotations

import sys
from typing import assert_never

from koe.config import DEFAULT_CONFIG, KoeConfig
from koe.types import ExitCode, PipelineOutcome


def main() -> None:
    try:
        outcome = run_pipeline(DEFAULT_CONFIG)
        sys.exit(outcome_to_exit_code(outcome))
    except Exception:
        sys.exit(2)


def run_pipeline(config: KoeConfig) -> PipelineOutcome:
    raise NotImplementedError("Implemented in Sections 2-6")


def outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode:
    match outcome:
        case "success":
            return 0
        case (
            "no_focus"
            | "no_speech"
            | "error_dependency"
            | "error_audio"
            | "error_transcription"
            | "error_insertion"
        ):
            return 1
        case "error_unexpected":
            return 2
        case _ as unreachable:
            assert_never(unreachable)
```

### Success Criteria

#### Validation

- [x] `uv run pytest tests/test_types.py`
- [x] `uv run pytest tests/test_config.py`
- [x] `uv run pytest tests/test_main.py`

#### Standard Checks

- [x] `uv run pyright`
- [x] `uv run ruff check src/ tests/`

**Implementation Note**: Proceed when T-01..T-22 pass except explicitly deferred T-21 cleanup runtime `xfail`.

---

## Phase 4: Final Gate + Traceability Proof

**Owner**: `/implement-plan`
**Commit**: `chore: validate section 1 acceptance gates`

### Overview

Execute final AC verification and lock Section 1 completion evidence.

### Changes Required

#### 1. Acceptance gate scriptable checks
**File**: none (command-only validation)
**Changes**: run and record output in PR/validation notes.

```bash
make lint
make typecheck
make test
uv run pytest tests/test_main.py -k "outcome_to_exit_code" -q
```

### Success Criteria

#### Validation

- [x] AC-1 file presence check succeeds.
- [x] AC-2 tests T-01..T-17 passing.
- [x] AC-3 tests T-18/T-19/T-20 passing and `uv run koe` resolves entrypoint.
- [x] AC-4 `make` targets execute.
- [x] AC-5 lint/typecheck clean.

#### Standard Checks

- [x] `uv run pyright`
- [x] `uv run ruff check src/ tests/`
- [x] `uv run pytest tests/`

**Implementation Note**: Section 1 complete after all checks pass and deferred T-21 runtime cleanup remains marked as expected `xfail`.

## Testing Strategy

Test phases come first. Implementation phases only make those tests pass.

### Tests (written by `/test-implementer`)

- `tests/test_types.py`: T-01..T-17
- `tests/test_config.py`: T-18..T-19
- `tests/test_main.py`: T-20..T-22

### Additional Validation

- `uv run pyright` for static contract enforcement.
- `uv run ruff check src/ tests/` for lint and annotation policy.
- `make run` to verify CLI entrypoint resolves (`koe.main:main`).

### Manual Testing Steps

None required for Section 1. All validation is agent-self-verifiable.

## Execution Graph

**Phase Dependencies:**

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4
```

| Phase | Depends On | Can Parallelize With |
|-------|------------|---------------------|
| 1 | - | - |
| 2 | 1 | - |
| 3 | 2 | - |
| 4 | 3 | - |

**Parallel Execution Notes:**

- Section 1 is intentionally sequential because contracts, imports, and tests have hard ordering.
- No safe parallel split without causing cross-file merge/conflict overhead.

## References

- Requirements: `thoughts/projects/2026-02-20-koe-m1/spec.md:27`
- Section 1 research: `thoughts/projects/2026-02-20-koe-m1/working/section-1-research.md:28`
- API design: `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:35`
- Test spec: `thoughts/projects/2026-02-20-koe-m1/working/section-1-test-spec.md:63`

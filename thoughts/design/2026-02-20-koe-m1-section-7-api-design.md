# Koe M1 Section 7 API Design

## Scope

- Section-only scope: `thoughts/projects/2026-02-20-koe-m1/spec.md` Section 7 acceptance criteria (`AC1`-`AC4`).
- Focus modules only: `src/koe/main.py` gate surfaces, `Makefile` command contracts, and onboarding docs artifacts for M1 delivery gates.
- Design intent: define explicit pass/fail contracts and objective evidence expectations for Section 7 sign-off.

## Design References

- Spec: `thoughts/projects/2026-02-20-koe-m1/spec.md`
- Research: `thoughts/projects/2026-02-20-koe-m1/working/section-7-research.md`
- Gate orchestrator: `src/koe/main.py`
- Command surface: `Makefile`, `pyproject.toml`
- Onboarding artifacts: `README.md`, `docs/project-brief.md`

## Surface A: `main.py` Delivery-Gate API

### Public gate functions

```python
def main() -> None
def dependency_preflight(config: KoeConfig, /) -> Result[None, DependencyError]
def run_pipeline(config: KoeConfig, /) -> PipelineOutcome
def outcome_to_exit_code(outcome: PipelineOutcome) -> ExitCode
```

### Contract

- `dependency_preflight` is a non-raising startup gate. It returns `Err[DependencyError]` when any required tool is missing (`xdotool`, `xclip`, `notify-send`) or when `whisper_device != "cuda"`.
- `run_pipeline` is the lifecycle gate that returns controlled outcomes for expected states (`success`, `no_focus`, `no_speech`, `error_dependency`, `error_audio`, `error_transcription`, `error_insertion`, `already_running`).
- `run_pipeline` cleanup invariants are mandatory:
  - lock must be released on every lock-acquired path;
  - audio artifact must be removed on every artifact-created path;
  - notification failure must not mask pipeline cleanup.
- `outcome_to_exit_code` is exhaustive and total:
  - `success -> 0`
  - controlled outcomes -> `1`
  - `error_unexpected -> 2`
  - fallback arm guarded by `assert_never`.
- `main` is the exception boundary and maps any uncaught `Exception` to process exit `2`.

### Evidence expectations

- Unit proof for gate mapping and exception boundary:
  - `tests/test_main.py:19`
  - `tests/test_main.py:67`
  - `tests/test_main.py:112`
  - `tests/test_main.py:116`
  - `tests/test_main.py:170`
  - `tests/test_main.py:267`
  - `tests/test_main.py:749`
- E2E requirement (AC1) is separate from this unit evidence and must be satisfied by one dedicated integration test artifact (see Surface C).

## Surface B: Makefile Command Delivery Gates

### Public command API

```make
make lint      # uv run ruff check src/ tests/
make typecheck # uv run pyright
make test      # uv run pytest tests/
make run       # uv run koe
```

### Contract

- `make lint`: pass only when ruff exits `0` and no unmanaged suppressions are introduced.
- `make typecheck`: pass only when pyright strict exits `0` with `0 errors, 0 warnings`.
- `make test`: pass only when pytest exits `0` with no failures/errors for the full `tests/` suite.
- `make run`: two-tier contract:
  - automated environments: must fail explicitly (never crash) when runtime prerequisites are missing;
  - M1 target environment (Arch Linux + X11 + CUDA + mic + deps installed): must complete with exit `0` and observable terminal insertion.

### Evidence expectations

- AC3 command-surface evidence from research session:
  - `make lint` passed.
  - `make typecheck` passed with zero errors/warnings.
  - `make test` passed (`175 passed`).
  - `make run` exited non-zero in non-target environment, which is acceptable only when explicit and non-silent.
- Command definitions and entrypoint evidence:
  - `Makefile:1`
  - `Makefile:4`
  - `Makefile:7`
  - `Makefile:10`
  - `Makefile:13`
  - `pyproject.toml:17`

## Surface C: Docs Artifacts Delivery Gates

### Public docs API

- Primary onboarding contract artifact: `README.md`.
- Supporting source for required setup content: `docs/project-brief.md`.

### Contract

- `README.md` must be sufficient for a new contributor to reach first successful transcription within 15 minutes on the target M1 environment.
- Required minimum sections:
  - system prerequisites (Python, CUDA/cudnn, PortAudio, xdotool, xclip, libnotify);
  - hardware requirements and X11 requirement;
  - install steps (`uv` workflow) and verification checks;
  - run flow (`make lint`, `make typecheck`, `make test`, `make run`);
  - first-run success signals (notification sequence, pasted text in terminal, clipboard restore intent);
  - troubleshooting for no focus, missing mic, CUDA/transcription unavailable, and dependency failure.
- README must be self-sufficient for first run; it can reference deeper docs, but must not require them to execute the happy path.

### Evidence expectations

- Current AC4 status is fail because `README.md` only contains title + one-line description (`README.md:1`, `README.md:3`).
- Completion evidence for AC4 is a timed cold-start onboarding runbook validation in target environment (<= 15 minutes) using only README.

## Section 7 Gate Matrix

| AC | Contract owner | Pass criteria | Evidence artifact |
|---|---|---|---|
| AC1: module unit + one e2e integration | `main.py` gate surfaces + `tests/` | module-boundary tests present and passing; one dedicated terminal-flow integration test present and passing | `tests/test_*.py` + integration test file |
| AC2: required error-path tests | `main.py` mapping + module error surfaces | no-focus, missing-mic, CUDA/transcription unavailable, insertion/dependency failures covered and passing | `tests/test_window.py`, `tests/test_audio.py`, `tests/test_transcribe.py`, `tests/test_insert.py`, `tests/test_main.py` |
| AC3: command execution | `Makefile` + `pyproject` entrypoint | lint/typecheck/test pass in clean dev env; run path explicit and non-silent, and success on target runtime | command output transcripts + manual target-runtime check |
| AC4: onboarding readiness | `README.md` | new contributor reaches first successful transcription within 15 minutes using README instructions | timed onboarding validation record |

## Open Delivery Risks (Section 7 only)

- AC1 gap: explicit integration test source is currently missing (research says no dedicated integration test file found).
- AC3 ambiguity: `make run` non-zero in non-target env is expected, but must be treated as explicit controlled failure, not command-surface breakage.
- AC4 blocker: README is currently insufficient for onboarding gate.

## Design Outcome

- Section 7 gates are defined as API contracts with objective evidence requirements.
- M1 delivery should be considered blocked until AC1 integration artifact and AC4 onboarding artifact are both satisfied.

# Section 7 Delivery-Gate Contracts: Makefile Command Surfaces

**Scope**: M1 acceptance criteria only — `spec.md §7 AC3` (`make lint`, `make typecheck`,
`make test`, `make run` execute successfully in a clean environment).

**Ground truth examined**:
- `Makefile` (all 13 lines)
- `pyproject.toml` (all 67 lines — ruff, pyright, dependency-groups)
- `src/koe/main.py` — `outcome_to_exit_code`, `run_pipeline`, `dependency_preflight`
- `src/koe/types.py` — `ExitCode`, `PipelineOutcome`
- `section-7-research.md` — AC status, observed command outputs

---

## API Surface

Each command is a phony Make target that delegates to a single `uv run` invocation.
There are no flags, no environment variables, and no positional arguments exposed
at the `make` level. Callers invoke exactly as written.

### `make lint`

```
uv run ruff check src/ tests/
```

- **Tool**: ruff (version pinned `>=0.15.2` in `[dependency-groups].dev`)
- **Scope**: `src/` and `tests/` only — no `docs/`, no `thoughts/`
- **Rule sets active**: E, W, F, I, N, UP, B, SIM, TCH, RUF, ANN, C4, PT, RET, ARG, PL
  (`pyproject.toml:46-63`)
- **Line length**: 100 (`pyproject.toml:42`)
- **Target Python**: 3.12 (`pyproject.toml:41`)
- **Known inline suppressions** (three documented workarounds — not violations):
  - `types.py:16,21` → `# noqa: UP046` (Generic TypedDict syntax, Pyright/ruff limitation)
  - `types.py:26` → `# noqa: UP040` (TypeAlias alias, PEP 695 not yet supported)
  - `notify.py:26`, `main.py:56` → `# noqa: PLR0911` (≥8 return paths, structural necessity)

### `make typecheck`

```
uv run pyright
```

- **Tool**: pyright (version pinned `>=1.1.408` in `[dependency-groups].dev`)
- **Mode**: `typeCheckingMode = "strict"` (`pyproject.toml:34`)
- **Python version**: 3.12 (`pyproject.toml:33`)
- **Venv**: `.venv` at repo root (`pyproject.toml:35-36`)
- **Relaxed stubs policy**: `reportMissingTypeStubs = false`,
  `reportUnknownMemberType = false` (`pyproject.toml:37-38`)
- **Scope**: all Python discovered by pyright under the configured venv root

### `make test`

```
uv run pytest tests/
```

- **Tool**: pytest (version pinned `>=8.0.0` in `[dependency-groups].dev`)
- **Scope**: `tests/` directory — module-boundary unit tests only
- **Test files** (9 modules, all present):
  `test_types.py`, `test_config.py`, `test_hotkey.py`, `test_window.py`,
  `test_audio.py`, `test_transcribe.py`, `test_insert.py`, `test_notify.py`,
  `test_main.py`
- **Current count**: 175 collected, 0 skipped
- **Runtime**: ~0.65 s on clean hardware (all mocked — no subprocess calls)
- **Runtime deps in tests**: `typeguard>=4.3.0` for `check_type()` shape verification;
  `unittest.mock.patch` for all subprocess and OS isolation

### `make run`

```
uv run koe
```

- **Entrypoint**: `koe.main:main` (`pyproject.toml:17-18`)
- **Pipeline**: `dependency_preflight → acquire_instance_lock → check_x11_context →
  check_focused_window → capture_audio → transcribe_audio → insert_transcript_text`
- **Hard runtime requirements** (enforced by `dependency_preflight`):
  `xdotool`, `xclip`, `notify-send` on `$PATH`; `whisper_device == "cuda"` in config
- **Exit code semantics** (from `outcome_to_exit_code` in `main.py:116-133`):

  | Outcome | Exit code | Meaning |
  |---------|-----------|---------|
  | `"success"` | `0` | Transcription inserted; pipeline clean |
  | `"no_focus"` \| `"no_speech"` \| `"error_*"` \| `"already_running"` | `1` | Controlled failure; notification emitted |
  | Unhandled exception in `main()` | `2` | Programmer bug; `run_pipeline` raised |

---

## Gate Contract

A gate is **binary**: pass = proceed, fail = block. Each command has one pass condition
and explicit fail conditions.

### `make lint` Gate

| Condition | Status | Action |
|-----------|--------|--------|
| `ruff check` exits 0 | **PASS** | Proceed to typecheck |
| Any exit code ≠ 0 | **FAIL** | Block; developer must fix lint violation(s) |
| Any `# noqa` added without documented rationale | **FAIL** | Treated as suppression debt |

**Invariant**: Inline `# noqa` suppressions must be exhausted before raising. The five
existing suppressions are all documented Python/tooling workarounds
(`AGENTS.md §Python Workarounds`). New suppressions require an explicit comment
citing the limitation and the tracking item for removal.

### `make typecheck` Gate

| Condition | Status | Action |
|-----------|--------|--------|
| pyright exits 0; output is `0 errors, 0 warnings, 0 informations` | **PASS** | Proceed to test |
| Any error count > 0 | **FAIL** | Block; type error must be resolved |
| Any warning count > 0 | **FAIL** | Block; warnings are not acceptable background noise |
| pyright exits non-zero (tool failure) | **FAIL** | Block; environment broken |

**Invariant**: Strict mode means every narrowing branch must be exhaustive.
`assert_never` in `outcome_to_exit_code` is the enforcement mechanism for
`PipelineOutcome` — adding a new outcome variant without updating the match branch
is a type error, not a test failure.

### `make test` Gate

| Condition | Status | Action |
|-----------|--------|--------|
| pytest exits 0; 0 failed, 0 errors, 0 skipped | **PASS** | Proceed to `make run` (on target hardware) |
| Any test failed | **FAIL** | Block; behavioural contract broken |
| Any collection error | **FAIL** | Block; test infrastructure broken |
| pytest exits 0 but count < 175 | **INVESTIGATE** | A test was removed without justification |

**Invariant**: Tests are mocked at the subprocess boundary. A test that calls real
`xdotool`, `xclip`, `notify-send`, or loads a Whisper model is out of scope and
will fail in CI environments — this is an architectural violation, not an
environment problem.

### `make run` Gate

**This gate has two tiers: automated preflight, and manual M1 acceptance.**

**Tier 1 — Automated preflight (any environment)**:

| Condition | Status | Meaning |
|-----------|--------|---------|
| Exit code 2 | **FAIL** | Unhandled exception — programmer bug |
| Exit code 1 with no notification emitted (silent) | **FAIL** | Silent failure — `send_notification` contract broken |
| Exit code 1 in a dev/CI environment lacking GPU or X11 | **EXPECTED** | Preflight correctly rejected the environment; not a gate failure |

**Tier 2 — Manual M1 acceptance (target runtime only)**:

Requires: Arch Linux, X11 active, NVIDIA CUDA, `xdotool`/`xclip`/`notify-send` on
`$PATH`, PortAudio-backed microphone, terminal window focused.

| Condition | Status |
|-----------|--------|
| Exit code 0 AND transcribed text appears in the focused terminal | **PASS** |
| Exit code 0 AND no text appears | **FAIL** (insertion silently ignored) |
| Exit code 1 in target environment | **FAIL** (controlled failure where success was expected) |
| Exit code 2 in any environment | **FAIL** (programmer bug — unacceptable at M1) |

**Critical distinction**: `make run` exit code 1 in a dev environment is correct
and expected. The same exit code on target hardware after speaking is a gate failure.
The exit code alone is insufficient evidence; the notification and observed terminal
state are required corroboration.

---

## Evidence Expectations

What a developer observes on stdout/stderr for each passing state.

### `make lint` — Pass

```
$ make lint
uv run ruff check src/ tests/
All checks passed!
```

- stdout: `All checks passed!`
- stderr: empty
- exit: 0
- make output: no `Error` line

**Fail evidence**: any file path + line number on stdout, e.g.:
```
src/koe/types.py:5:1: F401 [*] `typing.Literal` imported but unused
```

### `make typecheck` — Pass

```
$ make typecheck
uv run pyright
[pyright output with version header]
0 errors, 0 warnings, 0 informations
```

- The critical line is the final summary: `0 errors, 0 warnings, 0 informations`
- exit: 0

**Fail evidence**: any count > 0 on any category:
```
/home/.../src/koe/types.py:26:1 - error: ...
1 error, 0 warnings, 0 informations
```

### `make test` — Pass

```
$ make test
uv run pytest tests/
============================= test session starts ==============================
platform linux -- Python 3.12.x, pytest-9.x.x ...
collected 175 items

tests/test_audio.py ......
tests/test_config.py ....
tests/test_hotkey.py ....
tests/test_insert.py ....................
tests/test_main.py ...................................
tests/test_notify.py ................................
tests/test_transcribe.py ..............................
tests/test_types.py ........................................
tests/test_window.py ....

============================= 175 passed in 0.65s ==============================
```

- The final summary line must be `N passed` with 0 failed/error/skipped
- exit: 0
- Runtime: sub-second (all mocked); a test run exceeding 5 s signals a subprocess
  mock boundary leak

**Fail evidence**: any `FAILED` or `ERROR` line in the summary.

### `make run` — Pass (dev/CI environment, no GPU/X11)

```
$ make run
uv run koe
make: *** [Makefile:13: run] Error 1
```

- `koe` process exits 1 (controlled preflight rejection)
- make echoes the non-zero exit as `Error 1` — this is make behaviour, not koe failure
- Desktop notification "error_dependency" should have fired if `notify-send` is present
- **This is correct behaviour** in a non-target environment

### `make run` — Pass (M1 target runtime)

```
$ make run
uv run koe
[Desktop notification: "Recording started"]
[User speaks]
[Desktop notification: "Processing"]
[Desktop notification: "Completed"]
```

- exit: 0 (make produces no error line)
- Spoken text appears in the previously-focused terminal input
- Desktop notifications appear in sequence: `recording_started → processing → completed`
- Clipboard is restored to its pre-invocation state

**Fail evidence (M1 target)**:
- exit 2: unhandled exception (programmer bug)
- exit 0 but no text pasted: insertion contract broken
- exit 1 with `error_transcription` notification: CUDA unavailable or model load failure
- No notification at any point with a non-zero exit: `send_notification` is broken

---

## Open Risks

### R1 — `make run` is not automatable at M1

`make run` requires physical hardware (CUDA GPU, X11, microphone, focused terminal).
There is no CI environment that satisfies all `dependency_preflight` checks. The M1
gate for this command is a **manual checkpoint**, not an automated one.

**Mitigation**: The three automated gates (`lint`, `typecheck`, `test`) are sufficient
for CI. `make run` acceptance is performed once on target hardware by the developer
before M1 sign-off. The research confirms this was the intent (`spec.md §7 AC3`
says "execute successfully in a clean environment" — meaning the target environment,
not CI).

**Gap to address**: There is no documented protocol for who performs the manual
`make run` acceptance, on which hardware, and what the sign-off artifact looks like.

### R2 — Missing explicit e2e terminal integration test (AC1 gap)

`spec.md §7 AC1` requires "one end-to-end terminal flow integration test."
`tests/test_main.py:267` provides a comprehensive mock-based orchestration test
(`test_run_pipeline_captured_path_orders_notifications_and_cleans_artifact`) that
covers the full happy path with all 175 passing tests covering error paths.

However, no `tests/*integration*.py` file exists and no test calls real system
processes. This is the confirmed AC1 gap from `section-7-research.md`.

**Risk**: If the gap is interpreted strictly, `make test` passing does not satisfy
AC1 for M1 sign-off.

**Clarification needed**: Does "e2e terminal integration test" mean:
  - (a) A test that exercises the real subprocess boundary (xdotool, xclip)?
  - (b) A test that exercises the full `run_pipeline` composition end-to-end,
        accepting mocked system calls?

If (b): `test_main.py:267` satisfies the intent. If (a): a new test file is required,
and it cannot run in CI without target hardware — creating a category of tests that
must be marked `@pytest.mark.integration` and excluded from `make test` in CI.

### R3 — `make test` count is not a formal gate threshold

The 175 test count is an observed fact, not a committed minimum. If tests are removed
or renamed, `make test` still passes. There is no floor on the count.

**Risk**: A test refactor could silently drop coverage while the gate remains green.

**Mitigation**: The ruff `ARG` and `ANN` rules catch unused fixtures. Pyright strict
catches unreferenced imports. Neither catches deleted test files. This risk is
acceptable at M1 scale (9 test files, <900 lines total) but should be revisited at M2.

### R4 — `make run` exit code 1 in CI is indistinguishable from a genuine regression

`make run` exits 1 both when `dependency_preflight` correctly rejects a dev environment
AND when the pipeline fails for a new bug. The exit code alone cannot distinguish them.

**Risk**: A CI pipeline that runs `make run` and treats exit 1 as "expected" will
silently swallow genuine regressions.

**Mitigation**: `make run` must not be included in automated CI gates. The three
tool-level gates (`lint`, `typecheck`, `test`) are the complete automated gate set.
`make run` is a manual M1 acceptance command only.

### R5 — README AC4 is unmet and blocks M1 sign-off

`spec.md §7 AC4` requires README onboarding sufficient for a new contributor to
achieve first transcription within 15 minutes. The current README (`README.md:1,3`)
contains only the project title and a one-line description.

**Risk**: `make test` passing and all other automated gates green does not satisfy M1
if the onboarding criterion is applied strictly. M1 sign-off is blocked on README
completion independent of command surface quality.

**This risk is a known open item** per `section-7-research.md §AC4`.

### R6 — `noqa` suppressions are not enumerated or guarded

Five `# noqa` suppressions exist across three files. There is no mechanism to
prevent new suppressions being added silently. Ruff does not have a "max-noqa-count"
configuration.

**Risk**: The zero-warnings policy erodes over time through suppression accumulation.

**Mitigation**: Code review is the current control. This is acceptable at M1 scale.
At M2, consider a `ruff check --statistics` step in CI to emit a suppression count
as observable signal.

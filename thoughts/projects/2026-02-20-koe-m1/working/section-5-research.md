---
date: 2026-02-20T16:17:27+11:00
researcher: opencode
git_commit: a1e66c2
branch: master
repository: koe
topic: "Section 5 of thoughts/projects/2026-02-20-koe-m1/spec.md. Focus: Text Insertion and Clipboard Safety"
tags: [research, codebase, section-5, insertion, clipboard]
status: complete
project_index: thoughts/projects/2026-02-20-koe-m1/index.md
project_section: "Section 5: Insertion and Clipboard Safety"
last_updated: 2026-02-20
last_updated_by: opencode
---

# Research: Section 5 Text Insertion and Clipboard Safety

**Date**: 2026-02-20T16:17:27+11:00
**Researcher**: opencode
**Git Commit**: a1e66c2
**Branch**: master
**Repository**: koe

## Research Question

Document the current as-is implementation status for Section 5 of `thoughts/projects/2026-02-20-koe-m1/spec.md`, with full acceptance-criteria coverage and concrete file:line evidence.

## Summary

Section 5 runtime behavior is not yet implemented. The insertion module is currently a stub (`src/koe/insert.py:1`), and `run_pipeline()` intentionally raises `NotImplementedError("Section 5 handoff: insertion")` on the transcription text arm (`src/koe/main.py:102`).

The type/config contracts required by Section 5 are already present: clipboard state, insertion error shape, insertion notification kind, insertion pipeline outcome, and paste key configuration (`src/koe/types.py:79`, `src/koe/types.py:108`, `src/koe/types.py:91`, `src/koe/types.py:143`, `src/koe/config.py:17`).

Cleanup guarantees that Section 5 depends on are already active in orchestration: audio artifact cleanup in inner `finally` and lock release in outer `finally` (`src/koe/main.py:103`, `src/koe/main.py:106`).

## Acceptance Criteria Coverage (Section 5)

Canonical criteria source: `thoughts/projects/2026-02-20-koe-m1/spec.md:82-87`.

### AC1: Insertion uses clipboard-write plus simulated paste

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:82`
- **Status**: not implemented in runtime
- **Evidence**:
  - Section 5 module is stub-only: `src/koe/insert.py:1`
  - Pipeline stops at handoff sentinel: `src/koe/main.py:102`
  - Strategy is specified in requirements/docs, not runtime code: `thoughts/projects/2026-02-20-koe-m1/sources/project-brief.md:84`, `docs/project-brief.md:84`

### AC2: Text insertion into terminal input in target environment

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:83`
- **Status**: not implemented in runtime
- **Evidence**:
  - No insertion function exists in codebase (`src/koe/insert.py:1`)
  - Main pipeline does not call any insertion code and raises instead (`src/koe/main.py:102`)

### AC3: Clipboard backup attempted and successful runs restore original clipboard

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:84`
- **Status**: contract defined; runtime behavior not implemented
- **Evidence**:
  - Clipboard backup type exists: `ClipboardState.content: str | None` (`src/koe/types.py:79-80`)
  - No backup/restore runtime implementation exists (`src/koe/insert.py:1`)
  - API design records planned Section 5 functions for save/restore and insertion (`thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:491-500`)

### AC4: Insertion failure path is explicit, actionable recovery feedback, cleanup still runs

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:85`
- **Status**: partially present (typed recovery payload + cleanup behavior), insertion failure runtime path not implemented
- **Evidence**:
  - Recovery-oriented field exists in insertion error contract: `transcript_text` (`src/koe/types.py:111`)
  - Notification kind for insertion errors exists (`src/koe/types.py:91`)
  - Pipeline outcome for insertion errors exists (`src/koe/types.py:143`) and maps to exit code 1 (`src/koe/main.py:119`)
  - Cleanup is guaranteed even on Section 5 handoff exception (`src/koe/main.py:103-106`)
  - Tests confirm cleanup on text-handoff path and on all transcription outcomes: `tests/test_main.py:420-455`, `tests/test_main.py:472-507`

### AC5: Clipboard restore failure after paste is surfaced explicitly

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:86`
- **Status**: not implemented in runtime
- **Evidence**:
  - No restore operation exists in runtime (`src/koe/insert.py:1`)
  - No explicit restore-failure notification branch exists in main pipeline (`src/koe/main.py:55-106`)
  - Notification payload has explicit handlers only for `already_running`, `error_focus`, `error_dependency`; insertion falls back to generic payload (`src/koe/notify.py:27-34`)

### AC6: Text-only clipboard guarantee and non-text limitation documented

- **Criterion**: `thoughts/projects/2026-02-20-koe-m1/spec.md:87`
- **Status**: partially documented
- **Evidence**:
  - Type boundary for clipboard is text-or-none only (`src/koe/types.py:79-80`)
  - Type tests enforce text-or-none shape (`tests/test_types.py:118-120`)
  - Design notes explicitly call out non-text case represented by `None` (`thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:194-196`, `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:737`)
  - Project brief confirms clipboard save/restore intent but does not add non-text runtime behavior (`docs/project-brief.md:84`, `docs/project-brief.md:238`)

## Detailed Findings

### Runtime Section 5 boundary in pipeline

- The text transcription arm currently ends at a Section 5 handoff exception (`src/koe/main.py:102`).
- This occurs only after transcription returns `kind == "text"` (`src/koe/main.py:98-102`).
- Both cleanup boundaries execute regardless: artifact removal then lock release (`src/koe/main.py:103-106`).

### Section 5 module state

- `insert.py` currently contains only a module docstring and no implementation (`src/koe/insert.py:1`).

### Type surface already prepared for Section 5

- Clipboard state type exists (`src/koe/types.py:79-80`).
- Insertion error contract exists with transcript preservation field (`src/koe/types.py:108-111`).
- Notification and pipeline outcome enums include insertion variants (`src/koe/types.py:91`, `src/koe/types.py:143`).

### Config surface for paste strategy

- Paste keystroke config is already modeled: modifier + key (`src/koe/config.py:17-18`).
- Defaults are `ctrl` + `v` (`src/koe/config.py:31-32`).

### Notification behavior relevant to insertion failures

- Notification transport is best-effort and non-raising (`src/koe/notify.py:12-23`).
- Insertion error kind has no dedicated payload formatter and currently resolves through generic fallback (`src/koe/notify.py:34`).

## Tests and Current Verification Surface

- `error_insertion` outcome mapping is already covered in exit code tests (`tests/test_main.py:108-113`).
- Section 5 handoff is currently asserted as `NotImplementedError` for text transcription path (`tests/test_main.py:420-455`).
- Artifact cleanup around handoff path is validated (`tests/test_main.py:454`, `tests/test_main.py:507`).
- Type-shape tests validate clipboard and insertion error contracts (`tests/test_types.py:118-120`, `tests/test_types.py:136-143`, `tests/test_types.py:179-184`).

## Architecture Documentation (as implemented)

- Procedural orchestration for pre-Section-5 stages is active in `run_pipeline()` (`src/koe/main.py:55-106`).
- Section 5 is a typed-but-unimplemented boundary: runtime placeholder + established type/config vocabulary (`src/koe/main.py:102`, `src/koe/types.py:79-111`, `src/koe/config.py:17-18`).
- Cleanup invariants required by Section 5 acceptance are present in orchestration `finally` blocks (`src/koe/main.py:103-106`).

## Historical Context (thoughts/)

- Section 5 acceptance criteria and clipboard-safety obligations: `thoughts/projects/2026-02-20-koe-m1/spec.md:76-87`.
- Spec mirror Section 5 user stories/criteria: `thoughts/specs/2026-02-20-koe-m1-spec.md:110-119`.
- Section 1 API design already defines Section 5 typed contracts and planned insertion/clipboard interfaces: `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:190-198`, `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:243-252`, `thoughts/design/2026-02-20-koe-m1-section-1-api-design.md:491-500`.
- Section 4 historical context documents text handoff to Section 5 and `InsertionError.transcript_text` handoff intent: `thoughts/projects/2026-02-20-koe-m1/working/section-4-historical-context.md:243-279`.

## Related Research

- `thoughts/projects/2026-02-20-koe-m1/working/project-level-research-architecture.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-4-research.md`
- `thoughts/projects/2026-02-20-koe-m1/working/section-4-historical-context.md`

## Open Questions

- Should non-text/binary clipboard restoration be implemented in M1 or remain explicitly documented as text-only (`thoughts/projects/2026-02-20-koe-m1/spec.md:146`, `thoughts/specs/2026-02-20-koe-m1-spec.md:210`)?

## Assumptions & Risks

- **Assumption**: metadata helper script `hack/spec_metadata.sh` is unavailable in this working tree.
  - **Why**: direct invocation returned `No such file or directory`.
  - **Validation approach**: add/restore script or provide alternative metadata command surface.
  - **Risk if wrong**: document metadata format could drift from project convention.

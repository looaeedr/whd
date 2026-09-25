---
whd_doc_role: HISTORICAL
whd_contract: implementation-plan-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue #212 T8 Final Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a clean, fully validated integration candidate containing current production plus accepted T0-T7 modularization, then non-force integrate only after all final gates are GREEN.

**Architecture:** Start from the locked production head, merge only the exact accepted T7 source, resolve overlapping durable-rule files in favor of current production authority plus compatible T7 additions, clean temporary QA residue, validate the candidate exhaustively, then re-fetch production and integrate only if ancestry/drift remains valid. Production is never used as the conflict-resolution workspace.

**Tech Stack:** Python 3.12, pytest, Tk/Xvfb, Git/GitHub Actions, DXF/ezdxf.

**Spec:** `docs/superpowers/specs/2026-09-14-issue212-final-integration-design.md`

## Global Constraints
- Production base is locked initially at `e0a82f28f4ce3204c9fae56326f34f1a0964851f`.
- Accepted T7 exact target is `254f82f589e684b59e48dabb93ce2a6767d440bc`.
- No direct production mutation before final acceptance.
- No feature work, geometry/DXF fixes, assertion weakening, golden rewrite, or force integration.
- Validation is judge-only, never a production calculation source.
- No RUN identity means RUN_NOT_CREATED: create/fix the prerequisite; do not wait.

---

### Task 1: Lock lineage and create clean integration candidate

**Files:**
- Read: Git refs/commits only
- Modify: candidate Git history only

**Interfaces:**
- Consumes: production `e0a82f28...`, accepted T7 `254f82f5...`
- Produces: candidate commit with both lineages as ancestors

- [ ] Re-fetch production and both locked SHAs; fail if either moved/vanished.
- [ ] Verify T7 ancestry includes accepted T6 cleaned head `2e354528...`.
- [ ] Merge `integrate/issue212-t7-accepted-20260914` into `integrate/issue212-final-combined-20260914`; never use the later T7 branch head.
- [ ] Resolve conflicts only on the candidate. Preserve current production durable execution rules, especially `EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE`, while retaining compatible T7 additions.
- [ ] Record merge parents and changed-file inventory in durable #212 evidence.

### Task 2: Clean temporary residue without deleting durable regressions

**Files:**
- Delete only temporary `.scratch/issue20x-*`, T0-T7 trigger markers, one-shot QA workflows/probes proven temporary
- Preserve: `tests/**`, `gui_modules/**`, approved `docs/**`, `.agents/skills/**`, AI/trap library durable rules

**Interfaces:**
- Consumes: merged candidate
- Produces: clean candidate with no temporary QA residue

- [ ] Inventory every candidate-only scratch/workflow/probe file and classify TEMPORARY vs DURABLE.
- [ ] Remove TEMPORARY files only; do not delete permanent regression tests or durable knowledge.
- [ ] Run repository source scan proving no temporary issue-specific QA workflow/trigger remains.
- [ ] Commit cleanup separately from the merge/conflict-resolution commit.

### Task 3: Candidate preflight and focused validation

**Files:**
- Test: modularization and renderer dependency suites already present in `tests/`
- Evidence: #212 durable remote QA evidence/artifacts

**Interfaces:**
- Consumes: cleaned candidate exact SHA
- Produces: fail-closed preflight + focused GREEN evidence

- [ ] Run `tools/phase6_skill_preflight.py` for #212 against exact changed files/evidence.
- [ ] Run focused T0-T7 modularization, renderer dependency, state ownership, physical identity, 2D↔3D, save/reload, DXF suites.
- [ ] Capture `config.ini` and DXF/reference manifest before tests and compare after tests.
- [ ] If no concrete GitHub Actions RUN exists, classify RUN_NOT_CREATED and immediately fix/execute the prerequisite instead of polling.

### Task 4: Full Headless and Xvfb combined acceptance

**Files:**
- Test: complete repository pytest collection under the established Headless/Xvfb split
- Evidence: terminal logs + artifacts

**Interfaces:**
- Consumes: same exact candidate SHA from Task 3 unless a diagnosed fix creates a new SHA
- Produces: terminal full-suite evidence with exact counts

- [ ] Run full Headless suite to terminal and record exact pass/fail/skip counts.
- [ ] Run full Xvfb suite to terminal and record exact pass/fail/skip counts.
- [ ] For any failure, inspect the exact failed nodeid/signature before changing code.
- [ ] An L4 failure may be labeled inherited only after parent/candidate A/B reproduces the same nodeid and signature; otherwise fail closed.
- [ ] Re-run post-test `config.ini`, DXF/reference, tracked-source, project-schema and geometry-drift invariants.

### Task 5: Final drift audit and production integration

**Files:**
- Git refs/history only until integration

**Interfaces:**
- Consumes: terminal GREEN candidate and fresh production refetch
- Produces: non-force production integration or a fail-closed rebuild requirement

- [ ] Re-fetch `cleanup/2d-3d-sync` immediately before integration.
- [ ] If production is no longer `e0a82f28...` or is not safely reconcilable with the tested candidate, do not integrate; rebuild candidate from new production and repeat required validation.
- [ ] Verify candidate contains both production and accepted T7 lineage and that unapproved production geometry drift is zero.
- [ ] Perform non-force integration only; no force update/rollback.

### Task 6: Exact-production post-integration verification and closure

**Files:**
- Read/validate exact integrated production SHA
- Update: GitHub issue evidence/status only

**Interfaces:**
- Consumes: integrated production SHA
- Produces: #212 and #203 closure evidence

- [ ] Run exact-production focused/post-integration validation and invariants on the integrated SHA.
- [ ] Confirm temporary QA workflow/trigger cleanup remotely after validation.
- [ ] Write final run IDs, SHAs, counts, manifests, drift result, and cleanup result to #212.
- [ ] Close #212 as completed only after terminal GREEN exact-production proof.
- [ ] Close #203 only after #212 closure and final production verification are both confirmed.
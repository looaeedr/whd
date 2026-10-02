---
whd_doc_role: CURRENT
whd_contract: ci-sharding-t0-implementation-plan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #304 T0 Baseline Timing + Authoritative Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the immutable pre-sharding CI timing, collection, lane-membership, Xvfb classification, and protected-invariant baseline on one exact repository head.

**Architecture:** Add one temporary QA workflow that preserves the existing serial lane execution model. It collects exact pytest node IDs, runs every canonical lane to terminal with timing and `--durations=30`, captures non-zero Xvfb rc without `bash -e` bypassing classification, and uploads a single evidence artifact. No test semantics, production code, taxonomy, or sharding behavior change in T0.

**Tech Stack:** GitHub Actions, Bash, Python 3.12, pytest, Xvfb, JUnit XML, existing `tools/test_lane_policy.py` and `tools/test_lane_audit.py`.

**Spec:** `docs/superpowers/specs/2026-09-16-ci-test-sharding-parallelization-design.md`

## Global Constraints

- Parent task: #303; task: #304.
- Exact predecessor for T0 branch: `3b59cb7bcc8ee5dc649924d17b164a55ec10f821`, a docs-only descendant of accepted TEST Cleanup head `a632d1158ba49364b1962a0ed27f4b4109ea4b85`.
- No production/test semantic changes and no sharding.
- Runtime inventory comes from pytest collection, never from a hard-coded `2153` assertion.
- `xvfb-run` rc is captured under `set +e`; `CLASSIFICATION_NOT_RUN` is distinct from HANG/TIMEOUT.
- Every modified file is on `ci-sharding/issue304-t0-baseline-20260916`; production `cleanup/2d-3d-sync` is untouched.
- Final evidence must report queue delay, `EXECUTION_WALL_CLOCK`, `END_TO_END_WALL_CLOCK`, per-lane timings, slowest tests, exact Xvfb failed node IDs, classifier state, and protected hashes.

## Fail-closed knowledge preflight evidence

The required skills/references for this CI + pytest + UI/Xvfb validation task were explicitly read before continuing the implementation:

- `Python測試實務`
- `UI設計與去AI味`
- `READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- `READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`

The preflight remains fail-closed: if the registry requires additional skills/references, the workflow must stop before collection/execution until the evidence is complete.

---

### Task 1: Baseline QA Workflow

**Files:**
- Create: `.github/workflows/issue304-t0-baseline.yml`
- Test/output: `.scratch/issue304/*` inside the GitHub Actions runner

**Interfaces:**
- Consumes: canonical lane expressions from `tools/test_lane_policy.py`; collection audit from `tools/test_lane_audit.py`.
- Produces: `issue304-t0-baseline-evidence` artifact with exact collection lists, lane timings/results, duration logs, Xvfb classification, and invariant hashes.

- [ ] **Step 1: Capture workflow/run timing identity before checkout**

Record runner start epoch immediately, then query the current Actions run for `created_at` and `run_started_at`. Persist queue delay separately from execution timing.

- [ ] **Step 2: Capture immutable scope and protected hashes**

Fail if branch changes relative to predecessor include anything except the T0 plan/workflow and later permanent evidence. Hash all tracked files plus a dedicated `config.ini` / DXF subset before validation.

- [ ] **Step 3: Collect full and per-lane node IDs**

Run `pytest --collect-only -q tests` plus each canonical lane expression. Filter canonical node IDs into text files and write `lane-membership.json`. Reconcile full set against lane union and fail on missing/extra nodes.

- [ ] **Step 4: Run legacy serial lanes with timing**

Run governance, unit, geometry, projection, persistence, dxf, architecture, ui-headless, integration, then Xvfb serially. Every command includes `--durations=30`, JUnit XML, terminal log, start/end timestamps, and child rc.

- [ ] **Step 5: Classify Xvfb after child completion**

The Xvfb child may return rc=1. The classifier must still execute and record `classifier_started`, `classifier_rc`, exact failed node IDs, and whether the failures equal the accepted 13-node inherited baseline set. A non-zero child rc with no classifier execution is `CLASSIFICATION_NOT_RUN`, never HANG.

- [ ] **Step 6: Verify invariants and aggregate evidence**

Recompute tracked-file and config/DXF hashes, require equality, require clean tracked worktree, calculate execution/end-to-end timing, and upload all evidence even when a lane is red.

- [ ] **Step 7: Acceptance gate**

Require collection union parity, every non-Xvfb lane rc=0, exact accepted Xvfb failure set if Xvfb remains red, classifier terminal success, and protected invariants GREEN.

### Task 2: Permanent T0 Evidence and Handoff

**Files:**
- Create after terminal run: `docs/superpowers/verification/2026-09-16-issue304-t0-baseline.md`

**Interfaces:**
- Consumes: terminal run/artifact from Task 1.
- Produces: exact T0 accepted head and baseline values that #305 must use as its parent.

- [ ] **Step 1: Read terminal run and artifact**

Record run ID, job ID, exact workflow SHA, artifact ID/digest, collection counts, lane results/timings, queue delay, execution/end-to-end timing, slowest nodes, Xvfb classification, and invariant results.

- [ ] **Step 2: Write permanent verification evidence**

The document must carry `WHD_DOC_META_V1` frontmatter and distinguish observed measurements from historical references.

- [ ] **Step 3: Fresh closing verification**

Read back the committed evidence and branch SHA, verify production `cleanup/2d-3d-sync` was not moved, then close #304 only when all acceptance gates are evidenced.

- [ ] **Step 4: Handoff**

Update #303 with `CURRENT_ACCEPTED_HEAD=<T0 accepted SHA>` and instruct #305 to branch from that exact SHA. Do not begin #305 from moving production.

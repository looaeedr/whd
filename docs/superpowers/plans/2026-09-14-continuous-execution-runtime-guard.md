---
whd_doc_role: HISTORICAL
whd_contract: implementation-plan-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Continuous Execution Runtime Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace phrase-only continuous-execution enforcement with an executable checkpoint/resume/finalization controller backed by behavior tests and remote QA.

**Architecture:** Add a small pure-Python controller in `tools/continuity_controller.py` that owns continuity state validation, atomic JSON checkpoint persistence, resume identity, transition rules, and workflow-finalization gating. Remote execution skills delegate to this controller; tests exercise behavior directly, including simulated runtime interruption and reload, instead of only searching documentation markers.

**Tech Stack:** Python 3, stdlib `dataclasses`, `enum`, `json`, `pathlib`, `tempfile`/atomic `Path.replace`, pytest, GitHub Actions.

**Spec:** GitHub issue #216.

## Global Constraints

- Production target is `cleanup/2d-3d-sync`; all modifications stay on fresh branch until terminal acceptance.
- Validation/test/golden evidence only judges correctness; it never becomes production calculation authority.
- All non-terminal checkpoints require an explicit `next_action`.
- `WAITING_REMOTE` additionally requires exact `run_id + head_sha` ownership.
- Workflow finalization is forbidden for every non-terminal checkpoint.
- Runtime interruption must preserve exact checkpoint state, remote identity, cursor, and evidence so the next runtime resumes rather than restarts.
- Temporary QA workflows are removed before final integration.

---

### Task 1: Behavior contract RED

**Files:**
- Create: `tests/process/test_continuity_controller.py`
- Create temporarily: `.github/workflows/issue216-continuity-controller-qa.yml`

**Interfaces:**
- Consumes: future `tools.continuity_controller` API.
- Produces: executable RED evidence for required state and persistence behavior.

- [ ] **Step 1: Write failing behavior tests**

Tests import `Checkpoint`, `ContinuityState`, `CheckpointError`, `FinalizationBlocked`, `load_checkpoint`, `save_checkpoint`, `transition_checkpoint`, and `assert_finalizable`; verify missing implementation is RED before production code exists.

- [ ] **Step 2: Run focused remote RED**

Run: `python -m pytest tests/process/test_continuity_controller.py -q`
Expected: FAIL during import because `tools.continuity_controller` does not exist.

- [ ] **Step 3: Record exact RED run/head in issue #216**

Capture run id, head SHA, failed step and bounded error marker.

### Task 2: Executable controller GREEN

**Files:**
- Create: `tools/continuity_controller.py`
- Test: `tests/process/test_continuity_controller.py`

**Interfaces:**
- Produces:
  - `class ContinuityState(str, Enum)`
  - `class CheckpointError(RuntimeError)`
  - `class FinalizationBlocked(CheckpointError)`
  - `@dataclass(frozen=True) class Checkpoint`
  - `save_checkpoint(path: Path, checkpoint: Checkpoint) -> None`
  - `load_checkpoint(path: Path) -> Checkpoint`
  - `transition_checkpoint(checkpoint: Checkpoint, *, state: ContinuityState, next_action: str | None = None, run_id: int | None = None, job_id: int | None = None, head_sha: str | None = None, log_cursor: str | None = None, evidence: tuple[str, ...] | None = None) -> Checkpoint`
  - `assert_finalizable(checkpoint: Checkpoint) -> None`

- [ ] **Step 1: Implement minimal validation and immutable checkpoint model**

Non-terminal = `RUNNING`, `WAITING_REMOTE`, `RECOVERING`, `BLOCKED`; terminal = `TERMINAL_SUCCESS`, `TERMINAL_FAILURE`. Every non-terminal requires nonblank `next_action`; `WAITING_REMOTE` requires positive integer `run_id` and nonblank `head_sha`; terminal checkpoints must have `next_action=None`.

- [ ] **Step 2: Implement atomic save/load**

Serialize versioned JSON to sibling temporary file and replace target only after successful write; load rejects unknown version, malformed state, and invalid fields.

- [ ] **Step 3: Implement transition/finalization gate**

Terminal checkpoints cannot transition to any other state. `assert_finalizable` raises `FinalizationBlocked` for all non-terminal states.

- [ ] **Step 4: Run focused tests to GREEN**

Run: `python -m pytest tests/process/test_continuity_controller.py -q`
Expected: all PASS.

### Task 3: Delegate Skills and durable knowledge to executable authority

**Files:**
- Modify: `.agents/skills/engineering/monitoring-remote-qa/SKILL.md`
- Modify: `.agents/skills/engineering/執行開發任務/SKILL.md`
- Modify: `個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md`
- Modify: `tests/process/test_continuous_execution_durable_contract.py`

**Interfaces:**
- Consumes: `tools/continuity_controller.py`.
- Produces: `EXECUTABLE_CONTINUITY_CONTROLLER_V1` durable marker and behavior-backed authority.

- [ ] **Step 1: Add delegation contract**

Skills must state that prose gates do not constitute enforcement; durable checkpoints/finalization use the executable controller. `WAITING_REMOTE` observations preserve exact `run_id/head_sha/job_id/log_cursor`.

- [ ] **Step 2: Replace phrase-only confidence with executable contract checks**

Existing marker tests remain compatibility guards, but new tests import and execute the controller, ensuring the repository cannot claim runtime enforcement from documentation alone.

- [ ] **Step 3: Run process regression suite**

Run: `python -m pytest tests/process/test_continuity_controller.py tests/process/test_continuous_execution_durable_contract.py tests/process/test_long_log_context_safe_execution_contract.py -q`
Expected: all PASS.

### Task 4: Remote acceptance and cleanup

**Files:**
- Temporary: `.github/workflows/issue216-continuity-controller-qa.yml`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: terminal remote evidence and a tree with no temporary workflow.

- [ ] **Step 1: Run final remote QA**

Workflow records exact branch head, Python compile, focused behavior/process tests, and invariant hashes.

- [ ] **Step 2: Poll same run to terminal**

Lock the exact `run_id + head_sha`; inspect jobs/steps until terminal. On failure, read only bounded failed-job logs and repair on the same work branch.

- [ ] **Step 3: Delete temporary workflow after terminal GREEN**

Delete `.github/workflows/issue216-continuity-controller-qa.yml`; confirm compare against accepted implementation contains only intended permanent files.

- [ ] **Step 4: Verify production drift before integration**

Re-read `cleanup/2d-3d-sync`; if its head differs from baseline, classify drift before integrating. Never force-update production.

- [ ] **Step 5: Integrate non-force and close issue only after final production verification**

Final production must contain controller/tests/durable delegation but no issue216 temporary workflow; record exact production SHA and evidence in #216.
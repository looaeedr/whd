---
whd_doc_role: REFERENCE
whd_contract: issue312-t8-final-ci-integration-qualification-plan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue 312 T8 Final CI Integration Qualification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close #312/T8 by running a fresh optimized final acceptance against the exact accepted T7 tested SHA, qualifying current production drift and the exact integration shape without mutating production, securing permanent evidence before cleanup, updating durable CI operating rules, and leaving the chain in `QUALIFIED_FOR_INTEGRATION` until the user explicitly says `合`.

**Architecture:** T8 deliberately separates **orchestration identity** from **tested identity**. The T8 branch may contain the qualification workflow, tests, checkpoint, cleanup gate, drift audit, and knowledge updates; however every full-acceptance execution job checks out and tests exactly `db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f`. The workflow reuses the existing T6/T7 manifest, shard, Xvfb, aggregation, inherited-RED, timing, and invariant helpers; T8 adds only orchestration, final qualification, read-only drift qualification, cleanup safety, and durable readback.

**Tech Stack:** GitHub Actions YAML, Python 3.12, pytest, Xvfb, existing `tools/test_shard_*`, `tools/xvfb_shard_*`, `tools/test_shard_aggregation.py`, `tools/test_shard_tuning.py`, Git/GitHub compare and issue APIs, JSON/Markdown evidence.

**Spec:** `docs/superpowers/specs/2026-09-16-ci-test-sharding-parallelization-design.md`

## Global Constraints

- Exact accepted T7 tested SHA: `db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f`.
- T8 orchestration branch: `ci-sharding/issue312-t8-final-qualification-20260917`.
- Orchestration SHA must never be reported as the tested SHA unless a separate full acceptance actually tests that SHA.
- All full-acceptance collection/execution/Xvfb jobs must explicitly checkout the exact accepted T7 SHA.
- Full collection is runtime-derived; historical counts are evidence only, never a hard-coded authority.
- `FULL_COLLECTION == UNIQUE_SHARD_UNION`; missing, extra, or duplicate ownership is FAIL.
- Xvfb/Tk remains isolated by job/display; no global GUI `pytest -n auto`.
- Only exact inherited baseline RED classification is accepted; no broader exception matching.
- `EXECUTION_WALL_CLOCK`, `END_TO_END_WALL_CLOCK`, and queue time remain separate evidence.
- `config.ini`, DXF, project/tracked-tree, production geometry authority, and other protected inputs must remain unchanged.
- No cleanup before permanent final-acceptance evidence is secured.
- Before deleting any branch/ref, inspect every OPEN PR `head.ref` and `base.ref`; a live PR ref is never deleted.
- Production drift/integration qualification is read-only; do not mutate `cleanup/2d-3d-sync` to make qualification pass.
- If a required workflow has no concrete RUN identity, diagnose/fix the trigger immediately; never poll a nonexistent run.
- No merge/integration without explicit user authorization `合`.
- Final T8 state before merge authorization is exactly `QUALIFIED_FOR_INTEGRATION`.

---

### Task 1: Establish T8 preflight, checkpoint, and fail-closed final-qualification contract

**Files:**
- Create: `docs/superpowers/checkpoints/issue312-t8-preflight-evidence.txt`
- Create: `docs/superpowers/checkpoints/issue312-t8.json`
- Create: `tools/issue312_t8_final_qualification.py`
- Create: `tests/test_issue312_t8_final_qualification.py`

**Interfaces:**
- Consumes: accepted T7 SHA, final acceptance evidence, production drift evidence, cleanup evidence, durable-rule readback.
- Produces: `validate_final_qualification(payload: dict) -> dict` and `QualificationError(code)`.

- [ ] **Step 1: Write the T8 knowledge preflight evidence**

The preflight must record these exact existing authorities:

```text
READ_SKILL: Python測試實務
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_SKILL: executable-continuity-controller
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: docs/superpowers/specs/2026-09-16-ci-test-sharding-parallelization-design.md
```

The boundary section must state that T8 orchestration commits are evidence-only/CI-only, the tested SHA remains `db0b79cd...`, production is read-only, and cleanup is forbidden until final evidence is secured.

- [ ] **Step 2: Write characterization tests before the helper exists**

```python
import pytest

from tools.issue312_t8_final_qualification import QualificationError, validate_final_qualification

ACCEPTED = "db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f"


def good_payload():
    return {
        "accepted_t7_sha": ACCEPTED,
        "tested_sha": ACCEPTED,
        "collection": {"full": 2270, "unique_executed": 2270, "missing": [], "extra": [], "duplicate": []},
        "results": {"unclassified_red": [], "infra_errors": []},
        "timing": {"execution_seconds": 314.0, "end_to_end_seconds": 316.0, "queue_seconds": 2.0},
        "protected_drift": {},
        "production": {"mutated": False, "drift_audit_complete": True, "integration_shape_qualified": True},
        "cleanup": {"evidence_secured": True, "open_pr_refs_checked": True, "deleted_live_pr_refs": []},
        "durable_rules": {"updated": True, "readback_verified": True},
        "final_state": "QUALIFIED_FOR_INTEGRATION",
    }


def test_final_qualification_green():
    assert validate_final_qualification(good_payload())["decision"] == "GREEN"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda p: p.__setitem__("tested_sha", "wrong"), "T7_SHA_MISMATCH"),
        (lambda p: p["collection"]["missing"].append("x"), "MISSING_NODES"),
        (lambda p: p["collection"]["extra"].append("x"), "EXTRA_NODES"),
        (lambda p: p["collection"]["duplicate"].append("x"), "DUPLICATE_NODES"),
        (lambda p: p["results"]["unclassified_red"].append("x"), "UNCLASSIFIED_RED"),
        (lambda p: p["protected_drift"].update({"config.ini": "changed"}), "PROTECTED_DRIFT"),
        (lambda p: p["production"].__setitem__("mutated", True), "PRODUCTION_MUTATION"),
        (lambda p: p["cleanup"].__setitem__("evidence_secured", False), "CLEANUP_BEFORE_EVIDENCE"),
        (lambda p: p["cleanup"]["deleted_live_pr_refs"].append("live"), "LIVE_PR_REF_DELETED"),
        (lambda p: p["durable_rules"].__setitem__("readback_verified", False), "DURABLE_RULE_READBACK_MISSING"),
        (lambda p: p.__setitem__("final_state", "MERGED"), "INVALID_FINAL_STATE"),
    ],
)
def test_final_qualification_fails_closed(mutation, code):
    payload = good_payload()
    mutation(payload)
    with pytest.raises(QualificationError) as exc:
        validate_final_qualification(payload)
    assert exc.value.code == code
```

- [ ] **Step 3: Run the focused RED**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py
```
Expected: import/collection FAIL because `tools.issue312_t8_final_qualification` is absent.

- [ ] **Step 4: Implement the minimal helper and checkpoint schema**

`tools/issue312_t8_final_qualification.py` must expose:

```python
ACCEPTED_T7_SHA = "db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f"


class QualificationError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def validate_final_qualification(payload: dict) -> dict:
    if payload["accepted_t7_sha"] != ACCEPTED_T7_SHA or payload["tested_sha"] != ACCEPTED_T7_SHA:
        raise QualificationError("T7_SHA_MISMATCH")
    c = payload["collection"]
    if c["missing"]:
        raise QualificationError("MISSING_NODES")
    if c["extra"]:
        raise QualificationError("EXTRA_NODES")
    if c["duplicate"]:
        raise QualificationError("DUPLICATE_NODES")
    if c["full"] != c["unique_executed"]:
        raise QualificationError("COLLECTION_EXECUTION_MISMATCH")
    if payload["results"]["unclassified_red"]:
        raise QualificationError("UNCLASSIFIED_RED")
    if payload["protected_drift"]:
        raise QualificationError("PROTECTED_DRIFT")
    if payload["production"]["mutated"]:
        raise QualificationError("PRODUCTION_MUTATION")
    if not payload["production"]["drift_audit_complete"]:
        raise QualificationError("DRIFT_AUDIT_INCOMPLETE")
    if not payload["production"]["integration_shape_qualified"]:
        raise QualificationError("INTEGRATION_SHAPE_UNQUALIFIED")
    if not payload["cleanup"]["evidence_secured"]:
        raise QualificationError("CLEANUP_BEFORE_EVIDENCE")
    if not payload["cleanup"]["open_pr_refs_checked"]:
        raise QualificationError("OPEN_PR_REF_GATE_NOT_RUN")
    if payload["cleanup"]["deleted_live_pr_refs"]:
        raise QualificationError("LIVE_PR_REF_DELETED")
    if not payload["durable_rules"]["updated"] or not payload["durable_rules"]["readback_verified"]:
        raise QualificationError("DURABLE_RULE_READBACK_MISSING")
    if payload["final_state"] != "QUALIFIED_FOR_INTEGRATION":
        raise QualificationError("INVALID_FINAL_STATE")
    return {"decision": "GREEN", **payload}
```

Initial `issue312-t8.json` records issue, branch, accepted predecessor, orchestration head, `run_id: null`, `phase: PREP`, and `cleanup_authorized: false`.

- [ ] **Step 5: Run GREEN and commit**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py
```
Expected: all PASS.

Commit:
```bash
git add docs/superpowers/checkpoints/issue312-t8-preflight-evidence.txt docs/superpowers/checkpoints/issue312-t8.json tools/issue312_t8_final_qualification.py tests/test_issue312_t8_final_qualification.py
git commit -m "#312 T8 add final qualification fail-closed contract"
```

---

### Task 2: Add T8 orchestration workflow while pinning the tested checkout to accepted T7

**Files:**
- Create: `.github/workflows/qa-issue312-t8-final-qualification.yml`
- Modify: `tests/test_issue312_t8_final_qualification.py`

**Interfaces:**
- Consumes: T8 orchestration run SHA and exact tested SHA `db0b79cd...`.
- Produces: final optimized shard evidence and `issue312-t8-final-acceptance` artifact bound to `tested_sha=db0b79cd...`.

- [ ] **Step 1: Add source-structure tests for dual identity**

The test must parse/read the workflow text and require:

```text
TESTED_SHA: db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f
actions/checkout@v4 with ref: ${{ env.TESTED_SHA }} for every collection/execution job
orchestration_sha recorded separately from tested_sha
one authoritative live manifest generated from TESTED_SHA checkout
20 non-GUI logical shards + 4 isolated Xvfb logical shards according to live manifest
existing T5 xdist authorization policy reused
existing T6 concurrency budget/timing policy reused
aggregate missing/extra/duplicate/unclassified/protected gates retained
Unified Summary and permanent artifact uploaded
```

- [ ] **Step 2: Run workflow-contract RED**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py -k workflow
```
Expected: FAIL because the T8 workflow is absent.

- [ ] **Step 3: Implement the workflow by reusing T7/T6 commands, not rewriting execution ownership**

Workflow stages:

```text
focused-contract
plan
optimized-non-gui matrix
optimized-xvfb matrix
aggregate
qualification-evidence
```

`focused-contract` checks out orchestration HEAD so it can run the new T8 tests/helper.

Every full-acceptance stage checks out the tested tree explicitly:

```yaml
- uses: actions/checkout@v4
  with:
    ref: ${{ env.TESTED_SHA }}
    fetch-depth: 0
```

The plan job verifies:

```bash
test "$(git rev-parse HEAD)" = "$TESTED_SHA"
python tools/test_shard_manifest.py --out-dir .scratch/issue312/plan/manifest --source-sha "$TESTED_SHA"
```

The workflow must reuse the existing authoritative inherited Xvfb failure contract and existing `tools/test_shard_execution.py`, `tools/xvfb_shard_execution.py`, `tools/test_shard_aggregation.py`, and `tools/test_shard_tuning.py` semantics from the tested SHA.

- [ ] **Step 4: Run focused GREEN**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py -k workflow
```
Expected: PASS.

- [ ] **Step 5: Commit and require a concrete RUN identity**

Commit:
```bash
git add .github/workflows/qa-issue312-t8-final-qualification.yml tests/test_issue312_t8_final_qualification.py
git commit -m "#312 T8 wire pinned final optimized acceptance"
```

After push, a concrete T8 RUN must appear. If no RUN exists, inspect trigger/path/branch conditions immediately; do not wait.

---

### Task 3: Monitor the fresh final acceptance to terminal and secure permanent evidence

**Files:**
- Modify: `docs/superpowers/checkpoints/issue312-t8.json`

**Interfaces:**
- Consumes: exact T8 RUN ID and run jobs/artifacts.
- Produces: permanent final-acceptance evidence with exact tested SHA, counts, classifications, timings, protected invariants, artifact IDs/digests.

- [ ] **Step 1: Lock `run_id + orchestration_sha + tested_sha` in the checkpoint**

Required checkpoint fields:

```json
{
  "run_id": 0,
  "orchestration_sha": "actual T8 workflow commit SHA",
  "tested_sha": "db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f",
  "phase": "WAITING_REMOTE",
  "cleanup_authorized": false
}
```

`run_id` is replaced with the concrete numeric run ID before entering polling.

- [ ] **Step 2: Actively poll the same locked RUN through every required job**

Verify terminal state for:

```text
focused-contract
plan
all optimized non-GUI jobs
all four optimized Xvfb jobs
aggregate
qualification-evidence
```

On failure, identify exact failed job/step first, read only a bounded log slice, classify root cause, and continue from that gate.

- [ ] **Step 3: Read final artifact/log evidence, not only the run badge**

Require:

```text
FULL_COLLECTION == UNIQUE_SHARD_UNION
MISSING=[]
EXTRA=[]
DUPLICATE=[]
UNCLASSIFIED_RED=[]
ERRORS=0 unless separately classified infrastructure evidence exists and the run remains non-GREEN
PROTECTED_DRIFT=0
exact inherited baseline RED set only
EXECUTION_WALL_CLOCK present
END_TO_END_WALL_CLOCK present
QUEUE present
Unified Summary present
```

- [ ] **Step 4: Mark evidence secured only after artifact readback**

Set:

```json
{
  "final_acceptance": "GREEN",
  "evidence_secured": true,
  "cleanup_authorized": true,
  "tested_sha": "db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f"
}
```

The evidence-only checkpoint commit may be `[skip ci]`; it must never replace the tested SHA in the acceptance record.

- [ ] **Step 5: Commit secured evidence checkpoint**

```bash
git add docs/superpowers/checkpoints/issue312-t8.json
git commit -m "#312 T8 secure final acceptance evidence [skip ci]"
```

---

### Task 4: Perform a fresh read-only production drift audit and qualify the exact integration shape

**Files:**
- Create: `tools/issue312_t8_drift_audit.py`
- Modify: `tests/test_issue312_t8_final_qualification.py`
- Create: `docs/superpowers/checkpoints/issue312-t8-drift-evidence.md`

**Interfaces:**
- Consumes: current `cleanup/2d-3d-sync` HEAD, accepted tested SHA, T8 orchestration branch HEAD, compare file list.
- Produces: deterministic file-classification report and `integration_shape_qualified` boolean without modifying production.

- [ ] **Step 1: Write drift classifier tests**

```python
from tools.issue312_t8_drift_audit import classify_path


def test_ci_paths_are_not_production_source():
    assert classify_path(".github/workflows/qa-issue312-t8-final-qualification.yml") == "CI_OR_EVIDENCE"
    assert classify_path("tools/test_shard_manifest.py") == "CI_OR_EVIDENCE"
    assert classify_path("docs/superpowers/checkpoints/issue312-t8.json") == "CI_OR_EVIDENCE"


def test_production_source_fails_out_of_ci_class():
    assert classify_path("gui.py") == "PRODUCTION_SOURCE"
    assert classify_path("gui_modules/parts/door.py") == "PRODUCTION_SOURCE"
```

- [ ] **Step 2: Run RED**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py -k drift
```
Expected: FAIL until the helper exists.

- [ ] **Step 3: Implement explicit CI/evidence prefixes**

The helper may classify only these as CI/evidence by default:

```python
CI_PREFIXES = (
    ".github/workflows/qa-issue30",
    ".github/workflows/qa-issue31",
    "tools/test_shard_",
    "tools/xvfb_shard_",
    "tools/issue311_t7_",
    "tools/issue312_t8_",
    "tests/test_issue3",
    "docs/superpowers/",
    ".agents/skills/engineering/",
    "個人AI檔案庫/",
)
```

Any unmatched path is `PRODUCTION_SOURCE`; no permissive fallback.

- [ ] **Step 4: Run GREEN and perform live GitHub compares**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py -k drift
```
Expected: PASS.

Then record exact:

```text
current production HEAD
accepted tested SHA
T8 orchestration HEAD
merge-base(s)
ahead/behind counts
changed paths and classifications
whether accepted-chain/production divergence is CI-only or includes production-source changes
exact non-mutating integration shape that would require qualification after explicit `合`
```

- [ ] **Step 5: Commit drift evidence**

```bash
git add tools/issue312_t8_drift_audit.py tests/test_issue312_t8_final_qualification.py docs/superpowers/checkpoints/issue312-t8-drift-evidence.md
git commit -m "#312 T8 qualify production drift and integration shape"
```

---

### Task 5: Gate cleanup with OPEN PR head/base protection and delete only safe temporary refs

**Files:**
- Create: `tools/issue312_t8_cleanup_gate.py`
- Modify: `tests/test_issue312_t8_final_qualification.py`
- Create: `docs/superpowers/checkpoints/issue312-t8-cleanup-evidence.md`

**Interfaces:**
- Consumes: secured-evidence flag, temporary-ref candidates, every OPEN PR `head.ref` and `base.ref`.
- Produces: `safe`, `protected`, and `blocked_reason`; deletion is allowed only for `safe` refs.

- [ ] **Step 1: Write cleanup-gate tests**

```python
import pytest
from tools.issue312_t8_cleanup_gate import CleanupGateError, compute_safe_deletions


def test_open_pr_head_or_base_is_protected():
    result = compute_safe_deletions(
        candidates={"qa/temp-a", "qa/temp-b"},
        open_pr_refs={"qa/temp-a", "cleanup/2d-3d-sync"},
        evidence_secured=True,
    )
    assert result == {"safe": ["qa/temp-b"], "protected": ["qa/temp-a"]}


def test_cleanup_before_evidence_fails_closed():
    with pytest.raises(CleanupGateError) as exc:
        compute_safe_deletions({"qa/temp-a"}, set(), evidence_secured=False)
    assert exc.value.code == "CLEANUP_BEFORE_EVIDENCE"
```

- [ ] **Step 2: Run RED**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py -k cleanup
```
Expected: FAIL until the helper exists.

- [ ] **Step 3: Implement minimal deterministic cleanup gate**

```python
class CleanupGateError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def compute_safe_deletions(candidates: set[str], open_pr_refs: set[str], evidence_secured: bool) -> dict:
    if not evidence_secured:
        raise CleanupGateError("CLEANUP_BEFORE_EVIDENCE")
    protected = sorted(candidates & open_pr_refs)
    safe = sorted(candidates - open_pr_refs)
    return {"safe": safe, "protected": protected}
```

- [ ] **Step 4: Run GREEN, fetch OPEN PR refs fresh, and delete only the computed safe set**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py -k cleanup
```
Expected: PASS.

Before every deletion batch, refresh OPEN PR refs. Never delete `cleanup/2d-3d-sync`, the active T8 branch, or any open PR head/base.

- [ ] **Step 5: Record exact deleted/protected refs and commit evidence**

```bash
git add tools/issue312_t8_cleanup_gate.py tests/test_issue312_t8_final_qualification.py docs/superpowers/checkpoints/issue312-t8-cleanup-evidence.md
git commit -m "#312 T8 gate and record temporary QA cleanup"
```

---

### Task 6: Persist the new CI operating rules into existing canonical skills/AI references and prove readback

**Files:**
- Modify: `.agents/skills/engineering/Python測試實務/SKILL.md`
- Modify: `.agents/skills/engineering/monitoring-remote-qa/SKILL.md`
- Modify: `.agents/skills/engineering/long-log-context-safe-execution/SKILL.md`
- Modify: `.agents/skills/engineering/executable-continuity-controller/SKILL.md`
- Modify: `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- Modify: `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- Modify: `個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md`
- Modify: `個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md`
- Modify: `tests/test_issue312_t8_final_qualification.py`
- Create: `docs/superpowers/checkpoints/issue312-t8-knowledge-readback.md`

**Interfaces:**
- Consumes: existing canonical authority ownership from T7 preflight.
- Produces: durable, non-duplicated rules plus exact committed-file readback evidence.

- [ ] **Step 1: Add exact-presence tests for durable rules**

Tests must verify the designated authorities contain these semantics and no conflicting obsolete rule remains:

```text
NO_RUN_ID => diagnose/fix the trigger immediately; do not wait/poll
DETERMINISTIC_SHARD_OWNERSHIP => one authoritative manifest, missing/extra/duplicate FAIL
FLAKY_WARNING => first-run unexpected RED + retry GREEN remains [FLAKY-WARNING]
CLASSIFICATION_NOT_RUN != HANG/TIMEOUT
CI_CONCURRENCY_BUDGET limits simultaneous runners, not logical shard ownership
DURATION_REBALANCE is deliberate/versioned; HRW remains authoritative until evidence justifies replacement
UNIFIED_SUMMARY is one-page human summary backed by complete machine artifacts
TESTED_SHA and ORCHESTRATION_SHA are separate identities during qualification
```

- [ ] **Step 2: Run durable-rule RED**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py -k durable
```
Expected: FAIL for each genuinely missing durable rule.

- [ ] **Step 3: Update existing authorities only; do not create competing skills**

Each rule goes into the current owner closest to its domain. Cross-domain documents contain bridges/incident lessons, not a second canonical implementation.

- [ ] **Step 4: Run GREEN and fresh readback from the pushed branch**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py -k durable
```
Expected: PASS.

After commit/push, fetch each modified authority from the exact branch HEAD and record the rule, file, and readback SHA in `issue312-t8-knowledge-readback.md`.

- [ ] **Step 5: Commit durable knowledge update**

```bash
git add .agents/skills/engineering/Python測試實務/SKILL.md .agents/skills/engineering/monitoring-remote-qa/SKILL.md .agents/skills/engineering/long-log-context-safe-execution/SKILL.md .agents/skills/engineering/executable-continuity-controller/SKILL.md 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md tests/test_issue312_t8_final_qualification.py docs/superpowers/checkpoints/issue312-t8-knowledge-readback.md
git commit -m "#312 T8 persist CI operating rules and readback"
```

---

### Task 7: Fresh final verification, #303 accepted-chain update, #312 closure, and no-merge handoff

**Files:**
- Modify: `docs/superpowers/checkpoints/issue312-t8.json`
- Create: `docs/superpowers/checkpoints/issue312-t8-final-payload.json`

**Interfaces:**
- Consumes: final-acceptance artifact, live production drift evidence, cleanup evidence, durable-rule readback, issue states.
- Produces: fail-closed `GREEN` final payload and issue comments/state showing `QUALIFIED_FOR_INTEGRATION`, not merged.

- [ ] **Step 1: Run the complete T8 focused contract suite fresh**

Run:
```bash
python -m pytest -q tests/test_issue312_t8_final_qualification.py
```
Expected: all PASS with zero failures.

- [ ] **Step 2: Re-read the authoritative T8 acceptance RUN and artifact fresh**

Require terminal `success`, exact tested SHA `db0b79cd...`, collection reconciliation, exact inherited RED classification, no missing/extra/duplicate/unclassified nodes, protected drift zero, and timing triple present.

- [ ] **Step 3: Build and validate the final payload**

`issue312-t8-final-payload.json` must contain the live values from Tasks 3–6, then run:

```bash
python - <<'PY'
import json
from pathlib import Path
from tools.issue312_t8_final_qualification import validate_final_qualification
p = json.loads(Path('docs/superpowers/checkpoints/issue312-t8-final-payload.json').read_text())
print(json.dumps(validate_final_qualification(p), indent=2, sort_keys=True))
PY
```

Expected:
```json
{
  "decision": "GREEN",
  "final_state": "QUALIFIED_FOR_INTEGRATION"
}
```
plus the full evidence payload.

- [ ] **Step 4: Update #303 and #312 with exact evidence**

#312 final comment records:

```text
accepted tested SHA
T8 orchestration SHA
final acceptance RUN ID
collection count and reconciliation
PASS/SKIP/exact inherited RED/unclassified RED counts
missing/extra/duplicate=0
protected drift=0
execution/end-to-end/queue timings
current production HEAD and integration-shape qualification
cleanup deleted/protected refs
knowledge readback locations
final state=QUALIFIED_FOR_INTEGRATION
NOT MERGED; explicit `合` still required
```

#303 is updated to mark #310, #311, and #312 complete and to record the final accepted/qualified evidence chain without claiming production integration.

- [ ] **Step 5: Close #312 only after fresh verification readback**

Set #312 state `closed`, reason `completed`. Do not merge, move, or mutate production. The next action after closure is to wait for explicit `合` before any production integration operation.

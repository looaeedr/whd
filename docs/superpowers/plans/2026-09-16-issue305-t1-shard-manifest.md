---
whd_doc_role: CURRENT
whd_contract: ci-sharding-t1-implementation-plan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #305 T1 Deterministic Shard Manifest Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic, auditable pytest lane/shard manifests from the existing WHD lane taxonomy without changing test execution semantics.

**Architecture:** Keep `tools/test_lane_policy.py` as lane authority. Add one versioned shard-count JSON source and one focused manifest engine that canonicalizes pytest node ids, performs SHA-256 HRW/Rendezvous assignment, reconciles full/lane/shard ownership fail-closed, and writes canonical JSON plus SHA-256 digests. T1 generates metadata only; no matrix execution, xdist, cache, production behavior, skip/xfail, or test expectation changes.

**Tech Stack:** Python 3.12 stdlib (`hashlib`, `json`, `pathlib`, `subprocess`), pytest, existing `tools/test_lane_policy.py`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-16-ci-test-sharding-parallelization-design.md` + `docs/superpowers/specs/2026-09-16-ci-test-sharding-parallelization-revision-notes.md`

## Global Constraints

- Parent: #303; task: #305; exact predecessor: `d31d68420718b3e612e469a0a856d9bcf202d527` (#304/T0 accepted).
- Branch: `ci-sharding/issue305-t1-manifest-20260916`; production `cleanup/2d-3d-sync` is not a parent and must not be mutated.
- `tools/test_lane_policy.py` remains the lane-expression authority; T1 must not invent a second taxonomy.
- HRW input is stable UTF-8 data equivalent to `algorithm_version + lane + canonical_node_id + shard_id`, hashed with SHA-256; collection index and Python built-in `hash()` are forbidden.
- Manifest JSON is canonical (`sort_keys=True`, compact separators, UTF-8, trailing newline only when written); digest is SHA-256 over canonical payload before embedding/reporting the digest.
- Runtime inventory comes from pytest collection. No `2153` hard-coded acceptance assertion in production tooling.
- Same node set + same lane topology + same algorithm version produces byte-for-byte identical manifests regardless of input order.
- Adding an HRW shard may only keep an existing node on its old shard or move it to the new shard; it must not remap between two pre-existing shards.
- Fail closed on lane-union mismatch, duplicate lane ownership, shard missing/extra nodes, or duplicate shard ownership.
- T1 execution remains legacy/serial; shard manifests are metadata only.
- Protected `config.ini` / DXF / tracked-tree invariants must remain GREEN.
- READ_SKILL: Python測試實務
- READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
- READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md

---

### Task 1: RED contracts for deterministic ownership

**Files:**
- Create: `tests/test_issue305_shard_manifest.py`

**Interfaces:**
- Consumes future API from `tools.test_shard_manifest`.
- Locks: `canonical_node_id`, `hrw_score`, `choose_shard`, `build_manifests`, `canonical_json_bytes`.

- [ ] **Step 1: Add canonical node-id tests**

Test that ` ./tests\\test_a.py::test_case[param] ` canonicalizes to `tests/test_a.py::test_case[param]`, while parameter text and case remain unchanged.

- [ ] **Step 2: Add SHA-256 HRW determinism tests**

Use fixed lane/node/shard ids and a golden `hrw_score` integer derived from the normative byte framing. Verify repeated calls and shuffled shard-id input produce the same owner.

- [ ] **Step 3: Add HRW remap-stability tests**

Generate at least 200 synthetic node ids. Compare ownership for shards `s00,s01,s02` vs `s00,s01,s02,s03`; every changed owner must be `s03`. Adding an unrelated node to the inventory must not change any existing node's owner.

- [ ] **Step 4: Add reconciliation failure tests**

Construct tiny full/lane sets that independently trigger missing lane node, extra lane node, duplicate lane ownership, missing shard node, extra shard node, and duplicate shard ownership. Each must raise `ManifestError` with a stable reason token.

- [ ] **Step 5: Add byte-stability test**

Build the same logical input twice with reversed/shuffled node and lane dictionary order; assert `lane_manifest_bytes` and `shard_manifest_bytes` are byte-for-byte identical and their SHA-256 digests match.

- [ ] **Step 6: Run RED**

Run: `python -m pytest -q tests/test_issue305_shard_manifest.py`
Expected: collection/import failure because `tools.test_shard_manifest` does not exist yet. This is the required TDD RED.

---

### Task 2: Minimal manifest engine + authoritative config

**Files:**
- Create: `config/ci_test_shards.json`
- Create: `tools/test_shard_manifest.py`
- Test: `tests/test_issue305_shard_manifest.py`

**Interfaces:**
- `canonical_node_id(raw: str) -> str`
- `hrw_score(lane: str, node_id: str, shard_id: str, *, algorithm: str = ALGORITHM_VERSION) -> int`
- `choose_shard(lane: str, node_id: str, shard_ids: Sequence[str]) -> str`
- `canonical_json_bytes(payload: object) -> bytes`
- `build_manifests(full_nodes: Iterable[str], lane_nodes: Mapping[str, Iterable[str]], shard_counts: Mapping[str, int], *, source_sha: str) -> ManifestBundle`
- CLI: `python tools/test_shard_manifest.py --out-dir PATH [--config config/ci_test_shards.json] [--source-sha SHA]`

- [ ] **Step 1: Add the single shard-count authority**

Create `config/ci_test_shards.json` with schema `WHD_TEST_SHARD_CONFIG_V1`, algorithm `sha256-hrw-v1`, and counts:
`governance=1, unit=2, geometry=4, projection=2, persistence=1, dxf=1, architecture=1, ui=2, integration=6, xvfb_ui=4`.

- [ ] **Step 2: Implement canonical node ids and HRW**

Normalize only path separators/leading `./`/surrounding whitespace. Frame SHA-256 bytes with NUL separators: `sha256-hrw-v1\0<lane>\0<canonical-node>\0<shard-id>`. Select the highest numeric digest score; iterate sorted shard ids so an astronomically unlikely score tie resolves to lexicographically smallest id.

- [ ] **Step 3: Implement canonical manifests**

Sort lanes, shard ids, and node ids. Emit lane payload schema `WHD_TEST_LANE_MANIFEST_V1` and shard payload schema `WHD_TEST_SHARD_MANIFEST_V1`. Include source SHA, algorithm, config digest, full collection digest, node counts, lane/shard membership and reconciliation report. Do not include timestamps or runner-specific data.

- [ ] **Step 4: Implement fail-closed reconciliation**

Require full set equals lane union and exactly one lane owner per node. Assign each lane node to exactly one configured shard and require global unique shard union equals full set. Raise `ManifestError` with stable tokens: `LANE_MISSING`, `LANE_EXTRA`, `LANE_DUPLICATE`, `SHARD_MISSING`, `SHARD_EXTRA`, `SHARD_DUPLICATE`, `CONFIG_LANE_MISMATCH`, or `INVALID_SHARD_COUNT`.

- [ ] **Step 5: Implement live collection CLI**

Reuse `LANE_EXPRESSIONS` + `XVFB_UI_EXPRESSION` from `tools.test_lane_policy.py`; collect full and per-lane node ids through `python -m pytest --collect-only -q tests`. Write `full-collection.txt`, `lane-manifest.json`, `shard-manifest.json`, `reconciliation.json`, and `manifest-digests.json` under `--out-dir`.

- [ ] **Step 6: Run focused GREEN**

Run: `python -m pytest -q tests/test_issue305_shard_manifest.py`
Expected: all T1 focused tests PASS.

---

### Task 3: Live 2153-equivalent reconciliation + repeatability QA

**Files:**
- Create: `.github/workflows/issue305-t1-manifest.yml`
- Read only: `config.ini`, `基準檔/**/*.dxf`
- Artifact: `.scratch/issue305/**`

**Interfaces:**
- Consumes `tools/test_shard_manifest.py` CLI.
- Produces remote evidence that live collection reconciles and two independent manifest generations are byte-identical.

- [ ] **Step 1: Add preflight and immutable-scope gates**

Require exact #304 predecessor ancestry; run Phase6 skill preflight with this plan as evidence. Capture tracked/config/DXF hashes before QA.

- [ ] **Step 2: Run focused tests**

Run `python -m pytest -q tests/test_issue305_shard_manifest.py`.

- [ ] **Step 3: Generate manifests twice**

Run the CLI into `.scratch/issue305/run-a` and `run-b` on the same workflow SHA. Compare `lane-manifest.json`, `shard-manifest.json`, `reconciliation.json`, and `manifest-digests.json` byte-for-byte.

- [ ] **Step 4: Assert live equations from generated evidence**

Require lane missing/extra/duplicate lists empty; shard missing/extra/duplicate lists empty; live full count equals lane union count and unique shard union count. Report observed count rather than asserting the historical literal 2153.

- [ ] **Step 5: Governance + invariants**

Run governance lane and strict governance, compare config/DXF/tracked hashes, and require clean tracked worktree.

- [ ] **Step 6: Upload QA artifact and fail closed**

Upload `.scratch/issue305`. The workflow exits zero only after all deterministic/reconciliation/invariant gates are GREEN.

---

### Task 4: Permanent evidence + serial handoff

**Files:**
- Create after terminal QA: `docs/superpowers/verification/2026-09-16-issue305-t1-shard-manifest.md`

**Interfaces:**
- Produces exact T1 accepted head for #306/T2.

- [ ] **Step 1: Record exact terminal evidence**

Record run/job/head/artifact/digest, observed full count, lane/shard reconciliation, manifest digests, repeatability comparison, focused tests, governance and protected invariants.

- [ ] **Step 2: Fresh closing verification**

Prove accepted delta after QA consists only of permanent evidence, re-read the evidence commit, run governance/strict validation with the complete collection-time dependency set, and fresh-read production without mutating it.

- [ ] **Step 3: Close and hand off**

Close #305 only after closing verification GREEN. Update #303 `CURRENT_ACCEPTED_HEAD` / `LAST_ACCEPTED_SERIAL_TASK` / `NEXT_SERIAL_TASK`, then branch #306 from the exact accepted #305 head.

---
whd_doc_role: CURRENT
whd_contract: ci-sharding-t2-non-gui-implementation-plan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #306 T2 Non-Xvfb Job-Level Sharding Implementation Plan

**Goal:** Execute every non-Xvfb pytest node exactly once through deterministic T1 shard ownership, with bounded GitHub runner concurrency, and prove result parity against a serial reference on the same exact head.

**Exact predecessor:** `8a008b68d8c0058de589d79faf5865a96922460b` (#305/T1 accepted)

**Task branch:** `ci-sharding/issue306-t2-non-gui-sharding-20260916`

## Required evidence preflight

- READ_SKILL: Python測試實務
- READ_SKILL: UI設計與去AI味
- READ_SKILL: diagnosing-bugs
- READ_SKILL: tdd
- READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
- READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md

## Scope

T2 consumes `tools/test_shard_manifest.py` and `config/ci_test_shards.json` from accepted T1. It must not recalculate ownership independently inside shard jobs.

Execution lanes:

- governance: 1 logical shard
- unit: 2
- geometry: 4
- projection: 2
- persistence: 1
- dxf: 1
- architecture: 1
- ui headless: 2
- integration: 6

`xvfb_ui` is excluded from T2 execution and remains untouched for #307/T3.

Initial `CI_CONCURRENCY_BUDGET`: 4 runners. Logical shard ownership remains unchanged if the budget changes.

No xdist. No cache. No production source changes. No test expectation/skip/xfail changes.

## Architecture

1. A single planning job generates the authoritative T1 shard manifest once.
2. `tools/test_shard_execution.py` reads that manifest and emits a compact GitHub matrix containing non-Xvfb lane/shard ids only.
3. Matrix shard jobs download that exact manifest artifact and execute the exact assigned node ids. They never invoke marker-based lane discovery.
4. Each shard gets its own GitHub-hosted runner workspace and explicit runner-local `--basetemp` root.
5. `tools/test_shard_execution.py` always captures child pytest rc, JUnit counts, assigned-node count and execution duration before returning.
6. A serial reference job executes the same manifest-owned non-Xvfb nodes lane-by-lane on the same workflow head.
7. `tools/test_shard_aggregate.py` proves exact node union/no duplicates and compares per-lane PASS/FAIL/SKIP/ERROR totals against serial reference.
8. Shard jobs query their GitHub Actions job metadata to record queue wait (`started_at - created_at`) and record test execution duration separately.

## TDD Task 1 — RED execution-plan contracts

Create `tests/test_issue306_non_gui_sharding.py` before implementation.

Contracts:

- T2 plan excludes `xvfb_ui` completely.
- Matrix has exactly one entry per configured non-Xvfb logical shard.
- Every matrix entry identifies lane/shard/count only; node ownership stays in the manifest artifact.
- Concurrency budget must be positive integer and must not mutate matrix ownership.
- Exact shard-node extraction fails closed for unknown lane/shard and rejects Xvfb in T2 mode.
- Aggregate reconciliation rejects missing, extra, duplicate or count-mismatched executed nodes.
- Aggregate per-lane result totals must equal serial-reference totals.
- Result parsing requires pytest/JUnit testcase count to equal assigned node count.

Required RED: import failure because `tools.test_shard_execution` / `tools.test_shard_aggregate` do not exist.

## TDD Task 2 — Minimal helpers

Create:

- `config/ci_test_execution.json` — execution-policy schema with `ci_concurrency_budget=4` only; it does not duplicate shard counts.
- `tools/test_shard_execution.py` — matrix creation, node extraction, exact pytest execution, JUnit/result JSON.
- `tools/test_shard_aggregate.py` — fail-closed node/result reconciliation.

Focused GREEN must pass all #306 unit contracts.

## Task 3 — Remote parallel acceptance

Create temporary QA workflow on a fresh QA branch. It must:

- prove exact ancestry from #305 accepted head;
- run fail-closed preflight using this plan;
- capture protected config/DXF hashes;
- generate one authoritative manifest artifact;
- emit matrix + max-parallel output from execution config;
- run serial same-head reference lane-by-lane;
- run every non-Xvfb logical shard with matrix `max-parallel=4`;
- use runner-local `--basetemp`;
- record per-shard queue wait and test execution duration;
- aggregate every result and prove exact non-Xvfb union/no duplicate;
- compare per-lane PASS/FAIL/SKIP/ERROR totals to serial reference;
- keep Xvfb absent from execution evidence;
- rerun Governance/strict authority and protected invariants;
- upload acceptance artifacts and fail closed.

## Acceptance equations

```text
T2_EXPECTED_NON_XVFB = UNION(T1 lanes except xvfb_ui)
UNION(EXECUTED_SHARD_NODES) == T2_EXPECTED_NON_XVFB
DUPLICATE_EXECUTED_NODES == []
MISSING_EXECUTED_NODES == []
EXTRA_EXECUTED_NODES == []
for each lane:
  SHARDED_PASS_FAIL_SKIP_ERROR == SERIAL_REFERENCE_PASS_FAIL_SKIP_ERROR
XVFB_EXECUTED_NODES == []
```

## Closing

After terminal remote GREEN, write permanent verification evidence on a fresh closing branch. Closing verification must prove evidence-only accepted delta, focused contracts, manifest/result reproducibility, Governance/strict GREEN, config/DXF/tracked invariants GREEN, and fresh production readback without mutation. Only then close #306 and hand exact accepted SHA to #307/T3.

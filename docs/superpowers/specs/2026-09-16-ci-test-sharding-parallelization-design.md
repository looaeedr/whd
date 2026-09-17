---
whd_doc_role: CURRENT
whd_contract: ci-test-sharding-parallelization-design
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD CI Test Sharding / Parallelization Design Specification

Date: 2026-09-16 (Asia/Taipei)
Repository: `looaeedr/whd`
Status: Design approved for specification; implementation not yet authorized
Scope owner: Test/CI execution architecture only

## 1. Purpose

WHD currently has a complete regression collection of **2153 tests**. A full validation cycle can take roughly **30 minutes wall-clock**, which is too slow for repeated task acceptance, recovery, A/B classification, and final integration work.

This specification defines a new CI execution architecture that reduces wall-clock time by running the **same complete test collection** in deterministic parallel shards while preserving every existing correctness, governance, drift, and inherited-RED gate.

The optimization is an execution-architecture change only. It must not weaken validation, alter production behavior, or redefine a failing test as passing merely to improve speed.

## 2. Primary goals

1. Preserve the exact full regression population. The authoritative full collection remains **2153 tests** until the repository itself legitimately changes that count.
2. Reduce full acceptance wall-clock time to a target of **12 minutes or less** under normal GitHub-hosted runner conditions.
3. Treat **15 minutes** as the performance acceptance ceiling for the completed design. A fresh full-suite acceptance above 15 minutes is a performance FAIL unless GitHub infrastructure degradation is separately evidenced.
4. Keep shard membership deterministic and reproducible.
5. Keep Xvfb/Tk execution isolated so GUI state cannot leak between parallel workers.
6. Preserve current fail-closed behavior for missing tests, duplicate tests, unclassified RED, protected-file drift, collection drift, and production drift.
7. Produce enough artifacts to reproduce any shard failure locally or in a focused remote rerun.

## 3. Non-goals

This work does **not**:

- delete tests to meet the time target;
- add broad `skip` / `xfail` markers to reduce runtime;
- modify production geometry, persistence, UI behavior, DXF authority, project schema, or physical-part identity;
- change a test assertion merely because it is slow;
- redefine inherited baseline RED without fresh A/B evidence;
- use nondeterministic test selection;
- make full acceptance optional;
- replace the existing lane taxonomy with one undifferentiated pytest command.

## 4. Current baseline

The current authoritative full collection is 2153 tests. The accepted lane structure observed during TEST Cleanup validation is:

| Lane | Collected | Typical terminal result in accepted evidence |
|---|---:|---|
| Governance | 191 | GREEN after documentation-governance recovery |
| Unit / State | 79 | 77 PASS / 2 SKIP |
| Geometry / Manufacturing | 550 | 499 PASS / 51 SKIP |
| Projection / 2D↔3D | 96 | 95 PASS / 1 SKIP |
| Persistence | 40 | 31 PASS / 9 SKIP |
| DXF | 15 | 15 PASS |
| Architecture | 10 | 8 PASS / 2 SKIP |
| UI Headless | 223 | 133 PASS / 90 SKIP |
| Integration | 836 | 727 PASS / 109 SKIP |
| Xvfb UI | 113 | 100 PASS / 13 inherited baseline RED in current evidence |

The exact counts may change only when repository test inventory legitimately changes. The sharding system must derive its runtime inventory from pytest collection, not from hard-coded historical totals.

## 5. Chosen architecture

### 5.1 High-level approach

Use a two-level execution model:

1. **Lane level:** keep the existing semantic lane taxonomy.
2. **Shard level:** split large lanes into deterministic shards that run as independent GitHub Actions jobs.

For non-GUI tests, a shard may additionally use conservative in-job pytest parallelism after state-isolation proof. For Tk/Xvfb tests, parallelism occurs only through separate isolated jobs/displays; Xvfb tests must not share a Tk display or mutable GUI process state across workers.

### 5.2 Why deterministic sharding is the primary mechanism

Deterministic sharding is preferred over purely dynamic timing-based assignment because it gives:

- stable reproduction from a shard id;
- stable node ownership;
- easier comparison across A/B runs;
- simpler artifact lookup;
- no dependency on stale historical timing data;
- lower risk that timing noise changes the exact composition of a failing shard.

Historical duration data may later be used to rebalance deterministic shard boundaries, but it must not make shard membership unpredictable within a given committed manifest/version.

## 6. Test inventory and shard assignment

### 6.1 Authoritative collection step

Before any test shard begins, CI must produce an authoritative node inventory using pytest collection for every lane.

Required outputs:

- full collected node-id list;
- lane-to-node mapping;
- shard-to-node mapping;
- total unique node count;
- duplicate-node report;
- missing-from-union report;
- extra-in-union report;
- SHA256 digest of each mapping artifact.

The gate is fail-closed:

```text
FULL_COLLECTION == UNION(ALL_LANE_COLLECTIONS)
UNIQUE_SHARD_UNION == FULL_COLLECTION
MISSING_FROM_SHARDS == []
EXTRA_IN_SHARDS == []
DUPLICATE_SHARD_OWNERSHIP == []
```

A workflow that executes quickly but fails any of these equations is invalid.

### 6.2 Deterministic assignment rule

Each node id must have exactly one shard owner inside its lane.

Preferred implementation for v1:

1. Collect ordered node ids for the lane.
2. Sort by canonical node id.
3. Assign each node by stable hash modulo shard count, or by a committed deterministic manifest generated from that ordered set.
4. Persist the resulting mapping as an artifact.

The selected algorithm must produce the same mapping for the same node set, lane, shard-count configuration, and repository commit.

### 6.3 Shard-count configuration

Shard counts are configuration, not scattered YAML literals. One authoritative configuration source must declare them.

Initial target configuration:

| Lane | Initial shard count | Notes |
|---|---:|---|
| Governance | 1 | Small; keep serial |
| Unit / State | 2 | Low risk for process isolation |
| Geometry / Manufacturing | 4 | Large CPU-heavy lane |
| Projection / 2D↔3D | 2 | Moderate size |
| Persistence | 1 | Keep serial until file/state isolation is proven |
| DXF | 1 | Protect baseline files and deterministic file access |
| Architecture | 1 | Small |
| UI Headless | 2 | Parallel jobs, not shared GUI objects |
| Integration | 6 | Largest lane; primary wall-clock win |
| Xvfb UI | 4 | Four isolated X servers/jobs |

This is an initial design value, not a promise that every lane must stay at that count. Final implementation must tune counts using measured durations while preserving deterministic ownership.

## 7. Non-GUI in-job parallelism

### 7.1 Allowed use

`pytest-xdist` or equivalent worker parallelism may be used only for shards that pass a state-isolation audit.

A lane is eligible only when tests do not rely on shared mutable:

- `config.ini`;
- DXF baseline files;
- fixed filesystem paths;
- singleton application state;
- global caches whose values depend on execution order;
- fixed network/IPC ports;
- shared Tk roots;
- process-wide environment mutations without cleanup.

### 7.2 Default safety rule

The first implementation must gain most speed from **GitHub job-level sharding**. In-job xdist is an optional second-stage optimization for proven-safe lanes.

Do not enable `-n auto` globally.

### 7.3 Worker-local state

When xdist is used, each worker must receive a unique temporary root and any mutable test resource must resolve underneath that worker-local root.

Protected repository inputs must remain read-only from the test contract perspective.

## 8. Xvfb / Tk strategy

### 8.1 Isolation model

Xvfb tests must be split into multiple independent GitHub jobs. Each job starts its own X server through its own `xvfb-run` invocation.

Required properties:

- one isolated display namespace per shard job;
- no shared `Tk()` root across shard jobs;
- no `pytest -n auto` inside the Tk/Xvfb shard unless a future dedicated proof demonstrates safety;
- each shard may still run its assigned tests serially inside its own display;
- all Tk roots / Toplevels must be destroyed by existing fixture cleanup before job exit.

### 8.2 Initial Xvfb topology

Initial target: **4 Xvfb shards**.

The 113 current Xvfb tests should therefore execute as four deterministic groups, each with its own display. Exact group size does not need to be equal by count; it should be adjusted for wall-clock balance after duration evidence is collected.

### 8.3 Xvfb timing evidence

Each Xvfb shard must emit:

- shard id;
- node-id list;
- start/end timestamps;
- pytest duration summary (`--durations`);
- PASS / FAIL / SKIP counts;
- failed node ids;
- failure signatures;
- display identifier or equivalent isolation evidence.

## 9. Workflow topology

The target workflow has five conceptual stages.

### Stage A — Preflight / authority

- validate execution claim when applicable;
- validate exact expected head SHA;
- validate production/reference SHA when the workflow is qualification-sensitive;
- validate required Skills/governance preflight;
- capture protected-file hashes.

### Stage B — Inventory / shard manifest

- collect all nodes;
- classify by lane;
- generate deterministic shard manifests;
- verify unique ownership and full union;
- upload manifests and digests.

### Stage C — Parallel execution

Run shard jobs concurrently using a GitHub Actions matrix or generated matrix.

Every shard receives its manifest rather than independently guessing which tests belong to it.

### Stage D — Aggregation / classification

Aggregate all shard artifacts and verify:

- every expected shard reported;
- every expected node executed or was legitimately skipped by its existing test contract;
- no node disappeared;
- no node executed in two shards;
- lane PASS/FAIL/SKIP totals reconcile with shard totals;
- inherited RED exceptions match fresh accepted evidence when exceptions are allowed;
- any unexpected RED is unclassified and fails the workflow.

### Stage E — Invariants / performance / final gate

- compare protected-file hashes before/after;
- verify tracked-tree cleanliness where applicable;
- publish total wall-clock and per-shard timing;
- enforce performance acceptance threshold;
- upload final combined evidence.

## 10. Performance contract

### 10.1 Metrics

Every full acceptance run must publish:

- workflow queued time;
- execution start time;
- final completion time;
- total wall-clock execution time;
- per-stage duration;
- per-lane duration;
- per-shard duration;
- slowest 30 pytest nodes per large lane;
- shard imbalance ratio.

### 10.2 Acceptance targets

For a normal GitHub-hosted runner run with no separately evidenced service degradation:

- **Target:** `TOTAL_EXECUTION_WALL_CLOCK <= 12 minutes`
- **Hard performance gate:** `TOTAL_EXECUTION_WALL_CLOCK <= 15 minutes`

A run between 12 and 15 minutes may pass functional acceptance but must report `PERFORMANCE_TARGET_MISSED`. A run above 15 minutes fails the CI optimization acceptance.

Queue time caused by GitHub runner availability must be reported separately and must not be silently mixed with execution wall-clock.

### 10.3 Shard balance

No large-lane shard should take more than 1.75× the median shard duration for that lane after the tuning phase, unless a single indivisible test itself causes the excess. Such a test must be listed explicitly in the timing artifact.

## 11. Correctness and safety gates

The optimized workflow must retain or strengthen all of the following:

1. **Collection completeness:** full set equals shard union.
2. **No duplicate ownership:** one node, one shard.
3. **Governance validation:** WHD documentation authority remains valid.
4. **Protected invariants:** `config.ini`, DXF baselines, project schema, production geometry authority, physical-part identity, and other currently protected sources remain unchanged unless the task explicitly authorizes them.
5. **Tracked-tree cleanliness:** validation must not leave untracked or modified runtime artifacts in the tested tree when the existing workflow requires cleanliness.
6. **Inherited RED classification:** only exact A/B-proven inherited failures may be accepted as inherited. Parallelization must not broaden exception matching.
7. **Fresh production identity:** qualification workflows must fail if the production reference moved from the expected SHA.
8. **No test mutation for speed:** test semantics cannot be weakened to hit timing targets.
9. **No production mutation for CI:** production code cannot be changed merely to make sharding or xdist easier unless separately specified and approved.

## 12. Failure semantics

### 12.1 Missing shard

If any expected shard job fails to start, crashes before producing evidence, or fails to upload its manifest/result artifact, aggregation fails closed.

### 12.2 Partial execution

A shard that collected N assigned nodes but did not produce terminal status for all N is invalid even if pytest exited zero for a partial command.

### 12.3 Flaky retry policy

Automatic rerun may be used only as diagnostic evidence. A first-run unexpected failure cannot be erased from the final acceptance record merely because a retry passes.

The final report must distinguish:

- first-run result;
- retry result;
- classification;
- whether the node is allowed to affect acceptance.

### 12.4 Infrastructure failure

Runner/network/package-index failures must be classified separately from test failures. They may justify rerunning the workflow, but the failed run remains part of evidence and must not be relabeled GREEN.

## 13. Artifacts and evidence

A full run must upload at least:

- `full-collection.txt`;
- `lane-manifest.json`;
- `shard-manifest.json`;
- per-shard pytest terminal log;
- per-shard JUnit XML or equivalent structured result;
- per-shard duration report;
- failed-node/signature report;
- collection reconciliation report;
- protected invariant before/after hashes;
- final aggregation summary;
- total timing report.

The final aggregation artifact must be sufficient to answer:

- Which shard owned this test?
- Did the test run?
- How long did it take?
- What was its terminal result?
- Was a RED inherited, governance-related, infrastructure-related, or new regression?
- Did any protected repository state change?

## 14. Full acceptance versus focused acceptance

### 14.1 Focused task validation

Normal implementation tasks should run:

- tests directly affected by changed code;
- required lane-focused regressions;
- architecture/governance gates required by the task;
- relevant Xvfb shard(s) when GUI behavior is touched.

### 14.2 Full acceptance

The complete 2153-test equivalent collection remains mandatory for:

- master/final acceptance points defined by the work order;
- production integration qualification;
- CI architecture changes themselves;
- any task whose acceptance contract explicitly requires full regression.

Focused testing is a speed optimization for intermediate work, not a replacement for final full validation.

## 15. Rollout plan

### Phase 0 — Baseline timing capture

Run the current serial/full architecture with standardized timing output and `--durations` evidence. Record per-lane and slowest-node baselines.

### Phase 1 — Deterministic manifest tooling

Implement collection reconciliation and shard manifest generation without changing execution parallelism. Prove 2153 full set equals unique shard union.

### Phase 2 — Parallelize non-GUI large lanes

Enable job-level shards for Integration, Geometry, Unit/State, Projection, and UI Headless as allowed. Keep Persistence/DXF serial initially.

### Phase 3 — Xvfb isolation shards

Split Xvfb into four independent display jobs. Prove exact node ownership and identical functional result to the pre-sharding baseline.

### Phase 4 — Optional safe xdist

Only after state-isolation proof, enable conservative worker parallelism within selected non-GUI shards.

### Phase 5 — Performance tuning

Use measured durations to rebalance deterministic shard mappings. Do not alter test semantics.

### Phase 6 — Final combined acceptance

Run the full optimized workflow repeatedly enough to establish reproducibility, then verify performance, functional results, artifacts, invariants, and no test loss.

## 16. Required A/B proof before replacing the old full-suite path

The old and new execution architectures must be compared on the same accepted repository head.

Required proof:

```text
OLD_FULL_COLLECTION == NEW_FULL_COLLECTION
OLD_FAILED_NODE_SET == NEW_FAILED_NODE_SET
OLD_ALLOWED_SKIP_CONTRACT == NEW_ALLOWED_SKIP_CONTRACT
NEW_MISSING_NODES == []
NEW_DUPLICATE_NODES == []
PROTECTED_DRIFT == 0
```

For inherited RED, failure identity must use canonical node + meaningful validation reason, not unstable pytest pretty-print truncation.

The new workflow cannot become authoritative until this A/B gate is GREEN.

## 17. Rollback criteria

Immediately revert to the previous full-suite execution path if any of these are observed after rollout:

- nondeterministic shard ownership;
- missing or duplicate tests;
- order-dependent failures introduced by parallelism;
- mutation of shared config/DXF/project state;
- Xvfb cross-shard state leakage;
- aggregation incorrectly reports GREEN with a failed/missing shard;
- inability to reproduce a failing shard from its manifest;
- performance improvement depends on weakening tests.

Rollback must restore execution architecture only; it must not discard test cases or acceptance evidence.

## 18. Proposed implementation work breakdown

The implementation should be split into serial tasks so each layer is independently provable.

### T0 — Baseline timing and inventory

Deliver current wall-clock baseline, per-lane durations, slowest nodes, exact 2153 inventory, and immutable evidence artifact.

### T1 — Shard manifest engine

Deliver deterministic node ownership, lane/shard manifests, collection reconciliation, duplicate/missing gates, and unit tests for the sharding algorithm.

### T2 — Non-GUI job-level sharding

Parallelize Integration/Geometry/Projection/Unit/UI-Headless as justified, preserving exact result parity.

### T3 — Xvfb four-way isolation

Create four isolated Xvfb shard jobs and prove same failed-node/signature set as baseline.

### T4 — Aggregation and final evidence

Combine shard results into one fail-closed acceptance decision with complete artifacts and timing telemetry.

### T5 — Optional xdist safety expansion

Audit mutable state and introduce worker-level parallelism only where proven safe.

### T6 — Performance tuning

Rebalance deterministic shards using measured durations until target is met or bottlenecks are documented.

### T7 — Old-vs-new A/B acceptance

Run legacy and optimized full suite on the exact same head and prove result parity, full collection parity, invariant parity, and no missing/duplicate execution.

### T8 — Final CI integration / cleanup

Remove superseded temporary QA workflows, retain durable tooling and documentation, perform branch/workflow cleanup with OPEN PR head/base protection, and integrate only after explicit authorization.

## 19. Definition of Done

This CI optimization is complete only when all of the following are simultaneously true:

- full authoritative test collection is preserved;
- unique shard union equals full collection;
- no duplicate shard ownership exists;
- old/new functional A/B result parity is proven;
- Xvfb failures, if any, match their accepted classification evidence exactly;
- all protected invariants remain GREEN;
- no production behavior was modified for CI convenience;
- full combined run target is at or below 12 minutes, or the implementation has at minimum passed the hard <=15 minute gate with `PERFORMANCE_TARGET_MISSED` explicitly reported;
- all timing and test-result artifacts are downloadable and reproducible;
- temporary QA assets are cleaned with branch-ref protection;
- permanent Skills/AI/pitfall documentation is updated for any new CI operating rule introduced by implementation;
- final integration is performed only with explicit user authorization.

## 20. Permanent operating rules introduced by this design

1. **Speed never overrides coverage.** Parallelization may change when/where a test runs, not whether it runs.
2. **Shard ownership is an audited contract.** Missing or duplicate nodes are acceptance failures.
3. **Tk/Xvfb parallelism is process/display isolation, not shared-worker concurrency.**
4. **No global `pytest -n auto`.** Worker parallelism is opt-in per proven-safe lane.
5. **A/B before authority switch.** The optimized workflow must prove parity with the previous accepted workflow before replacing it.
6. **Performance is now measurable acceptance evidence.** Full-suite runtime must be reported and gated, not treated as an informal observation.
7. **No RUN identity means no waiting.** If a CI action should have created a RUN and no concrete RUN exists, diagnose/repair the trigger immediately rather than polling nothing.

## 21. Expected outcome

The intended result is not “fewer tests.” It is the same WHD regression coverage executed as a controlled parallel graph.

The largest expected gains come from:

- splitting the 836-test Integration lane;
- splitting the 550-test Geometry lane;
- running independent semantic lanes concurrently;
- splitting the 113 real-GUI Xvfb tests across isolated displays;
- optionally adding worker-level concurrency only where shared-state audits prove it safe.

The resulting CI should make full acceptance practical during active development while preserving WHD's fail-closed validation model.
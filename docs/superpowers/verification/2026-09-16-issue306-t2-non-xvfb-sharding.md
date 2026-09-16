---
whd_doc_role: CURRENT
whd_contract: issue306-t2-non-xvfb-sharding-verification
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #306 T2 — Non-Xvfb Job-Level Sharding Verification

Date: 2026-09-16 (Asia/Taipei)
Parent: #303
Task: #306 / T2
Exact predecessor: `8a008b68d8c0058de589d79faf5865a96922460b` (#305/T1 accepted)
Implementation head: `a10d05455c90181a02d4a903774e1e9b777d6b74`
Production reference: `cleanup/2d-3d-sync @ 2bbf59fbb2ff2e79c67d9817964d3ff6213b2228`

## Scope delivered

T2 introduces bounded GitHub Actions job-level execution for every non-Xvfb logical shard while preserving the accepted T1 manifest as the sole ownership source.

Implementation artifacts:

- `config/ci_test_execution.json` — execution policy containing the CI concurrency budget; it does not duplicate shard ownership.
- `tools/test_shard_execution.py` — exact manifest-driven matrix creation and shard/lane execution with JUnit/result capture.
- `tools/test_shard_aggregate.py` — fail-closed exact node union and per-lane result reconciliation against a same-head serial reference.
- `tests/test_issue306_non_gui_sharding.py` — matrix, ownership, budget, JUnit-count and reconciliation contracts.
- `tests/test_issue306_aggregate_cli_import.py` — regression contract proving the aggregate CLI can be executed directly as `python tools/test_shard_aggregate.py` from repository root.
- `docs/superpowers/plans/2026-09-16-issue306-t2-non-gui-sharding.md` — implementation plan and fail-closed skill/reference evidence.

No production geometry/UI/persistence/DXF behavior changed. T2 does not use global `pytest -n auto`, does not run Xvfb, and does not reduce live collection coverage.

## TDD and bug-regression chain

Primary T2 RED:

- RUN: `35098541821`
- Preflight: GREEN
- Expected RED: T2 execution helpers did not exist yet; focused pytest failed during collection/import.

Initial focused GREEN:

- RUN: `35098799711`
- Result: `12 PASS / 0 FAIL`
- This established the initial execution/aggregation contracts before remote matrix acceptance.

First full matrix attempt:

- RUN: `35098997000`
- Same-head serial reference: SUCCESS
- 20/20 non-Xvfb shard jobs: SUCCESS
- Final aggregate harness: RED before reconciliation because direct script execution raised `ModuleNotFoundError: No module named 'tools'`.
- This was a CLI bootstrap/harness defect, not a functional test regression.

The defect was converted to a dedicated TDD regression on a fresh branch.

Direct-script regression RED:

- RUN: `35099694429`
- QA head: `a76b63645baf57685f0969136b44501070951739`
- Preflight: GREEN (`diagnosing-bugs`, `tdd`, and pitfall reference all present)
- Exact RED: `tests/test_issue306_aggregate_cli_import.py::test_aggregate_cli_can_start_as_direct_repo_script`
- Exact root cause: `ModuleNotFoundError: No module named 'tools'` from `python tools/test_shard_aggregate.py --help`.

Bugfix focused GREEN:

- RUN: `35100202763`
- QA head: `abc7e924d621213be6fca9d8bef71843cd04c63a`
- Preflight: GREEN
- Focused contracts: `13 passed / 0 failed`
- The fix only adds repository-root import bootstrap for direct CLI execution; reconciliation semantics were not weakened.

## Final full acceptance

Final acceptance workflow:

- RUN: `35100480637`
- QA head: `47c61560592a916ff072a84cc3aedb7ad20241c1`
- Implementation SHA locked by workflow: `a10d05455c90181a02d4a903774e1e9b777d6b74`
- QA delta: exactly `.github/workflows/issue306-t2-parallel-acceptance2.yml`
- Workflow conclusion: SUCCESS
- Plan job: SUCCESS
- Same-head serial reference: SUCCESS
- 20/20 matrix shard jobs: SUCCESS
- Aggregate/final gate: SUCCESS

Live inventory/reconciliation:

- full collection: `2177`
- lane union: `2177`
- unique shard union: `2177`
- non-Xvfb nodes executed by T2: `2064`
- Xvfb nodes excluded from T2 execution: `113`
- non-Xvfb logical shard jobs: `20`
- Xvfb logical shards excluded: `4`
- executed unique non-Xvfb nodes: `2064`
- missing executed nodes: `0`
- extra executed nodes: `0`
- duplicate executed nodes: `0`
- Xvfb executed nodes: `0`
- lane result parity with same-head serial reference: `true`

Manifest/config evidence:

- execution concurrency budget: `4`
- T1 shard-config SHA-256: `59fb472d2bde2959f72ee4467985cd72f2da1ea788afa609d3aedd7c253e8766`
- lane manifest SHA-256: `9d4ecd2fee1a369b83151e681b7f43ca48c33349aeaec353cb116f083ef767d1`
- shard manifest SHA-256: `895705b5bd428df51d6c982fb9fb5caf6e2fcd4651aeeab10e76204f375587f3`

Per-lane same-head parity:

| Lane | Nodes | PASS | SKIP | FAIL | ERROR |
| --- | ---: | ---: | ---: | ---: | ---: |
| architecture | 10 | 8 | 2 | 0 | 0 |
| dxf | 15 | 15 | 0 | 0 | 0 |
| geometry | 550 | 499 | 51 | 0 | 0 |
| governance | 191 | 191 | 0 | 0 | 0 |
| integration | 837 | 728 | 109 | 0 | 0 |
| persistence | 40 | 31 | 9 | 0 | 0 |
| projection | 96 | 95 | 1 | 0 | 0 |
| ui | 235 | 145 | 90 | 0 | 0 |
| unit | 90 | 88 | 2 | 0 | 0 |
| **Total non-Xvfb** | **2064** | **1800** | **264** | **0** | **0** |

Every sharded lane's PASS/FAIL/SKIP/ERROR totals matched the same-head serial reference exactly.

## Bounded parallelism and timing evidence

The matrix consumed the authoritative T1 manifest and used `max-parallel=4`; changing the runner budget does not change logical ownership.

Final acceptance timing evidence:

- shard jobs recorded: `20`
- configured concurrency budget: `4`
- maximum observed queue wait: `162.0 s`
- maximum observed pure test execution duration: `14.075001451000006 s`
- each shard used a runner-local `--basetemp` root.

The acceptance workflow itself ran from `2026-09-16T13:12:53Z` to `2026-09-16T13:17:34Z`. This is an observed acceptance-run wall clock, not a guaranteed CI SLA.

## Governance and protected invariants

Final acceptance proved:

- Governance: `191 passed / 1986 deselected`
- strict governance: `GREEN governed=427`
- reference protected-invariant step: GREEN
- every shard protected-invariant step: GREEN
- tracked repository diff after each shard/reference execution: clean
- config.ini / tracked DXF validation state remained unchanged inside each isolated runner workspace
- production fresh-read: `cleanup/2d-3d-sync @ 2bbf59fbb2ff2e79c67d9817964d3ff6213b2228`
- `ISSUE306_PRODUCTION_READBACK=GREEN`
- final fail-closed marker: `ISSUE306_T2_NON_XVFB_ACCEPTANCE=GREEN`

Acceptance artifact:

- artifact id: `10447918747`
- artifact name: `issue306-t2-acceptance-evidence`
- artifact size: `155083 bytes`
- artifact digest: `sha256:e8a418325420ae8b808ca3f8431a40c551106309e2a080adb780854d463030ca`

The plan artifact was also emitted as artifact `10447888298`, digest `sha256:e59318832e84c019a8b7e16dff22559e0e43383b509dbd0de2c0a10be3fe5ef5`.

## Acceptance statement

T2 is eligible for acceptance only after a fresh closing-verification run proves this verification document is the only closing delta above implementation head `a10d05455c90181a02d4a903774e1e9b777d6b74`, reruns the 13 focused contracts, validates the accepted manifest/aggregation evidence and Governance/strict authority, confirms protected invariants, and fresh-reads production at the locked SHA without mutation.

No production integration is authorized by this document. After closing verification is GREEN, T3/#307 must start from the exact accepted T2 closing head and handle real Tk/Xvfb sharding separately.

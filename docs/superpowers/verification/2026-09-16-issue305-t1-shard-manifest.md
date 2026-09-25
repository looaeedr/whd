---
whd_doc_role: CURRENT
whd_contract: issue305-t1-shard-manifest-verification
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #305 T1 — Deterministic Shard Manifest Engine Verification

Date: 2026-09-16 (Asia/Taipei)
Parent: #303
Task: #305 / T1
Exact predecessor: `d31d68420718b3e612e469a0a856d9bcf202d527` (#304 accepted)
Implementation head: `08ca3ba57d9066171aea4491e48cb71d257da66a`
Production reference at closing start: `cleanup/2d-3d-sync @ 2bbf59fbb2ff2e79c67d9817964d3ff6213b2228`

## Scope delivered

T1 adds metadata/tooling only:

- `config/ci_test_shards.json` — single authoritative logical shard-count configuration.
- `tools/test_shard_manifest.py` — canonical node-id normalization, SHA-256 HRW/Rendezvous ownership, manifest generation, reconciliation and CLI.
- `tests/test_issue305_shard_manifest.py` — deterministic ownership, bounded-remap, fail-closed reconciliation and byte-stability contracts.
- `docs/superpowers/plans/2026-09-16-issue305-t1-shard-manifest.md` — implementation plan.

No production geometry/UI/persistence/DXF behavior changed. T1 does not enable matrix execution, xdist, caching, or parallel test execution.

## TDD RED

Focused RED workflow:

- RUN: `35096004421`
- QA head: `e266f25642682b46ea36518c83f6953caa0fdff9`
- Preflight: GREEN
- Expected RED: `ModuleNotFoundError: No module named 'tools.test_shard_manifest'`
- Pytest result: collection error, rc=2

This is the required pre-implementation RED proving the contracts existed before the manifest engine.

## Focused GREEN

Focused GREEN workflow:

- RUN: `35096238799`
- QA head: `53f711573cf9cdd62e220faa32b00f92d3252cc8`
- Focused contracts: `11 passed in 0.07s`
- Preflight: GREEN
- Workflow conclusion: SUCCESS

The contracts prove:

- path-only canonical node-id normalization;
- fixed `sha256-hrw-v1` framing;
- shard-order-independent ownership;
- adding a new shard only moves changed nodes to that new shard;
- adding unrelated tests does not remap existing nodes;
- stable fail-closed reason tokens for missing/extra/duplicate ownership;
- byte-identical manifests and digests for logically identical inputs.

## Live manifest acceptance

Acceptance workflow:

- RUN: `35096405962`
- Job: `104794727507`
- QA head: `55284c903d07c6e1b349d8c6260d094329e7dd88`
- Implementation SHA locked by workflow: `08ca3ba57d9066171aea4491e48cb71d257da66a`
- QA delta: workflow-only
- Workflow conclusion: SUCCESS

Live collection/reconciliation:

- full collection: `2164`
- lane union: `2164`
- unique shard union: `2164`
- lane missing: `0`
- lane extra: `0`
- lane duplicate: `0`
- shard missing: `0`
- shard extra: `0`
- shard duplicate: `0`

The increase from the #304 historical baseline 2153 to 2164 is exactly the 11 new T1 contract tests. Production tooling does not hard-code 2153; runtime inventory comes from live pytest collection.

Repeatability:

- independent run A and run B manifests were byte-for-byte identical;
- `ISSUE305_MANIFEST_REPEATABILITY=BYTE_IDENTICAL`.

Digests:

- config SHA-256: `59fb472d2bde2959f72ee4467985cd72f2da1ea788afa609d3aedd7c253e8766`
- full collection SHA-256: `7669221adca0b5ac13b5793f48fbcadd38adaa2ba51e0fffade839229cb86d23`
- lane manifest SHA-256: `6020cfc899fdf9bbeb5fe9a9b739c51c44463255ffb8cd9fd284e010b89dcdd3`
- shard manifest SHA-256: `fe480dc973ffd252cdddecc1c6a68a6765d94fd13d35c474bb296a19f87e4d1c`

Artifact:

- artifact id: `10445714092`
- artifact name: `issue305-t1-manifest-evidence`
- artifact digest: `sha256:3d2ed87063b79b4c79787383ad493399348e49fd4141bd0e7e7cdbd1b35231eb`

## Governance and protected invariants

Live acceptance proved:

- Governance: `191 passed / 1973 deselected`
- strict governance: `GREEN governed=425`
- `config.ini` SHA-256 before/after identical: `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`
- tracked DXF count: `10`
- DXF manifest SHA-256 before/after identical: `3d6bbd29e84cece743300535cff83f9d2edfb06e4ad56ba822991c48ac1e83e9`
- tracked tree invariant: GREEN
- `ISSUE305_PROTECTED_INVARIANTS=GREEN`
- final fail-closed gate: `ISSUE305_T1_MANIFEST_ACCEPTANCE=GREEN`

## Acceptance statement

T1 is eligible for acceptance only after a fresh closing-verification run proves that this evidence commit is an evidence-only descendant of the implementation head, focused contracts and governance remain GREEN, accepted manifest evidence is reproducible, production is fresh-read without mutation, and protected invariants remain unchanged.

No production integration is authorized by this document. T2 must branch from the exact accepted T1 closing head after closing verification is GREEN.

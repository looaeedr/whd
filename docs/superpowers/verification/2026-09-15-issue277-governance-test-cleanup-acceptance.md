---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue 277 / T2 Governance TEST Cleanup Acceptance

- Date: 2026-09-15
- Master: #274
- Task: #277 / T2
- Exact parent: `a6f0eaae87c4a4aa7dea8c55feaaee1dafbf21f6`
- Exact tested head: `010b80c9e277d440dd22343823ff0578c52fba4a`
- Acceptance run: `34983681537`
- Acceptance conclusion: `SUCCESS`

## TDD / migration evidence

- Exact-parent stale semantic-doc contract was reconfirmed RED before acceptance.
- The obsolete oracle was the free-text `CURRENT` requirement around `ENDCAP_TOP_OVERLAY_STANDARD_V1@3` in reference/historical material.
- `AI_HANDOFF.md` remains `REFERENCE / handoff-ledger`.
- `CONTEXT.md` remains `REFERENCE / project-reference`.
- The global pitfall ledger remains reference material rather than runtime/domain authority.
- `phase6-dimension-semantics` is resolved through the Canonical Authority Map to the unique CURRENT owner `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`.
- Existing dimension/overlay/fixture semantic coverage was preserved, but it now validates the canonical owner instead of promoting handoff/reference prose to authority.

## GREEN evidence

- `tests/test_phase6_semantic_doc_status.py`: **8 passed**.
- `tests/knowledge/test_issue233_strict_metadata_migration.py`: **6 passed**.
- Full governance lane: **191 passed / 1952 deselected**.
- Durable `tests/process/**` governance coverage remained collected and passed its coverage gate.
- Outcome-control drift: `0` new skip / skipif / xfail weakening.
- `config.ini` / DXF protected before-after manifest diff: empty.

## Metadata debt repaired

Four governed Markdown files encountered by strict validation were brought under `WHD_DOC_META_V1` without changing their substantive requirements:

- T0 inventory verification record → `HISTORICAL / verification-provenance`.
- T1 taxonomy acceptance record → `HISTORICAL / verification-provenance`.
- T2 implementation plan → `HISTORICAL / implementation-plan-provenance`.
- X independent-chain governance spec → `CURRENT / x-independent-task-chain-governance`.

## Safety / scope

- Production source drift: **0**.
- Geometry authority changes: **0**.
- DXF authority changes: **0**.
- UI behavior changes: **0**.
- Runtime physical-part identity changes: **0**.
- Test outcome controls were not weakened.

## Parallel-chain rule

T2 is one member of the T2/T3/T4 parallel group. Its closing HEAD is **not** the parent of #278 or #279. Both sibling tasks continue to use the common accepted T1 parent:

`a6f0eaae87c4a4aa7dea8c55feaaee1dafbf21f6`

Only after T2, T3 and T4 are all accepted may #280 / T5 reconcile their independent accepted heads.

## Result

`ISSUE277_T2_GOVERNANCE_ACCEPTED=1`

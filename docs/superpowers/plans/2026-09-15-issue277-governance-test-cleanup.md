---
whd_doc_role: HISTORICAL
whd_contract: implementation-plan-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue 277 Governance TEST Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace stale free-text documentation authority assertions with structured WHD governance metadata / canonical-authority contracts while preserving all durable process coverage.

**Architecture:** Keep production untouched. The semantic-doc test becomes a governance test that consumes `tools/knowledge_governance.py` and the Canonical Authority Map rather than treating prose markers, historical fixture dimensions, or the literal word `CURRENT` as authority. Existing `tests/knowledge/**` and `tests/process/**` remain permanent governance coverage.

**Tech Stack:** Python 3.12, pytest, `WHD_DOC_META_V1`, `tools/knowledge_governance.py`, GitHub Actions.

**Spec:** `WHD_TEST_CLEANUP_SPEC_2026-09-15.md` and issue #277.

## Global Constraints

- Fresh branch from `a6f0eaae87c4a4aa7dea8c55feaaee1dafbf21f6` only.
- Tests are judges, never runtime / geometry / dimension / DXF / identity authority.
- No production geometry, UI, DXF, physical-part identity, or canonical domain rule changes.
- No skip/xfail to hide reds.
- Any retired assertion requires explicit structured-authority replacement evidence.

---

### Task 1: Prove inherited semantic-doc RED

**Files:**
- Read: `tests/test_phase6_semantic_doc_status.py`
- QA only: temporary issue277 workflow

- [ ] Run the stale semantic-doc test on the exact T2 parent.
- [ ] Verify the known first test fails because `AI_HANDOFF.md` is `REFERENCE` and the V1@3 occurrence is historical/superseded, not because of import/environment errors.
- [ ] Preserve the failure log as migration evidence.

### Task 2: Replace prose authority with structured governance authority

**Files:**
- Modify: `tests/test_phase6_semantic_doc_status.py`
- Read/consume: `tools/knowledge_governance.py`
- Read/consume: `個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md`

- [ ] Mark the module as governance coverage.
- [ ] Assert `AI_HANDOFF.md` metadata is `REFERENCE / handoff-ledger`.
- [ ] Assert `CONTEXT.md` metadata is `REFERENCE / project-reference`.
- [ ] Assert Canonical Authority Map metadata is valid `WHD_DOC_META_V1` and is a CURRENT governed document.
- [ ] Assert the machine-readable `phase6-dimension-semantics` CURRENT row points to `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`.
- [ ] Keep only historical/fixture assertions that verify a document is explicitly non-authoritative; do not use fixture values as current truth.

### Task 3: Governance lane regression

**Files:**
- Existing: `tests/knowledge/**`
- Existing: `tests/process/**`
- Existing: T1 taxonomy policy

- [ ] Run `pytest -m governance` and require GREEN.
- [ ] Run strict metadata / canonical authority permanent tests explicitly.
- [ ] Confirm durable process tests remain collected in governance lane.
- [ ] Confirm no new skip/skipif/xfail controls.

### Task 4: Closing acceptance

- [ ] Capture config.ini / DXF manifests before and after.
- [ ] Confirm parent→candidate production source drift = 0.
- [ ] Record terminal run identity + head SHA.
- [ ] Remove temporary workflow/scratch artifacts.
- [ ] Add permanent verification record.
- [ ] Non-force fast-forward the Master work-order branch only after all gates are GREEN.

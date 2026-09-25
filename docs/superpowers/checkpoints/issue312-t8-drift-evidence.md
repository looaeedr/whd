---
whd_doc_role: REFERENCE
whd_contract: issue312-t8-drift-evidence
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue 312 / T8 Production Drift + Integration Shape Evidence

Date: 2026-09-17 (Asia/Taipei)

## Locked identities

- Production branch: `cleanup/2d-3d-sync`
- Fresh production HEAD: `8ccf1a9404a641ed892ab63e6f2c0e01ee80d6d9`
- Accepted T7 tested SHA: `db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f`
- Common merge-base: `a632d1158ba49364b1962a0ed27f4b4109ea4b85`
- T8 orchestration branch remains separate and does not change either tested or production identity.

## Fresh compare

`production...accepted-T7` is `diverged`.

- Accepted T7 side: 94 commits after the merge-base.
- Production side: 78 commits after the merge-base.
- Exact changed-path intersection between `merge-base..accepted-T7` and `merge-base..production`: **0 paths**.
- Accepted T7 side changes are additive CI sharding / QA / tests / evidence / CI configuration from the shared base.
- Production side changes are continuity / closure / task-chain governance, process tests, process tooling, skills, and AI-library governance from the shared base.
- No application production geometry/UI source path is modified on both sides.

## Conservative classifier note

`tools/issue312_t8_drift_audit.py` is intentionally fail-closed. Only the committed explicit CI/evidence prefixes return `CI_OR_EVIDENCE`; every unmatched path returns `PRODUCTION_SOURCE`. Therefore some CI-specific configuration or older T0 helper paths that are outside those prefixes are conservatively marked `PRODUCTION_SOURCE` for manual review rather than silently whitelisted. This classifier result does not broaden authority or mutate either branch.

## Exact integration shape

The qualified integration shape is **not** a fast-forward of accepted T7 onto production.

Required shape after explicit user authorization `合`:

1. Re-read `cleanup/2d-3d-sync` and require it is still exactly `8ccf1a9404a641ed892ab63e6f2c0e01ee80d6d9`; if it moved, this evidence is stale and a fresh audit is mandatory.
2. Use current production as the first-parent integration base.
3. Integrate the accepted CI chain represented by `db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f` as the second parent / incoming chain; do not force-update production to the T7 SHA.
4. Preserve production-only governance/process changes and accepted-chain CI sharding changes. The fresh audit found zero exact changed-path overlap from the common merge-base.
5. Do not include T8 orchestration-only commits as if they were part of the accepted tested chain unless a separate acceptance explicitly qualifies them.
6. Production mutation remains forbidden until explicit `合`.

## Qualification decision

- `drift_audit_complete`: **true**
- `production_mutated`: **false**
- `integration_shape_qualified`: **true**
- `fast_forward_allowed`: **false**
- `explicit_merge_authorization_present`: **false**
- Current state: **QUALIFIED SHAPE / NOT MERGED**

This evidence qualifies the deterministic integration shape only. It does not itself authorize or perform production integration.

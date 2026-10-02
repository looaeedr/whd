---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #282 T7 Combined Acceptance / Final Drift / Integration Qualification

Date: 2026-09-16 (Asia/Taipei)
Parent: #274
Predecessor: #281

## Exact authority

- Frozen production baseline for the TEST Cleanup chain: `269a2972f0f88ffc7085ee3f1483a57145d8b2e8`
- T6 accepted / T7 tested candidate: `ad1aedc12ca00f458df4dda5854c29f243ce6e90`
- Live production observed during final qualification: `cleanup/2d-3d-sync @ d72e81b5820b9cb54008a2dda9e96cdc673a9734`
- Combined acceptance RUN: `35069029443 @ cd04fb62cbf361c309189d39186d6714e4c883a1` — SUCCESS
- Final exact live-production RED A/B qualification RUN: `35077647680 @ 4d14a20c29e09216109df73be6e87a61eabb0936` — SUCCESS
- Earlier qualification harness runs `35069138735`, `35069373518`, and `35070808313` are diagnostic evidence only; their harness/classifier defects were corrected without changing production or the T7 candidate.

## Combined acceptance

RUN `35069029443` collected the complete test set and lane union:

- full collection: `2153`
- lane union: `2153`
- missing from union: `0`
- extra in union: `0`
- Governance: `191 PASS / 0 FAIL`
- Unit: `77 PASS / 2 SKIP / 0 FAIL`
- Geometry: `499 PASS / 51 SKIP / 0 FAIL`
- Projection: `95 PASS / 1 SKIP / 0 FAIL`
- Persistence: `31 PASS / 9 SKIP / 0 FAIL`
- DXF: `15 PASS / 0 FAIL`
- Architecture: `8 PASS / 2 SKIP / 0 FAIL`
- UI Headless: `133 PASS / 90 SKIP / 0 FAIL`
- Integration: `727 PASS / 109 SKIP / 0 FAIL`
- Xvfb UI: `100 PASS / 13 FAIL`

The migration / replacement audit ran `14 PASS / 0 FAIL`. Protected `config.ini` and DXF hash manifests were identical before/after validation. The QA-only diff for the combined runner contained only `.github/workflows/issue282-combined-acceptance.yml`; no QA workflow was part of the tested candidate tree.

## Xvfb inherited RED

The exact 13 Xvfb failures are the same historical GUI baseline nodes classified in #281. Final live-production A/B RUN `35077647680` proved:

- `XVFB_EXACT_FAILED_NODE_MATCH=GREEN count=13`
- `XVFB_EXACT_FAILURE_SIGNATURE_MATCH=GREEN count=13`
- `XVFB_RED_CLASSIFICATION=LIVE_PRODUCTION_INHERITED_BASELINE_RED`
- `NEW_MERGED_RED=0`

No production behavior, geometry, dimensions, DXF authority, project schema, or physical-part identity was changed to make those contracts green.

## Live-production drift and synthetic merge qualification

At final qualification, production and the TEST Cleanup chain had diverged from the frozen baseline:

- merge base: `269a2972f0f88ffc7085ee3f1483a57145d8b2e8`
- TEST Cleanup candidate side: `59` commits ahead of the merge base
- live production side: `56` commits ahead of the merge base
- candidate and production were therefore not eligible for direct fast-forward integration.

An isolated two-parent synthetic merge of live production `d72e81b5820b9cb54008a2dda9e96cdc673a9734` with candidate `ad1aedc12ca00f458df4dda5854c29f243ce6e90` completed with zero conflicts. The synthetic merge retained complete `2153/2153` taxonomy collection and protected config/DXF invariants.

The merged tree introduced no new test RED. Its only non-Xvfb RED was the same four governance test nodes already RED on live production. Exact A/B showed the underlying governance debt improved monotonically:

- live production governance metadata debt count: `2`
- synthetic merge governance metadata debt count: `1`
- remaining common debt: `docs/governance/issue263-t0-inventory.md`
- debt removed by the TEST Cleanup chain: `個人AI檔案庫/第二層_專案與SOP/09_X第二主分支與獨立工單鏈治理規格.md`
- `MERGED_GOVERNANCE_DEBT_STRICT_SUBSET_OF_PRODUCTION=GREEN`
- `GOVERNANCE_RED_CLASSIFICATION=LIVE_PRODUCTION_INHERITED_WITH_MONOTONIC_IMPROVEMENT`

RUN `35077647680` sealed:

- `GOVERNANCE_EXACT_FAILED_NODE_MATCH=GREEN count=4`
- `XVFB_EXACT_FAILED_NODE_MATCH=GREEN count=13`
- `MERGED_CONFIG_DXF_INVARIANTS=GREEN`
- `NEW_MERGED_RED=0`
- `INTEGRATION_RECOMMENDATION=QUALIFIED`
- `NO_PRODUCTION_REF_MUTATION=GREEN`

`QUALIFIED` means the TEST Cleanup chain can be integrated by an explicit later non-force integration operation. It does not authorize or perform that production merge.

## Final changed-file manifest versus frozen chain baseline

`269a2972f0f88ffc7085ee3f1483a57145d8b2e8...ad1aedc12ca00f458df4dda5854c29f243ce6e90` is `59` commits ahead and changes exactly these 34 paths:

1. `docs/plans/2026-09-15-test-cleanup-t4-acceptance.md`
2. `docs/plans/2026-09-15-test-cleanup-t4-gui-characterization-retirement.md`
3. `docs/superpowers/plans/2026-09-15-issue277-governance-test-cleanup.md`
4. `docs/superpowers/plans/2026-09-15-issue278-box-body-identity-test-cleanup.md`
5. `docs/superpowers/plans/2026-09-15-issue280-permanent-test-reconciliation-and-move.md`
6. `docs/superpowers/verification/2026-09-15-issue275-test-inventory-manifest.json`
7. `docs/superpowers/verification/2026-09-15-issue275-test-inventory.csv.gz`
8. `docs/superpowers/verification/2026-09-15-issue275-test-inventory.md`
9. `docs/superpowers/verification/2026-09-15-issue276-pytest-taxonomy-acceptance.md`
10. `docs/superpowers/verification/2026-09-15-issue277-governance-test-cleanup-acceptance.md`
11. `docs/superpowers/verification/2026-09-15-issue278-box-body-identity-test-cleanup-acceptance.md`
12. `docs/superpowers/verification/2026-09-15-issue280-reconciliation-audit.md`
13. `docs/superpowers/verification/2026-09-15-issue280-test-move-manifest.md`
14. `docs/superpowers/verification/2026-09-16-issue280-permanent-test-move-acceptance.md`
15. `docs/superpowers/verification/2026-09-16-issue280-post-move-preflight-evidence.md`
16. `docs/superpowers/verification/2026-09-16-issue281-full-lane-preflight-evidence.md`
17. `docs/superpowers/verification/2026-09-16-issue281-t6-full-lane-classification.md`
18. `pytest.ini`
19. `tests/architecture/test_box_body_single_source.py` (renamed from `tests/test_box_body_single_source_t3.py`, with contract edits)
20. `tests/architecture/test_project_actions_ownership.py` (renamed from `tests/test_issue210_project_actions_move_contract.py`)
21. `tests/architecture/test_renderer_ownership.py`
22. `tests/conftest.py`
23. `tests/governance/test_semantic_doc_status.py`
24. `tests/projection/test_part_panel_projection.py` (renamed from `tests/test_issue209_part_panel_projection.py`)
25. `tests/projection/test_renderer_behavior.py` (renamed/retired from `tests/test_issue211_renderer_dependency_gate.py`)
26. `tests/test_issue276_test_taxonomy_contract.py`
27. `tests/test_issue280_taxonomy_relocation_safety.py`
28. `tests/test_phase6_semantic_doc_status.py` (removed)
29. `tests/ui/test_box_body_physical_child_navigation.py` (renamed from `tests/test_issue76_box_body_subtabs_2d_3d.py`, with contract edits)
30. `tests/ui/test_gui_drawing_contract.py` (renamed from `tests/test_issue206_gui_modularization_characterization.py`, with characterization retirement edits)
31. `tests/ui/test_gui_toolbar_contract.py`
32. `tools/test_lane_audit.py`
33. `tools/test_lane_policy.py`
34. `個人AI檔案庫/第二層_專案與SOP/09_X第二主分支與獨立工單鏈治理規格.md`

This T7 verification record is the only additional closing-tree path after the fully tested `ad1aedc...` candidate.

## Closing rule

Before #282 / #274 are closed:

1. advance the persistent work-order branch non-force to the closing head containing this record;
2. delete only TEST Cleanup temporary claim/task/QA refs after a live OPEN-PR head+base guard passes;
3. rerun post-cleanup collection/governance/invariant/readback checks on the exact accepted head;
4. fresh-read production and prove it remains unchanged;
5. do not merge `cleanup/2d-3d-sync` without explicit user authorization.

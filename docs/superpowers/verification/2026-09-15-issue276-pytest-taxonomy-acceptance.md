---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue 276 / T1 Pytest Taxonomy Acceptance

- Date: 2026-09-15
- Parent accepted head: `b5ae852e4aaa236413b0a1acaf097ffb5dbb2776`
- Tested head: `70fc5bf24e91aa91b884dc5aff578b0a680fdb31`
- Remote QA run: `34981248957`
- Remote QA conclusion: `SUCCESS`

## TDD evidence

- Requirement RED run: `34979789448`
- RED contract proved the taxonomy foundation was absent before implementation.
- CLI regression pre-fix commit: `fd682c61e8b346b242eff99aa8e379a32a169fd2`
- Replacement QA proved `test_lane_audit.py` failed there with `ModuleNotFoundError: No module named 'tools'`.
- Current-head taxonomy contract: `5 passed`.

## Collection evidence

- T0 parent collection: `2136` nodes.
- T1 candidate collection: `2141` nodes.
- New nodes: `5` T1 governance/contract tests.
- Lane-union count: `2141`.
- Missing from lane union: `0`.
- Extra in lane union: `0`.

Lane counts from the terminal artifact:

- governance: 183
- unit: 79
- geometry: 550
- projection: 93
- persistence: 40
- dxf: 15
- architecture: 11
- ui headless: 222
- xvfb ui: 115
- integration: 833

Lane counts are overlapping reporting counts where secondary marker selection applies; acceptance is based on exact union equality, not summed totals.

## Safety / invariants

- `pytest.ini` registers the required taxonomy markers plus transitional `requires_tk_display`.
- Lane policy only adds classification markers; it does not add skip/skipif/xfail or redefine expected behavior.
- `OUTCOME_CONTROL_DRIFT=0`.
- `config.ini` / DXF protected manifest diff: `0 bytes`.
- Production source / geometry / schema authority was not changed by T1.
- Temporary T1 QA workflow and preflight scratch evidence are removed in the closing commit; this file is the permanent acceptance record.

## Result

`ISSUE276_T1_TAXONOMY_QA=GREEN`

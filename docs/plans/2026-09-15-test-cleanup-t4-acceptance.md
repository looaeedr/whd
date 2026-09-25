---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# TEST Cleanup T4 — Final Acceptance / Retirement Record

Issue: #279
Master: #274
Date: 2026-09-15
Status: ACCEPTED

## Lineage

- Authoritative T1 sibling base: `a6f0eaae87c4a4aa7dea8c55feaaee1dafbf21f6`
- T4 tested candidate: `84ae70954967b476227f7e11bcbcf15624e8e013`
- T2 accepted sibling: `eb967e92c951cec8fde9c76d171a9685232a3ea2`
- T3 accepted sibling: `e1d484c247af5b7f384a8883d31357efb7820049`
- T4 remained an independent sibling from the common T1 base; T2/T3 were not ancestors of the T4 candidate.

## Retirement decision

`tests/test_issue206_gui_modularization_characterization.py` was a migration-era characterization suite created to freeze behavior during the first GUI modularization extraction wave. It is retired only after permanent successor coverage was established and independently proven equivalent for the durable behavior.

| Retired coverage | Permanent successor |
| --- | --- |
| corner preview canvas projection | `tests/test_gui_drawing_contract.py` |
| corner target flip matrix | `tests/test_gui_drawing_contract.py` |
| exact toolbar whole-dictionary snapshot | `tests/test_gui_toolbar_contract.py` semantic toolbar contract |
| monolithic `render_drawing_scene` canvas-call snapshot | `tests/test_gui_drawing_contract.py` semantic rendering contract |

Permanent #210 and #211 architecture/render-boundary contracts remain intact and were re-run during both replacement proof and final acceptance.

## Replacement proof before retirement

QA head: `8fd68802295239f7ed1aa83f90809d83494f3b92`
Run: `34990283992`, attempt 2 — SUCCESS
Artifact: `10405596679`

Evidence:

- old #206 characterization and permanent successors coexisted;
- focused suite including #206 + successors + #210/#211: **36 PASS / 0 FAIL**;
- taxonomy responsibility GREEN;
- no skip/xfail outcome masking;
- `PRODUCTION_SOURCE_DRIFT=0`;
- `config.ini` / DXF invariants GREEN;
- fail-closed Skill/reference preflight GREEN.

## Final post-retirement acceptance

Final QA head: `2c48b6b789f7cec21eb9053a2951c09f98c9460d`
Run: `34990686579`, attempt 2 — SUCCESS
Artifact: `10404409746`

Evidence:

- exact candidate lock GREEN;
- migration-era #206 file absent;
- permanent successors present;
- exact candidate changed-file set GREEN;
- post-retirement focused suite (`test_gui_drawing_contract.py`, `test_gui_toolbar_contract.py`, #210, #211): **23 PASS / 0 FAIL**;
- taxonomy responsibility GREEN;
- no skip/xfail outcome masking;
- QA-only delta from candidate GREEN;
- `config.ini` / DXF invariants GREEN;
- final acceptance seal GREEN.

The only warning in the focused runs was the pre-existing `fold_designer_bridge.py:6169` invalid escape sequence warning; no T4 production file changed.

## Exact candidate scope

Relative to T1 base, the tested T4 candidate changed exactly these paths:

1. `docs/plans/2026-09-15-test-cleanup-t4-gui-characterization-retirement.md`
2. `tests/test_gui_drawing_contract.py`
3. `tests/test_gui_toolbar_contract.py`

No production/runtime geometry, DXF authority, persistence, schema, physical-part identity, renderer ownership, or project-state source was modified.

## Acceptance conclusion

T4 is accepted as TEST-governance cleanup. The migration characterization was not deleted to hide a failing test: replacement equivalence was proven first, then the retired file was removed, then the exact post-retirement candidate was revalidated.

The next stage is #280 / T5, which must explicitly reconcile the independently accepted T2/T3/T4 sibling heads before repository-wide permanent test rename/move/coverage consolidation. The shared T1 serial accepted head must not be advanced by pretending any one parallel sibling contains the others.

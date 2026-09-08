# DM4 Checkpoint

- task_id: DIVIDER-FW-DEEP-MODULE-V1
- work_order: #54
- branch: work/dm4-divider-resolved-sinks
- trusted_parent: 6da176c316523042a73e41883e532b7fb52a3123
- acceptance_tested_sha: adbb190db065fb36f2c77776639ccdbea63222bd
- final_verified_behavior: 41 passed / 0 failed
- config_sha256: 980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67
- source_ownership_scan: PASS
- compile: PASS

## Production change
`phase6_project_file.py`
- project writer strips derived top-level `final_geometry`.
- project reader ignores legacy persisted derived `final_geometry`.
- Reload therefore depends on authoritative state + canonical solve, not renderer/probe/final-material cache.

## Guards
`tests/test_dm4_divider_resolved_sinks.py`
- active Divider final query consumes resolved part render data.
- project write/read strips derived final geometry and probe-like values.

## Important architecture note
`gui._query_fold_designer_render_data` is an upstream nominal material producer required by the canonical solve. It must not be confused with the final 2D/3D/DXF sink.

## QA provenance
- false-seam A/B classification: 34235459293
- valid persistence RED: 34235910339
- focused GREEN: 34236190221
- final acceptance: 34238904268
- historical redundant T48-3 file cleanup commit: 1e206306ac38719c1c24df84fdb439b4d8846dab

## Cleanup
- DM4 one-shot workflows removed.
- no post-acceptance production change.

## Resume
DM4 is terminal GREEN. Next owning issue: #55.

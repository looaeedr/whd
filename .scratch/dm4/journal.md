# DM4 Journal

## 2026-09-08
- task_id: DIVIDER-FW-DEEP-MODULE-V1
- work_order: #54
- role: [當前角色：#54 實作者]
- repository: looaeedr/whd
- branch: work/dm4-divider-resolved-sinks
- parent: work/dm3-divider-canonical-relief@6da176c316523042a73e41883e532b7fb52a3123

## Preflight
- AGENTS.md read.
- Phase6 Knowledge Preflight required Skills/references read.
- Preflight route reproduced and GREEN before DM4 production/test write.

## Consumer trace
- single 3D: active Divider uses `_phase6_resolve_manufacturing_geometry(...).part(key).render_data`.
- assembly 3D: consumes the same resolved geometry bundle.
- DXF resolved sink: `save_resolved_manufacturing_geometry_dxf` serializes already-resolved `PartRenderData` only.
- final scene view contains no Divider/FW/relief recomputation.
- `gui._query_fold_designer_render_data` is an upstream nominal Divider producer for the canonical whole-cabinet solve, not a final sink.

## False seam investigation
- Initial RED `34234635069` treated the GUI nominal producer as a sink.
- A/B run `34235459293` proved the corresponding fail-closed production change caused the R1 live-family-switch regression: parent PASS, modified head FAIL.
- That production change was fully reverted.
- The incorrect guard was removed. This evidence is retained to prevent the same architectural misclassification.

## Valid RED / production fix
- Valid RED: run `34235910339` @ `6f3b002014bfc3bb17e96172b293ae72108be72f`
  - result: 1 passed / 1 failed.
  - failure: `phase6_project_file.write_project()` persisted derived top-level `final_geometry`.
- Production fix: `phase6_project_file.py`
  - writer forces `final_geometry = {}`.
  - reader discards legacy persisted derived `final_geometry`.
  - authoritative snapshot state remains the persistence source; Reload re-solves canonical geometry.

## Focused GREEN
- run `34236190221` @ `889d3e5ddbb111df28ce8628cfe4f6ed01d6f005`
- terminal: success.

## Final current-head acceptance
- run `34238904268` @ `adbb190db065fb36f2c77776639ccdbea63222bd`
- behavior: **41 passed / 0 failed**
- compile boundary: PASS
- source ownership scan: PASS
- config before: `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`
- config after:  `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`

## T48-3 provenance
- Historical `tests/test_issue48_final_geometry_sync.py` was intentionally removed by commit `1e206306ac38719c1c24df84fdb439b4d8846dab` with message `cleanup: remove redundant test_issue48_final_geometry_sync.py`.
- DM4 therefore verifies current durable replacement guards rather than resurrecting the removed historical file.

## Cleanup / drift
- one-shot DM4 workflows removed after terminal success.
- post-acceptance delta contains workflow cleanup only before final checkpoint/journal write.
- no post-acceptance production geometry/code change.

## Final status
- production delta from DM3 base: `phase6_project_file.py` only.
- test delta: `tests/test_dm4_divider_resolved_sinks.py`.
- blocked: none.
- next: close #54 and transfer to #55 Combined Acceptance / AI Library / skill writeback / integration.

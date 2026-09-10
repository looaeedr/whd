# Issue #93 T0 Baseline / Spec / Knowledge Gate Evidence

## Branch / target

- production target: `cleanup/2d-3d-sync`
- recorded target HEAD: `925808ab29009bff76670daf7dbbccc232e33b6b`
- implementation branch: `feat/corner-data-2d-entry-convergence-20260910`
- production code change in T0: `0`

## Required knowledge read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
READ_REFERENCE: release_required_artifacts.json

Required skills read/executed for this gate:

- `phase6-corner-3d-model-integrity`
- `驗證板件與DXF`
- `monitoring-remote-qa`
- `phase6-release-packaging` for planned skill/docs writeback

## Remote preflight / baseline evidence

### Run 1

- run_id: `34463630853`
- head_sha: `8f63b5892f22506a6c3af8701cbb32f5938e3ef4`
- conclusion: `success`
- task preflight: PASS
- baseline: `38 passed, 10 skipped, 1 warning`
- config.ini before/after: `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`

### Run 2 — changed-file preflight

- run_id: `34463739057`
- head_sha: `2075760f2c72e29eeb024d30b11c825eaff3eedc`
- conclusion: `success`
- task preflight: PASS
- planned changed-file preflight: PASS
- baseline: `38 passed, 10 skipped, 1 warning in 2.23s`
- config.ini before/after: `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`

## Baseline test scope

- `tests/test_issue45_dynamic_parts_2d_roundtrip.py`
- `tests/test_phase6_project_controller.py`
- `tests/test_phase6_project_file.py`
- `tests/test_phase6_project_ownership.py`
- `tests/test_phase6_project_session.py`
- `tests/test_dxf_acceptance.py`
- `tests/test_multipart_dxf_acceptance.py`
- `tests/test_resolved_manufacturing_export.py`
- `tests/test_resolved_manufacturing_geometry.py`

## Dependency inventory

Legacy `gui.py` still owns a top-level 2D Notebook and widget-bound navigation through:

- `self.notebook`
- `self.tab_z`
- `self.tab_head`
- `self.tab_tail`
- `self.tab_door`
- `self.tab_base_plate`
- stable key -> legacy tab selection -> `refresh_corner_type_panel()` / `draw_preview()`

Fold Designer already owns the reusable navigation/SSOT side:

- `part_selector` / `part_var` / `part_choice_menu`
- `designer_workspace.available_parts`
- `_phase6_operator_part_selector_keys`
- `_phase6_box_body_piece_keys`
- `_phase6_activate_operator_part`
- same resolved aggregate manufacturing result for physical BoxBody child render data
- assembly parts panel + topology refresh pattern

## T0 locked rules

- `截角資料` is a UI mode, never a manufacturing part.
- 3D and unfold use the same authoritative state/render data.
- stable part key is identity; labels are presentation only.
- stale selection must be dropped when the authoritative part disappears.
- multipart parent must resolve to remembered valid child or first authoritative child; never aggregate fake unfold.
- View lifecycle must not mutate manufacturing state.
- legacy removal is `connect -> parity -> delete`, never delete first.
- validation is an oracle only and cannot become a production input.

## Durable writeback

- `docs/superpowers/specs/2026-09-10-corner-data-2d-entry-convergence-spec.md`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md`
- `.agents/skills/engineering/截角資料入口收斂/SKILL.md`
- this verification checkpoint

T0 may transfer to T1 only after these files are remotely re-read from the implementation branch and the issue records the terminal run evidence above.

---
whd_doc_role: REFERENCE
whd_contract: issue478-t0-ownership-census
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #478 / Phase 4 T0 — Fresh Ownership Census

## Identity

- Master: #486
- Ticket: #478
- Production target: `cleanup/2d-3d-sync`
- Frozen X execution base: `02a58dfe1102db0d3a97ed04f12f5ec1286a68b9`
- Frozen Git tree: `d06054fc42802e24180efbe020413f4ce0bb8ee0`
- Work-order branch: `work/issue486-phase4-ownership-20260922`
- Preflight evidence commit: `2a694bfe9c6c876d1191c1b8c91efac1780b6b63`
- Bridge blob: `22335b2dd2c4421d76698423d36b0aa967f5f1d3`
- Bridge LOC: **8046**
- Top-level defs/classes: **340 = 335 functions + 5 classes**
- Requirement RED authority: user-approved Phase 4 v1.1, R1–R4.
- This ticket is census/evidence only: **no production/test behavior change is authorized**.

## Phase6 Knowledge Preflight

Canonical `tools/phase6_skill_preflight.py` was executed against the exact matched-route projection extracted from the canonical registry blob `4ed99227c91212fc06fe00074430975884b2e79a`; connector-side matching against the full exact registry produced the same route/Skill/reference set.

Matched routes:
- `dispatching-workflow`
- `phase6-corner-relief-3d`
- `part-dxf-acceptance`

Required Skills read:
- `派工`
- `issue-closure-gate`
- `phase6-corner-3d-model-integrity`
- `驗證板件與DXF`
- `monitoring-remote-qa`

Required references read:
- `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `基準檔/截角資料庫/README_母規則說明.md`
- `基準檔/截角資料庫/certified_relief_rules.json`
- `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`
- `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`

Initial preflight exit = 0. Planned-changed-files preflight exit = 0.

## R1 — FinalScene composition census

Bridge targets:

| Symbol | Lines | LOC | Bridge references |
|---|---:|---:|---|
| `_phase6_final_scene_visibility` | 701–709 | 9 | 701, 847 |
| `_phase6_final_scene_render_committed` | 710–728 | 19 | 710, 861 |
| `_phase6_final_scene_set_preview_enabled` | 729–744 | 16 | 729, 747, 864 |
| `_phase6_final_scene_refresh_preview` | 745–754 | 10 | 745, 867 |
| `_phase6_final_scene_adapter` | 755–873 | **119** | 755, 5335, 5405, 5421, 5426, 5430, 5434, 7910, 7960, 7964 |

`_phase6_final_scene_adapter` constructs all **35 / 35** `FinalSceneCompositionPorts` fields inline. Exact field identity parity with `gui_modules/application/fold_designer_adapter.py::FinalSceneCompositionPorts` was confirmed.

The existing application composition owner already contains:
- `Phase6FoldDesignerComposition.final_scene_renderer(...)`
- `Phase6FoldDesignerComposition.final_scene_adapter(...)`

Therefore T1's RED is specifically **application port wiring ownership**, not a missing FinalScene renderer/view owner.

Display-effect writes currently visible in bridge:
- `_phase6_final_scene_set_preview_enabled`: writes `self.preview_3d_enabled`
- `_phase6_final_scene_refresh_preview`: writes temporary `self._phase6_force_sync_preview`
- renderer / update-intent calls remain presentation/application effects; they are not manufacturing authority.

## R2 — Derived physical-part sync census

`_phase6_sync_authoritative_derived_parts`: lines **874–1074**, **201 LOC**, bridge references:
874, 1696, 2195, 6089, 7267, 7303.

Projection/derivation tokens present in the same function:
- `_phase6_door_part_projections`
- `derive_door_layout_cells`
- `divider_part_profiles`
- `_phase6_box_body_piece_part_profiles`
- `build_standard_part_profiles`

Navigation/workspace mutation calls present in the same function:
- `remove_part`
- `sync_derived_parts`
- `stash_features`
- `set_active_part`
- `set_selected_part`
- `add_part`
- `stash_profiles`

Total navigation call sites in this function: **16**.

This mechanically confirms R2: projection/planning and mutation are mixed in one bridge implementation. T2/T3 must separate planning from mutation without moving manufacturing formulas into the navigation/workspace owner.

## R3 — Linked Endcap ownership census

`_phase6_rebuild_linked_endcaps`: lines **1194–1271**, **78 LOC**, bridge references:
1194, 2883, 3141, 6088, 7315, 7390, 7882.

Observed owner seams:
- reads `self._phase6_input_snapshot`
- reads `self.designer_workspace`
- reads `self.state`
- calls existing fold-profile derivation `build_linked_endcap_xy_profiles`
- coordinates workspace profile stash/update

T3 must characterize this against the new Derived plan seam and choose exactly one approved decision:
- `DEEPEN_FOLD_PROFILES`
- `JOIN_DERIVED_PART_PLAN`
- `KEEP_COMPATIBILITY`

No decision is made by T0.

## R4 — Settings projection/glue census — EXACT 6

| Symbol | Lines | LOC | Bridge references |
|---|---:|---:|---|
| `_phase6_settings_endcap_fw_projection` | 3467–3481 | 15 | 3467, 3710 |
| `_phase6_settings_box_structure_projection` | 3482–3586 | **105** | 3482, 3706 |
| `_phase6_settings_bottom_wrap_projection` | 3587–3610 | 24 | 3587, 3714 |
| `_phase6_settings_corner_projection` | 3611–3701 | **91** | 3611, 3717 |
| `_phase6_settings_context_extension_projection` | 3702–3733 | 32 | 3702, 3781 |
| `_phase6_sync_settings_panel_extension` | 3734–3764 | 31 | 3734, 3792 |

The six-function scope is complete and matches Phase 4 v1.1.

Notable current behavior:
- projection functions are primarily read/projection seams;
- `_phase6_sync_settings_panel_extension` writes presentation/widget compatibility state including bottom-wrap variables, piece input hosts/sections/vars/entries, corner lock/status objects.
- T4 must run a deletion test and choose only:
  - `DEEPEN_EXISTING_SETTINGS_PANEL`
  - `EXTRACT_PURE_SETTINGS_PROJECTION`
  - `KEEP_BRIDGE_COMPATIBILITY`

T0 does not preselect one.

## Architecture / accepted-boundary baseline

- Root owner reverse-imports of `fold_designer_bridge`: **0**
  - `gui_modules/application/fold_designer_adapter.py`: 0
  - `phase6_final_scene_view.py`: 0
  - `phase6_settings_panel.py`: 0
  - `phase6_workspace_navigation_controller.py`: 0
  - `phase6_designer_workspace.py`: 0
  - `phase6_fold_profiles.py`: 0
- `install_fold_designer_bridge_facade` bindings: **69**
- `phase6_workspace_shell.py`: absent — preserves #447 `NO_EXTRACTION`
- `phase6_part_editor_session.py`: absent — preserves #448 `C_KEEP_BRIDGE_COMPATIBILITY`
- Existing #449 bootstrap-only test remains present and protected.

## Protected test baseline

| Test | Blob SHA |
|---|---|
| `tests/test_issue445_settings_presentation_owner.py` | `ba60c06b2a1b101cc28923de5cb385ce9aa78315` |
| `tests/test_issue447_workspace_shell_owner.py` | `bcf795b4a7bb99270b3f75ddcee4abc14a6b3076` |
| `tests/test_issue448_part_editor_owner_decision.py` | `3faa7e81b004a6cf2d487c0f1ff4dee97a735888` |
| `tests/test_issue449_fix11_init_bootstrap_owner.py` | `e8ebf0d11a853445b216ada66d51cf8769ed2f02` |
| `tests/test_phase6_designer_workspace.py` | `75a6caa3ff6ca1ee37f440c420dd645e50ade69c` |

These are test-oracle/protection evidence, not domain truth.

## Protected Git-object baseline

- `config.ini` blob: `3165d9f4192ac80fcfdca54fbbe7d1a22900a0d1`, size 983.
- DXF blobs: **10 files**.

| DXF path | Blob SHA |
|---|---|
| `基準檔/指示燈/123.dxf` | `f7486cd1fee6ff9b7aa3b1cf73565d6a6787f127` |
| `基準檔/指示燈/小門 - 複製.dxf` | `171406f2609032bf917fea62f0588e6d9d94c99b` |
| `基準檔/指示燈/小門.dxf` | `171406f2609032bf917fea62f0588e6d9d94c99b` |
| `基準檔/指示燈/盒子.dxf` | `195c710ab5e7700b1574f48191f9869fd9effa1e` |
| `基準檔/通用/19門.dxf` | `c9ffd7b7b528a04d89ec36fb66e07d7b61d05b9a` |
| `基準檔/金庫型/中隔.dxf` | `9d54945080e4780bf9c19d48b0d55e630a64968d` |
| `基準檔/金庫型/封頭尾.dxf` | `55da4e4bd607315eaad59a2e57f6e3eb1702d7f0` |
| `基準檔/金庫型/箱身.dxf` | `acdb2c800166d220de1fc38a78b4ba50f0efd825` |
| `基準檔/金庫型/門.dxf` | `ca65d3d8aa40746c2177ea5aa5df329bd0544751` |
| `基準檔/開孔/AS&VS.dxf` | `cb60c770999f72ba2c8b62b6b987d53fe44ff7d2` |

## Zero-behavior-change evidence before census commit

Compare `02a58dfe… → 2a694bfe…`:
- ahead by 1
- changed files exactly one:
  - `logs/preflight/issue478-t0-preflight.txt` (added)
- production files changed: **0**
- test files changed: **0**
- Skill files changed: **0**
- DXF/config changed: **0**

## T0 handoff contract

T1 may rely on this frozen census but must not treat current LOC, current call counts, tests, or fixture data as product/manufacturing authority.

T1's exact first target is R1:
- deepen the existing `Phase6FoldDesignerComposition`;
- remove deep inline `FinalSceneCompositionPorts(...)` construction from bridge;
- do not create a second FinalScene owner;
- maintain G1–G4 and the 69-binding ratchet.

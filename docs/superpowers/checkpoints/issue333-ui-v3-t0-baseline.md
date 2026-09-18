# #333 / T0 — UI v3 baseline / authority inventory

## Run identity

- Parent: #332
- Task: #333
- Production target: `cleanup/2d-3d-sync`
- Production HEAD at branch cut: `d88bf904317fb16744bfc644bb89ff7b405c435e`
- Fresh branch: `ui/issue333-v3-baseline-20260918`
- Rule: T0 is characterization only. No production UI implementation is changed here.

## Authority inventory

| Surface | Current production owner / route | Authority rule preserved for T1–T9 |
|---|---|---|
| File toolbar | `fold_designer_bridge._phase6_build_project_toolbar` under `top_command_row` | Presentation only; open/save/save-as keep current callbacks |
| DXF / STOCK output | `_phase6_build_output_controls`; DXF delegates `_phase6_export_selected_dxf_callback`; STOCK stages existing `draw_stock` setting | Layout may move; callbacks/state owners may not |
| 3D display controls | `_phase6_build_visual_controls`; text-size uses existing `ui_text_size_var` / settings panel lifecycle | No second display/text-scale state |
| Global settings | `Phase6SettingsPanel.build_left_global_controls` mounted through `right_global_host`; structural controls added by `_phase6_build_global_persistent_controls` | Existing settings service/panel remains state owner |
| Sheet-metal selector | `part_choice_button/menu` projects `part_var`; selection resolves through `_phase6_activate_operator_part` / DM7 navigation and `designer_workspace` | Menu and Structure Tree remain projections of the same workspace authority |
| Add / remove | Visible `add_part_menu` calls existing `add_part`; delete calls `remove_selected_part`; physical identity remains in `designer_workspace.available_parts` | Reposition only; do not duplicate part-presence state |
| Workspace content modes | Assembly via `_phase6_show_assembly`; Corner Data via `_phase6_show_corner_data`; real part editor via `activate_part` | Switching is presentation/navigation only |
| Structure Tree | Built from authoritative available parts and DM7 navigation projection; uses existing view-state vars | No second active-part/visibility owner |
| Renderer viewport | Existing `renderer.canvas.get_tk_widget()` installed by the Fold Designer renderer path | Layout may reclaim pixels; renderer/geometry authority is immutable |
| Theme | `whd_theme.WHD_THEME`, `WHD_SEMANTIC_COLORS`, `apply_ttk_dark_theme`, `configure_tk_menu` | Shared token/provider remains the only palette authority |
| Menu / popup presentation | Existing classic `tk.Menu` instances in Fold Designer / GUI; shared adapter already exists in `whd_theme.configure_tk_menu` | T1 may apply adapter only; commands/state stay untouched |
| Keyboard / focus | Existing local bindings include Delete and editor/popup lifecycle bindings; no Fold Designer Ctrl+S/Ctrl+O binding is present at this baseline | T7 must route new shortcuts to existing authoritative actions |

## Confirmed v3 RED at baseline

Current production still creates:

- `output_controls_frame = ttk.LabelFrame(..., text="輸出")` under `right_controls_host`.
- `_phase6_build_output_controls(self)` after the right-side visual/global control construction.
- the top command row currently builds the project toolbar, while output remains a separate right-side surface.

This is a direct, source-observable mismatch with v3: file + output must share one top row and the second full Output section must disappear. The characterization RED therefore tests this gap without changing production layout.

## Protected invariant baseline

### Repository / config

- production commit: `d88bf904317fb16744bfc644bb89ff7b405c435e`
- `config.ini` blob: `3165d9f4192ac80fcfdca54fbbe7d1a22900a0d1`

### Baseline DXF blobs

| Path | Blob SHA |
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

### Authority-owner blobs at branch cut

| Owner | Blob SHA |
|---|---|
| `phase6_designer_workspace.py` | `b403cb4780ff328ff96bdac4f8cb2b06dfbcb4fd` |
| `phase6_workspace_controller.py` | `64ac0f200621510543442b6a3354c68652f4468a` |
| `phase6_project_file.py` | `8647529718f4a9c0d042c8cc20abc9ad3e57e7f9` |
| `phase6_final_scene_view.py` | `5047f8c3e6b5c1e9c63f01c22bf436f29675bc20` |
| `phase6_settings_panel.py` | `5cca99d9131320b2db6213c16b615700babda718` |
| `whd_theme.py` | `72b3c96628ef48a79f9b2142ddd987021a7b3f91` |
| `fold_designer_bridge.py` | `c72aa40f9ceffb910ad2a026dd5e7de824f8387e` |

These SHAs are a T0 baseline, not a mandate that presentation files can never change. T1–T7 may change presentation owners where their tickets allow it; config/DXF and domain-authority semantics remain protected.

## T0 acceptance

T0 is accepted only when:

1. characterization suite has exactly the intended v3 layout RED and authority guards stay GREEN;
2. branch diff contains no production implementation change;
3. protected baseline above is recorded and traceable;
4. the RED is not reinterpreted as permission to change geometry, persistence, selector authority, renderer authority, or schema.

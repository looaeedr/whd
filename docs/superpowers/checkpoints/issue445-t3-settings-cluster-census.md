# Issue #445 / T3 — Settings presentation live-cluster census

- Master: #441
- Issue: #445
- Authoritative predecessor: `29b47853e21582a8533cda79a1a381a04a5571f3` (#444 accepted HEAD)
- Work branch: `refactor/issue445-t3-settings-owner-20260921`
- Bridge Git blob: `dfc2b4ed6a8734120c4ab3d7f8707d16ebf22873`
- Existing Settings owner blob: `phase6_settings_panel.py@099cb67c38546a2aa03d4c70a3a90e11652f3089`
- T0 census baseline: facade bindings = 69
- Local clean-checkout attempt: BLOCKED by runtime DNS (`Could not resolve host: github.com`); inventory below was therefore performed against exact GitHub Git objects via connector, not dirty worktree bytes.

## Selected live cluster manifest

The selected seam is **Tk presentation construction only**, currently implemented in the bridge and already entered through the existing `Phase6SettingsPanel.render_context_extensions` extension seam:

1. `_phase6_build_endcap_fw_settings`
2. `_phase6_build_box_structure_settings`
3. `_phase6_build_endcap_joint_settings`
4. `_phase6_build_receiving_bottom_wrap_settings`
5. `_phase6_build_corner_settings`
6. orchestration seam: `_phase6_render_settings_panel_extensions`

Why this is live:
- each builder constructs visible `ttk` Frames / Labels / Entries / Checkbuttons / Menubuttons;
- `_phase6_render_settings_panel_extensions` is passed into the already-canonical `Phase6SettingsPanel` as `render_context_extensions`;
- the bridge still owns those concrete widget builders even though the panel owns the settings page/container lifecycle.

## Existing owner to deepen

`phase6_settings_panel.py::Phase6SettingsPanel`

The existing owner already owns:
- Settings center / scroll host / settings fields;
- generic SettingSpec widgets;
- page cache and settings context;
- baseline/advanced presentation;
- callback-only mutation seams.

T3 must deepen this existing owner. **No new competing Settings panel/module is allowed.**

## Explicit exclusions / mutation boundary

Do **not** move canonical mutation/state ownership into the presentation owner. The following remain bridge/service/domain callbacks or delegates:
- `_phase6_settings_transactions` and all transaction commits;
- `_phase6_set_endcap_fw_follow`, `_phase6_set_endcap_fw_override`;
- box-structure mutation/commit helpers;
- AssemblyJoint mutation helpers;
- receiving bottom-wrap canonical commits;
- corner transaction/state mutation;
- BendingUI symmetry presentation (owned by T2 / `phase6_bending_ui.py`);
- deleted symmetry builder / deleted Assembly settings no-op.

The presentation owner may receive narrow callbacks/data needed to render and invoke those existing owners; it must not become a second transaction/state owner.

## Acceptance direction

```text
SELECTED_LIVE_CLUSTER_FROZEN=1
EXISTING_SETTINGS_OWNER=phase6_settings_panel.py
COMPETING_SETTINGS_OWNER=0
MUTATION_OWNER_MOVE=0
DUPLICATE_SYMMETRY_UI=0
NEXT_DECISION=EXTRACT_SELECTED_TK_PRESENTATION_CLUSTER
```

Next executable action: add RED ownership contracts that fail while the selected Tk builder implementations remain in `fold_designer_bridge.py`, while locking mutation ownership/reverse-import/facade invariants.

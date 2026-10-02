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


## T3 implementation checkpoint — 2026-09-21

- RED contract commit: `b4b97490fe43f70c61ac825bf13062c3ca5d33d1`
- Panel-owner commit: `fa569fb52058327ade5a3b8bed42ff05908b177e`
- Bridge-projection commit: `db51ddd6165cc963b56038ddb0ad27175851f946`
- Validation PR: #456 (draft / validation only)
- Local clone remains unavailable because runtime DNS cannot resolve github.com; no local result is used as acceptance evidence.

Exact Git-object ownership classifier at `db51ddd6`:

```text
SELECTED_BUILDERS_REMAINING_IN_BRIDGE=[]
PANEL_RENDER_OWNED_CONTEXT_EXTENSIONS=1
PANEL_REVERSE_IMPORT_BRIDGE=0
PANEL_FORBIDDEN_TRANSACTION_DOMAIN_TOKENS=[]
OLD_BRIDGE_RENDER_EXTENSION_OWNER=0
PURE_BRIDGE_EXTENSION_PROJECTION=1
EXPLICIT_PANEL_CALLBACK_WIRING=1
STATIC_OWNERSHIP_DECISION=GREEN
```

Implementation boundary:
- concrete Tk construction for BoxBody structure, EndCap FW, receiving bottom-wrap and Corner extension rows is now implemented by `Phase6SettingsPanel`;
- bridge retains domain/state projection and canonical mutation callbacks;
- EndCap Joint settings compatibility hook is no longer a Settings-panel builder; the drawing-edge owner remains unchanged;
- transaction/state ownership, symmetry presentation, geometry, DXF and persistence semantics are intentionally unchanged.

Next action:
1. run PR-triggered focused remote QA against the exact current candidate;
2. if GREEN, update durable evidence/claim, close validation PR without merge, complete drift/readback and issue #445 acceptance;
3. only then release #445 and hand #446 the accepted HEAD.

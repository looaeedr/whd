# Issue #541 / B6-1 — Facade Audit Batch 1

- Parent controller: #531
- Parent accepted HEAD: `b04310c426ccb07dbc18a09b451a27e54fd2d24f`
- Final GREEN HEAD: `cef59e90877ca9f87d542d6d50ae348027200539`
- Facade count: **69 → 65**

## Evidence

- V1 audit RUN `35795523293`: GREEN but **NON_ACCEPTANCE_EVIDENCE** because BACKUP/tooling paths polluted runtime counts.
- V2 audit RUN `35795603842`: GREEN, current production/tests only.
- Replacement RED RUN `35795722034`: expected RED, **2 failed / 1 passed**.
- Final GREEN RUN `35795824278`: **25 passed / 1 skipped**.
- `B6_1_ACCOUNTED=12`
- `B6_1_UNCLASSIFIED=0`
- `B6_1_DYNAMIC_REF_UNREVIEWED=0`
- removed = **4**
- retained = **8**

## Final classification

- `__getattr__` → `LEGACY_REQUIRED`
- `_phase6_last_cutting_mesh` → `PROPERTY_COMPAT`
- `_phase6_last_cutting_material` → `PROPERTY_COMPAT`
- `_phase6_cutting_mesh_error` → `NO_CALLER`
- `_phase6_zoom_scale` → `PROPERTY_COMPAT`
- `_phase6_view_initialized` → `NO_CALLER`
- `_phase6_base_renderer_render` → `NO_CALLER`
- `_phase6_scroll_cid` → `NO_CALLER`
- `__init__` → `LEGACY_REQUIRED`
- `_refresh_part_buttons` → `LEGACY_REQUIRED`
- `_refresh_part_button_states` → `LEGACY_REQUIRED`
- `_refresh_add_part_menu` → `LEGACY_REQUIRED`

## Removal rationale

The four `NO_CALLER` entries were private view compatibility properties with **0 current production refs, 0 tests, and 0 dynamic refs** after excluding tracked BACKUP/tooling evidence. Their `FinalSceneView` backing state remains intact; only the unused facade exposure was removed.

Batch terminal does not make #531 terminal. Continue with #542/B6-2.

# Issue #541 / B6-1 — Facade Audit Batch 1

- Parent accepted HEAD: `b04310c426ccb07dbc18a09b451a27e54fd2d24f`
- Corrected audit RUN: `35795603842 @ 058cc7e9c9c688b1d8ecf0916229a43d45990bb9`
- Replacement RED RUN: `35795722034 @ 88a7273047572f299d66759160030e8378ceda28`
- GREEN RUN: `35795824278 @ cef59e90877ca9f87d542d6d50ae348027200539`
- GREEN: **25 passed / 1 skipped**
- Facade count: **69 → 65**
- Accounted: **12 / 12**
- `UNCLASSIFIED=0`
- `DYNAMIC_REF_UNREVIEWED=0`

## Final classification

| key | class |
|---|---|
| `__getattr__` | `LEGACY_REQUIRED` |
| `_phase6_last_cutting_mesh` | `PROPERTY_COMPAT` |
| `_phase6_last_cutting_material` | `PROPERTY_COMPAT` |
| `_phase6_cutting_mesh_error` | `NO_CALLER` |
| `_phase6_zoom_scale` | `PROPERTY_COMPAT` |
| `_phase6_view_initialized` | `NO_CALLER` |
| `_phase6_base_renderer_render` | `NO_CALLER` |
| `_phase6_scroll_cid` | `NO_CALLER` |
| `__init__` | `LEGACY_REQUIRED` |
| `_refresh_part_buttons` | `LEGACY_REQUIRED` |
| `_refresh_part_button_states` | `LEGACY_REQUIRED` |
| `_refresh_add_part_menu` | `LEGACY_REQUIRED` |

## Removal

Removed after replacement RED/GREEN:

- `_phase6_cutting_mesh_error`
- `_phase6_view_initialized`
- `_phase6_base_renderer_render`
- `_phase6_scroll_cid`

The first audit run `35795523293` is **NON_ACCEPTANCE_EVIDENCE** because it counted `BACKUP/**` and tooling as live production consumers. V2 corrected that classification before any deletion.

This batch terminal does not close #531. Next canonical batch is #542.

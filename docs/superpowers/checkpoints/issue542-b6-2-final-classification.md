# Issue #542 / B6-2 — Facade Audit Batch 2

- Parent lineage HEAD: `2c5bcd5784501c892a2e5f3fc1da318374aaec22`
- Audit RUN: `35796289899 @ 61f75b16a5f358eba0609fcd2ac6616d1485e452`
- Replacement RED: `35796616236 @ 58b8150e99ed4b147b617f3764dcd72471be30b4`
- GREEN: `35796724897 @ 46f7cc0eb5137cd88e8669e400b31417d82d968a`
- GREEN total: **25 passed / 3 skipped**
- Accounted: **12 / 12**
- `UNCLASSIFIED=0`
- `DYNAMIC_REF_UNREVIEWED=0`
- Facade count: **65 → 64**

## Final classification

| key | class |
|---|---|
| `_save_current_part` | `LEGACY_REQUIRED` |
| `_load_part_holes` | `LEGACY_REQUIRED` |
| `activate_part` | `PUBLIC_REQUIRED` |
| `show_home` | `PUBLIC_REQUIRED` |
| `on_3d_scroll` | `PUBLIC_REQUIRED` |
| `add_part` | `PUBLIC_REQUIRED` |
| `select_part` | `PUBLIC_REQUIRED` |
| `activate_selected_part` | `NO_CALLER` |
| `remove_selected_part` | `PUBLIC_REQUIRED` |
| `remove_part` | `PUBLIC_REQUIRED` |
| `available_parts` | `PROPERTY_COMPAT` |
| `active_part_key` | `PROPERTY_COMPAT` |

## Removal

Only the facade binding for `activate_selected_part` was removed. The implementation function `_fix11_activate_selected_part` remains; B6-2 proved the facade exposure had no caller, not that the implementation body was dead.

This batch terminal does not close #531. Next canonical batch is #543.

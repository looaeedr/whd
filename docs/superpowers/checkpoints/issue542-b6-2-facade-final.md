# Issue #542 / B6-2 — Facade Audit Batch Final

- Controller: #531
- Parent accepted HEAD: `2c5bcd5784501c892a2e5f3fc1da318374aaec22`
- Audit RUN: `35796289899` — SUCCESS
- Replacement RED RUN: `35796616236` — expected RED proven
- GREEN RUN: `35796724897 @ 46f7cc0eb5137cd88e8669e400b31417d82d968a` — SUCCESS
- GREEN: **25 passed / 3 skipped**
- Artifact: `10724111058`
- `B6_2_ACCOUNTED=12`
- `B6_2_UNCLASSIFIED=0`
- `B6_2_DYNAMIC_REF_UNREVIEWED=0`
- Facade count: **65 → 64**

## Final classification

| key | class | production refs | test refs | dynamic refs |
|---|---|---:|---:|---:|
| `_save_current_part` | `LEGACY_REQUIRED` | 10 | 8 | 0 |
| `_load_part_holes` | `LEGACY_REQUIRED` | 2 | 0 | 0 |
| `activate_part` | `PUBLIC_REQUIRED` | 9 | 165 | 0 |
| `show_home` | `PUBLIC_REQUIRED` | 1 | 6 | 0 |
| `on_3d_scroll` | `PUBLIC_REQUIRED` | 1 | 1 | 0 |
| `add_part` | `PUBLIC_REQUIRED` | 6 | 8 | 0 |
| `select_part` | `PUBLIC_REQUIRED` | 3 | 5 | 0 |
| `activate_selected_part` | `NO_CALLER` | 0 | 0 | 0 |
| `remove_selected_part` | `PUBLIC_REQUIRED` | 3 | 1 | 0 |
| `remove_part` | `PUBLIC_REQUIRED` | 6 | 10 | 0 |
| `available_parts` | `PROPERTY_COMPAT` | 52 | 118 | 18 |
| `active_part_key` | `PROPERTY_COMPAT` | 28 | 28 | 16 |

`activate_selected_part` is the only `NO_CALLER` item in this batch. Its facade entry was removed after replacement RED; the underlying `_fix11_activate_selected_part` implementation remains because B6 audits facade exposure, not dead-code ownership.

The other 11 bindings retain concrete live compatibility evidence.

## Handoff

B6 controller aggregate after B6-2: **24 / 69 accounted**, facade count **64**. Continue serially to #543/B6-3 after #542 finalization.

# Issue #543 / B6-3 — Facade Audit Batch 3

- Parent accepted HEAD: `90bce030feed775fc852d9bd8f8ef21482471a4a`
- Consumer audit RUN: `35801179888 @ 13adff5e2f054b695a2f90d34a7ecc2d6a857ba7`
- Replacement RED RUN: `35801296639 @ 90030cbb3aaf76fe83b249714fd343ccdf55015d`
- Final GREEN RUN: `35801394151 @ f8e006c466f91e5dd174d6c8cadc05473ba5baaa`
- GREEN total: **31 passed / 9 skipped**
- Accounted: **12 / 12**
- `UNCLASSIFIED=0`
- `DYNAMIC_REF_UNREVIEWED=0`
- Facade count: **64 → 62**

## Final classification

| key | class |
|---|---|
| `selected_part_key` | `PROPERTY_COMPAT` |
| `_phase6_part_profiles` | `PROPERTY_COMPAT` |
| `_phase6_part_features` | `PROPERTY_COMPAT` |
| `_phase6_part_face_features` | `PROPERTY_COMPAT` |
| `_phase6_workspace_dirty` | `PROPERTY_COMPAT` |
| `_phase6_switching_part` | `PROPERTY_COMPAT` |
| `_phase6_box_body_active_piece_key` | `PROPERTY_COMPAT` |
| `apply_external_assembly_type` | `PUBLIC_REQUIRED` |
| `export_phase6_snapshot` | `PUBLIC_REQUIRED` |
| `show_global_settings` | `NO_CALLER` |
| `toggle_baseline_data` | `PUBLIC_REQUIRED` |
| `save_settings_context_as_defaults` | `NO_CALLER` |

## Removal

Only facade exposure for `show_global_settings` and `save_settings_context_as_defaults` was removed. Their underlying implementation functions remain; this batch proves no facade consumer, not dead implementation ownership.

## Controller handoff

B6 aggregate after B6-3: **36 / 69 accounted**. Next canonical batch is #544 / B6-4.

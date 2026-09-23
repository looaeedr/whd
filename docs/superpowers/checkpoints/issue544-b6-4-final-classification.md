# Issue #544 / B6-4 — Facade Audit Batch 4

- Parent accepted HEAD: `4b2bf0174c59dabf487a430c4dc49cddd47ce410`
- Consumer audit RUN: `35801778565 @ 7f151937db4abc8d661fec27311b36e25e72350f`
- Replacement RED RUN: `35801927028 @ 476678276f19b465103a05b7a2267bb7653f91ac` — expected RED proven
- Initial GREEN RUN: `35810494194 @ 8a5411f03d4f6e4f2a826be09df7c6f4e5bd6bed`
  - Headless: **30 passed / 6 skipped**
  - Xvfb: **5 failed / 12 passed**
- Xvfb A/B RUN: `35810672744 @ 5ea6ad53a95be038677b08c0243a8932c77235cf`
  - baseline failures: **5**
  - candidate failures: **5**
  - **candidate-only failures: 0**
- Architecture RUN: `35810925170 @ ed1d3b441a2467800c274c613c8078b459e48761` — GREEN
- Accounted: **12 / 12**
- `UNCLASSIFIED=0`
- `DYNAMIC_REF_UNREVIEWED=0`
- Facade count: **62 → 60**

## Final classification

| key | class | prod refs | test refs | dynamic refs |
|---|---|---:|---:|---:|
| `save_current_settings_as_defaults` | `PUBLIC_REQUIRED` | 2 | 1 | 0 |
| `flush_pending_settings` | `PUBLIC_REQUIRED` | 11 | 17 | 0 |
| `_phase6_publish_live_state` | `LEGACY_REQUIRED` | 7 | 20 | 6 |
| `_phase6_resolve_manufacturing_geometry` | `LEGACY_REQUIRED` | 6 | 24 | 3 |
| `toggle_advanced_settings` | `NO_CALLER` | 0 | 0 | 0 |
| `apply_external_settings` | `PUBLIC_REQUIRED` | 4 | 8 | 14 |
| `apply_external_model` | `PUBLIC_REQUIRED` | 2 | 0 | 1 |
| `apply_external_sync` | `PUBLIC_REQUIRED` | 2 | 3 | 7 |
| `_phase6_refresh_corner_data_unfold_view` | `LEGACY_REQUIRED` | 1 | 13 | 3 |
| `on_ui_text_size_changed` | `PUBLIC_REQUIRED` | 1 | 2 | 0 |
| `apply_external_corner_state` | `PUBLIC_REQUIRED` | 2 | 0 | 7 |
| `_phase6_corner_parameters_unlocked` | `CAN_DIRECT_OWNER` | 0 | 10 | 0 |

## Mutations

- `toggle_advanced_settings`: `NO_CALLER` → facade entry removed.
- `_phase6_corner_parameters_unlocked`: `CAN_DIRECT_OWNER` → test-only instance callers migrated to `fold_designer_bridge._phase6_corner_parameters_unlocked(designer, part_key)`, then facade entry removed.
- Underlying implementation functions remain; this batch contracts compatibility exposure only.

## Xvfb classification

The five Xvfb failures in the initial GREEN run are pre-existing baseline debt for the exact same test set. Immutable A/B comparison produced **candidate-only failure count 0**. They are not regressions introduced by B6-4 and are not repaired in this facade audit batch.

## Controller handoff

B6 aggregate after B6-4: **48 / 69 accounted**. Next canonical batch is #545 / B6-5.

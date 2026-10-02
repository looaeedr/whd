# Issue #545 / B6-5 — Facade Audit Batch 5

- Parent accepted HEAD: `f7179554c448a4af5b271d251290912efe115a38`
- Consumer audit RUN: `35811547955 @ 4dcdbd07241988738374b506abd57e3818a07559`
- Replacement RED RUN: `35811700857 @ 41b87ea8cadcb8bb9dd2a4b97743a0eb1aacef5e`
- Production/test migration HEAD: `39d2cdc4e0a2ba11036d645dd1a87d53f69c799d`
- Candidate GREEN RUN: `35815867302 @ 54797c37b1cdae0c6b05cff3f7f0c71fa7f8e9db`
- Parent Xvfb baseline RUN: `35816036734`
- Architecture replacement RUN: `35816292956 @ c23d0b7154c246145c58059617f67018ba993270`
- Architecture artifact: `10731333032`

## Acceptance

- Headless facade contracts: **7 passed**
- Candidate Xvfb: **11 failed / 49 passed**
- Parent accepted Xvfb: **11 failed / 49 passed**
- **Candidate-only Xvfb fail count = 0**
- `B6_5_ACCOUNTED=12`
- `B6_5_UNCLASSIFIED=0`
- `B6_5_DYNAMIC_REF_UNREVIEWED=0`
- Facade count: **60 → 52**
- Removed facade exposures: **8**
- Direct-owner migrations: **7**

## Final classification

| key | class |
|---|---|
| `toggle_corner_parameter_lock` | `CAN_DIRECT_OWNER` |
| `_render_settings_context` | `CAN_DIRECT_OWNER` |
| `on_baseline_model_changed` | `CAN_DIRECT_OWNER` |
| `confirm_corner_transaction` | `CAN_DIRECT_OWNER` |
| `cancel_corner_transaction` | `CAN_DIRECT_OWNER` |
| `reset_initial_values` | `PUBLIC_REQUIRED` |
| `export_workspace_state_if_dirty` | `CAN_DIRECT_OWNER` |
| `save_diagnostic_file` | `NO_CALLER` |
| `save_project_file` | `PUBLIC_REQUIRED` |
| `save_project_file_as` | `PUBLIC_REQUIRED` |
| `load_project_file` | `PUBLIC_REQUIRED` |
| `_phase6_on_endcap_edge_relation_selected` | `CAN_DIRECT_OWNER` |

`save_diagnostic_file` is the single true `NO_CALLER` item. Seven test-only facade users were migrated to direct module-owner calls before their facade entries were removed. The four project/reset APIs remain live public compatibility surfaces.

The 11 Xvfb failures are immutable parent-baseline debt for this batch: exact candidate-only delta is zero.

## Controller handoff

B6 aggregate after B6-5: **60 / 69 accounted**. Continue serially to #546/B6-6.

# Issue #546 / B6-6 — Facade Audit Batch 6

- Parent accepted HEAD: `c06f5fb976b96e0db58452438ed8977b9d86e800`
- Consumer audit RUN: `35816653419 @ 80ab12e34c34f60ff1d921ca1712875a5aeda6f4`
- Replacement RED RUN: `35816829506 @ 87da454f3c6bab8dee33d2e8233e7972cd632bbe`
- Production migration HEAD: `fb2d5c5cdc10f3a32f0e466fa78377a9a606829c`
- Candidate GREEN RUN: `35817570889 @ b9dd61041f43d91c3c083cba6e4ad206cc4c8c79`
- Immutable A/B RUN: `35817807414 @ 12f0c6bdc962c003f0b7c6862d8d455f0574dd87`
- A/B artifact: `10731144611`

## Acceptance

- Headless focused contracts: **24 passed**
- Candidate Xvfb: **3 failed / 28 passed**
- Parent accepted Xvfb: **3 failed / 28 passed**
- **Candidate-only Xvfb failures = 0**
- `B6_6_ACCOUNTED=9`
- `B6_6_UNCLASSIFIED=0`
- `B6_6_DYNAMIC_REF_UNREVIEWED=0`
- Facade count: **52 → 45**
- Removed facade exposures: **7**
- Public-required retained seams: **2**

## Final classification

| key | class |
|---|---|
| `_phase6_render_endcap_edge_controls` | `NO_CALLER` |
| `_phase6_commit_base_plate_edge_shrink` | `CAN_DIRECT_OWNER` |
| `submit_update_intent` | `PUBLIC_REQUIRED` |
| `apply_settings_delta` | `CAN_DIRECT_OWNER` |
| `switch_active_part` | `CAN_DIRECT_OWNER` |
| `publish_if_changed` | `CAN_DIRECT_OWNER` |
| `_phase6_flush_update_intents` | `CAN_DIRECT_OWNER` |
| `set_3d_preview_enabled` | `PUBLIC_REQUIRED` |
| `refresh_3d_preview` | `NO_CALLER` |

The seven removed class-facade bindings do not delete their underlying `_phase6_*` functions. The two public runtime seams remain on `Phase6FoldDesignerApp`.

Three stale class-oracle assertions for `apply_settings_delta`, `switch_active_part`, and `publish_if_changed` were changed to direct module-owner contracts. Existing direct callers for base-plate shrink and lifecycle flush already use the module-owner function surface.

The three Xvfb failures are immutable parent-baseline debt for this batch: exact candidate-only delta is zero.

## Controller handoff

B6 aggregate after B6-6: **69 / 69 accounted**. Continue to #531 controller aggregate acceptance; batch terminal is not controller terminal.

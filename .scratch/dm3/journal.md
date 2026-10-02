# DM3 Divider canonical relief journal

Owning issue: #53
Base: `work/dm2-divider-physical-contract@63810a32a371fde6e153089ca1c4f642ce535a54`

## Implementation
- Added `ae_engine/divider_manufacturing.py` as the canonical Divider manufacturing-domain boundary.
- `resolve_divider_final_geometry()` now owns FW placement proof, collision/backprojection relief candidate, material cut, refold, post-cut verification, final material and evidence.
- `fold_designer_bridge.py` delegates to the manufacturing-domain resolver; it no longer calls the low-level Divider relief candidate / verification helpers directly.
- Removed placeholder final-material / relief authority records from `BoxBodyDividerPart.physical_geometry_contract`.

## TDD evidence
- RED run `34230242366`: 3 intended architecture failures.
- Focused GREEN run `34230991438`: 3 passed / 0 failed.
- Related regression run `34231087452`: 22 passed / 2 skipped / 0 failed.

## Final acceptance
Run `34231526901`
Tested SHA `94381511375d91ed4374e5a7c9dc1e16e8844b96`
- Exact historical T48-2 command: 13 passed / 0 failed.
- Current durable final-material / reload / project-authority / Ø6.4 / DM3 guards: 32 passed / 0 failed.
- Production compile: PASS.
- Architecture ownership scan: PASS.
- `config.ini` before/after SHA256 in both acceptance groups: `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`.

## T48-3 authority note
`tests/test_issue48_final_geometry_sync.py` was a one-shot acceptance test. It existed at historical T48-3 SHA `16b92919592592d77e37242d9a280a93cb332d9d`, then was deliberately removed during T48-4 cleanup together with `.github/workflows/t48-3-final-geometry-sync.yml`. Current durable guards are therefore used instead of resurrecting the cleaned one-shot test.

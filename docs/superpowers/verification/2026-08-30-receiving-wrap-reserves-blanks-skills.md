# 2026-08-30 Receiving WRAP / Reserves / Blank / Skills Verification

## Scope

- Receiving EndCap lower-face WRAP independent from INSERT / OVERLAY / INSERT_OVERLAY.
- Adjustable `reserve_u` / `reserve_v` under parameter-lock UI.
- Head/Tail linked WRAP state with independent final material.
- Canonical unfolded blank information per physical sheet.
- Piece-level side/back 3D geometry and receiving-only core-origin placement.
- Project skills relocated to `.agents/skills/` and release cleanup for legacy `skills/`.

## Fresh verification evidence

- `tests/test_receiving_bottom_wrap_registry.py + test_receiving_bottom_wrap_linkage.py + test_piece_level_joint_geometry.py + test_canonical_unfolded_blank_info.py`: 35 passed.
- Vault/custom collision regressions affected by core-origin scope: 6 passed after receiving-only scoping.
- `tests/test_phase6_assembly_3d_view.py`: 16 non-Tk passed; both real Tk selector tests passed in separate fresh Xvfb processes.
- `tests/test_phase6_3d_view_regressions.py`: 5/5 passed in separate fresh processes.
- `tests/test_overlay_formed_fw_registry_contract.py`: 3/3 passed.
- `tests/test_phase6_box_body_structure.py`: 20 headless + 5 real Tk passed when real Tk tests were isolated.
- Registry GUI matrix INSERT / INSERT_OVERLAY / OVERLAY: 3/3 passed under Xvfb.
- WRAP Save/Reload and verified Joint persistence: 3/3 passed.
- Selected global project Save/Reload GUI flows: 3/3 passed.
- Release cleanup/policy integrity: 12/12 passed.
- Project Python compile gate: 200 files compiled, 0 errors (before release cleanup additions; rerun required at final gate).
- `config.ini` SHA256 remained `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`.

## Baseline-known failures excluded from new-regression count

The canonical pre-change verification tree already fails legacy tests in unrelated Manufacturing API fixtures (invalid dummy DXF / legacy indicator-baseline expectations) and a stale UI test expecting `class EditorUndoHistory`. These were reproduced against the pre-change baseline and were not introduced or masked by this change.

## Release rule

No package is considered delivered until FULL and UPDATE are built from the canonical baseline, CRC/SHA256 verified, UPDATE cleanup is exercised, and the extracted FULL passes the final responsibility gate.

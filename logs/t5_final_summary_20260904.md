# T5 Ownership / Focused Integration Gate

- Focused file set: 103 test files
- Collected tests: 815
- Fresh Headless: 648 passed / 167 skipped / 0 failed
- Xvfb: 815 passed / 0 failed, all 103 files executed across isolated fresh-Xvfb batches
- Real regression found during Xvfb: `tests/test_receiving_cabinet_2d.py::test_receiving_gui_part_specs_drive_actual_2d_contracts_and_survive_snapshot_restore`
- Root cause: GUI family-policy adapter coerced optional `FourCornerTypePolicy.bottom_fw=None` to `float(None)` after T3 facade migration.
- Fix: use policy `bottom_fw` when present, otherwise base `policy.fw` only as the generic facade fallback input. Receiving `side_rear_bend + thickness` formula unchanged.
- Regression proof: failing test RED with TypeError; after minimal fix 1/1 PASS; final affected Xvfb batch 100/100 PASS.
- Final changed-file Phase6 Knowledge Preflight: PASS.
- `config.ini` SHA256: `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67` (unchanged).

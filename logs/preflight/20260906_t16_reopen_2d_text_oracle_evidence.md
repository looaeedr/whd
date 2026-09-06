# T16 Reopen — 2D Derived-Part Text Oracle

Source T18 run: 34028206636
Owning issue: #16
RED nodeid:
- tests/test_multi_door_gui.py::test_multi_door_cells_contain_no_metadata_text_and_double_click_is_bound

Diagnosis:
- T16 intentionally projects authoritative divider/frame placements into the 2D Door layout.
- T16 2D annotations use tags `door_layout_divider` and `door_layout_frame`.
- The old oracle prohibited every text item inside a Door cell, contradicting T16 and the product requirement that 3D-visible derived information also be visible in 2D.
- The 50 mm text is the T16 top/left/right planar frame inset; it is distinct from the T17 80 mm inward depth datum.

Correction boundary:
- test-only
- no production change
- cell-interior text must belong to authoritative divider/frame tags
- unrelated metadata text remains forbidden
- coordinate hit-testing remains the interaction seam

Correction commit:
- 446c027ef205279e38fb0bf14ecf0f56b908e7a2

Combined remote QA:
- run 34028808208
- head ff166bcebfc3d70262854f09669ac61939d99f2e
- multi-door GUI 49 PASS
- T11 family guards 17 PASS
- T16 placement/roundtrip/multipart 19 PASS
- total 85 PASS / 0 FAIL
- config canonical before/after unchanged

RESULT: GREEN / READY TO RECLOSE T16

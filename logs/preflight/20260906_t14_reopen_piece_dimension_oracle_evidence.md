# T14 Reopen Wave 6 — Per-Piece Dimension Presentation Oracle

Source T18 run: 34029782615
Source artifact: 9988306394
Owning issue: #15

Single true RED:
- tests/test_phase6_t03_piece_dimensions.py::test_real_two_piece_settings_page_shows_per_piece_formed_outer_and_material_dimensions

Diagnosis:
- The old oracle expected each piece name + formed outer + material dimensions in one text widget.
- T14 child-section contract renders one LabelFrame per authoritative physical piece.
- The piece name is the section title.
- "包外尺寸" and "料尺寸" are separate labels inside that same section.
- Stable identity is section._phase6_part_key == box_body:<role>.
- Production behavior matches T14; presentation oracle is stale.

Correction boundary:
- test-only
- no production change
- verify section keys/stable ids, section titles, one formed label and one material label per section

RESULT: DIAGNOSED / READY FOR ORACLE CORRECTION


ORACLE CORRECTION COMMIT:
- 611637f058d36e46f69eb162e8939adfd88b88b8

REMOTE QA RUN: 34030224332
REMOTE QA HEAD: 1f4d5835885d140dd5c101826a10576d24ad532b
REMOTE QA: 41 PASS / 0 FAIL (10 + 31)
CONFIG SHA256 BEFORE/AFTER:
980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67

RESULT: GREEN / READY TO RECLOSE T14

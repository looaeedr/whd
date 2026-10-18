"""#1820 CADCraft fidelity gate: unit, geometry, annotation and block negatives.

All drawings are synthetic, generated inside tmp_path; no customer DXF.
"""
from shutil import copy2

import ezdxf

from tools.issue1820_cadcraft_dxf_fidelity_gate import audit


def _fixture(tmp_path):
    source, saved = tmp_path / "source.dxf", tmp_path / "cadcraft-copy.dxf"
    doc = ezdxf.new("R2010", units=ezdxf.units.MM)
    doc.layers.new("CUTTING", dxfattribs={"color": 3})
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "CUTTING"})
    msp.add_circle((25, 30), radius=5, dxfattribs={"layer": "CUTTING"})
    msp.add_arc((70, 40), radius=20, start_angle=10, end_angle=90)
    msp.add_text("測試尺寸", dxfattribs={"height": 2.5})
    block = doc.blocks.new(name="WHD_TEST_BLOCK")
    block.add_line((0, 0), (3, 0))
    msp.add_blockref("WHD_TEST_BLOCK", (50, 50))
    doc.saveas(source)
    copy2(source, saved)
    return source, saved


def test_identical_source_and_disposable_copy_pass(tmp_path):
    a, b = _fixture(tmp_path)
    result = audit(a, b)
    assert result["result"] == "PASS", result
    assert not result["failures"]


def test_unitless_to_inch_must_fail_even_when_entity_count_unchanged(tmp_path):
    a, b = _fixture(tmp_path)
    source = ezdxf.readfile(a)
    source.header["$INSUNITS"] = 0
    source.saveas(a)
    target = ezdxf.readfile(b)
    target.header["$INSUNITS"] = 1
    target.saveas(b)
    # Simulates #1209: only the unit contract is known to differ.
    result = audit(a, b)
    assert result["result"] == "FAIL_CLOSED"
    assert "$INSUNITS_DRIFT" in result["failures"]


def test_same_entity_count_but_moved_cutting_hole_must_fail(tmp_path):
    a, b = _fixture(tmp_path)
    doc = ezdxf.readfile(b)
    circle = next(e for e in doc.modelspace() if e.dxftype() == "CIRCLE")
    circle.dxf.center = (25.125, 30)
    doc.saveas(b)
    result = audit(a, b)
    assert "MODEL_DIFF" in result["failures"]


def test_same_count_but_changed_text_and_block_contents_fail(tmp_path):
    a, b = _fixture(tmp_path)
    doc = ezdxf.readfile(b)
    text = next(e for e in doc.modelspace() if e.dxftype() == "TEXT")
    text.dxf.text = "其他標註"
    block_line = next(iter(doc.blocks["WHD_TEST_BLOCK"]))
    block_line.dxf.end = (4, 0)
    doc.saveas(b)
    result = audit(a, b)
    assert "MODEL_DIFF" in result["failures"]
    assert "BLOCKS_DIFF" in result["failures"]


def test_explicit_default_insert_scale_does_not_fail_as_wrong_geometry(tmp_path):
    a, b = _fixture(tmp_path)
    doc = ezdxf.readfile(b)
    insert = next(e for e in doc.modelspace() if e.dxftype() == "INSERT")
    insert.dxf.xscale = 1.0
    insert.dxf.yscale = 1.0
    insert.dxf.zscale = 1.0
    insert.dxf.rotation = 0.0
    doc.saveas(b)
    result = audit(a, b)
    assert result["result"] == "PASS", result


def test_dimension_value_change_not_masked_as_harmless_serialization(tmp_path):
    a, b = _fixture(tmp_path)
    doc = ezdxf.readfile(a)
    doc.modelspace().add_linear_dim(
        base=(60, 20), p1=(0, 0), p2=(50, 0), angle=0
    ).render()
    doc.saveas(a)
    doc = ezdxf.readfile(a)
    dim = next(e for e in doc.modelspace() if e.dxftype() == "DIMENSION")
    assert dim
    copy2(a, b)
    dst = ezdxf.readfile(b)
    dim2 = next(e for e in dst.modelspace() if e.dxftype() == "DIMENSION")
    dim2.dxf.text = "999"
    dst.saveas(b)
    result = audit(a, b)
    assert "MODEL_DIFF" in result["failures"]


def test_no_inplace_rewrite(tmp_path):
    a, _ = _fixture(tmp_path)
    try:
        audit(a, a)
    except ValueError as exc:
        assert str(exc) == "ORIGINAL_MUST_NOT_BE_THE_RESAVED_DXF"
    else:
        assert False, "audit must refuse in-place DXF modification"



def test_solid_inside_block_is_fingerprinted_and_geometry_changes_fail(tmp_path):
    """Actual R5 user drawings contain SOLID entities in DIMENSION/INSERT blocks.

    SOLID is a four-vertex geometry entity, not an unsupported metadata entry.
    """
    a, b = _fixture(tmp_path)
    source = ezdxf.readfile(a)
    source.blocks["WHD_TEST_BLOCK"].add_solid(
        [(0, 0), (5, 0), (5, 5), (0, 5)]
    )
    source.saveas(a)
    copy2(a, b)
    assert audit(a, b)["result"] == "PASS"

    saved = ezdxf.readfile(b)
    solid = next(e for e in saved.blocks["WHD_TEST_BLOCK"]
                 if e.dxftype() == "SOLID")
    solid.dxf.vtx1 = (5.125, 0, 0)
    saved.saveas(b)

    result = audit(a, b)
    assert result["result"] == "FAIL_CLOSED"
    assert "BLOCKS_DIFF" in result["failures"]

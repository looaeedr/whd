"""#1959 WHD-origin geometry -> real CADCraft --cmd new drawing proof."""
import json
import math
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.sheetmetal_features import (
    FeatureAnchor, CircleFeature, RectFeature, ProfileFeature, Vec2,
    feature_surface_from_rect, resolve_surface_features,
)
from tools.issue1959_whd_cadcraft_command_draw import (
    CadcraftCommandProofError, cadcraft_argv, demo_instructions,
    from_whd_resolved, run_proof, verify_dxf,
)


def test_wdh_feature_shapes_generate_explicit_metric_cadcraft_commands(tmp_path):
    instructions = demo_instructions()
    assert [x.kind for x in instructions] == ["circle", "rectangle", "profile"]
    assert instructions[0].points == ((25.0, 30.0),)
    assert instructions[0].radius == 5.0
    assert any(x < 0 for x, y in instructions[2].points)
    args = cadcraft_argv("cadcraft-cli", instructions, tmp_path/"new.dxf", tmp_path/"new.png")
    assert args[:3] == ["cadcraft-cli", "run", "--metric"]
    assert args.count("--cmd") == 3
    assert args[-4:] == ["--save", str(tmp_path/"new.dxf"), "--export", str(tmp_path/"new.png")]
    raw = [json.loads(args[n+1].split(" ", 1)[1])
           for n, token in enumerate(args) if token == "--cmd"]
    assert [args[n+1].split(" ", 1)[0] for n, token in enumerate(args) if token=="--cmd"] == [
        "circle", "pline", "pline"
    ]
    assert raw[0] == {"center": [25.0,30.0], "radius": 5.0}
    assert raw[1]["closed"] and len(raw[1]["vertices"])==4
    assert raw[2]["closed"] and len(raw[2]["vertices"])==4


def _make_dxf(path, instructions, *, units=ezdxf.units.MM):
    doc=ezdxf.new("R2010",units=units)
    for inst in instructions:
        if inst.kind=="circle":
            doc.modelspace().add_circle(inst.points[0],inst.radius)
        else:
            doc.modelspace().add_lwpolyline(inst.points,close=True)
    doc.saveas(path)


def test_independent_ezdxf_geometry_audit_accepts_correct_3_holes(tmp_path):
    items=demo_instructions()
    target=tmp_path/"cadcraft_fresh.dxf"
    _make_dxf(target, items)
    assert verify_dxf(target, items)["entity_count"]==3


def test_units_not_explicit_mm_refused(tmp_path):
    items=demo_instructions()
    target=tmp_path/"bad.dxf"
    _make_dxf(target, items, units=ezdxf.units.IN)
    with pytest.raises(CadcraftCommandProofError,match="MILLIMETRE_HEADER_MISMATCH"):
        verify_dxf(target,items)


def test_circle_radius_and_rect_vertex_changes_fail_closed(tmp_path):
    items=demo_instructions()
    target=tmp_path/"bad.dxf"
    _make_dxf(target, items)
    doc=ezdxf.readfile(target)
    list(doc.modelspace())[0].dxf.radius=7
    doc.saveas(target)
    with pytest.raises(CadcraftCommandProofError,match="CIRCLE_COORDINATE_OR_RADIUS_MISMATCH"):
        verify_dxf(target,items)
    _make_dxf(target,items)
    doc=ezdxf.readfile(target)
    rect=list(doc.modelspace())[1]
    pts=list(rect.get_points("xyseb"))
    x,y,sw,ew,b=pts[1]
    pts[1]=(x+.25,y,sw,ew,b)
    rect.set_points(pts,format="xyseb")
    doc.saveas(target)
    with pytest.raises(CadcraftCommandProofError,match="POLYGON_COORDINATE_OR_BULGE_MISMATCH"):
        verify_dxf(target,items)


def test_extra_and_open_entities_are_rejected(tmp_path):
    items=demo_instructions()
    target=tmp_path/"bad.dxf"
    _make_dxf(target, items)
    doc=ezdxf.readfile(target)
    doc.modelspace().add_line((0,0),(100,100))
    doc.saveas(target)
    with pytest.raises(CadcraftCommandProofError,match="ENTITY_COUNT_MISMATCH"):
        verify_dxf(target,items)
    _make_dxf(target,items)
    doc=ezdxf.readfile(target)
    list(doc.modelspace())[1].close(False)
    doc.saveas(target)
    with pytest.raises(CadcraftCommandProofError,match="OPEN_OR_WRONG_ENTITY_PROFILE"):
        verify_dxf(target,items)


def test_cadcraft_cannot_overwrite_any_existing_path(tmp_path):
    existing=tmp_path/"existing.dxf"
    existing.write_bytes(b"private manufacturing file must survive")
    with pytest.raises(CadcraftCommandProofError,match="REFUSE_TO_OVERWRITE"):
        run_proof("cadcraft-cli",demo_instructions(),existing)
    assert existing.read_bytes()==b"private manufacturing file must survive"


def test_whd_actual_resolve_surface_path_works_not_raw_dxf():
    surface=feature_surface_from_rect("1959",Vec2(-100,-100),Vec2(200,200))
    features=(
        CircleFeature(diameter=12,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(20,30)),
        RectFeature(width=24,height=14,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                    offset=Vec2(88,60),rotation_deg=90),
        ProfileFeature(points=(Vec2(-6,-5),Vec2(7,-5),Vec2(10,6),Vec2(-4,9)),
                       anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                       offset=Vec2(140,95)),
    )
    resolved=tuple(resolve_surface_features(surface,features,300,300))
    items=from_whd_resolved(resolved)
    assert [i.kind for i in items]==["circle","rectangle","profile"]
    assert items[0].radius==6
    assert items[2].points[0]==(134,90)


def test_invalid_circle_rect_profile_rejected():
    actual=demo_instructions()
    bad_circle=SimpleNamespace()
    from ae_engine.sheetmetal_features import ResolvedCircle, ResolvedRect, ResolvedProfile
    with pytest.raises(CadcraftCommandProofError,match="NON_POSITIVE_RADIUS"):
        from_whd_resolved((ResolvedCircle(center=Vec2(2,3),radius=0),))
    with pytest.raises(CadcraftCommandProofError,match="OUT_OF_RANGE_COORDINATE"):
        from_whd_resolved((ResolvedCircle(center=Vec2(float("nan"),1),radius=5),))
    with pytest.raises(CadcraftCommandProofError,match="NON_POSITIVE_RECTANGLE_DIMENSION"):
        from_whd_resolved((ResolvedRect(center=Vec2(2,3),width=-1,height=2),))
    with pytest.raises(CadcraftCommandProofError,match="SELF_INTERSECTING_OR_ZERO_AREA_PROFILE"):
        from_whd_resolved((ResolvedProfile(points=(
            Vec2(0,0),Vec2(10,10),Vec2(0,10),Vec2(10,0),
        )),))


def test_unknown_wdh_input_rejected_not_converted():
    with pytest.raises(CadcraftCommandProofError,match="UNSUPPORTED_WHD_FEATURE"):
        from_whd_resolved((object(),))

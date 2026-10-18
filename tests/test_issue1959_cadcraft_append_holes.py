"""#1959 add-only CADCraft drawing exchange -> real WHD Session.

No arbitrary DXF import: the original WHD-issued entities are an immutable
prefix, with only strictly verified new CUTTING holes appended on layer 0.
"""
import ezdxf
import pytest

from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor, Vec2,
    feature_surface_from_rect, resolve_surface_features,
)
from gui_modules.editors.cadcraft_manual_hole_return_bridge import (
    create_manual_return_ticket, stage_manual_cadcraft_return,
)
from phase6_hole_editor_session import Phase6HoleEditorSession, HoleEditorAction
from tools.issue1959_whd_cadcraft_command_draw import (
    CadcraftCommandProofError, from_whd_resolved,
)


def _fixture(tmp_path):
    surface = feature_surface_from_rect("cadcraft-append", Vec2(-100, -100),
                                        Vec2(400, 400))
    original = CircleFeature(
        10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40, 40)
    )
    features = [original]
    session = Phase6HoleEditorSession("cadcraft-append", features)
    path = tmp_path / "whd-issued-exchange.dxf"
    doc = ezdxf.new("R2010", units=ezdxf.units.MM)
    expected = from_whd_resolved(
        tuple(resolve_surface_features(surface, features, 500, 500))
    )
    doc.modelspace().add_circle(expected[0].points[0], expected[0].radius)
    doc.saveas(path)
    ticket = create_manual_return_ticket(
        output=path, features=features, session=session,
        surface=surface, width=500, height=500,
    )
    return original, features, session, path, ticket


def _add_all(path):
    doc = ezdxf.readfile(path)
    doc.modelspace().add_circle((-30, -20), 6)
    doc.modelspace().add_lwpolyline(
        [(205, 125), (225, 125), (225, 140), (205, 140)], close=True
    )
    # Exact rotated rectangle: first edge (20, 10), adjacent (-8, 16).
    doc.modelspace().add_lwpolyline(
        [(260, 220), (280, 230), (272, 246), (252, 236)], close=True
    )
    doc.modelspace().add_lwpolyline(
        [(250, 300), (266, 300), (274, 309), (261, 322), (249, 314)], close=True
    )
    doc.saveas(path)


def test_cadcraft_appends_circle_rectangle_rotated_rectangle_profile_with_confirm(tmp_path):
    original, features, session, path, ticket = _fixture(tmp_path)
    identity = id(features)
    _add_all(path)
    stage = stage_manual_cadcraft_return(ticket)
    assert stage.moves == ()
    assert len(stage.additions) == 4
    circle, rect, rotated, contour = stage.additions
    assert isinstance(circle, CircleFeature)
    assert circle.offset == Vec2(-30, -20) and circle.diameter == 12
    assert isinstance(rect, RectFeature)
    assert rect.width == 20 and rect.height == 15
    assert rect.offset == Vec2(215, 132.5)
    # WHD RectFeature allows only 90-degree rotations; preserve arbitrary
    # orientation via an equivalent ProfileFeature instead of flattening.
    assert isinstance(rotated, ProfileFeature)
    assert rotated.points == (
        Vec2(260, 220), Vec2(280, 230), Vec2(272, 246), Vec2(252, 236)
    )
    assert isinstance(contour, ProfileFeature)
    assert features[0] == original and id(features) == identity
    assert session.has_active_edit
    stage.confirm()
    assert not session.has_active_edit and len(features) == 5
    session.execute(HoleEditorAction.undo())
    assert features == [original] and id(features) == identity


def test_cadcraft_new_holes_cancel_and_stale_exchange_protection(tmp_path):
    original, features, session, path, ticket = _fixture(tmp_path)
    _add_all(path)
    staged = stage_manual_cadcraft_return(ticket)
    staged.cancel()
    assert features == [original] and not session.has_active_edit
    staged = stage_manual_cadcraft_return(ticket)
    doc = ezdxf.readfile(path)
    doc.modelspace().add_circle((345, 345), 3)
    doc.saveas(path)
    with pytest.raises(CadcraftCommandProofError, match="CHANGED_AFTER_VALIDATION"):
        staged.confirm()
    assert features == [original] and not session.has_active_edit


@pytest.mark.parametrize("modify,code", [
    (lambda d: d.header.__setitem__("$INSUNITS", 1), "MILLIMETRE_HEADER_MISMATCH"),
    (lambda d: d.modelspace().add_line((70, 70), (80, 80)), "ENTITY_COUNT_MISMATCH"),
    (lambda d: d.modelspace().add_circle((40, 40), 7), "WHD_FEATURE_COLLISION"),
    (lambda d: d.modelspace().add_circle((405, 45), 10), "OUTSIDE_WHD_PHYSICAL_SURFACE"),
    (lambda d: d.modelspace().add_circle((180, 180), -4), "INVALID_NEW_CIRCLE"),
    (lambda d: d.modelspace().add_circle((160, 160), 5,
                                        dxfattribs={"layer": "CUTTING"}),
     "NEW_HOLE_NOT_ON_EXCHANGE_LAYER"),
    (lambda d: d.modelspace().add_lwpolyline(
        [(110, 190), (125, 190), (125, 210)], close=False
    ), "ENTITY_COUNT_MISMATCH"),
    (lambda d: d.modelspace().add_lwpolyline(
        [(110, 190), (125, 190), (125, 210)], close=True,
        dxfattribs={"const_width": 1}
    ), "NEW_HOLE_POLYLINE_WIDTH"),
    (lambda d: d.modelspace().add_lwpolyline(
        [(110, 190), (125, 190), (125, 210)], close=True,
        dxfattribs={"elevation": 2}
    ), "NEW_HOLE_POLYLINE_ELEVATION"),
    (lambda d: d.modelspace().add_lwpolyline(
        [(110, 190), (125, 190), (125, 210), (110, 210)], close=True,
        dxfattribs={"thickness": 1}
    ), "NEW_HOLE_NONZERO_THICKNESS"),
    (lambda d: d.modelspace().add_lwpolyline(
        [(110, 190), (125, 210), (110, 210), (125, 190)], close=True
    ), "SELF_INTERSECTING_OR_ZERO_AREA_PROFILE"),
])
def test_cadcraft_rejects_unsafe_additions_without_committing(
    tmp_path, modify, code
):
    original, features, session, path, ticket = _fixture(tmp_path)
    doc = ezdxf.readfile(path)
    modify(doc)
    doc.saveas(path)
    with pytest.raises(CadcraftCommandProofError, match=code):
        stage_manual_cadcraft_return(ticket)
    assert features == [original] and not session.has_active_edit


def test_resize_original_cannot_be_disguised_as_new_hole(tmp_path):
    original, features, session, path, ticket = _fixture(tmp_path)
    doc = ezdxf.readfile(path)
    list(doc.modelspace())[0].dxf.radius = 7
    doc.modelspace().add_circle((215, 210), 4)
    doc.saveas(path)
    with pytest.raises(CadcraftCommandProofError, match="CIRCLE_SIZE_OR_PLANE_CHANGED"):
        stage_manual_cadcraft_return(ticket)
    assert features == [original] and not session.has_active_edit


def test_new_hole_actual_whd_manufacturing_cutting_after_confirm(tmp_path):
    from collections import Counter
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part
    from tools.issue1959_whd_real_manufacturing_parity import _signature

    # This deliberately uses original WHD's real manufacturing exporter,
    # instead of treating CADCraft's exchange DXF as a manufacturing drawing.
    orig, features, session, path, ticket = _fixture(tmp_path)
    doc = ezdxf.readfile(path)
    doc.modelspace().add_circle((150, 130), 5)
    doc.saveas(path)
    stage_manual_cadcraft_return(ticket).confirm()
    session.finish(commit=True)
    assert len(features) == 2 and features[1].offset == Vec2(150, 130)
    cfg = dict(width=500, height=600, thickness=2, frame_width=25,
               gap_w=3.5, gap_h=3.5, fold_left=19, fold_right=19,
               fold_top=19, fold_bottom=19)
    authority = tmp_path / "authority"
    authority.mkdir()
    ctx = ManufacturingContext(resource_root=authority, draw_stock=False)
    before, after = tmp_path / "before.dxf", tmp_path / "after.dxf"
    generate_part(DoorPartSpec(**cfg, features=(orig,)), before, ctx)
    generate_part(DoorPartSpec(**cfg, features=tuple(features)), after, ctx)
    old_entities = tuple(ezdxf.readfile(before).modelspace())
    new_entities = tuple(ezdxf.readfile(after).modelspace())
    assert len(new_entities) == len(old_entities) + 1
    before_sig = Counter(_signature(e) for e in old_entities)
    after_sig = Counter(_signature(e) for e in new_entities)
    assert sum((after_sig - before_sig).values()) == 1
    assert not (before_sig - after_sig)
    new_circles = [e for e in new_entities if e.dxftype() == "CIRCLE"
                   and e.dxf.layer == "CUTTING"]
    assert len(new_circles) == 2
    assert any(abs(e.dxf.radius - 5) < 1e-6 for e in new_circles)


def test_empty_whd_face_creates_first_hole_in_cadcraft_exchange_and_confirm(tmp_path):
    """First-hole path: WHD owns blank metric DXF, CADCraft adds, WHD confirms."""
    from gui_modules.editors.cadcraft_command_preview_bridge import (
        prepare_whd_cadcraft_commands, draw_whd_commands_with_cadcraft,
    )
    surface = feature_surface_from_rect("blank-face", Vec2(-100, -100),
                                        Vec2(400, 400))
    features = []
    identity = id(features)
    session = Phase6HoleEditorSession("blank-face", features)
    instructions = prepare_whd_cadcraft_commands(
        surface=surface, features=features, width=500, height=500,
    )
    assert instructions == ()
    issued = draw_whd_commands_with_cadcraft(
        instructions=instructions, executable="not-executed-for-empty-source",
        output_dir=tmp_path,
    )
    assert issued.geometry_evidence["scope"] == "EMPTY_WHD_ISSUED_EXCHANGE"
    assert issued.preview_png.read_bytes().startswith(
        bytes([137, 80, 78, 71, 13, 10, 26, 10])
    )
    empty_doc = ezdxf.readfile(issued.output_dxf)
    assert empty_doc.header["$INSUNITS"] == 4
    assert empty_doc.header["$MEASUREMENT"] == 1
    assert not list(empty_doc.modelspace())
    ticket = create_manual_return_ticket(
        output=issued.output_dxf, features=features, session=session,
        surface=surface, width=500, height=500,
    )
    with pytest.raises(CadcraftCommandProofError, match="DRAWING_NOT_EDITED"):
        stage_manual_cadcraft_return(ticket)
    # Simulated CADCraft geometry edit, followed by real WHD Session staging.
    empty_doc.modelspace().add_circle((-25, -15), 7)
    empty_doc.modelspace().add_lwpolyline(
        [(140, 130), (156, 130), (156, 143), (140, 143)], close=True
    )
    empty_doc.saveas(issued.output_dxf)
    pending = stage_manual_cadcraft_return(ticket)
    assert pending.moves == () and len(pending.additions) == 2
    assert len(features) == 2 and session.has_active_edit
    pending.cancel()
    assert not features and not session.has_active_edit
    pending = stage_manual_cadcraft_return(ticket)
    pending.confirm()
    assert id(features) == identity
    assert features[0].offset == Vec2(-25, -15)
    assert isinstance(features[1], RectFeature)
    assert features[1].offset == Vec2(148, 136.5)
    session.execute(HoleEditorAction.undo())
    assert not features


def test_empty_face_rejects_prepopulated_or_wrong_unit_seed(tmp_path):
    from gui_modules.editors.cadcraft_command_preview_bridge import (
        draw_whd_commands_with_cadcraft,
    )
    surface = feature_surface_from_rect("empty-reject", Vec2(0, 0), Vec2(300, 300))
    features = []
    session = Phase6HoleEditorSession("empty-reject", features)
    output = draw_whd_commands_with_cadcraft(
        instructions=(), executable="not-executed", output_dir=tmp_path
    ).output_dxf
    doc = ezdxf.readfile(output)
    doc.modelspace().add_circle((75, 75), 4)
    doc.saveas(output)
    with pytest.raises(CadcraftCommandProofError, match="INVALID_BLANK_EXCHANGE_DXF"):
        create_manual_return_ticket(
            output=output, features=features, session=session,
            surface=surface, width=300, height=300,
        )
    doc.modelspace().delete_all_entities()
    doc.header["$INSUNITS"] = 1
    doc.saveas(output)
    with pytest.raises(CadcraftCommandProofError, match="INVALID_BLANK_EXCHANGE_DXF"):
        create_manual_return_ticket(
            output=output, features=features, session=session,
            surface=surface, width=300, height=300,
        )


def test_blank_exchange_never_overwrites_existing_file(tmp_path):
    from gui_modules.editors.cadcraft_command_preview_bridge import (
        draw_whd_commands_with_cadcraft,
    )
    source = tmp_path / "whd-command-drawing.dxf"
    source.write_bytes(b"existing-user-file-untouched")
    with pytest.raises(CadcraftCommandProofError, match="REFUSE_TO_OVERWRITE"):
        draw_whd_commands_with_cadcraft(
            instructions=(), executable="not-executed", output_dir=tmp_path
        )
    assert source.read_bytes() == b"existing-user-file-untouched"

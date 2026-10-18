"""#1959 manual CADCraft hole movement returns only through original WHD Session."""
import ezdxf
import pytest

from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor,
    Vec2, feature_surface_from_rect, resolve_surface_features,
)
from gui_modules.editors.cadcraft_manual_hole_return_bridge import (
    create_manual_return_ticket, stage_manual_cadcraft_return,
)
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from tools.issue1959_whd_cadcraft_command_draw import (
    CadcraftCommandProofError, from_whd_resolved,
)


def _fixture(tmp_path):
    surface = feature_surface_from_rect("manual-1959", Vec2(0, 0), Vec2(300, 300))
    features = [
        CircleFeature(10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40, 40)),
        RectFeature(20, 12, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                    Vec2(95, 95), rotation_deg=90),
        ProfileFeature((Vec2(145, 145), Vec2(160, 145), Vec2(159, 165),
                        Vec2(140, 163)), FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                       Vec2(0, 0)),
    ]
    session = Phase6HoleEditorSession("manual-1959", features)
    path = tmp_path / "isolated-cadcraft.dxf"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.new("R2010", units=ezdxf.units.MM)
    instructions = from_whd_resolved(tuple(
        resolve_surface_features(surface, features, 300, 300)
    ))
    for inst in instructions:
        if inst.kind == "circle":
            doc.modelspace().add_circle(inst.points[0], inst.radius)
        else:
            doc.modelspace().add_lwpolyline(inst.points, close=True)
    doc.saveas(path)
    ticket = create_manual_return_ticket(
        output=path, features=features, session=session,
        surface=surface, width=300, height=300,
    )
    return surface, features, session, path, ticket


def _move(path, index, dx, dy):
    doc = ezdxf.readfile(path)
    entity = list(doc.modelspace())[index]
    if entity.dxftype() == "CIRCLE":
        xyz = entity.dxf.center
        entity.dxf.center = (xyz.x + dx, xyz.y + dy, xyz.z)
    else:
        entity.set_points([(x+dx, y+dy) for x,y in entity.get_points("xy")], format="xy")
    doc.saveas(path)


def test_manual_circle_rectangle_profile_moves_confirm_undo_and_list_identity(tmp_path):
    _, features, session, path, ticket = _fixture(tmp_path)
    original = tuple(features)
    address = id(features)
    for index, dx, dy in ((0, 5, 3), (1, -7, 8), (2, 4, -5)):
        _move(path, index, dx, dy)
    pending = stage_manual_cadcraft_return(ticket)
    assert pending.moves == ((0, 5, 3), (1, -7, 8), (2, 4, -5))
    assert session.has_active_edit
    assert id(features) == address
    assert features[0].offset == Vec2(45, 43)
    assert features[1].offset == Vec2(88, 103)
    assert features[2].offset == Vec2(4, -5)
    pending.confirm()
    assert not session.has_active_edit
    session.execute(HoleEditorAction.undo())
    assert tuple(features) == original and id(features) == address


def test_manual_cancel_and_unedited_output_have_no_committed_side_effect(tmp_path):
    _, features, session, path, ticket = _fixture(tmp_path)
    original = tuple(features)
    with pytest.raises(CadcraftCommandProofError, match="DRAWING_NOT_EDITED"):
        stage_manual_cadcraft_return(ticket)
    _move(path, 0, 3, 0)
    stage_manual_cadcraft_return(ticket).cancel()
    assert tuple(features) == original
    assert not session.has_active_edit


def test_extra_entities_wrong_units_and_bulge_fail_closed(tmp_path):
    _, features, session, path, ticket = _fixture(tmp_path)
    initial = tuple(features)
    doc = ezdxf.readfile(path)
    doc.modelspace().add_line((1, 1), (2, 2))
    doc.saveas(path)
    with pytest.raises(CadcraftCommandProofError, match="ENTITY_COUNT_MISMATCH"):
        stage_manual_cadcraft_return(ticket)
    assert tuple(features) == initial and not session.has_active_edit
    doc = ezdxf.readfile(path)
    doc.modelspace().delete_entity(list(doc.modelspace())[-1])
    doc.header["$INSUNITS"] = 1
    doc.saveas(path)
    with pytest.raises(CadcraftCommandProofError, match="MILLIMETRE_HEADER_MISMATCH"):
        stage_manual_cadcraft_return(ticket)
    doc.header["$INSUNITS"] = 4
    poly = list(doc.modelspace())[2]
    poly.set_points([(x, y, 0, 0, 1 if i == 1 else 0)
                     for i, (x, y) in enumerate(poly.get_points("xy"))], format="xyseb")
    doc.saveas(path)
    with pytest.raises(CadcraftCommandProofError, match="SHAPE_OR_ROTATION_CHANGED"):
        stage_manual_cadcraft_return(ticket)


def test_oversize_collision_and_changed_source_session_fail_closed(tmp_path):
    _, features, session, path, ticket = _fixture(tmp_path)
    _move(path, 0, 260, 0)
    with pytest.raises(CadcraftCommandProofError, match="OUTSIDE_WHD_PHYSICAL_SURFACE"):
        stage_manual_cadcraft_return(ticket)
    # Recreate original pristine drawing before a different manual movement.
    _, features2, session2, path2, ticket2 = _fixture(tmp_path / "second")
    _move(path2, 0, 55, 55)
    with pytest.raises(CadcraftCommandProofError, match="WHD_FEATURE_COLLISION"):
        stage_manual_cadcraft_return(ticket2)
    session2.execute(HoleEditorAction.insert(
        CircleFeature(6, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(210, 210))
    ))
    with pytest.raises(CadcraftCommandProofError, match="STALE_OR_MODIFIED_WHD_SESSION"):
        stage_manual_cadcraft_return(ticket2)


def test_tampering_after_preview_rolls_back_pending_session(tmp_path):
    _, features, session, path, ticket = _fixture(tmp_path)
    before = tuple(features)
    _move(path, 0, 3, 3)
    pending = stage_manual_cadcraft_return(ticket)
    _move(path, 1, 1, 1)
    with pytest.raises(CadcraftCommandProofError, match="CHANGED_AFTER_VALIDATION"):
        pending.confirm()
    assert not session.has_active_edit and tuple(features) == before


def test_approved_source_feature_cannot_receive_manual_return_ticket(tmp_path):
    surface, features, session, path, _ = _fixture(tmp_path)
    features[0] = CircleFeature(
        10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40, 40),
        source_type="RECEIVING_NFB_CSV",
    )
    with pytest.raises(CadcraftCommandProofError, match="UNSUPPORTED_OR_DIRTY_WHD_SOURCE"):
        create_manual_return_ticket(
            output=path, features=features, session=session,
            surface=surface, width=300, height=300,
        )


def test_manual_return_confirm_rebuilds_original_whd_manufacturing(tmp_path):
    """Actual WHD exporter sees only approved Session features, not CADCraft DXF."""
    from collections import Counter
    from ae_engine import ae
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part
    from tools.issue1959_whd_real_manufacturing_parity import _signature

    door = dict(width=500, height=600, thickness=2, frame_width=25,
                gap_w=3.5, gap_h=3.5, fold_left=19, fold_right=19,
                fold_top=19, fold_bottom=19)
    finished_width, finished_height = ae.calculate_door_finished_size(
        500, 600, 25, 3.5, 3.5, 2
    )
    surface = feature_surface_from_rect(
        "1959-real-door", Vec2(0, 0), Vec2(finished_width, finished_height)
    )
    original = CircleFeature(10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(110, 130))
    features = [original]
    session = Phase6HoleEditorSession("1959-real-door", features)
    exchange = tmp_path / "cadcraft-only-exchange.dxf"
    proof = ezdxf.new("R2010", units=ezdxf.units.MM)
    proof.modelspace().add_circle((110, 130), 5)
    proof.saveas(exchange)
    ticket = create_manual_return_ticket(
        output=exchange, features=features, session=session,
        surface=surface, width=finished_width, height=finished_height,
    )
    _move(exchange, 0, 10, -5)
    staged = stage_manual_cadcraft_return(ticket)
    assert staged.moves == ((0, 10, -5),)
    staged.confirm()
    assert features[0].offset == Vec2(120, 125)
    session.finish(commit=True)

    authority = tmp_path / "authority"
    authority.mkdir()
    context = ManufacturingContext(resource_root=authority, draw_stock=False)
    before_path = tmp_path / "whd-before.dxf"
    after_path = tmp_path / "whd-after-confirm.dxf"
    generate_part(DoorPartSpec(**door, features=(original,)), before_path, context)
    generate_part(DoorPartSpec(**door, features=tuple(features)), after_path, context)
    before_entities = list(ezdxf.readfile(before_path).modelspace())
    after_entities = list(ezdxf.readfile(after_path).modelspace())
    before = Counter(_signature(entity) for entity in before_entities)
    after = Counter(_signature(entity) for entity in after_entities)
    assert sum((before - after).values()) == 1
    assert sum((after - before).values()) == 1
    unchanged = before & after
    assert sum(unchanged.values()) == len(before_entities) - 1
    initial_hole = [e for e in before_entities if e.dxftype() == "CIRCLE"
                    and e.dxf.layer == "CUTTING"]
    final_hole = [e for e in after_entities if e.dxftype() == "CIRCLE"
                  and e.dxf.layer == "CUTTING"]
    assert len(initial_hole) == len(final_hole) == 1
    assert initial_hole[0].dxf.center.x == 342
    assert initial_hole[0].dxf.center.y == 147
    assert final_hole[0].dxf.center.x == 332
    assert final_hole[0].dxf.center.y == 142
    assert final_hole[0].dxf.radius == 5
    assert exchange != after_path and exchange.is_file()

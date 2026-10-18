"""#1959 second stage: CADCraft output may only stage into original WHD Session."""
import ezdxf
import pytest

from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor, Vec2,
    feature_surface_from_rect, resolve_surface_features,
)
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from tools.issue1959_whd_cadcraft_command_draw import from_whd_resolved
from gui_modules.editors.cadcraft_command_session_bridge import (
    CadcraftCommandProofError, stage_verified_cadcraft_drawing,
)


def _context():
    surface=feature_surface_from_rect("1959-physical-finished-face",
                                      Vec2(-100,-100),Vec2(200,200))
    candidates=(
        CircleFeature(diameter=10,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(25,30),layer="CUTTING"),
        RectFeature(width=20,height=12,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                    offset=Vec2(70,45),layer="CUTTING",rotation_deg=90),
        ProfileFeature(points=(Vec2(-20,5),Vec2(-7,4),Vec2(-5,16),Vec2(-24,20)),
                       anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                       offset=Vec2(0,0),layer="CUTTING"),
    )
    old=CircleFeature(diameter=4,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(-70,-70),layer="CUTTING")
    features=[old]
    return surface,candidates,features,Phase6HoleEditorSession("hole_editor",features)


def _cadcraft_like_output(output,surface,candidates,units=ezdxf.units.MM):
    resolved=tuple(resolve_surface_features(surface,candidates,300,300))
    instructions=from_whd_resolved(resolved)
    doc=ezdxf.new("R2010",units=units)
    for part in instructions:
        if part.kind=="circle":
            doc.modelspace().add_circle(part.points[0],part.radius)
        else:
            doc.modelspace().add_lwpolyline(part.points,close=True)
    doc.saveas(output)


def _stage(output,surface,candidates,session):
    return stage_verified_cadcraft_drawing(
        output=output,whd_candidates=candidates,session=session,
        surface=surface,width=300,height=300,
    )


def test_preview_cancel_confirm_and_undo_preserve_original_list_identity(tmp_path):
    surface,candidates,features,session=_context()
    path=tmp_path/"cadcraft-isolated.dxf"
    _cadcraft_like_output(path,surface,candidates)
    original=tuple(features)
    original_list_id=id(features)

    pending=_stage(path,surface,candidates,session)
    assert session.has_active_edit and tuple(features)==original+candidates
    assert pending.active
    pending.cancel()
    assert tuple(features)==original and not session.has_active_edit
    assert id(features)==original_list_id

    pending=_stage(path,surface,candidates,session)
    pending.confirm()
    assert not pending.active and not session.has_active_edit
    assert tuple(features)==original+candidates
    assert session.snapshot().undo_depth==1
    session.execute(HoleEditorAction.undo())
    assert tuple(features)==original and id(features)==original_list_id


def test_editor_cancel_all_reverts_even_after_stage_confirm(tmp_path):
    surface,candidates,features,session=_context()
    path=tmp_path/"cadcraft-isolated.dxf"
    _cadcraft_like_output(path,surface,candidates)
    old=tuple(features)
    _stage(path,surface,candidates,session).confirm()
    assert len(features)==4
    session.finish(commit=False)
    assert tuple(features)==old


def test_wrong_units_fail_without_touching_original_session(tmp_path):
    surface,candidates,features,session=_context()
    path=tmp_path/"bad-inch.dxf"
    _cadcraft_like_output(path,surface,candidates,units=ezdxf.units.IN)
    with pytest.raises(CadcraftCommandProofError,match="MILLIMETRE_HEADER_MISMATCH"):
        _stage(path,surface,candidates,session)
    assert len(features)==1 and not session.has_active_edit


def test_output_tampering_between_preview_and_confirm_is_fail_closed(tmp_path):
    surface,candidates,features,session=_context()
    path=tmp_path/"cadcraft-isolated.dxf"
    _cadcraft_like_output(path,surface,candidates)
    pending=_stage(path,surface,candidates,session)
    path.write_bytes(path.read_bytes()+b"tampered")
    with pytest.raises(CadcraftCommandProofError,match="CADCRAFT_OUTPUT_CHANGED_AFTER_VALIDATION"):
        pending.confirm()
    pending.cancel()
    assert len(features)==1 and not session.has_active_edit


def test_collision_and_out_of_surface_rejected_before_staging(tmp_path):
    surface,candidates,features,session=_context()
    path=tmp_path/"cadcraft-isolated.dxf"
    _cadcraft_like_output(path,surface,candidates)
    conflicting=CircleFeature(diameter=12,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                              offset=Vec2(-70,-70),layer="CUTTING")
    with pytest.raises(CadcraftCommandProofError,match="WHD_FEATURE_COLLISION"):
        _stage(path,surface,(conflicting,),session)
    assert not session.has_active_edit and len(features)==1
    outside=CircleFeature(diameter=10,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                          offset=Vec2(201,200),layer="CUTTING")
    with pytest.raises(CadcraftCommandProofError,match="OUTSIDE_WHD_PHYSICAL_SURFACE"):
        _stage(path,surface,(outside,),session)
    assert len(features)==1


def test_preexisting_active_edit_and_non_cutting_feature_never_overwritten(tmp_path):
    surface,candidates,features,session=_context()
    path=tmp_path/"cadcraft-isolated.dxf"
    _cadcraft_like_output(path,surface,candidates)
    session.execute(HoleEditorAction.select(0))
    with pytest.raises(CadcraftCommandProofError,match="PREEXISTING_ACTIVE_EDIT"):
        _stage(path,surface,candidates,session)
    session.execute(HoleEditorAction.cancel_active())
    bad=CircleFeature(diameter=10,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(25,30),layer="MARKING")
    with pytest.raises(CadcraftCommandProofError,match="ONLY_VERIFIED_WHD_CUTTING_FEATURES"):
        _stage(path,surface,(bad,),session)
    assert len(features)==1


def test_different_dxf_coordinates_or_extra_entity_rejected(tmp_path):
    surface,candidates,features,session=_context()
    path=tmp_path/"cadcraft-isolated.dxf"
    _cadcraft_like_output(path,surface,candidates)
    doc=ezdxf.readfile(path)
    circle=list(doc.modelspace())[0]
    circle.dxf.radius=100.0
    doc.saveas(path)
    with pytest.raises(CadcraftCommandProofError,match="CIRCLE_COORDINATE_OR_RADIUS_MISMATCH"):
        _stage(path,surface,candidates,session)
    assert len(features)==1
    _cadcraft_like_output(path,surface,candidates)
    doc=ezdxf.readfile(path)
    doc.modelspace().add_line((0,0),(2,2))
    doc.saveas(path)
    with pytest.raises(CadcraftCommandProofError,match="ENTITY_COUNT_MISMATCH"):
        _stage(path,surface,candidates,session)
    assert len(features)==1


def test_verified_output_is_not_manufacturing_and_no_session_is_modified_before_validation(tmp_path):
    surface,candidates,features,session=_context()
    path=tmp_path/"missing.dxf"
    with pytest.raises(CadcraftCommandProofError,match="CADCRAFT_STAGE_VALIDATION_FAILED"):
        _stage(path,surface,candidates,session)
    assert features and len(features)==1 and not session.has_active_edit

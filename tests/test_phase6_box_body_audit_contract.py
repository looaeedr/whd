import pytest

from ae_engine.box_body_structure import resolve_box_body_structure, resolve_box_body_piece_face_features
from ae_engine.contracts import BoxBodyPartSpec
from ae_engine.manufacturing_api import build_box_body_structure_render_data
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, ResolvedCircle, ResolvedProfile
from ae_engine.sheetmetal_geometry import Vec2
from phase6_box_body_structure import (
    BoxBodyStructureType,
    default_box_body_structure_state,
    set_active_structure,
    update_structure_config,
    reconcile_box_body_structure_for_total_w_change,
    set_three_piece_width,
)
from phase6_final_scene_view import _phase6_box_body_structure_meshes
from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments
from test_phase6_box_body_structure import _snapshot


def _two_piece_state():
    return set_active_structure(
        default_box_body_structure_state(), BoxBodyStructureType.TWO_PIECE_W_SPLIT
    )


def _side_back_state():
    return set_active_structure(
        default_box_body_structure_state(), BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT
    )


def _structure(state, *, w=1200.0, h=1600.0, d=400.0, t=2.0):
    snapshot = _snapshot(w=w, t=t)
    return resolve_box_body_structure(
        build_box_body_profile(snapshot), w=w, h=h, t=t, structure_state=state
    )


def test_corrupt_two_piece_saved_widths_fail_closed_in_resolver():
    state = update_structure_config(
        _two_piece_state(),
        BoxBodyStructureType.TWO_PIECE_W_SPLIT,
        {"left_w": 600.0, "right_w": 500.0, "driver": "left"},
    )
    with pytest.raises(ValueError, match="總和|不一致|corrupt|非法"):
        _structure(state)


def test_corrupt_three_piece_saved_widths_fail_closed_in_resolver():
    state = update_structure_config(
        set_active_structure(
            default_box_body_structure_state(), BoxBodyStructureType.THREE_PIECE_W_SPLIT
        ),
        BoxBodyStructureType.THREE_PIECE_W_SPLIT,
        {"left_w": 50.0, "middle_w": 1000.0, "right_w": 60.0, "driver": "side"},
    )
    with pytest.raises(ValueError, match="總和|左右|不一致|corrupt|非法"):
        _structure(state)



def test_normal_total_w_commit_reconciles_three_piece_from_last_driver():
    state = set_active_structure(
        default_box_body_structure_state(), BoxBodyStructureType.THREE_PIECE_W_SPLIT
    )
    state = set_three_piece_width(state, 1200.0, "middle", 1000)
    changed = reconcile_box_body_structure_for_total_w_change(state, 1300.0)
    cfg = changed["configs"][BoxBodyStructureType.THREE_PIECE_W_SPLIT.value]
    assert cfg["middle_w"] == pytest.approx(1000.0)
    assert cfg["left_w"] == pytest.approx(150.0)
    assert cfg["right_w"] == pytest.approx(150.0)

    # A total W that makes the remembered middle driver impossible is rejected
    # at the commit seam instead of being clamped or leaking corrupt state.
    with pytest.raises(ValueError):
        reconcile_box_body_structure_for_total_w_change(state, 900.0)

def test_side_back_assembled_mesh_stays_inside_original_w_d_envelope():
    w, d, h, t = 1200.0, 400.0, 1600.0, 2.0
    snapshot = _snapshot(w=w, t=t)
    profile = build_box_body_profile(snapshot)
    spec = BoxBodyPartSpec(
        width=w,
        height=h,
        depth=d,
        thickness=t,
        frame_width=25.0,
        fold_profile=profile_to_fold_segments(profile),
        structure_state=_side_back_state(),
    )
    render_data = build_box_body_structure_render_data(spec)
    meshes = _phase6_box_body_structure_meshes(render_data, thickness=t)
    vertices = [point for _piece, triangles in meshes for tri in triangles for point in tri]
    xs = [p[0] for p in vertices]
    zs = [p[2] for p in vertices]
    assert max(xs) - min(xs) <= w + 1e-6
    assert max(zs) - min(zs) <= d + 1e-6
    # Rear folds must remain inside the enclosure width rather than flare outward.
    assert min(xs) >= -w / 2.0 - 1e-6
    assert max(xs) <= w / 2.0 + 1e-6


@pytest.mark.parametrize("layer", ["CUTTING", "BLIND_HOLE", "MARKING", "DATUM"])
def test_cross_seam_circle_is_clipped_per_piece_and_keeps_process_layer(layer):
    structure = _structure(_two_piece_state())
    feature = CircleFeature(
        diameter=40.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(600.0, 800.0),
        layer=layer,
        source_type="audit_cross_seam",
    )
    stores = resolve_box_body_piece_face_features(
        structure,
        face_features={"back": [feature]},
        w=1200.0,
        h=1600.0,
        d=400.0,
        t=2.0,
    )
    for key in ("box_body_left", "box_body_right"):
        assert stores[key], key
        # A seam-crossing circle is no longer a full circle on either physical plate.
        assert not any(isinstance(item, ResolvedCircle) for item in stores[key])
        assert all(getattr(item, "layer", None) == layer for item in stores[key])
        assert all(isinstance(item, ResolvedProfile) for item in stores[key])
        if layer in {"MARKING", "DATUM", "BLIND_HOLE"}:
            # Non-cutting process contours must not be artificially seam-closed.
            assert all(not any(closed for _sub_layer, _pts, closed in item.layered_profiles)
                       for item in stores[key])


def test_legacy_workspace_without_structure_keeps_integral_and_uses_model_editability_for_lock():
    from phase6_designer_workspace import Phase6DesignerWorkspace

    known = Phase6DesignerWorkspace.from_snapshot({"model": "金庫型", "existing_parts": ["box_body"]})
    custom = Phase6DesignerWorkspace.from_snapshot({"model": "自訂", "existing_parts": ["box_body"]})
    legacy_unknown = Phase6DesignerWorkspace.from_snapshot({"model": "未知類型", "existing_parts": ["box_body"]})

    assert known.box_body_structure_state()["active_type"] == BoxBodyStructureType.INTEGRAL.value
    assert known.box_body_structure_state()["locked"] is True
    assert custom.box_body_structure_state()["active_type"] == BoxBodyStructureType.INTEGRAL.value
    assert custom.box_body_structure_state()["locked"] is False
    assert legacy_unknown.box_body_structure_state()["locked"] is False


def test_explicit_saved_structure_lock_wins_over_legacy_model_fallback():
    from phase6_designer_workspace import Phase6DesignerWorkspace

    explicit = default_box_body_structure_state()
    explicit["locked"] = True
    ws = Phase6DesignerWorkspace.from_snapshot({
        "model": "自訂",
        "existing_parts": ["box_body"],
        "box_body_structure": explicit,
    })
    assert ws.box_body_structure_state()["locked"] is True


def test_cross_seam_rect_cutting_is_clipped_into_each_piece_material():
    from ae_engine.sheetmetal_features import RectFeature

    structure = _structure(_two_piece_state())
    feature = RectFeature(
        width=80.0,
        height=40.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(600.0, 800.0),
        layer="CUTTING",
        source_type="audit_rect",
    )
    stores = resolve_box_body_piece_face_features(
        structure,
        face_features={"back": [feature]},
        w=1200.0, h=1600.0, d=400.0, t=2.0,
    )
    assert stores["box_body_left"] and stores["box_body_right"]
    assert all(isinstance(item, ResolvedProfile) for item in stores["box_body_left"])
    assert all(isinstance(item, ResolvedProfile) for item in stores["box_body_right"])


def test_layered_profile_is_clipped_per_sub_layer_without_process_promotion():
    from ae_engine.sheetmetal_features import ProfileFeature

    structure = _structure(_two_piece_state())
    feature = ProfileFeature(
        points=(),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(600.0, 800.0),
        layer="CUTTING",
        layered_profiles=(
            ("CUTTING", (Vec2(-30.0, -20.0), Vec2(30.0, -20.0), Vec2(30.0, 20.0), Vec2(-30.0, 20.0)), True),
            ("MARKING", (Vec2(-40.0, 0.0), Vec2(40.0, 0.0)), False),
            ("DATUM", (Vec2(-35.0, 10.0), Vec2(35.0, 10.0)), False),
        ),
        source_type="audit_layered",
    )
    stores = resolve_box_body_piece_face_features(
        structure,
        face_features={"back": [feature]},
        w=1200.0, h=1600.0, d=400.0, t=2.0,
    )
    for key in ("box_body_left", "box_body_right"):
        layers = [item.layer for item in stores[key]]
        assert "CUTTING" in layers
        assert "MARKING" in layers
        assert "DATUM" in layers
        for item in stores[key]:
            for sub_layer, _points, closed in item.layered_profiles:
                assert sub_layer == item.layer
                if sub_layer in {"MARKING", "DATUM"}:
                    assert closed is False


def test_cross_seam_cutting_changes_each_piece_material_but_marking_does_not():
    snapshot = _snapshot(w=1200.0, t=2.0)
    profile = build_box_body_profile(snapshot)

    def build(layer):
        feature = CircleFeature(
            diameter=40.0,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(600.0, 800.0),
            layer=layer,
            source_type="audit_material",
        )
        spec = BoxBodyPartSpec(
            width=1200.0, height=1600.0, depth=400.0, thickness=2.0, frame_width=25.0,
            fold_profile=profile_to_fold_segments(profile),
            structure_state=_two_piece_state(),
            face_features={"back": (feature,)},
        )
        return build_box_body_structure_render_data(spec)

    plain = BoxBodyPartSpec(
        width=1200.0, height=1600.0, depth=400.0, thickness=2.0, frame_width=25.0,
        fold_profile=profile_to_fold_segments(profile), structure_state=_two_piece_state(),
    )
    plain_data = build_box_body_structure_render_data(plain)
    cutting_data = build("CUTTING")
    marking_data = build("MARKING")
    for base_piece, cut_piece, mark_piece in zip(plain_data.pieces, cutting_data.pieces, marking_data.pieces):
        assert cut_piece.render_data.material.area < base_piece.render_data.material.area
        assert mark_piece.render_data.material.area == pytest.approx(base_piece.render_data.material.area)

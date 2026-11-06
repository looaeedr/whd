"""#2517: persisted BoxBody finished-face holes -> canonical physical 3-sheet DXF."""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2


REPO = Path(__file__).resolve().parents[1]
SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
FACE_ROLES = {"left": "left_side", "back": "back", "right": "right_side"}


def _saved():
    saved = family_policy.apply_fresh_family_defaults({}, "受電箱")
    saved.update(SOURCE)
    saved["model"] = "受電箱"
    saved["box_body_structure_state"] = api.resolve_receiving_box_body_structure_state(None)
    saved["box_body_fold_profile"] = api.build_box_body_fold_profile(saved)
    saved["endcap_fold_profiles"] = {
        role: api.build_endcap_xy_fold_profiles(saved, part_key=role)
        for role in ("head", "tail")
    }
    saved["endcap_corner_policies"] = {
        role: family_policy.endcap_corner_policy(
            "受電箱", frame_width=saved["fw"], thickness=saved["t"],
            state=saved["box_body_structure_state"],
        )
        for role in ("head", "tail")
    }
    return saved


def _faces():
    # GUI's actual saved finished-face coordinates, NOT material-sheet UV.
    # PANEL_CENTER resolves through the existing Engine Fold and face mapper.
    return {
        "left": (CircleFeature(
            8.222, FeatureAnchor.PANEL_CENTER, Vec2(0.0, 0.0)),),
        "back": (CircleFeature(
            8.444, FeatureAnchor.PANEL_CENTER, Vec2(0.0, 0.0)),),
        "right": (CircleFeature(
            8.666, FeatureAnchor.PANEL_CENTER, Vec2(0.0, 0.0)),),
    }


def _request(saved, confirmed):
    return ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            "P1", "verified-saved-faces", "set1", "bay1",
        ),
        source_dimensions_mm=SOURCE,
        operator_confirmation="saved_operator_confirmed",
        operator_snapshot=saved,
        confirmed_box_body_face_features=confirmed,
    )


def test_original_saved_finished_face_holes_reach_three_physical_dxfs(tmp_path):
    saved = _saved()
    faces = _faces()
    saved["part_face_features"] = {
        "box_body": {key: list(rows) for key, rows in faces.items()}
    }
    original = deepcopy(saved)

    specs = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_box_body_face_features=faces,
    ))
    assert tuple(specs) == ("box_body", "head", "tail")
    body = specs["box_body"]
    assert {
        key: tuple(rows) for key, rows in body.face_features.items()
    } == faces

    # Exact same PartSpec owner used by the WHD live GUI, without any separate
    # finished-face -> material/UV math or external DXF geometry.
    direct = api.build_box_body_operator_part_spec(
        saved, model_name="受電箱",
        face_features=faces,
        fold_profile=saved["box_body_fold_profile"],
        structure_state=saved["box_body_structure_state"],
        endcap_y_profiles={
            role: saved["endcap_fold_profiles"][role]["Y"]
            for role in ("head", "tail")
        },
        snapshot=saved,
    )
    assert body == direct

    context = ManufacturingContext(resource_root=REPO)
    staged_guards = []
    exported = export_verified_resolved_integration_bays(
        (_request(saved, faces),), tmp_path / "verified",
        context=context, pre_commit_guard=lambda: staged_guards.append("current"),
    )
    assert staged_guards == ["current", "current"]
    assert exported.physical_dxf_roundtrip_verified
    assert not exported.complete_assembly_certified
    assert len(exported.output_files) == 5  # three Body sheets plus Head/Tail

    rendered = api.build_box_body_structure_render_data(body, context)
    assert {piece.role for piece in rendered.pieces} == set(FACE_ROLES.values())
    for face, role in FACE_ROLES.items():
        piece = next(p for p in rendered.pieces if p.role == role)
        output = next(
            Path(p) for p in exported.output_files.values()
            if "box_body" in Path(p).stem and role in Path(p).stem
        )
        reopened = ezdxf.readfile(output)
        assert reopened.audit().errors == []
        assert any(
            entity.dxftype() == "CIRCLE"
            and entity.dxf.layer == "CUTTING"
            and abs(float(entity.dxf.radius) - faces[face][0].diameter / 2.0) < 1e-6
            for entity in reopened.modelspace()
        ), (face, output)
        assert api.verify_saved_part_render_data_dxf(
            piece.render_data, output,
        ).ok
    assert saved == original


@pytest.mark.parametrize("variant,code", (
    ("omitted", "RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED"),
    ("missing_back", "RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED"),
    ("mismatch_left", "RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED"),
    ("illegal_role", "RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED"),
    ("illegal_layer", "RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED"),
    ("illegal_anchor", "RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED"),
    ("nonfinite", "RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED"),
    ("malformed_saved", "RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED"),
))
def test_unconfirmed_or_malformed_finished_face_source_cannot_output_dxf(
    tmp_path, variant, code,
):
    saved = _saved()
    faces = _faces()
    saved["part_face_features"] = {
        "box_body": {key: list(rows) for key, rows in faces.items()}
    }
    confirmed = dict(faces)
    if variant == "omitted":
        confirmed = None
    elif variant == "missing_back":
        confirmed.pop("back")
    elif variant == "mismatch_left":
        confirmed["left"] = (CircleFeature(
            10.0, FeatureAnchor.PANEL_CENTER, Vec2(0.0, 0.0)),)
    elif variant == "illegal_role":
        confirmed["front"] = confirmed.pop("back")
    elif variant == "illegal_layer":
        confirmed["back"] = (CircleFeature(
            8.444, FeatureAnchor.PANEL_CENTER, Vec2(0.0, 0.0),
            layer="MARKING"),)
    elif variant == "illegal_anchor":
        confirmed["back"] = (CircleFeature(
            8.444, "missing", Vec2(0.0, 0.0)),)
    elif variant == "nonfinite":
        confirmed["back"] = (CircleFeature(
            8.444, FeatureAnchor.PANEL_CENTER, Vec2(float("nan"), 0.0)),)
    elif variant == "malformed_saved":
        saved["part_face_features"]["box_body"] = []

    before = deepcopy(saved)
    with pytest.raises(ValueError, match=code):
        export_verified_resolved_integration_bays(
            (_request(saved, confirmed),), tmp_path / "blocked",
            context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert saved == before
    assert not list(tmp_path.rglob("*.dxf"))


def test_independently_confirmed_face_source_is_supported_without_gui_saved_rows():
    saved = _saved()
    assert "part_face_features" not in saved
    faces = _faces()
    spec = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_box_body_face_features=faces,
    ))["box_body"]
    assert {k: tuple(v) for k, v in spec.face_features.items()} == faces


def test_fresh_family_can_use_independently_confirmed_finished_face_cutting():
    faces = _faces()
    part = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_box_body_face_features=faces,
    ))["box_body"]
    assert {k: tuple(v) for k, v in part.face_features.items()} == faces


def test_physical_sheet_and_finished_face_sources_do_not_confuse_roles():
    saved = _saved()
    faces = _faces()
    saved["part_face_features"] = {
        "box_body": {k: list(v) for k, v in faces.items()}
    }
    saved["physical_piece_features"] = {}
    spec = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved,
        confirmed_box_body_piece_features={},
        confirmed_box_body_face_features=faces,
    ))["box_body"]
    assert {k: tuple(v) for k, v in spec.face_features.items()} == faces
    assert not spec.physical_piece_features

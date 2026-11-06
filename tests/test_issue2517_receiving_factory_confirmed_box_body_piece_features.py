"""#2517 Receiving saved three physical Body sheets: Engine hole source -> verified DXF."""
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
ROLES = ("left_side", "back", "right_side")


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


def _features():
    # Material-sheet UV (not finished cabinet W/H) and unique radii enable
    # detection of the three *actual* physical CUTTING holes after DXF reload.
    return {
        "box_body:left_side": (CircleFeature(
            8.222, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(85.0, 140.0)),),
        "box_body:back": (CircleFeature(
            8.444, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(370.0, 140.0)),),
        "box_body:right_side": (CircleFeature(
            8.666, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(85.0, 140.0)),),
    }


def _request(saved, confirmed, *, confirmation="saved_operator_confirmed"):
    return ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            "P1", "real-confirmed-source", "set1", "bay1",
        ),
        source_dimensions_mm=SOURCE,
        operator_confirmation=confirmation,
        operator_snapshot=saved if confirmation == "saved_operator_confirmed" else None,
        confirmed_box_body_piece_features=confirmed,
    )


def test_original_three_sheet_holes_generate_verified_independent_dxfs(tmp_path):
    saved = _saved()
    features = _features()
    saved["physical_piece_features"] = {
        key: list(rows) for key, rows in features.items()
    }
    original = deepcopy(saved)
    parts = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_box_body_piece_features=features,
    ))
    assert tuple(parts) == ("box_body", "head", "tail")
    assert {
        key: tuple(rows) for key, rows in parts["box_body"].physical_piece_features.items()
    } == features
    assert saved == original

    # Same Engine spec projection as a GUI caller on the exact saved source.
    direct = api.build_box_body_operator_part_spec(
        saved, model_name="受電箱",
        fold_profile=saved["box_body_fold_profile"],
        structure_state=saved["box_body_structure_state"],
        endcap_y_profiles={
            role: saved["endcap_fold_profiles"][role]["Y"]
            for role in ("head", "tail")
        },
        snapshot=saved,
    )
    assert direct == parts["box_body"]

    checks = []
    context = ManufacturingContext(resource_root=REPO)
    result = export_verified_resolved_integration_bays(
        (_request(saved, features),), tmp_path / "verified",
        context=context, pre_commit_guard=lambda: checks.append("source-current"),
    )
    assert checks == ["source-current", "source-current"]
    assert result.physical_dxf_roundtrip_verified
    assert result.complete_assembly_certified is False
    assert len(result.output_files) == 5  # three sheets + Head + Tail

    physical = api.build_box_body_structure_render_data(parts["box_body"], context)
    assert {piece.role for piece in physical.pieces} == set(ROLES)
    for piece in physical.pieces:
        path = next(
            Path(filename) for filename in result.output_files.values()
            if "box_body" in Path(filename).stem and piece.role in Path(filename).stem
        )
        reopened = ezdxf.readfile(path)
        assert reopened.audit().errors == []
        hole = features[f"box_body:{piece.role}"][0]
        assert any(
            item.dxftype() == "CIRCLE"
            and item.dxf.layer == "CUTTING"
            and abs(float(item.dxf.radius) - hole.diameter / 2.0) < 1e-6
            for item in reopened.modelspace()
        ), piece.role
        assert api.verify_saved_part_render_data_dxf(
            piece.render_data, path,
        ).ok
    assert saved == original


@pytest.mark.parametrize("variant,code", (
    ("not_confirmed", "RECEIVING_FACTORY_BOX_BODY_PIECE_FEATURE_SOURCE_UNCONFIRMED"),
    ("caller_forged", "RECEIVING_FACTORY_BOX_BODY_PIECE_FEATURE_SOURCE_UNCONFIRMED"),
    ("missing_saved", "RECEIVING_FACTORY_BOX_BODY_PIECE_FEATURE_SOURCE_UNCONFIRMED"),
    ("wrong_role", "RECEIVING_FACTORY_BOX_BODY_PIECE_FEATURE_SOURCE_UNCONFIRMED"),
    ("wrong_layer", "RECEIVING_FACTORY_BOX_BODY_PIECE_FEATURE_SOURCE_UNCONFIRMED"),
    ("wrong_anchor", "RECEIVING_FACTORY_BOX_BODY_PIECE_FEATURE_SOURCE_UNCONFIRMED"),
    ("bad_coordinate", "RECEIVING_FACTORY_BOX_BODY_PIECE_FEATURE_SOURCE_UNCONFIRMED"),
    ("legacy_conflict", "RECEIVING_FACTORY_BOX_BODY_PIECE_FEATURE_SOURCE_UNCONFIRMED"),
    ("unconfirmed_face", "RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED"),
))
def test_unconfirmed_or_corrupt_original_three_sheet_source_never_commits(
    tmp_path, variant, code,
):
    saved = _saved()
    original = _features()
    saved["physical_piece_features"] = {
        key: list(rows) for key, rows in original.items()
    }
    confirmed = dict(original)
    if variant == "not_confirmed":
        confirmed = None
    elif variant == "caller_forged":
        confirmed["box_body:back"] = (
            CircleFeature(10.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(370.0, 140.0)),
        )
    elif variant == "missing_saved":
        saved["physical_piece_features"] = {}
    elif variant == "wrong_role":
        confirmed["box_body:divider:a"] = confirmed.pop("box_body:back")
    elif variant == "wrong_layer":
        confirmed["box_body:back"] = (
            CircleFeature(8.444, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                          Vec2(370.0, 140.0), layer="MARKING"),
        )
    elif variant == "wrong_anchor":
        confirmed["box_body:back"] = (
            CircleFeature(8.444, FeatureAnchor.PANEL_CENTER, Vec2(370.0, 140.0)),
        )
    elif variant == "bad_coordinate":
        confirmed["box_body:back"] = (
            CircleFeature(8.444, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                          Vec2(float("nan"), 140.0)),
        )
    elif variant == "legacy_conflict":
        saved["part_features"] = {
            "box_body:back": [CircleFeature(
                11.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                Vec2(370.0, 140.0),
            )],
        }
    elif variant == "unconfirmed_face":
        saved["box_body_face_features"] = {
            "left": [original["box_body:left_side"][0]],
        }

    frozen = deepcopy(saved)
    with pytest.raises(ValueError, match=code):
        export_verified_resolved_integration_bays(
            (_request(saved, confirmed),), tmp_path / "blocked",
            context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert saved == frozen
    assert not list(tmp_path.rglob("*.dxf"))


def test_legacy_saved_sheet_holes_are_not_dropped_or_reinterpreted(tmp_path):
    saved = _saved()
    features = _features()
    saved["part_features"] = {
        key: list(rows) for key, rows in features.items()
    }
    # Older projects have no physical_piece_features key; the Engine's
    # canonical BoxBody owner still resolves exactly the confirmed old store.
    assert "physical_piece_features" not in saved
    parts = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_box_body_piece_features=features,
    ))
    assert {
        key: tuple(rows) for key, rows in parts["box_body"].physical_piece_features.items()
    } == features


def test_untrusted_fresh_family_cannot_gain_body_hole_certification():
    with pytest.raises(
        ValueError, match="RECEIVING_FACTORY_BOX_BODY_FEATURES_REQUIRE_SAVED_OPERATOR",
    ):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="fresh_family_confirmed",
            confirmed_box_body_piece_features=_features(),
        )


def test_outside_confirmed_sheet_hole_fails_real_finalscene_without_dxf(tmp_path):
    saved = _saved()
    features = _features()
    feature = CircleFeature(
        8.444, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(9999.0, 9999.0),
    )
    features["box_body:back"] = (feature,)
    saved["physical_piece_features"] = {
        key: list(rows) for key, rows in features.items()
    }
    with pytest.raises(ValueError, match="feature outside feature surface"):
        export_verified_resolved_integration_bays(
            (_request(saved, features),), tmp_path / "rejected",
            context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert not list(tmp_path.rglob("*.dxf"))

"""#2517: saved Head/Tail holes cannot be erased by trusted Bay source export."""
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


SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
REPO = Path(__file__).resolve().parents[1]


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


def _holes():
    return {
        "head": (CircleFeature(
            6.374, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            Vec2(390.0, 150.0),
        ),),
        "tail": (CircleFeature(
            6.758, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            Vec2(390.0, 160.0),
        ),),
    }


def _verified_request(saved, confirmed):
    return ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            "P1", "saved-source", "set-1", "bay-1",
        ),
        source_dimensions_mm=SOURCE,
        operator_confirmation="saved_operator_confirmed",
        operator_snapshot=saved,
        confirmed_endcap_features=confirmed,
    )


def test_saved_matching_head_tail_holes_survive_actual_verified_dxf(tmp_path):
    saved = _saved()
    holes = _holes()
    saved["part_features"] = {role: list(rows) for role, rows in holes.items()}
    before = deepcopy(saved)

    specs = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_endcap_features=holes,
    ))
    assert tuple(specs) == ("box_body", "head", "tail")
    for role in ("head", "tail"):
        assert tuple(specs[role].holes) == holes[role]
    assert saved == before

    checks = []
    context = ManufacturingContext(resource_root=REPO)
    exported = export_verified_resolved_integration_bays(
        (_verified_request(saved, holes),),
        tmp_path / "manufactured", context=context,
        pre_commit_guard=lambda: checks.append("source-current"),
    )
    assert checks == ["source-current", "source-current"]
    assert exported.physical_dxf_roundtrip_verified
    assert not exported.complete_assembly_certified
    assert len(exported.output_files) == 5  # 3 physical Body + Head/Tail
    for role in ("head", "tail"):
        path = next(
            Path(output) for output in exported.output_files.values()
            if Path(output).name.endswith(f"{role}.dxf")
        )
        reopened = ezdxf.readfile(path)
        assert reopened.audit().errors == []
        assert any(
            entity.dxftype() == "CIRCLE"
            and entity.dxf.layer == "CUTTING"
            and abs(float(entity.dxf.radius) - holes[role][0].diameter / 2) < 1e-6
            for entity in reopened.modelspace()
        ), role
        scene = api.build_operator_part_render_data(specs[role], context)
        assert api.verify_saved_part_render_data_dxf(scene, path).ok
    assert saved == before


@pytest.mark.parametrize("variant", (
    "head_unconfirmed", "tail_unconfirmed",
    "head_mismatch", "tail_mismatch",
    "saved_role_none", "saved_role_false",
))
def test_saved_endcap_holes_never_get_lost_or_substituted(tmp_path, variant):
    saved = _saved()
    holes = _holes()
    saved["part_features"] = {role: list(rows) for role, rows in holes.items()}
    submitted = dict(holes)
    if variant == "head_unconfirmed":
        submitted.pop("head")
    elif variant == "tail_unconfirmed":
        submitted.pop("tail")
    elif variant == "head_mismatch":
        submitted["head"] = (CircleFeature(
            10.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(390.0, 150.0)),)
    elif variant == "tail_mismatch":
        submitted["tail"] = (CircleFeature(
            10.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(390.0, 160.0)),)
    elif variant == "saved_role_none":
        saved["part_features"]["head"] = None
    elif variant == "saved_role_false":
        saved["part_features"]["head"] = False

    before = deepcopy(saved)
    with pytest.raises(ValueError, match="RECEIVING_SAVED_ENDCAP_SOURCE_FEATURES_MISMATCH"):
        export_verified_resolved_integration_bays(
            (_verified_request(saved, submitted),), tmp_path / "blocked",
            context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert saved == before
    assert not list(tmp_path.rglob("*.dxf"))


def test_external_confirmed_endcap_cutting_without_saved_role_still_allowed():
    # A CADSplit-verified source is not necessarily authored into WHD's GUI
    # saved PartFeatures, and must not be discarded just for that reason.
    saved = _saved()
    saved["part_features"] = {}
    holes = _holes()
    specs = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_endcap_features=holes,
    ))
    assert tuple(specs["head"].holes) == holes["head"]
    assert tuple(specs["tail"].holes) == holes["tail"]


def test_invalid_unrelated_door_source_keeps_door_error_owner():
    # The EndCap gate may not replace established Door saved-state diagnostics
    # when no head/tail feature source exists.
    saved = _saved()
    saved["part_features"] = False
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="saved_operator_confirmed",
            operator_snapshot=saved,
            confirmed_door_layout_columns=((800.0, (1600.0,)),),
        )

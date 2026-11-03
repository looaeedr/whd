"""#2517 Receiving confirmed Door CUTTING Feature source, no parallel exporter."""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    ManufacturingIntegrationRequest, dispatch_manufacturing_integration,
    export_verified_resolved_integration_bays,
)
from ae_engine.sheetmetal_feature_core import (
    CircleFeature, RectFeature, FeatureAnchor,
)
from ae_engine.sheetmetal_geometry import Vec2

REPO = Path(__file__).resolve().parents[1]
SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
COLUMNS = ((800.0, (1100.0, 500.0)),)
UPPER = "door_c1_r1"
LOWER = "door_c1_r2"


def _hole():
    return CircleFeature(
        diameter=13.75, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(100.0, 100.0), layer="CUTTING",
    )


def _saved():
    saved = family_policy.apply_fresh_family_defaults({}, "受電箱")
    saved.update(SOURCE)
    saved["box_body_structure_state"] = manufacturing_api.resolve_receiving_box_body_structure_state(None)
    saved["box_body_fold_profile"] = manufacturing_api.build_box_body_fold_profile(saved)
    saved["endcap_fold_profiles"] = {
        key: manufacturing_api.build_endcap_xy_fold_profiles(saved, part_key=key)
        for key in ("head", "tail")
    }
    saved["endcap_corner_policies"] = {
        key: family_policy.endcap_corner_policy(
            "受電箱", frame_width=saved["fw"], thickness=saved["t"],
            state=saved["box_body_structure_state"],
        ) for key in ("head", "tail")
    }
    return saved


def _request(features, *, confirmation="fresh_family_confirmed", saved=None):
    return ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity("P1", "verified-source", "Set1", "Bay1"),
        source_dimensions_mm=SOURCE, operator_confirmation=confirmation,
        operator_snapshot=saved, door_layout_columns=COLUMNS,
        confirmed_door_features=features,
    )


def test_source_and_gui_confirmed_inputs_are_same_engine_part_spec():
    features = {UPPER: (_hole(),), LOWER: ()}
    raw = deepcopy(features)
    parts = manufacturing_api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=COLUMNS, confirmed_door_features=features,
    )
    assert features == raw
    specs = dict(parts)
    assert tuple(specs) == ("box_body", "head", "tail", UPPER, LOWER)
    assert type(specs[UPPER]) is DoorPartSpec
    assert specs[UPPER].features == (_hole(),)
    assert specs[UPPER].feature_space == "finished_face"
    assert specs[LOWER].features == ()
    direct = manufacturing_api.map_door_features_to_unfolded_material(specs[UPPER])
    assert len(direct) == 1 and direct[0].diameter == _hole().diameter


def test_confirmed_door_cutting_is_present_in_reopened_dxf(tmp_path):
    dest = tmp_path / "verified"
    checked = []
    result = export_verified_resolved_integration_bays(
        (_request({UPPER: (_hole(),)}),), dest,
        context=ManufacturingContext(resource_root=REPO),
        pre_commit_guard=lambda: checked.append("revalidated"),
    )
    assert checked == ["revalidated", "revalidated"]
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert not result.external_cli_enabled
    assert len(result.output_files) == 7
    upper = next(Path(p) for p in result.output_files.values()
                 if Path(p).name.endswith(f"{UPPER}.dxf"))
    lower = next(Path(p) for p in result.output_files.values()
                 if Path(p).name.endswith(f"{LOWER}.dxf"))
    reopened = ezdxf.readfile(upper)
    circles = [entity for entity in reopened.modelspace()
               if entity.dxftype() == "CIRCLE" and entity.dxf.layer == "CUTTING"]
    assert any(abs(float(circle.dxf.radius) - 6.875) < 1e-6 for circle in circles)
    assert "CUTTING" in {e.dxf.layer for e in ezdxf.readfile(lower).modelspace()}


def test_saved_operator_hole_source_matches_explicit_confirmation():
    saved = _saved()
    saved["part_features"] = {UPPER: [_hole()], LOWER: []}
    frozen = deepcopy(saved)
    parts = manufacturing_api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_door_layout_columns=COLUMNS,
        confirmed_door_features={UPPER: (_hole(),)},
    )
    assert dict(parts)[UPPER].features == (_hole(),)
    assert saved == frozen


@pytest.mark.parametrize("features,code", [
    ({UPPER: ()}, "RECEIVING_SAVED_DOOR_SOURCE_FEATURES_MISMATCH"),
    ({LOWER: (_hole(),)}, "RECEIVING_SAVED_DOOR_SOURCE_FEATURES_MISMATCH"),
    ({UPPER: (CircleFeature(8.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                            Vec2(float("nan"), 100.0)),)}, "RECEIVING_DOOR_SOURCE_FEATURES_INVALID"),
    ({UPPER: (CircleFeature(8.0, FeatureAnchor.PANEL_CENTER,
                            Vec2(20.0, 20.0)),)}, "RECEIVING_DOOR_SOURCE_FEATURES_INVALID"),
    ({UPPER: (RectFeature(20.0, 20.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                          Vec2(40.0, 40.0), layer="MARKING"),)}, "RECEIVING_DOOR_SOURCE_FEATURES_INVALID"),
    ({"door_c3_r4": (_hole(),)}, "RECEIVING_DOOR_SOURCE_FEATURES_INVALID"),
    ({UPPER: (object(),)}, "RECEIVING_DOOR_SOURCE_FEATURES_INVALID"),
])
def test_unconfirmed_or_invalid_saved_features_do_not_stage_dxf(features, code, tmp_path):
    saved = _saved()
    saved["part_features"] = {UPPER: [_hole()]}
    out = tmp_path / "out"
    with pytest.raises(ValueError, match=code):
        export_verified_resolved_integration_bays(
            (_request(features, confirmation="saved_operator_confirmed", saved=saved),),
            out, pre_commit_guard=lambda: None,
        )
    assert not out.exists()


def test_fresh_door_features_need_confirmed_topology_and_original_source(tmp_path):
    with pytest.raises(ValueError, match="RECEIVING_DOOR_LAYOUT_REQUIRED_FOR_FEATURES"):
        manufacturing_api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="fresh_family_confirmed",
            confirmed_door_features={UPPER: (_hole(),)},
        )
    with pytest.raises(ValueError, match="RECEIVING_OPERATOR_CONFIRMATION_REQUIRED"):
        manufacturing_api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmed_door_layout_columns=COLUMNS,
            confirmed_door_features={UPPER: (_hole(),)},
        )
    refused = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest(
            "export", "受電箱",
            ManufacturingSourceIdentity("P1", "raw-source", "Set1", "Bay1"),
        ),
    )
    assert refused.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"
    assert not refused.manufacturing_authorized
    assert not (tmp_path / "out").exists()

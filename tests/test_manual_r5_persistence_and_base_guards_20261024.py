# -*- coding: utf-8 -*-
"""Independent source-verified R5 contract gaps found absent from merged localX."""
import pytest

from ae_engine.receiving_assignment_core import validate_positions
from ae_engine.receiving_base_fixing_plate import receiving_base_fixing_plate_previews
from ae_engine.receiving_base_fixing_plate_mating import resolve_base_fixing_plate_xy_mating
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_nfb_persistence import contains_submitted_nfb
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
from phase6_project_file import _normalize_authoritative_door_state
from phase6_quantity_model import (
    QUANTITY_MODE, normalize_quantity_snapshot, quantity_only_change,
)


def _quantity():
    return {
        "schema": "phase6-quantity-v1",
        "versions": [{"version_id": "quantity-v1", "piece_count": 2,
                      "head_features": [], "tail_features": []}],
        "selected_version_id": "quantity-v1",
        "next_version_number": 2,
    }


def test_r5_workspace_quantity_is_promoted_before_save_strips_nested_alias():
    model = _quantity()
    snapshot = {"active_mode": QUANTITY_MODE,
                "workspace": {"active_mode": QUANTITY_MODE, "quantity": model}}
    saved = normalize_quantity_snapshot(snapshot, for_save=True)
    assert saved["quantity"]["versions"][0]["piece_count"] == 2
    assert "quantity" not in saved.get("workspace", {})
    assert not quantity_only_change(
        {"active_mode": QUANTITY_MODE, "quantity": model,
         "workspace": {"quantity": model}},
        {"active_mode": QUANTITY_MODE, "quantity": model,
         "workspace": {"quantity": "invalid"}},
    )


def test_r5_multibay_allocation_rejects_bool_index_that_compares_equal_to_zero():
    valid = {"sets": [{"bays": [{}]}]}
    good = validate_positions(valid, ["v1"], {"v1": 1}, {(0, 0): "v1"})
    assert good == ((0, 0),)
    for layout, counts, assigned in (
        ({"sets": ["invalid"]}, None, {(0, 0): "v1"}),
        (valid, [True], {(0, 0): "v1"}),
        (valid, None, {(False, False): "v1"}),
    ):
        with pytest.raises(ValueError):
            validate_positions(layout, ["v1"], {"v1": 1}, assigned,
                               expected_counts=counts)


def test_r5_project_saved_door_authority_rejects_bool_nan_and_invalid_heights():
    for snapshot in (
        {"door_nameplate_center_datum_top": True},
        {"door_nameplate_center_datum_top": float("nan")},
        {"door_layout_columns": [[True, [500.]]]},
        {"door_layout_columns": [[400., "500"]]},
        {"door_layout_columns": [[400., [float("nan")]]]},
    ):
        with pytest.raises(ValueError):
            _normalize_authoritative_door_state(snapshot)


def test_r5_receiving_base_configuration_rejects_boolean_geometry():
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_CONFIG_INVALID"):
        receiving_base_plate_values({
            "model": "受電箱",
            "receiving_base_plate": {
                "pattern": RECEIVING_BASE_PATTERN_LEFT,
                "height": True, "shrink_top": 20., "shrink_bottom": 20.,
                "shrink_left": 20., "shrink_right": 20., "bend": 20.,
            },
        })


def test_r5_base_fixing_plate_preview_rejects_boolean_width():
    assert receiving_base_fixing_plate_previews({
        "model": "受電箱", "w": True, "t": 2.,
        "receiving_base_plate": {"pattern": RECEIVING_BASE_PATTERN_LEFT},
    }, available_parts=("base_plate",)) == ()


def test_r5_real_base_fixing_plate_xy_source_rejects_corrupt_dimension():
    with pytest.raises(ValueError, match="FIXING_PLATE_GEOMETRY_NONFINITE"):
        resolve_base_fixing_plate_xy_mating({
            "model": "受電箱", "w": float("nan"), "t": 2.,
            "receiving_base_plate": {"pattern": RECEIVING_BASE_PATTERN_LEFT},
        }, side="left")


def test_r5_malformed_nfb_submission_inventory_never_raises_or_claims_true():
    for invalid in (
        {"receiving_layout": {"sets": "bad"}},
        {"receiving_layout": {"sets": ["bad"]}},
        {"receiving_layout": {"sets": [{"bays": "bad"}]}},
        {"quantity": {"versions": "bad"}},
    ):
        assert contains_submitted_nfb(invalid) is False
    assert contains_submitted_nfb(
        {"quantity": {"versions": [{"nfb_config_submitted": True}]}}
    ) is True


def test_r6_invalid_v5_and_legacy_model_identity_does_not_become_source():
    from ae_engine.receiving_nfb_model_identity import (
        validate_stored_model_ref, display_model_ref,
    )
    for invalid in ("  TEST.dxf", "TEST .dxf ", "AB:C.dxf", ".dxf", " : .dxf"):
        with pytest.raises(ValueError):
            validate_stored_model_ref(invalid)
    with pytest.raises(ValueError, match="NFB V5"):
        display_model_ref("nfbv5:士林:MODEL:INVALID")


def test_r6_v5_numeric_csv_forbids_identity_delimiter(tmp_path):
    from ae_engine.receiving_nfb_numeric_catalog import HEADER, read_numeric_specs
    source = tmp_path / "NFB數值規格.csv"
    source.write_text(
        ",".join(HEADER) + "\n" + "BAD:MODEL,60,100,40,50X90,25X80,5,0,0\n",
        encoding="utf-8-sig",
    )
    with pytest.raises(ValueError, match="型號不合法"):
        read_numeric_specs("士林", path=source)


def test_r6_pad_tooling_rejects_fake_sha_and_boolean_dimension(tmp_path):
    from ae_engine.receiving_nfb_pad_generator import PadToolingRule, read_pad_tooling_rule
    valid = {
        "revision": "test",
        "source_dxf_sha256": "a"*64,
        "tab_projection_mm": 2., "tab_height_mm": 2.,
        "tab_end_inset_mm": 5., "base_square_side_mm": 4.,
        "base_square_center_inset_x_mm": 10.,
    }
    PadToolingRule(**valid).validate()
    for field, value in (("source_dxf_sha256", "z"*64), ("tab_height_mm", True)):
        invalid = dict(valid, **{field: value})
        with pytest.raises(ValueError):
            PadToolingRule(**invalid).validate()
    path = tmp_path / "bad-tooling.json"
    path.write_text('{"schema":"RECEIVING_NFB_PAD_TOOLING_V1"}', encoding="utf-8")
    with pytest.raises(ValueError, match="加工規則格式"):
        read_pad_tooling_rule(path)


def test_r6_nfb_depth_and_surface_chain_reject_bool_mechanical_dimensions():
    from ae_engine.receiving_nfb_depth_surface_policy import (
        receiving_nfb_second_side_fold_mm, resolve_receiving_nfb_surface_chain,
    )
    with pytest.raises(ValueError, match="must not be boolean"):
        receiving_nfb_second_side_fold_mm(
            reference_nfb_depth_mm=True,
            secondary_nfb_depth_mm=60., base_plate_thickness_mm=1.5,
        )
    with pytest.raises(ValueError, match="must not be boolean"):
        resolve_receiving_nfb_surface_chain(
            inner_door_outer_face_from_front_mm=True,
            inner_door_thickness_mm=1.5,
            base_plate_thickness_mm=1.5,
            fixing_plate_thickness_mm=1.5,
            reference_nfb_depth_mm=60., secondary_nfb_depth_mm=30.,
        )

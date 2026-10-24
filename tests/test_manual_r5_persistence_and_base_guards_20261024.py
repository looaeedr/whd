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

@pytest.mark.parametrize("invalid_mode", [[], {}, ["quantity"], {"mode": "quantity"}, True, 1])
def test_r5_90_saved_mode_cannot_be_a_noncanonical_object(invalid_mode):
    """Corrupt saved mode is invalid project data, never an unhandled TypeError."""
    with pytest.raises(ValueError, match="不合法的箱體操作模式"):
        normalize_quantity_snapshot({"active_mode": invalid_mode}, for_save=True)

@pytest.mark.parametrize("bad", [None, True, False, -1., float("nan"), float("inf"), "-1", "0.1", [], {}])
def test_r5_76_dxf_acceptance_rejects_invalid_tolerances_before_readback(tmp_path, bad):
    """Untrusted verification tolerances must never be able to bless invalid CUTTING."""
    from ae_engine.dxf_acceptance import (
        _rows_close, _circle_rows_close, verify_saved_part_render_data_dxf,
    )
    from types import SimpleNamespace

    assert _rows_close(((("BEND", 1., 2.),)), ((("BEND", 1., 2.),)), bad) is False
    assert _circle_rows_close(((1., 2., 3.),), ((1., 2., 3.),), bad) is False
    for field in ("coordinate_tolerance", "area_tolerance"):
        result = verify_saved_part_render_data_dxf(
            SimpleNamespace(), tmp_path / "nonexistent.dxf", **{field: bad},
        )
        assert result.ok is False
        assert result.issues[0].category == "INVALID_TOLERANCE"


def test_r5_76_dxf_readback_rejects_nonfinite_area_tolerance_on_real_changed_cutting(tmp_path):
    """The saved DXF is independently reopened: NaN area tolerance cannot erase a mismatch."""
    import ezdxf
    from ae_engine import manufacturing_api as api
    from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
    from ae_engine.sheetmetal_geometry import Vec2

    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        points=(Vec2(0., 0.), Vec2(100., 0.), Vec2(100., 60.), Vec2(0., 60.)),
        layer="CUTTING", closed=True,
    ))
    render = api.PartRenderData(
        scene=scene,
        material=api.material_polygon_from_final_scene(scene),
        fold_guides=api.fold_guides_from_final_scene(scene),
    )
    path = tmp_path / "r5-76-changed-cutting.dxf"
    api.save_part_render_data_dxf(render, path, overwrite=True)
    doc = ezdxf.readfile(path)
    outline = tuple(doc.modelspace().query('LWPOLYLINE[layer=="CUTTING"]'))[0]
    pts = list(outline.get_points())
    pts[1] = (95., pts[1][1], *pts[1][2:])
    outline.set_points(pts)
    doc.saveas(path)

    good = api.verify_saved_part_render_data_dxf(render, path)
    assert good.ok is False
    assert any(issue.category == "CUTTING_MISMATCH" for issue in good.issues)
    blocked = api.verify_saved_part_render_data_dxf(render, path, area_tolerance=float("nan"))
    assert blocked.ok is False
    assert blocked.issues[0].category == "INVALID_TOLERANCE"

@pytest.mark.parametrize("origin,normal", [
    ((0., 0.), (0., 0., 1.)),
    ((0., 0., float("nan")), (0., 0., 1.)),
    ((0., 0., 0.), (0., 0.)),
    ((0., 0., 0.), (0., float("inf"), 1.)),
    ((True, 0., 0.), (0., 0., 1.)),
    ((0., 0., 0.), (0., 0., True)),
])
def test_r5_77_expected_mating_coverage_must_fail_closed_on_bad_plane(origin, normal):
    """Old R5 #77 RED: 2D origin must not raise a bare IndexError."""
    from ae_engine.joint_marking_policy import (
        ResolvedPhysicalMatingRegion, validate_expected_region_coverage,
    )
    triangle = ((0., 0., 0.), (10., 0., 0.), (10., 10., 0.))
    source = ResolvedPhysicalMatingRegion(
        part_id="panel", region_id="contact", region_role="locator",
        physical_face_kind="flat",
        supporting_plane=(origin, normal), outward_normal=normal,
        world_polygon=triangle,
    )
    result = validate_expected_region_coverage(source, triangle)
    assert result.status == "SKIPPED_FAIL_CLOSED"
    assert result.diagnostic_code == "OVERLAP_AUTHORITY_MISSING"


def test_r5_77_expected_mating_coverage_rejects_nonfinite_world_polygon_and_keeps_valid_contact():
    from ae_engine.joint_marking_policy import (
        ResolvedPhysicalMatingRegion, validate_expected_region_coverage,
    )
    triangle = ((0., 0., 0.), (10., 0., 0.), (10., 10., 0.))
    source = ResolvedPhysicalMatingRegion(
        part_id="panel", region_id="contact", region_role="locator",
        physical_face_kind="flat",
        supporting_plane=((0., 0., 0.), (0., 0., 1.)),
        outward_normal=(0., 0., 1.), world_polygon=triangle,
    )
    good = validate_expected_region_coverage(source, triangle)
    assert good.status == "COVERED"
    invalid = validate_expected_region_coverage(
        source,
        ((0., 0., 0.), (10., float("nan"), 0.), (10., 10., 0.)),
    )
    assert invalid.status == "SKIPPED_FAIL_CLOSED"
    assert invalid.diagnostic_code == "OVERLAP_AUTHORITY_MISSING"

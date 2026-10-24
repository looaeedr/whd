"""Regression tests for Round 7 deep audit bugfixes (#117 to #147)."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import ezdxf
import pytest

from ae_engine.certified_relief_formula_io import (
    CertifiedReliefRegistryError,
    _formula_ast_value,
    load_external_relief_rule_records,
)
from ae_engine.certified_relief_registry import (
    _data_formula_evaluator,
    _strict_registry_int,
    promote_relief_rule_candidate,
)
from ae_engine.divider_manufacturing import _divider_cross_registry_variables
from ae_engine.dxf_serialization import verify_quantity_check_dxf
from ae_engine.manufacturing_door_indicator import (
    indicator_box_unfolded_size,
    validate_door_indicator_fit,
)
import ae_engine.manufacturing_endcap_compat as endcap_compat
from ae_engine.manufacturing_verification import (
    verify_saved_resolved_manufacturing_geometry_batch_dxf,
)
from ae_engine.receiving_nfb_2d_preview import Nfb2DViewport
from ae_engine.receiving_nfb_base_assembly_xy import receiving_source_nfb_base_assembly_xy
from ae_engine.receiving_nfb_base_process_projection import (
    build_existing_receiving_base_with_verified_nfb,
)
from ae_engine.receiving_nfb_cutting_manufacturing import read_nfb_upper_source_profiles
from ae_engine.receiving_nfb_middle_3d_witness import witness_middle_plate_uv_on_folded_assembly
from ae_engine.receiving_nfb_middle_plate_projection import shadow_nfb_middle_plate_color150
from ae_engine.receiving_nfb_pad_base_mating import (
    verify_pad_solid_inside_real_base_cutouts,
    verify_real_pad_mesh_tab_engagement,
)
from ae_engine.receiving_nfb_pair_acceptance import validate_nfb_door_base_pair
from ae_engine.receiving_nfb_transactions import _verify_hole_locations
from ae_engine.sheetmetal_feature_surface import (
    feature_surface_from_rect,
    resolve_endcap_finished_face_guide,
)
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.side_sheet_datum import SideSheetDatum
from gui_modules.application.cabinet_controller import _restore_cabinet_family_runtime
from gui_modules.application.door_layout_controller import (
    DoorLayoutColumnState,
    validate_height_commit,
    validate_width_commit,
)
from gui_modules.application.fold_designer_composition_registry_edges import (
    commit_base_plate_edge_shrink,
)
from gui_modules.application.fold_designer_composition_state import build_project_snapshot
from gui_modules.application.quantity_version_controls import QuantityVersionControls
from gui_modules.application.receiving_endcap_thumbnail import (
    endcap_preview_geometry,
    paint_endcap_thumbnail,
)
from gui_modules.application.receiving_inner_door_thumbnail import inner_door_preview_rows
from gui_modules.application.render_snapshots import (
    indicator_box_render_snapshot,
    indicator_door_render_snapshot,
)
from gui_modules.parts.panels.assembly_corner import (
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    refresh_corner_type_panel,
    selection_from_manual_corner_controls,
)
from phase6_assembly_relief_state import (
    RELIEF_CONTRACT_VERSION,
    _active_rule_revision,
    _same_number,
    committed_relief_cuts,
    source_matches_current,
)
from phase6_endcap_semantics import (
    commit_box_fw,
    commit_endcap_bottom_wrap,
    commit_endcap_fw,
    resolve_endcap_fw,
    set_endcap_fw_follow,
)
from phase6_explicit_joint_pipeline import (
    _resolve_generic_joint,
    resolve_explicit_joint_reliefs,
)


def test_bug117_phase6_assembly_relief_state_same_number_and_revision():
    assert _same_number(None, None) is True
    assert _same_number(True, 1.0) is False
    assert _same_number(float("nan"), float("nan")) is False
    assert _active_rule_revision("box_body_corner_2level", True) is False
    assert _active_rule_revision("box_body_corner_2level", 1.9) is False

    bad_state = {
        "enabled": True,
        "parts": "not_a_dict",
        "source": "not_a_dict",
    }
    assert committed_relief_cuts(bad_state, "box_body", {}) == ()
    bad_source = {
        "relief_contract_version": RELIEF_CONTRACT_VERSION,
        "box_body_formed_fw": "not_a_dict",
    }
    assert source_matches_current(bad_source, bad_source, ("box_body",)) is False


def test_bug118_phase6_endcap_semantics_zero_box_fw_and_strict_types():
    state = {}
    commit_endcap_fw(state, "head", 25.0, box_fw=0.0)
    assert state["tail"]["value"] == 25.0  # first edit pairs both; what if mode is already independent?
    state2 = {"mode": "independent"}
    commit_endcap_fw(state2, "head", 25.0, box_fw=0.0)
    assert state2["tail"]["value"] == 0.0

    with pytest.raises(ValueError, match="不支援的封頭尾板件"):
        resolve_endcap_fw({}, "invalid_part")
    with pytest.raises(ValueError, match="不可為布林值"):
        commit_box_fw({}, True)
    with pytest.raises(ValueError, match="必須為有限數值"):
        commit_box_fw({}, float("nan"))

    follow_state = {}
    item = set_endcap_fw_follow(follow_state, "head", "false", box_fw=20.0)
    assert item["follow_box"] is False

    wrap_state = {}
    wrap_item = commit_endcap_bottom_wrap(wrap_state, "head", enabled="0", reserve_u=15.0)
    assert wrap_item["head"]["enabled"] is False
    with pytest.raises(ValueError, match="不可為布林值"):
        commit_endcap_bottom_wrap(wrap_state, "head", enabled=True, reserve_u=True)


def test_bug119_phase6_explicit_joint_pipeline_strict_inputs():
    with pytest.raises(ValueError, match="cannot be boolean"):
        resolve_explicit_joint_reliefs(
            (),
            (),
            finished_dimensions=(400.0, 500.0, 200.0),
            sheet_thickness=True,
            ops=None,
        )
    with pytest.raises(ValueError, match="cannot be boolean"):
        resolve_explicit_joint_reliefs(
            (),
            (),
            finished_dimensions=(400.0, 500.0, 200.0),
            sheet_thickness=1.5,
            clearance=False,
            ops=None,
        )
    joint = SimpleNamespace(
        joint_id="j1",
        subject_part="box_body",
        target_part="endcap_head",
        solver_constraints={"topology_levels": True},
    )
    decision = SimpleNamespace(
        joint=joint,
        relation="OVERLAY",
        source="explicit",
        registry_status="UNCERTIFIED",
        relief_key="endcap_head",
        preserve_key="box_body",
        relief_part=SimpleNamespace(
            render_data=SimpleNamespace(pieces=None, material=SimpleNamespace(is_empty=False))
        ),
        preserve_part=SimpleNamespace(
            render_data=SimpleNamespace(pieces=None)
        ),
    )
    inventory = SimpleNamespace(
        old_items={},
        saved_state={},
        diagnostics=[],
    )
    _resolve_generic_joint(
        SimpleNamespace(sheet_thickness=1.5, clearance=0.2),
        inventory,
        decision,
        ops=SimpleNamespace(state_item_matches=lambda *a: False),
    )
    assert len(inventory.diagnostics) == 1
    assert inventory.diagnostics[0].candidate_status == "TOPOLOGY_UNSPECIFIED"


def test_bug120_and_bug121_certified_relief_registry_and_formula_io():
    from shapely.geometry import box as shapely_box
    from ae_engine.certified_relief_registry import CertifiedReliefRule, CertifiedReliefStatus

    rule = CertifiedReliefRule(
        rule_id="test_r",
        revision=1,
        status=CertifiedReliefStatus.CERTIFIED,
        cabinet_family="general",
        part_role="endcap",
        joint_face="TOP_LEFT",
        assembly_intent=CornerTypeId.OVERLAY,
        topology_levels=1,
        formula_x="effective_mating_width + 5.0",
        formula_y="FW",
        formula_record={
            "primary_u": "effective_mating_width + 5.0",
            "primary_v": "FW",
        },
        evaluator=None,
    )
    res = _data_formula_evaluator(
        endcap_render_data=SimpleNamespace(
            material=shapely_box(0.0, 0.0, 200.0, 100.0),
            metadata={"nominal_fold_left": 15.0, "effective_mating_width": 0.0},
        ),
        box_body_x_profile=(),
        endcap_x_profile=(SimpleNamespace(phase6_key="endcap_w_flat", length=200.0),),
        endcap_y_profile=(SimpleNamespace(phase6_key="fw", length=20.0),),
        sheet_thickness=1.5,
        rule=rule,
    )
    assert res is not None
    assert res.corner_reliefs[0].measurement.primary_u == pytest.approx(5.0)

    node = ast.parse("FW", mode="eval").body
    with pytest.raises(CertifiedReliefRegistryError, match="cannot be boolean"):
        _formula_ast_value(node, {"FW": True})

    with pytest.raises(CertifiedReliefRegistryError):
        _strict_registry_int(True, "bad int")
    with pytest.raises(CertifiedReliefRegistryError):
        _strict_registry_int(1.9, "bad int")
    with pytest.raises(CertifiedReliefRegistryError):
        promote_relief_rule_candidate(
            "cand1",
            regression_evidence={"matrix_passed": "true", "cases": 1, "zero_penetration": True},
        )


def test_bug122_divider_manufacturing_zero_thickness_not_masked():
    divider = SimpleNamespace(thickness=0.0, notch_style="full_relief")
    with pytest.raises(ValueError, match="Divider thickness disagrees"):
        _divider_cross_registry_variables(divider, None, sheet_thickness=1.5)
    with pytest.raises(ValueError, match="positive sheet thickness"):
        _divider_cross_registry_variables(divider, None, sheet_thickness=True)


def test_bug123_manufacturing_endcap_compat_preserves_zero_height(monkeypatch):
    captured = {}

    def fake_stretched(model, w, h, d, *args, **kwargs):
        captured["h"] = h
        return SimpleNamespace(
            scene=SimpleNamespace(primitives=()),
            params={"total_depth": 200.0},
        )

    monkeypatch.setattr(endcap_compat, "_baseline_path", lambda *a, **kw: Path("dummy.dxf"))
    monkeypatch.setattr(endcap_compat.ae, "get_stretched_end_cap_data", fake_stretched)
    resolved = SimpleNamespace(
        model_name="WHD-1",
        width=400.0,
        height=0.0,
        depth=200.0,
        thickness=1.5,
        frame_width=25.0,
        corner_policy=None,
        x_topology=None,
        box_body_formed_fw_left=25.0,
        box_body_formed_fw_right=25.0,
        depth_comp_t=0.0,
        fold_left=15.0,
        fold_right=15.0,
        fold_top=15.0,
        fold_bottom=15.0,
        is_tail=True,
    )
    endcap_compat._baseline_endcap_holes_for_request(resolved, context=None)
    assert captured["h"] == 0.0


def test_bug124_and_bug125_manufacturing_verification_and_dxf_quantity(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        verify_saved_resolved_manufacturing_geometry_batch_dxf(
            [("   ", SimpleNamespace(parts=()))],
            tmp_path,
            resolved_physical_render_parts=lambda g: (),
            resolved_physical_dxf_filename=lambda p: "part.dxf",
            verify_part_dxf=lambda *a, **kw: None,
        )
    with pytest.raises(ValueError, match="duplicate manufacturing instance namespace"):
        verify_saved_resolved_manufacturing_geometry_batch_dxf(
            [
                ("SAME/NS", SimpleNamespace(parts=())),
                ("SAME:NS", SimpleNamespace(parts=())),
            ],
            tmp_path,
            resolved_physical_render_parts=lambda g: (),
            resolved_physical_dxf_filename=lambda p: "part.dxf",
            verify_part_dxf=lambda *a, **kw: None,
        )

    dxf_path = tmp_path / "no_check.dxf"
    doc = ezdxf.new("R2010")
    doc.modelspace().add_text("Q2")
    doc.saveas(dxf_path)
    from ae_engine.sheetmetal_drawing import TextPrimitive

    scene_with_q2 = SimpleNamespace(
        primitives=(
            TextPrimitive(
                text="Q2",
                insert=Vec2(0.0, 0.0),
                layer="CHECK",
                char_height=10.0,
                attachment_point=5,
                semantic_id="manufacturing_quantity",
            ),
        )
    )
    with pytest.raises(ValueError, match="missing CHECK layer"):
        verify_quantity_check_dxf(scene_with_q2, dxf_path)


def test_bug126_manufacturing_door_indicator_rejects_bool_and_float_groups():
    with pytest.raises(ValueError, match="整數"):
        indicator_box_unfolded_size((True,), thickness=1.5)
    with pytest.raises(ValueError, match="整數"):
        validate_door_indicator_fit(
            mode="indicator",
            groups=(1.8,),
            finished_width=400.0,
            finished_height=500.0,
            thickness=1.5,
        )


def test_bug127_and_bug128_sheetmetal_feature_surface_and_side_sheet_datum():
    with pytest.raises(ValueError, match="max_point > min_point"):
        feature_surface_from_rect(
            "s1",
            Vec2(100.0, 50.0),
            Vec2(50.0, 100.0),
        )
    with pytest.raises(ValueError, match="exceed 4\\*thickness"):
        resolve_endcap_finished_face_guide(width=6.0, depth=100.0, thickness=1.5)

    with pytest.raises(ValueError, match="cannot be boolean"):
        SideSheetDatum(outside_width=True, thickness=1.5)
    datum = SideSheetDatum(outside_width=500.0, thickness=1.5)
    with pytest.raises(ValueError, match="-1 \\(left\\) or \\+1 \\(right\\)"):
        datum.outside_face(True)


def test_bug129_to_bug131_receiving_nfb_cutting_and_base(tmp_path):
    import json
    reg_file = tmp_path / "reg.json"
    reg_file.write_text(
        json.dumps(
            {
                "schema": "WHD_NFB_UPPER_SOURCE_PROFILE_V1",
                "profiles": [
                    {
                        "brand": "B",
                        "indexed_filename": "M.dxf",
                        "source_sha256": "a" * 64,
                        "upper_handle": "1A",
                        "lower_reference_handle": "1B",
                        "upper_size_mm": [100.0, True],
                        "pad_kind": "none",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="NFB upper Color150 dimensions invalid"):
        read_nfb_upper_source_profiles(reg_file)

    from ae_engine.receiving_nfb_base_assembly_xy import receiving_nfb_layer_centers
    from ae_engine.contracts import BasePlatePartSpec
    from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER

    with pytest.raises(ValueError, match="RECEIVING_NFB_LAYER_COUNT_UNSUPPORTED"):
        receiving_nfb_layer_centers(
            {
                "receiving_layout": {
                    "sets": [
                        {
                            "stable_id": "s1",
                            "bays": [
                                {
                                    "stable_id": "b1",
                                    "nfb_config_submitted": True,
                                    "nfb_config": {
                                        "layer_count": "2",
                                        "holes": [{"manual_x_mm": 100.0}],
                                    },
                                }
                            ],
                        }
                    ]
                }
            },
            "inner_door_1",
        )

    base_spec = BasePlatePartSpec(
        model_name="受電箱",
        width=500.0,
        height=300.0,
        thickness=1.5,
        shrink_top=0.0,
        shrink_bottom=0.0,
        shrink_left=0.0,
        shrink_right=0.0,
        bend=0.0,
        receiving_bend_pattern=RECEIVING_BASE_PATTERN_CENTER,
        physical_id="base_plate_1",
    )
    with pytest.raises(ValueError, match="NFB Base Plate does not belong"):
        build_existing_receiving_base_with_verified_nfb(
            snapshot={"w": None, "h": 600.0, "t": 1.5},
            inner_door_id="id1",
            base_spec=base_spec,
            verified_inner_door=SimpleNamespace(),
            source_path="dummy.dxf",
            profile=SimpleNamespace(),
            lower_reference_handle="1B",
        )


def test_bug133_to_bug138_receiving_nfb_pipeline_validations():
    with pytest.raises(ValueError, match="NFB configured X/Y slot/rotation differs"):
        _verify_hole_locations(
            {
                "layer_count": 1,
                "holes": [
                    {
                        "physical_hole_id": "h1",
                        "manual_x_mm": 100.0,
                        "slot_index": 0,
                        "rotation_deg": 0,
                    }
                ],
            },
            SimpleNamespace(
                verified_hole_locations=(("h1", 100.0, True, 0, 0),)
            ),
        )

    vp = Nfb2DViewport()
    with pytest.raises(ValueError, match="NFB viewport screen dimensions invalid"):
        vp.reset(True, 100.0)
    vp.reset(200.0, 100.0)
    with pytest.raises(ValueError, match="NFB viewport pan delta invalid"):
        vp.pan(float("nan"), 0.0)
    with pytest.raises(ValueError, match="NFB viewport zoom anchor invalid"):
        vp.zoom(1.2, 200.0, 100.0, anchor=(True, 50.0))

    from ae_engine.door_dividers import BoxBodyDividerPart
    from ae_engine.manufacturing_render_data import PartRenderData
    from ae_engine.sheetmetal_drawing import DrawingScene
    from shapely.geometry import box as shapely_box

    div_obj = BoxBodyDividerPart.__new__(BoxBodyDividerPart)
    object.__setattr__(div_obj, "axis", "HORIZONTAL")
    base_render = PartRenderData.__new__(PartRenderData)
    object.__setattr__(base_render, "material", shapely_box(0.0, 0.0, 100.0, 100.0))
    with pytest.raises(ValueError, match="NFB UV witness point must be finite"):
        witness_middle_plate_uv_on_folded_assembly(
            {},
            div_obj,
            base_render,
            uv_xy="12",
            expected_world_x_mm=10.0,
        )

    from ae_engine.receiving_nfb_middle_plate_projection import NfbMiddlePlateUnfoldDatum
    from ae_engine.receiving_nfb_pad_base_mating import PadPattern

    object.__setattr__(div_obj, "stable_id", "div1")
    with pytest.raises(ValueError, match="NFB middle plate physical UV axis/datum is unresolved"):
        shadow_nfb_middle_plate_color150(
            {},
            div_obj,
            base_render,
            source_path="dummy.dxf",
            profile=SimpleNamespace(),
            lower_reference_handle="1B",
            verified_inner_door=SimpleNamespace(),
            physical_hole_id="h1",
            physical_datum=NfbMiddlePlateUnfoldDatum(
                part_id="div1",
                span_world_x_sign=True,
                core_depth_uv_x_mm=10.0,
                revision="rev1",
            ),
        )

    fake_pattern = PadPattern.__new__(PadPattern)
    object.__setattr__(fake_pattern, "manufacturing_ready", False)
    with pytest.raises(ValueError, match="PAD_MESH_MATING_REAL_PHYSICAL_Z_DRIFT"):
        verify_real_pad_mesh_tab_engagement(
            (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),),
            fake_pattern,
            (((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),) * 4,
            base_front_world_z_mm=0.0,
            world_x_mm=True,
            world_y_mm=10.0,
            rotation_deg=0,
        )
    with pytest.raises(ValueError, match="PAD_BASE_SLAB_COLLISION_INVALID_TOLERANCE_OR_DATUM"):
        verify_pad_solid_inside_real_base_cutouts(
            (),
            (),
            base_front_world_z_mm=0.0,
            thickness_mm=1.5,
            tolerance=True,
        )


def test_bug139_to_bug143_gui_application_controllers():
    columns = (
        DoorLayoutColumnState(width=200.0, width_auto=False, heights=(250.0, 250.0), height_auto=(False, True)),
        DoorLayoutColumnState(width=300.0, width_auto=True, heights=(500.0,), height_auto=(True,)),
    )
    with pytest.raises(ValueError, match="必須大於 0"):
        validate_width_commit(columns, column_index=0, total_width=500.0, current=True)
    with pytest.raises(ValueError, match="欄索引超出範圍"):
        validate_width_commit(columns, column_index=True, total_width=500.0, current=100.0)
    with pytest.raises(ValueError, match="列索引超出範圍"):
        validate_height_commit(columns, column_index=0, row_index=5, total_height=500.0, current=100.0)

    import gui_modules.application.quantity_version_controls as qvc
    qvc_ctrl = QuantityVersionControls(
        frame=SimpleNamespace(pack_forget=lambda: None),
        versions=SimpleNamespace(
            get_children=lambda: (),
            delete=lambda *a: None,
            insert=lambda *a, **kw: None,
            selection_set=lambda *a: None,
            focus=lambda *a: None,
        ),
        count_var=SimpleNamespace(set=lambda v: None),
        totals_var=SimpleNamespace(set=lambda v: None),
        ports={"snapshot": lambda: {"versions": [], "selected_version_id": "missing"}},
    )
    qvc_ctrl.refresh()

    with pytest.raises(ValueError, match="缺少有效封頭尾尺寸"):
        paint_endcap_thumbnail(object(), None, width=0.0, depth=100.0)
    with pytest.raises(ValueError, match="缺少有效封頭尾尺寸"):
        endcap_preview_geometry((), True, 100.0)

    with pytest.raises(ValueError, match="無效的內門預覽層數"):
        inner_door_preview_rows({"layers": True})

    fake_self = SimpleNamespace(
        app=SimpleNamespace(),
        _required=lambda ns, name: ns[name],
    )
    fake_ns = {
        "_BASE_PLATE_EDGE_SETTING_KEYS": {"TOP": "base_shrink_top"},
        "original": SimpleNamespace(tk=SimpleNamespace(TclError=RuntimeError)),
    }
    assert commit_base_plate_edge_shrink(fake_self, fake_ns, "top", True) is False
    assert commit_base_plate_edge_shrink(fake_self, fake_ns, "top", float("nan")) is False


def test_bug144_to_bug147_gui_panels_and_lifecycle_snapshots():
    class _Var:
        def __init__(self, val):
            self._val = val

        def get(self):
            return self._val

        def set(self, val):
            self._val = val

    host = SimpleNamespace(
        manual_corner_type_var=_Var(CornerTypeId.OVERLAY.value),
        manual_corner_amount_var=_Var("1.5"),
        manual_corner_secondary_retain_var=_Var(""),  # empty unused field!
        manual_corner_secondary_depth_var=_Var(""),   # empty unused field!
    )
    sel = selection_from_manual_corner_controls(host)
    assert sel is not None
    assert sel.type_id is CornerTypeId.OVERLAY
    assert sel.amount_t == 1.5

    class _Widget:
        def pack(self, **kw):
            pass

        def pack_forget(self):
            pass

        def configure(self, **kw):
            pass

        def winfo_ismapped(self):
            return True

    host_refresh = SimpleNamespace(
        corner_type_panel=_Widget(),
        corner_type_panel_anchor=None,
        _current_manual_corner_part_key=lambda: "head",
        manual_corner_state={"head": {}},
        manual_corner_part_label=_Widget(),
        _corner_part_type_editable=lambda pk: True,
        _corner_part_parameters_unlockable=lambda pk: True,
        _manual_corner_parameters_unlocked=lambda pk: False,
        manual_corner_title_label=_Widget(),
        manual_corner_fixed_summary=_Widget(),
        manual_corner_param_lock_button=_Widget(),
        manual_corner_editor_frame=_Widget(),
        manual_corner_pair_same={"head": {"top": True, "bottom": True}},
        manual_top_same_var=_Var(True),
        manual_bottom_same_var=_Var(True),
        _normalize_manual_corner_target=lambda pk: "top",
        _manual_selection_for_target=lambda pk, tk_key: SimpleNamespace(
            type_id=CornerTypeId.OVERLAY,
            cross_mode=None,
            direction=None,
            amount_t=0.0,
            secondary_retain_t=0.0,
            secondary_depth_t=0.0,
        ),
        manual_corner_type_var=_Var(""),
        manual_corner_cross_mode_var=_Var(""),
        manual_corner_direction_var=_Var(""),
        manual_corner_amount_var=_Var(""),
        manual_corner_secondary_retain_var=_Var(""),
        manual_corner_secondary_depth_var=_Var(""),
        _CORNER_MODE_LABELS={CrossCornerMode.STANDARD: "標準"},
        _CORNER_DIRECTION_LABELS={},
        _corner_number_text=lambda v: f"{v:g}",
        manual_corner_pair_buttons={},
        _manual_corner_parameters_editable=lambda pk: True,
        manual_corner_pair_same_checkbuttons={},
        manual_corner_type_buttons={},
        corner_type_small_canvases={},
        manual_corner_param_frame=_Widget(),
        manual_corner_param_summary=_Widget(),
        _corner_parameter_summary=lambda s: "",
        corner_type_preview_canvas=None,
    )
    refresh_corner_type_panel(host_refresh)
    assert host_refresh.manual_corner_amount_var.get() == "0"
    assert host_refresh.manual_corner_secondary_retain_var.get() == "0"
    assert host_refresh.manual_corner_secondary_depth_var.get() == "0"

    from shapely.geometry import box as shapely_box

    captured_groups = []
    snap_host = SimpleNamespace(
        indicator_l_var=_Var(99),
        indicator_layer_g_vars=[_Var(2), _Var(3)],
        indicator_x_var=_Var(0.0),
        indicator_y_var=_Var(0.0),
        surface_features={"indicator_box": (), "indicator_door": ()},
        _indicator_box_part_spec=lambda val, lg, features=(): (captured_groups.append(lg) or SimpleNamespace()),
        _indicator_door_part_spec_from_values=lambda val, lg, features=(): (
            captured_groups.append(lg) or (SimpleNamespace(), SimpleNamespace())
        ),
        _manufacturing_context=lambda draw_stock=False: SimpleNamespace(),
        _authoritative_render_data=lambda spec, ctx: SimpleNamespace(
            material=shapely_box(0.0, 0.0, 100.0, 100.0)
        ),
    )
    snap = indicator_box_render_snapshot(
        snap_host,
        {"w": 400.0, "h": 500.0, "d": 200.0, "t": 1.5, "fw": 25.0},
    )
    assert snap["layer_groups"] == (2, 3)

    import gui_modules.application.render_snapshots as rs_mod
    old_fn = rs_mod.manufacturing_api.door_finished_face_size
    rs_mod.manufacturing_api.door_finished_face_size = lambda spec, ctx: (400.0, 500.0)
    try:
        snap_door = indicator_door_render_snapshot(
            snap_host,
            {"w": 400.0, "h": 500.0, "d": 200.0, "t": 1.5, "fw": 25.0},
        )
    finally:
        rs_mod.manufacturing_api.door_finished_face_size = old_fn
    assert captured_groups[-1] == (2, 3)
    assert snap_door["finished_size"] == (400.0, 500.0)

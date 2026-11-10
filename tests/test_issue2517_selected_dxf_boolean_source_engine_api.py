"""#2517: raw checkbox source is Engine-owned before real physical DXF output."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import manufacturing_export_selection as owner
from ae_engine.contracts import (
    DoorPartSpec, ManufacturingContext,
    ResolvedManufacturingGeometry, ResolvedManufacturingPart,
)
from gui_modules.project.export_actions import _selected_export_flags


class OperatorVar:
    def __init__(self, raw):
        self.raw = raw

    def get(self):
        return self.raw


def _geometry(render_data=None):
    return ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart(part_key="door", render_data=render_data or object()),
        ResolvedManufacturingPart(part_key="base_plate", render_data=object()),
    ))


def _gui(raw_door="false", raw_base="true"):
    snapshot = {"model": "受電箱", "nfb_config_submitted": False}
    app = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        designer_workspace=SimpleNamespace(available_parts=("door", "base_plate")),
    )
    raw = {
        "export_z_var": "false", "export_head_var": "false",
        "export_tail_var": "false", "export_door_var": raw_door,
        "export_base_plate_var": raw_base, "export_ib_var": "false",
        "export_ib_door_var": "false",
    }
    return SimpleNamespace(
        fold_designer_app=app,
        **{name: OperatorVar(value) for name, value in raw.items()},
    ), raw, snapshot


def test_gui_selection_and_headless_api_share_serialized_boolean_source():
    host, raw, snapshot = _gui()
    original = deepcopy(snapshot)
    actual = _selected_export_flags(host, {"door", "base_plate"}, "false")
    assert actual == {
        "box_body": False, "head": False, "tail": False,
        "door": False, "base_plate": True,
        "indicator_box": False, "indicator_door": False,
    }
    original_values = {
        key: value.raw for key, value in vars(host).items()
        if key.endswith("_var")
    }
    reloaded = json.loads(json.dumps(original_values))
    headless = api.selected_project_export_flags(
        snapshot, {"door", "base_plate"}, ("door", "base_plate"),
        {
            "box_body": reloaded["export_z_var"],
            "head": reloaded["export_head_var"],
            "tail": reloaded["export_tail_var"],
            "door": reloaded["export_door_var"],
            "base_plate": reloaded["export_base_plate_var"],
            "indicator_box": reloaded["export_ib_var"],
            "indicator_door": reloaded["export_ib_door_var"],
        }, has_indicator_box="false",
    )
    assert actual == headless
    assert snapshot == original
    assert raw["export_door_var"] == "false"


def test_original_public_engine_owner_selects_only_confirmed_physical_parts():
    assert api.normalize_operator_selected_export_flags is (
        owner.normalize_operator_selected_export_flags
    )
    raw = json.loads(json.dumps({"door": "false", "base_plate": "true"}))
    before = deepcopy(raw)
    result = api.select_resolved_export_geometry(_geometry(), raw)
    assert [p.part_key for p in result.parts] == ["base_plate"]
    assert raw == before
    # A saved false checkbox cannot become a valid DXF selection by bool("false").
    false_only = api.select_resolved_export_geometry(_geometry(), {"door": "false"})
    assert false_only.parts == ()


def test_engine_selected_route_and_partial_retry_keep_serialized_false():
    route = api.plan_selected_resolved_export_route(
        {"model": "金庫型"}, {"door": "false", "base_plate": "true"},
    )
    assert dict(route.legacy_guard_flags) == {"door": False, "base_plate": True}
    assert not route.vault_composed
    missing = (
        "canonical resolved export: "
        "RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING: base_plate"
    )
    assert api.plan_unconfigured_receiving_base_export_retry(
        [missing], {"base_plate": "false", "head": "true"},
    ) is None
    retry = api.plan_unconfigured_receiving_base_export_retry(
        [missing], {"base_plate": "true", "head": "false"},
    )
    assert dict(retry) == {"base_plate": False, "head": False}
    assert api.selected_export_manufacturing_policy(
        {"model": "受電箱", "nfb_config_submitted": False},
        {"box_body": "false", "door": "true"},
    ) == (False, ())


@pytest.mark.parametrize("bad", ["false-ish", "2", 2, 0.25, None, [], {}, float("nan")])
def test_invalid_export_intention_is_rejected_before_any_output(tmp_path, bad):
    raw = {"door": "true", "base_plate": bad}
    original = deepcopy(raw)
    with pytest.raises(ValueError):
        api.normalize_operator_selected_export_flags(raw)
    with pytest.raises(ValueError):
        api.select_resolved_export_geometry(_geometry(), raw)
    with pytest.raises(ValueError):
        api.selected_project_export_flags(
            {"model": "金庫型"}, ("door",), (), raw,
        )
    with pytest.raises(ValueError):
        api.plan_selected_resolved_export_route({"model": "金庫型"}, raw)
    with pytest.raises(ValueError):
        api.plan_unconfigured_receiving_base_export_retry(
            ["irrelevant"], raw,
        )
    out = tmp_path / "must-not-exist"
    with pytest.raises(ValueError):
        api.save_selected_resolved_manufacturing_dxf(
            {"model": "金庫型"}, _geometry(), raw, out,
        )
    assert raw == original
    assert not out.exists()


def test_real_engine_door_dxf_reopens_with_true_flag_and_false_writes_nothing(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    spec = DoorPartSpec(
        width=800.0, height=1600.0, thickness=2.0, frame_width=29.0,
        model_name="受電箱", gap_w=3.5, gap_h=3.5,
        fold_left=19.0, fold_right=19.0, fold_top=19.0,
        fold_bottom=19.0, feature_space="finished_face",
    )
    data = api.build_part_render_data(
        spec, ManufacturingContext(resource_root=repo),
    )
    geometry = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart(part_key="door", render_data=data),
    ))
    snapshot = {"model": "受電箱", "nfb_config_submitted": False}
    no_output = tmp_path / "not-selected"
    flags = json.loads(json.dumps({"door": "false"}))
    assert api.save_selected_resolved_manufacturing_dxf(
        snapshot, geometry, flags, no_output,
    ) == {}
    assert not no_output.exists()

    output_dir = tmp_path / "selected"
    selected = api.save_selected_resolved_manufacturing_dxf(
        snapshot, geometry, {"door": "true"}, output_dir,
    )
    assert set(selected) == {"door"}
    actual_file = Path(selected["door"])
    assert actual_file.is_file()
    reopened = ezdxf.readfile(actual_file)
    layers = {entity.dxf.layer for entity in reopened.modelspace()}
    assert "CUTTING" in layers
    assert "BEND" in layers
    assert api.verify_saved_part_render_data_dxf(data, actual_file).ok


def test_shared_receiving_c_frame_preserves_door_intent_and_rejects_false_alias():
    c_frame = ResolvedManufacturingPart(
        part_key="box_body:divider:lower_shared", render_data=object(),
    )
    source = ResolvedManufacturingGeometry(parts=(c_frame,))
    assert api.select_resolved_export_geometry(
        source, {"box_body": "false", "door": "true"},
    ).parts == (c_frame,)
    assert api.select_resolved_export_geometry(
        source, {"box_body": "false", "door": "false"},
    ).parts == ()
    with pytest.raises(ValueError):
        api.select_resolved_export_geometry(
            source, {"box_body": "false", "door": "bad"},
        )

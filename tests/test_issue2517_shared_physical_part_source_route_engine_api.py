"""#2517 physical-part provider selection and preview rendering share Engine API."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import manufacturing_request_parts as owner
import phase6_manufacturing_adapter as gui_adapter


@pytest.mark.parametrize("key,collect,render,need_spec,committed", [
    ("box_body", "raw", "part_spec", False, False),
    ("head", "raw", "part_spec", True, True),
    ("tail", "raw", "part_spec", True, True),
    ("door", "raw", "part_spec", False, False),
    ("door:upper:0", "door", "part_spec", False, False),
    ("indicator_box", "indicator", "part_spec", False, False),
    ("indicator_door", "indicator", "part_spec", False, False),
    ("box_body:part:left", "multipart", "part_spec", False, False),
    ("box_body:divider:divider_1", "raw", "divider", False, False),
    ("inner_door:upper:panel", "raw", "inner_panel", False, False),
    ("inner_door:upper:top_frame", "raw", "inner_frame", False, False),
    ("nfb_pad:tier_1", "raw", "nfb_pad", False, False),
    ("base_plate:fixing_plate:nfb_layer:0:left", "raw", "fixing_plate", False, False),
    ("custom:1", "raw", "part_spec", True, False),
    ("unknown", "raw", "part_spec", False, False),
])
def test_existing_physical_ids_get_only_one_public_engine_route(
    key, collect, render, need_spec, committed,
):
    result = api.plan_operator_manufacturing_part_source(key)
    assert isinstance(result, owner.OperatorManufacturingPartSourcePlan)
    assert result == owner.plan_operator_manufacturing_part_source(key)
    assert (result.input_adapter, result.render_source) == (collect, render)
    assert result.requires_direct_part_spec is need_spec
    assert result.needs_committed_relief is committed
    assert not result.requires_custom_default_profile


@pytest.mark.parametrize("has_profiles,expected", [(False, True), (True, False)])
def test_custom_default_only_when_profile_missing(has_profiles, expected):
    plan = api.plan_operator_manufacturing_part_source(
        "custom:1", has_saved_profiles=has_profiles,
    )
    assert plan.requires_custom_default_profile is expected
    assert not api.plan_operator_manufacturing_part_source(
        "door", has_saved_profiles=False,
    ).requires_custom_default_profile


def test_actual_custom_catalog_profiles_follow_headless_default_engine():
    catalog = api.CustomPartCatalog()
    key = catalog.add(display_name="支撐板", fold_axis="X",
                      transverse_length=175, per_box_count=2)
    snap = {"model": "受電箱", "w": 800, "h": 1600, "d": 350, "t": 2,
            "fw": 29, "custom_parts": catalog.snapshot()}
    before = deepcopy(snap)
    class Workspace:
        active_part = "box_body"
        def profiles_for(self, part, default):
            return default
        def snapshot(self):
            return {"custom_parts": deepcopy(snap["custom_parts"])}
    app = SimpleNamespace(
        _phase6_input_snapshot=snap, _settings_values={},
        designer_workspace=Workspace(), state=SimpleNamespace(profiles={}),
    )
    x, y = gui_adapter._profile_inputs_for_part(app, key)
    expected = api.build_operator_default_part_fold_profiles(snap, key)
    assert x == tuple(expected["X"]) and y == tuple(expected["Y"])
    assert snap == before


@pytest.mark.parametrize("key,required", [
    ("head", True), ("tail", True), ("custom:1", True), ("door", False),
    ("box_body", False), ("inner_door:upper:panel", False),
])
def test_real_adapter_only_calls_part_spec_provider_for_engine_selected_ids(key,required):
    events = []
    def render(part, payload):
        events.append(("render", part, payload["_use_committed_relief"]))
        return object()
    def spec(part, payload):
        events.append(("spec", part, payload["_use_committed_relief"]))
        return object(), object()
    row = gui_adapter._domain_inputs_for_part(
        SimpleNamespace(), key, {}, render_data_provider=render,
        part_spec_provider=spec,
    )
    assert [event[0] for event in events] == (
        ["render", "spec"] if required else ["render"]
    )
    assert all(event[2] is False for event in events)
    assert (row[2] is not None) is required
    if key in ("head", "tail"):
        assert row[1] is None
    else:
        assert row[1] is row[0]


def test_gui_request_and_render_use_engine_source_plan_no_part_id_prefix_checks():
    root = Path(__file__).resolve().parents[1]
    adapter = (root / "phase6_manufacturing_adapter.py").read_text(encoding="utf-8")
    view = (root /
        "gui_modules/application/fold_designer_manufacturing_projection.py"
    ).read_text(encoding="utf-8")
    profile = adapter.split("def _profile_inputs_for_part(", 1)[1].split(
        "def _workspace_value(", 1,
    )[0]
    domain = adapter.split("def _domain_inputs_for_part(", 1)[1].split(
        "def _materialize_committed_endcap_inputs(", 1,
    )[0]
    render = view.split("def _query_fold_designer_render_data(", 1)[1].split(
        "def _payload_topology_context(", 1,
    )[0]
    for body in (profile, domain, render):
        assert "manufacturing_api.plan_operator_manufacturing_part_source(" in body
        assert "startswith(" not in body
        assert "endswith(" not in body
    assert "manufacturing_api.build_operator_default_part_fold_profiles(" in profile
    engine = (root / "ae_engine/manufacturing_request_parts.py").read_text(
        encoding="utf-8",
    )
    assert "from phase6_" not in engine and "from gui_modules" not in engine

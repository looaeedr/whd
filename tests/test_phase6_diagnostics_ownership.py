from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene

import phase6_diagnostics as diagnostics


class Mode(Enum):
    SAMPLE = "sample"


@dataclass(frozen=True)
class Record:
    mode: Mode
    values: tuple[int, int]


def _render_data_with_hole():
    scene = DrawingScene()
    scene.add_polyline([(0, 0), (100, 0), (100, 60), (0, 60)], layer="CUTTING", closed=True)
    scene.add_circle((30, 30), 5, layer="CUTTING")
    scene.add_line((10, 10), (90, 10), layer="BEND")
    material = manufacturing_api.material_polygon_from_final_scene(scene)
    guides = (manufacturing_api.FoldGuide("y", 10.0, 10.0, 90.0),)
    return manufacturing_api.PartRenderData(scene=scene, material=material, fold_guides=guides)


def test_diagnostics_module_is_ui_and_transaction_independent():
    source = Path(diagnostics.__file__).read_text(encoding="utf-8")
    forbidden = (
        "tkinter",
        "fold_designer_bridge",
        "phase6_project_session",
        "Phase6ProjectController",
        "SettingsService",
        "build_part_render_data",
        "material_polygon_from_final_scene",
    )
    for token in forbidden:
        assert token not in source


def test_json_safe_scene_material_and_fold_guides_are_stable():
    render_data = _render_data_with_hole()

    assert diagnostics.json_safe(Record(Mode.SAMPLE, (1, 2))) == {
        "mode": "sample",
        "values": [1, 2],
    }
    scene = diagnostics.serialize_scene(render_data.scene)
    material = diagnostics.material_diagnostic(render_data.material)
    guides = diagnostics.serialize_fold_guides(render_data.fold_guides)

    assert scene["primitive_count"] == 3
    assert any(row["type"] == "CirclePrimitive" and row["layer"] == "CUTTING" for row in scene["primitives"])
    assert material["geometry_type"] == "Polygon"
    assert material["interior_count"] == 1
    assert material["geojson"]["type"] == "Polygon"
    assert guides == [{"axis": "y", "position": 10.0, "span_start": 10.0, "span_end": 90.0}]


def test_active_snapshot_captures_exact_render_data_and_render_error():
    context = diagnostics.DiagnosticSnapshotContext(
        model="PW",
        active_part="door",
        settings={"w": 500.0},
        corner_state={"door": {"top_left": "sample"}},
        corner_pair_same={"door": {"top": True}},
        workspace={"existing_parts": ["door", "tail"]},
        active_part_payload={"model": "PW", "part": "door"},
    )
    snapshot = diagnostics.build_active_diagnostic_snapshot(context, _render_data_with_hole)
    assert snapshot["schema"] == "phase6-fold-diagnostic-v1"
    assert snapshot["active_part"] == "door"
    assert snapshot["final_geometry"]["material"]["interior_count"] == 1
    assert snapshot["render_error"] is None

    def explode():
        raise RuntimeError("boom")

    failed = diagnostics.build_active_diagnostic_snapshot(context, explode)
    assert failed["final_geometry"] is None
    assert failed["render_error"] == "RuntimeError: boom"


def test_all_part_diagnostics_isolates_one_render_failure():
    render_data = _render_data_with_hole()

    def payload_provider(key):
        return {"part": key, "model": "PW"}

    def render_provider(key, payload):
        assert payload["part"] == key
        if key == "tail":
            raise ValueError("tail failed")
        return render_data

    result = diagnostics.collect_final_geometry_diagnostics(
        ["box_body", "tail", "door"], payload_provider, render_provider
    )
    assert result["box_body"]["error"] is None
    assert result["door"]["material"]["interior_count"] == 1
    assert result["tail"]["scene"] is None
    assert result["tail"]["error"] == "ValueError: tail failed"


def test_all_part_diagnostics_reports_disconnected_provider_per_part():
    result = diagnostics.collect_final_geometry_diagnostics(
        ["head", "tail"], lambda key: {"part": key}, None
    )
    assert result["head"]["error"] == "3D final-scene provider is not connected"
    assert result["tail"]["error"] == "3D final-scene provider is not connected"


def test_utf8_json_writer_round_trips(tmp_path):
    path = tmp_path / "折彎診斷.json"
    payload = {"schema": "phase6-fold-diagnostic-v1", "label": "封尾", "x": 12.5}
    target = diagnostics.write_diagnostic_json(path, payload)
    assert target == path
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_bridge_reexports_diagnostic_serializers_without_duplicate_implementation():
    import fold_designer_bridge as bridge

    assert bridge._phase6_json_safe is diagnostics.json_safe
    assert bridge._phase6_serialize_scene is diagnostics.serialize_scene
    assert bridge._phase6_material_diagnostic is diagnostics.material_diagnostic
    assert bridge._phase6_serialize_fold_guides is diagnostics.serialize_fold_guides
    assert bridge._phase6_write_diagnostic_json is diagnostics.write_diagnostic_json

    source = Path(bridge.__file__).read_text(encoding="utf-8")
    for definition in (
        "def _phase6_json_safe(",
        "def _phase6_serialize_scene(",
        "def _phase6_material_diagnostic(",
        "def _phase6_serialize_fold_guides(",
        "def _phase6_write_diagnostic_json(",
    ):
        assert definition not in source

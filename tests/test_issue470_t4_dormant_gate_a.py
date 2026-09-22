from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import ezdxf
import pytest
from shapely.geometry import box

from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.manufacturing_api import (
    PartRenderData,
    save_resolved_manufacturing_geometry_dxf,
)
from ae_engine.sheetmetal_drawing import DrawingScene
from phase6_manufacturing_contracts import ManufacturingPartInput, ManufacturingResolveRequest


GATE_A_STATE = "FOUNDATION_MERGED / MARKING_NOT_ACTIVATED"


def _baseline_render() -> PartRenderData:
    scene = DrawingScene()
    scene.add_polyline(
        ((0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (0.0, 50.0)),
        layer="CUTTING",
        closed=True,
    )
    scene.add_line((10.0, 0.0), (10.0, 50.0), layer="BEND")
    scene.add_circle((25.0, 25.0), 3.0, layer="HOLE")
    return PartRenderData(scene=scene, material=box(0.0, 0.0, 100.0, 50.0))


def _request(render: PartRenderData) -> ManufacturingResolveRequest:
    return ManufacturingResolveRequest(
        source_revision="issue470-t4",
        source_fingerprint="gate-a-baseline",
        cache_key_fingerprint="gate-a-baseline",
        input_snapshot={"model": "金庫型", "t": 2.0},
        settings={"t": 2.0},
        canonical_part_keys=("indicator_box",),
        parts=(
            ManufacturingPartInput(
                part_key="indicator_box",
                render_data=render,
                scene_values={"part_key": "indicator_box"},
            ),
        ),
        operator_finished_dimensions=(100.0, 50.0, 20.0),
        cabinet_model="金庫型",
    )


def _primitive_signature(scene: DrawingScene):
    rows = []
    for item in tuple(scene.primitives):
        rows.append(repr(item))
    return tuple(rows)


def _dxf_signature(path: Path):
    doc = ezdxf.readfile(path)
    rows = []
    for entity in doc.modelspace():
        layer = str(entity.dxf.layer)
        kind = str(entity.dxftype())
        if kind == "LINE":
            payload = (
                round(float(entity.dxf.start.x), 6),
                round(float(entity.dxf.start.y), 6),
                round(float(entity.dxf.end.x), 6),
                round(float(entity.dxf.end.y), 6),
            )
        elif kind in {"LWPOLYLINE", "POLYLINE"}:
            if kind == "LWPOLYLINE":
                payload = tuple(
                    (round(float(x), 6), round(float(y), 6))
                    for x, y, *_ in entity.get_points()
                )
            else:
                payload = tuple(
                    (round(float(v.dxf.location.x), 6), round(float(v.dxf.location.y), 6))
                    for v in entity.vertices
                )
        elif kind == "CIRCLE":
            payload = (
                round(float(entity.dxf.center.x), 6),
                round(float(entity.dxf.center.y), 6),
                round(float(entity.dxf.radius), 6),
            )
        else:
            payload = ()
        rows.append((kind, layer, payload))
    return tuple(rows)


def test_gate_a_foundation_status_is_independently_resolvable_and_frozen():
    import ae_engine.joint_marking_policy as policy

    resolver = getattr(policy, "resolve_joint_marking_foundation_status", None)
    assert callable(resolver), "R3/T4: dormant Gate A foundation status resolver is missing"

    status = resolver()
    assert status.gate_state == GATE_A_STATE
    assert status.activation_enabled is False
    assert status.export_disposition == "UNRESOLVED"
    assert status.production_policy_count == 0
    with pytest.raises(FrozenInstanceError):
        status.activation_enabled = True


def test_manufacturing_owner_reaches_gate_a_status_without_activation():
    import phase6_manufacturing_service as service

    render = _baseline_render()
    result = service.resolve(_request(render))

    status = getattr(result.diagnostics, "joint_marking_foundation", None)
    assert status is not None, "R3/T4: manufacturing owner does not expose dormant marking foundation"
    assert status.gate_state == GATE_A_STATE
    assert status.activation_enabled is False
    assert status.production_policy_count == 0


def test_dormant_integration_preserves_final_scene_material_and_zero_joint_marking():
    import phase6_manufacturing_service as service

    render = _baseline_render()
    scene_before = _primitive_signature(render.scene)
    material_before = bytes(render.material.wkb)

    result = service.resolve(_request(render))
    resolved_render = result.geometry.part("indicator_box").render_data

    assert resolved_render is render
    assert _primitive_signature(resolved_render.scene) == scene_before
    assert bytes(resolved_render.material.wkb) == material_before
    assert not any(
        str(getattr(item, "layer", "")) == "MARKING"
        for item in resolved_render.scene.primitives
    )


def test_dormant_gate_a_dxf_entity_set_matches_pre_feature_baseline(tmp_path):
    import phase6_manufacturing_service as service

    render = _baseline_render()
    baseline = ResolvedManufacturingGeometry(
        parts=(ResolvedManufacturingPart("indicator_box", render),)
    )
    result = service.resolve(_request(render))

    baseline_dir = tmp_path / "baseline"
    gate_a_dir = tmp_path / "gate_a"
    baseline_paths = save_resolved_manufacturing_geometry_dxf(
        baseline, baseline_dir, overwrite=True
    )
    gate_a_paths = save_resolved_manufacturing_geometry_dxf(
        result.geometry, gate_a_dir, overwrite=True
    )

    assert set(baseline_paths) == set(gate_a_paths) == {"indicator_box"}
    assert _dxf_signature(Path(baseline_paths["indicator_box"])) == _dxf_signature(
        Path(gate_a_paths["indicator_box"])
    )
    assert not any(
        layer == "MARKING"
        for _kind, layer, _payload in _dxf_signature(Path(gate_a_paths["indicator_box"]))
    )

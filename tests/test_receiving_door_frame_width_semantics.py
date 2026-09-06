from __future__ import annotations

from pathlib import Path

import pytest

from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.manufacturing_api import build_part_render_data, door_finished_face_size
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges


# Requirement RED: Receiving FW=29 is already the formed outside occupation.\nPROJECT_ROOT = Path(__file__).resolve().parents[1]


def _door(*, model_name: str, height: float, frame_width: float, edges: DoorFrameEdges) -> DoorPartSpec:
    return DoorPartSpec(
        width=800.0,
        height=float(height),
        thickness=2.0,
        frame_width=float(frame_width),
        model_name=model_name,
        gap_w=3.5,
        gap_h=3.5,
        fold_left=19.0,
        fold_right=19.0,
        fold_top=19.0,
        fold_bottom=19.0,
        frame_edges=edges,
    )


def _blank_size(spec: DoorPartSpec) -> tuple[float, float]:
    render = build_part_render_data(
        spec,
        ManufacturingContext(resource_root=PROJECT_ROOT, draw_stock=False),
    )
    minx, miny, maxx, maxy = (float(value) for value in render.material.bounds)
    return maxx - minx, maxy - miny


def test_receiving_upper_door_uses_29_mm_formed_frame_occupation_without_adding_2t_again():
    spec = _door(
        model_name="受電箱",
        height=1100.0,
        frame_width=29.0,
        edges=DoorFrameEdges(bottom=False),
    )

    assert door_finished_face_size(spec) == pytest.approx((735.0, 1064.0))
    assert _blank_size(spec) == pytest.approx((769.0, 1098.0))


def test_receiving_lower_door_uses_same_29_mm_formed_frame_occupation_on_all_four_edges():
    spec = _door(
        model_name="受電箱",
        height=500.0,
        frame_width=29.0,
        edges=DoorFrameEdges(),
    )

    assert door_finished_face_size(spec) == pytest.approx((735.0, 435.0))
    assert _blank_size(spec) == pytest.approx((769.0, 469.0))


def test_vault_keeps_material_fw_semantics_so_25_plus_2t_still_occupies_29_mm():
    spec = _door(
        model_name="金庫型",
        height=500.0,
        frame_width=25.0,
        edges=DoorFrameEdges(),
    )

    assert door_finished_face_size(spec) == pytest.approx((735.0, 435.0))
    assert _blank_size(spec) == pytest.approx((769.0, 469.0))


def test_receiving_inner_door_derivation_uses_the_same_corrected_outer_door_finished_face():
    from ae_engine.cabinet_types.receiving import apply_family_defaults, derive_inner_door_frame_sets
    from ae_engine.cabinet_types import policy as cabinet_family_policy

    snapshot = apply_family_defaults({
        "model": "金庫型",
        "w": 400.0,
        "h": 600.0,
        "d": 250.0,
        "t": 2.0,
        "fw": 25.0,
    })

    panels = cabinet_family_policy.derive_inner_door_panels(snapshot)
    assert len(panels) == 1
    assert (panels[0].width, panels[0].height) == pytest.approx((635.0, 1014.0))

    frame_sets = derive_inner_door_frame_sets(snapshot)
    assert len(frame_sets) == 1
    assert frame_sets[0].spans == {
        "top": pytest.approx(635.0),
        "left": pytest.approx(1014.0),
        "right": pytest.approx(1014.0),
    }

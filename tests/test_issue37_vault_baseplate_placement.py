from __future__ import annotations

import pytest

from ae_engine.assembly_geometry import place_assembly_triangles
from ae_engine.assembly_placement import resolve_assembly_placement
from phase6_designer_workspace import Phase6DesignerWorkspace


def _vault_snapshot():
    return {
        "model": "金庫型",
        "w": 400.0,
        "h": 600.0,
        "d": 250.0,
        "t": 2.0,
        "fw": 25.0,
        "existing_parts": ["box_body", "head", "tail", "door", "base_plate"],
    }


def _rect_triangles(width: float, height: float):
    half_w = width / 2.0
    half_h = height / 2.0
    return (
        ((-half_w, -half_h, 0.0), (half_w, -half_h, 0.0), (half_w, half_h, 0.0)),
        ((-half_w, -half_h, 0.0), (half_w, half_h, 0.0), (-half_w, half_h, 0.0)),
    )


def test_vault_base_plate_resolves_authoritative_center_datum():
    placement = resolve_assembly_placement(_vault_snapshot(), "base_plate")

    assert placement.relationship == "BASE_PLATE"
    assert placement.parent_assembly_node == "box_body"
    assert placement.anchor == "box_body:center:base_plate"
    assert placement.mate_target == "box_body:base_plate_plane"
    assert placement.placement_kind == "base_plate"
    assert placement.world_offset == pytest.approx((0.0, 0.0, 0.0))
    assert placement.semantic_position == pytest.approx((0.0, 0.0, 0.0))


def test_vault_base_plate_folded_face_stays_inside_box_world_bounds():
    snapshot = _vault_snapshot()
    placement = resolve_assembly_placement(snapshot, "base_plate")

    # Vault nominal finished face after the existing 55 mm family shrink.
    local = _rect_triangles(290.0, 490.0)
    world = place_assembly_triangles(
        local,
        placement.placement_kind,
        (snapshot["w"], snapshot["h"], snapshot["d"]),
        placement.world_offset,
    )

    xs = [point[0] for tri in world for point in tri]
    ys = [point[1] for tri in world for point in tri]
    assert min(xs) >= -snapshot["w"] / 2.0 - 1e-6
    assert max(xs) <= snapshot["w"] / 2.0 + 1e-6
    assert min(ys) >= -snapshot["h"] / 2.0 - 1e-6
    assert max(ys) <= snapshot["h"] / 2.0 + 1e-6


def test_vault_base_plate_placement_persists_through_workspace_snapshot():
    snapshot = _vault_snapshot()
    ws = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": list(snapshot["existing_parts"]),
        "active_part": "base_plate",
    })
    stored = ws.resolve_and_store_assembly_placements(
        snapshot,
        resolver=resolve_assembly_placement,
    )
    assert stored["base_plate"]["placement_kind"] == "base_plate"
    assert stored["base_plate"]["world_offset"] == pytest.approx([0.0, 0.0, 0.0])

    rebuilt = Phase6DesignerWorkspace.from_snapshot(ws.snapshot())
    assert rebuilt.assembly_placements_snapshot()["base_plate"] == stored["base_plate"]


def test_bridge_uses_resolver_not_legacy_base_mapping():
    import fold_designer_bridge as bridge

    assert "base_plate" not in bridge._PHASE6_ASSEMBLY_PLACEMENTS
    kind, offset = bridge._phase6_assembly_placement_for_part(_vault_snapshot(), "base_plate")
    assert kind == "base_plate"
    assert offset == pytest.approx((0.0, 0.0, 0.0))

"""#2517: real persisted Receiving Sets need actual CROSS-Bay collision pairs.

The prior two-Set four-Bay GUI/DXF regression audited each Bay separately.
No combination of those independent audits can detect two neighbouring
cabinets crossing at the shared Joint plane.
"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import (
    ResolvedManufacturingGeometry, ResolvedManufacturingPart,
)
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays,
)
from tests.test_issue1502_current_csv_multi_bay_once import _provider
from tests.test_issue2517_saved_two_sets_four_bays_bom_collision_gui_dxf import (
    _saved_two_sets,
)


def test_real_saved_two_sets_both_cross_bay_world_matrices_are_stable(tmp_path):
    saved, original_bytes, authored, loaded = _saved_two_sets(tmp_path)
    before = deepcopy(loaded)
    original_provider, original_calls = _provider(authored)
    restored_provider, restored_calls = _provider(loaded)
    sets = loaded["receiving_layout"]["sets"]
    for si in (0, 1):
        existing = api.project_receiving_set_cross_bay_collision_display_audit(
            authored["receiving_layout"], original_provider,
            set_index=si, thickness_mm=loaded["t"],
        )
        after = api.project_receiving_set_cross_bay_collision_display_audit(
            loaded["receiving_layout"], restored_provider,
            set_index=si, thickness_mm=loaded["t"],
        )
        assert existing == after
        assert after.set_id == sets[si]["stable_id"]
        assert after.bay_ids == tuple(b["stable_id"] for b in sets[si]["bays"])
        assert len(after.physical_keys_by_bay) == 2
        assert after.bay_offsets[0] == (0.0, 0.0, 0.0)
        assert after.bay_offsets[1][0] == pytest.approx(sets[si]["bays"][0]["width"])
        assert all(keys for keys in after.physical_keys_by_bay)
        assert all(any(k.endswith("::box_body:left_side") for k in keys)
                   and any(k.endswith("::box_body:right_side") for k in keys)
                   and any(k.endswith("::box_body:back") for k in keys)
                   for keys in after.physical_keys_by_bay)
        expected = len(after.physical_keys_by_bay[0]) * len(after.physical_keys_by_bay[1])
        assert after.evaluated_pair_count == expected
        assert len(after.pairs) == expected
        first, second = (set(group) for group in after.physical_keys_by_bay)
        assert not first & second
        assert all((row.left in first and row.right in second)
                   or (row.right in first and row.left in second)
                   for row in after.pairs)
        # Inter-Bay mating has no global certified relief rule. The surface
        # classifier may produce clean or unresolved *diagnostic* rows but
        # can never promote independent Bays to verified contacts.
        assert all(row.status in (
            "AABB_SEPARATED", "NO_NONCOPLANAR_CROSSING",
            "UNRESOLVED_CROSSING",
        ) for row in after.pairs)
    assert original_calls == restored_calls == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert before == loaded
    assert saved.read_bytes() == original_bytes


def _simple_two_bay():
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )


def _synthetic_provider(*_indices):
    return ResolvedManufacturingGeometry((
        ResolvedManufacturingPart(
            part_key="box_body",
            render_data=SimpleNamespace(),
            placement="box_body",
            offset=(0.0, 0.0, 0.0),
        ),
    ))


def test_actual_joint_offset_detects_cross_bay_mesh_penetration(monkeypatch):
    from ae_engine import receiving_cross_bay_collision_display as impl

    # The right-hand side of Bay 1 intersects the left-hand side of Bay 2
    # ONLY after applying the Engine's physical 800 mm Joint translation.
    calls = []
    a = ((400., -1., -1.), (400., 1., -1.), (400., 0., 1.))
    b = ((-401., 0., -0.5), (-399., 0., -0.5), (-400., 0., 1.))
    remote = ((10000., 0., 0.), (10001., 0., 0.), (10000., 1., 0.))

    def real_owner_stub(parts, dimensions, thickness):
        calls.append((tuple(p.part_key for p in parts), dimensions, thickness))
        if len(calls) == 1:
            return {"world_triangles_by_part": {
                "box_body": (a,), "box_body:left_side": (remote,),
                "box_body:back": (remote,), "box_body:right_side": (a,),
            }}
        return {"world_triangles_by_part": {
            "box_body": (b,), "box_body:left_side": (b,),
            "box_body:back": (remote,), "box_body:right_side": (remote,),
        }}

    monkeypatch.setattr(impl, "build_joint_world_geometry", real_owner_stub)
    input_layout = _simple_two_bay()
    original = deepcopy(input_layout)
    audit = api.project_receiving_set_cross_bay_collision_display_audit(
        input_layout, _synthetic_provider, set_index=0, thickness_mm=2.0,
    )
    assert len(calls) == 2
    assert audit.bay_offsets == ((0.0, 0.0, 0.0), (800.0, 0.0, 0.0))
    assert audit.evaluated_pair_count == 9
    assert len(audit.unresolved) >= 1
    assert any(p.left.endswith("::box_body:right_side")
               and p.right.endswith("::box_body:left_side")
               or p.right.endswith("::box_body:right_side")
               and p.left.endswith("::box_body:left_side")
               for p in audit.unresolved)
    with pytest.raises(ValueError, match="RECEIVING_CROSS_BAY_CROSSING_UNVERIFIED"):
        audit.require_no_unresolved()
    assert input_layout == original


@pytest.mark.parametrize("bad", (True, -1, 1, 0.0, None, "0"))
def test_cross_bay_rejects_invalid_set_index(bad):
    with pytest.raises(IndexError, match="RECEIVING_CROSS_BAY_SET_INDEX_INVALID"):
        api.project_receiving_set_cross_bay_collision_display_audit(
            _simple_two_bay(), _synthetic_provider,
            set_index=bad, thickness_mm=2,
        )


@pytest.mark.parametrize("bad", (True, 0, -2, None, float("nan"), float("inf")))
def test_cross_bay_rejects_invalid_sheet_thickness(bad):
    with pytest.raises(ValueError, match="RECEIVING_CROSS_BAY_THICKNESS_INVALID"):
        api.project_receiving_set_cross_bay_collision_display_audit(
            _simple_two_bay(), _synthetic_provider,
            set_index=0, thickness_mm=bad,
        )


def test_missing_second_bay_scene_cannot_pass_as_zero_collision(monkeypatch):
    from ae_engine import receiving_cross_bay_collision_display as impl
    triangle = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    monkeypatch.setattr(impl, "build_joint_world_geometry",
                        lambda *_: {"world_triangles_by_part": {
                            "box_body": (triangle,),
                            "box_body:left_side": (triangle,),
                            "box_body:back": (triangle,),
                            "box_body:right_side": (triangle,),
                        }})
    seen = []

    def missing_on_second(si, bi):
        seen.append((si, bi))
        if bi == 1:
            return None
        return _synthetic_provider(si, bi)

    with pytest.raises(ValueError, match="RECEIVING_CROSS_BAY_FINALSCENE_REQUIRED"):
        api.project_receiving_set_cross_bay_collision_display_audit(
            _simple_two_bay(), missing_on_second,
            set_index=0, thickness_mm=2,
        )
    assert seen == [(0, 0), (0, 1)]


def test_one_bay_and_unapproved_provider_fail_closed():
    single = new_receiving_layout(width=800, height=1600, depth=350)
    with pytest.raises(ValueError, match="RECEIVING_CROSS_BAY_AT_LEAST_TWO_BAYS_REQUIRED"):
        api.project_receiving_set_cross_bay_collision_display_audit(
            single, _synthetic_provider, set_index=0, thickness_mm=2,
        )
    with pytest.raises(TypeError, match="RECEIVING_CROSS_BAY_RESOLVER_REQUIRED"):
        api.project_receiving_set_cross_bay_collision_display_audit(
            _simple_two_bay(), object(), set_index=0, thickness_mm=2,
        )


def test_missing_physical_world_is_not_misreported_as_empty_pair_matrix(monkeypatch):
    from ae_engine import receiving_cross_bay_collision_display as impl

    monkeypatch.setattr(impl, "build_joint_world_geometry",
                        lambda *_: {"world_triangles_by_part": {
                            "box_body": (),
                            "box_body:left_side": (),
                            "box_body:back": (),
                            "box_body:right_side": (),
                        }})
    with pytest.raises(ValueError, match="RECEIVING_CROSS_BAY_MISSING_PHYSICAL_WORLD_MESH"):
        api.project_receiving_set_cross_bay_collision_display_audit(
            _simple_two_bay(), _synthetic_provider,
            set_index=0, thickness_mm=2,
        )

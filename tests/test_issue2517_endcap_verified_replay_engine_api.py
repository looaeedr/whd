"""#2517: certified EndCap physical relief PartSpec replay is Engine-owned."""
import inspect
from types import SimpleNamespace

import pytest
from shapely.geometry import box

from ae_engine import manufacturing_api, replay_resolved_endcap_render
from ae_engine.contracts import EndCapPartSpec, ManufacturingContext
from phase6_manufacturing_service import _replay_endcap_render


def _part():
    spec = EndCapPartSpec(
        width=100.0, height=40.0, depth=80.0,
        thickness=2.0, frame_width=25.0,
    )
    return SimpleNamespace(
        part_key="head", part_spec=spec,
        manufacturing_context=ManufacturingContext(),
    )


def test_public_engine_owner_replays_verified_relief_without_mutating_spec(monkeypatch):
    part = _part()
    old = part.part_spec
    seen = []
    expected = SimpleNamespace(material=box(0, 0, 10, 10))

    def fake_build(spec, context):
        seen.append((spec, context))
        return expected

    monkeypatch.setattr(manufacturing_api, "build_part_render_data", fake_build)
    solution = SimpleNamespace(cut_polygon_2d=box(0, 0, 7, 9), solved_render_data=SimpleNamespace(material=box(0, 0, 10, 10)))
    assert manufacturing_api.replay_resolved_endcap_render is replay_resolved_endcap_render
    assert replay_resolved_endcap_render(part, solution) is expected
    assert part.part_spec is old
    assert part.part_spec.resolved_assembly_relief_cuts == ()
    assert len(seen) == 1
    new, context = seen[0]
    assert context is part.manufacturing_context
    assert new is not old
    assert len(new.resolved_assembly_relief_cuts) == 1
    assert len(new.resolved_assembly_relief_cuts[0]) == 4


def test_phase6_delegates_to_engine_and_does_not_serialize_cuts(monkeypatch):
    witness = object()
    part = object()
    solution = object()
    calls = []

    def fake_replay(p, s):
        calls.append((p, s))
        return witness

    monkeypatch.setattr("phase6_manufacturing_service.replay_resolved_endcap_render", fake_replay)
    assert _replay_endcap_render(part, solution) is witness
    assert calls == [(part, solution)]
    assert "resolved_assembly_relief_cuts" not in inspect.getsource(_replay_endcap_render)
    assert "serialize_joint_relief_polygons" not in inspect.getsource(_replay_endcap_render)


def test_lightweight_headless_fallback_and_fail_closed_without_part_spec():
    render = SimpleNamespace(material=box(0, 0, 10, 10))
    part = SimpleNamespace(part_key="head", part_spec=None)
    assert replay_resolved_endcap_render(part, SimpleNamespace(cut_polygon_2d=None, solved_render_data=render)) is render
    with pytest.raises(ValueError, match="authoritative relief replay unavailable: head"):
        replay_resolved_endcap_render(part, SimpleNamespace(cut_polygon_2d=None, solved_render_data=None))


def test_headless_replay_rejects_real_material_mismatch_without_gui_policy(monkeypatch):
    part = _part()
    canonical = SimpleNamespace(material=box(0, 0, 10, 10))
    monkeypatch.setattr(
        manufacturing_api, "build_part_render_data", lambda spec, ctx: canonical,
    )
    solution = SimpleNamespace(
        cut_polygon_2d=box(0, 0, 7, 9),
        solved_render_data=SimpleNamespace(material=box(0, 0, 9, 10)),
    )
    with pytest.raises(ValueError, match=r"2D/3D relief replay mismatch: head area=10\.000000"):
        replay_resolved_endcap_render(part, solution)
    # The caller's immutable PartSpec and prior canonical state remain intact.
    assert part.part_spec.resolved_assembly_relief_cuts == ()
    assert "symmetric_difference" not in inspect.getsource(
        __import__("phase6_manufacturing_service").resolve
    )


def test_engine_preserves_original_replay_tolerance_at_boundary(monkeypatch):
    part = _part()
    canonical = SimpleNamespace(material=box(0, 0, 10, 10))
    monkeypatch.setattr(
        manufacturing_api, "build_part_render_data", lambda spec, ctx: canonical,
    )
    # A 0.5e-5 mm² discrepancy remains accepted; 2e-5 mm² is rejected.
    small = SimpleNamespace(
        cut_polygon_2d=None,
        solved_render_data=SimpleNamespace(material=box(0, 0, 10.0000004, 10)),
    )
    assert replay_resolved_endcap_render(part, small) is canonical
    large = SimpleNamespace(
        cut_polygon_2d=None,
        solved_render_data=SimpleNamespace(material=box(0, 0, 10.000002, 10)),
    )
    with pytest.raises(ValueError, match="2D/3D relief replay mismatch"):
        replay_resolved_endcap_render(part, large)


def test_engine_requires_real_canonical_material_even_with_part_spec(monkeypatch):
    part = _part()
    monkeypatch.setattr(
        manufacturing_api, "build_part_render_data",
        lambda spec, ctx: SimpleNamespace(material=None),
    )
    with pytest.raises(ValueError, match="authoritative relief replay unavailable: head"):
        replay_resolved_endcap_render(
            part, SimpleNamespace(cut_polygon_2d=None, solved_render_data=None),
        )

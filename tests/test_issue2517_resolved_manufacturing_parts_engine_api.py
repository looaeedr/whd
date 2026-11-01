"""#2517: canonical physical part DTO materialization belongs to Engine."""
import inspect
from types import SimpleNamespace

import pytest
from ae_engine import manufacturing_api, materialize_resolved_manufacturing_parts
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
import phase6_manufacturing_service as service


def _part(name, *, render=None, x=None, y=None, placement="offset", offset=(0, 0, 0)):
    return SimpleNamespace(
        part_key=name, render_data=render or object(),
        x_profile=x or (), y_profile=y or (),
        placement=placement, offset=offset,
    )


def test_engine_builds_same_ordered_physical_dtos_without_geometry_inference():
    x = {"len": 17.0, "core": True}
    y = {"len": 22.0, "angle": 90.0}
    render = object()
    source = (
        _part("head", render=render, x=(x,), y=(y,), placement="top", offset=(0, 1, 2)),
        _part("box_body", render=object()),
    )
    result = materialize_resolved_manufacturing_parts(source)
    assert manufacturing_api.materialize_resolved_manufacturing_parts is materialize_resolved_manufacturing_parts
    assert all(isinstance(p, ResolvedManufacturingPart) for p in result)
    assert tuple(p.part_key for p in result) == ("head", "box_body")
    assert result[0].render_data is render
    assert result[0].placement == "top" and result[0].offset == (0, 1, 2)
    assert result[0].x_profile == ({"len": 17.0, "core": True},)
    assert result[0].y_profile == ({"len": 22.0, "angle": 90.0},)
    assert result[0].x_profile[0] is not x
    assert result[0].y_profile[0] is not y
    x["len"] = 999.0
    y["len"] = 999.0
    assert result[0].x_profile[0]["len"] == 17.0
    assert "len" not in result[0].y_profile[0]


def test_empty_physical_set_is_preserved_and_duplicate_fails_at_engine_contract():
    assert materialize_resolved_manufacturing_parts(()) == ()
    source = (_part("head"), _part("head"))
    parts = materialize_resolved_manufacturing_parts(source)
    with pytest.raises(ValueError, match="duplicate canonical part: head"):
        ResolvedManufacturingGeometry(parts=parts)


def test_service_delegates_and_no_longer_builds_canonical_part_spec():
    src = inspect.getsource(service.resolve)
    assert "materialize_resolved_manufacturing_parts(parts)" in src
    assert "ResolvedManufacturingPart(" not in src
    assert "dict(seg) for seg in tuple(part.x_profile or ())" not in src

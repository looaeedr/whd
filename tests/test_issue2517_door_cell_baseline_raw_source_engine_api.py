"""#2517 Door-cell DXF baseline preview must validate raw physical source before cache."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import ae, manufacturing_api
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges


def _values():
    return {
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 4.0,
        "door_fold_l": 15.0, "door_fold_r": 17.0,
        "door_fold_t": 12.0, "door_fold_b": 14.0,
    }


def _projection(values, *, family="金庫型", width=420.0, height=600.0, cache=None):
    return manufacturing_api.project_operator_door_cell_baseline(
        values, family_model=family, cell_width=width, cell_height=height,
        frame_edges=DoorFrameEdges(left=True, right=False, top=False, bottom=True),
        cache=cache,
    )


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field,bad", (
    ("w", True), ("w", float("nan")), ("h", False), ("h", 0),
    ("t", True), ("t", "nan"), ("fw", False), ("fw", float("inf")),
    ("door_gap_w", True), ("door_gap_h", "inf"),
    ("door_fold_l", True), ("door_fold_r", float("nan")),
    ("door_fold_t", False), ("door_fold_b", "oops"),
))
def test_raw_invalid_baseline_input_never_reaches_cache_or_dxf_stretch(
    monkeypatch, family, field, bad,
):
    monkeypatch.setattr(ae, "has_baseline_part", lambda *args: True)
    monkeypatch.setattr(ae, "baseline_expected_path", lambda *args: "/tmp/door.dxf")
    visited = []
    monkeypatch.setattr(ae, "baseline_source_fingerprint",
                        lambda path: visited.append("fingerprint") or ("fp",))
    monkeypatch.setattr(ae, "get_stretched_door_data",
                        lambda *args, **kw: pytest.fail(
                            "untrusted physical source reached Door DXF geometry"
                        ))
    source = _values()
    overrides = {}
    if field in {"w", "h"}:
        overrides["width" if field == "w" else "height"] = bad
    else:
        source[field] = bad
    before = deepcopy(source)
    baseline = _projection(source, family=family, **overrides, cache={})
    assert baseline == (None, "未使用基準檔（程式計算生成）")
    assert visited == []
    assert source == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_valid_numeric_strings_share_verified_baseline_cache_with_numbers(
    monkeypatch, family,
):
    monkeypatch.setattr(ae, "has_baseline_part", lambda *args: True)
    monkeypatch.setattr(ae, "baseline_expected_path",
                        lambda *args: "/tmp/door-fixture.dxf")
    monkeypatch.setattr(ae, "baseline_source_fingerprint", lambda path: ("fp",))
    monkeypatch.setattr(ae, "baseline_source_label",
                        lambda model, part: "baseline:" + str(model))
    scene = object()
    calls = []
    def stretch(model, *args, **kw):
        calls.append((model, args, kw))
        return SimpleNamespace(scene=scene)
    monkeypatch.setattr(ae, "get_stretched_door_data", stretch)
    cache = {}
    values = _values()
    source = {key: str(value) for key, value in values.items()}
    original = deepcopy(source)
    a = _projection(source, family=family, width="420.0", height="600.0",
                    cache=cache)
    b = _projection(values, family=family, cache=cache)
    assert a == b == (scene, "baseline:金庫型")
    assert len(calls) == 1
    assert calls[0][1][:3] == (420.0, 600.0, 2.0)
    assert source == original


def test_invalid_same_source_cannot_hit_a_previously_cached_scene(monkeypatch):
    monkeypatch.setattr(ae, "has_baseline_part", lambda *args: True)
    monkeypatch.setattr(ae, "baseline_expected_path", lambda *args: "/tmp/door.dxf")
    monkeypatch.setattr(ae, "baseline_source_fingerprint", lambda path: ("fp",))
    monkeypatch.setattr(ae, "baseline_source_label", lambda *args: "baseline")
    calls = []
    monkeypatch.setattr(ae, "get_stretched_door_data", lambda *a, **kw:
                        calls.append(1) or SimpleNamespace(scene="scene"))
    cache = {}
    assert _projection(_values(), cache=cache) == ("scene", "baseline")
    invalid = _values()
    invalid["t"] = True
    before = deepcopy(invalid)
    assert _projection(invalid, cache=cache) == (
        None, "未使用基準檔（程式計算生成）",
    )
    assert calls == [1]
    assert invalid == before


def test_missing_baseline_keeps_original_display_label_even_for_stale_inputs(
    monkeypatch,
):
    monkeypatch.setattr(ae, "has_baseline_part", lambda *args: False)
    monkeypatch.setattr(ae, "baseline_source_label",
                        lambda model, part: "missing:" + str(model))
    values = _values()
    values["t"] = True
    assert _projection(values) == (None, "missing:")

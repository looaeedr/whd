"""#2517: BoxBody editable-face baseline sources must traverse public Engine API."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ae_engine import ae, manufacturing_api as api
from gui_modules.rendering.box_body_view import box_body_baseline_faces


def _values():
    return {
        "w": 500.0, "h": 600.0, "d": 200.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
        "z_comp": 2.0,
    }


def test_public_engine_face_source_matches_real_vault_baseline():
    values = _values()
    cache = {}
    actual = api.project_operator_box_body_baseline_face_features(
        "金庫型", values, cache=cache
    )
    expected = ae.get_box_body_baseline_face_features("金庫型", **values)
    assert actual == expected
    assert set(actual) == {"left", "back", "right"}
    assert sum(len(v) for v in actual.values()) > 0
    assert len(cache) == 1
    assert api.project_operator_box_body_baseline_face_features(
        "金庫型", values, cache=cache
    ) is actual
    changed = {**values, "w": 501.0}
    api.project_operator_box_body_baseline_face_features(
        "金庫型", changed, cache=cache
    )
    assert len(cache) == 2


def test_missing_source_does_not_fabricate_edited_face_features():
    assert api.project_operator_box_body_baseline_face_features(
        "", _values()
    ) == {"left": [], "back": [], "right": []}
    assert api.operator_box_body_baseline_source_label(
        "金庫型"
    ) == ae.box_body_baseline_source_label("金庫型")


def test_gui_baseline_projection_delegates_without_accessing_low_level_ae(monkeypatch):
    observed = []
    result = {"left": ["engine"], "back": [], "right": []}
    def project(*args, **kwargs):
        observed.append((args, kwargs))
        return result
    monkeypatch.setattr(api, "project_operator_box_body_baseline_face_features", project)
    cache = {}
    host = SimpleNamespace(
        _baseline_source_model=lambda: "金庫型",
        _box_body_corner_policies=lambda fw: ("head", "tail"),
        _box_body_baseline_face_cache=cache,
    )
    assert box_body_baseline_faces(host, _values()) is result
    assert observed == [(("金庫型", _values()), {
        "head_corner_policy": "head",
        "tail_corner_policy": "tail",
        "cache": cache,
    })]
    assert cache == {}
    source = Path("gui_modules/rendering/box_body_view.py").read_text(encoding="utf-8")
    assert "ae_module." not in source
    gui_source = Path("gui.py").read_text(encoding="utf-8")
    assert "baseline_label_fn=manufacturing_api.operator_box_body_baseline_source_label" in gui_source
    assert "_box_body_baseline_faces_impl(self, val, ae_module=ae)" not in gui_source

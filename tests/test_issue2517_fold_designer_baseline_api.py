"""#2517: source-hole projection moves from GUI to Engine public API."""
from __future__ import annotations
import inspect
from types import SimpleNamespace
import pytest
from ae_engine import manufacturing_api, fold_designer_secondary_scene_rows, query_fold_designer_baseline_rows
from ae_engine import fold_designer_baseline_api as owner
from ae_engine.sheetmetal_drawing import DrawingScene
from gui_modules.application import fold_designer_manufacturing_projection as adapter


def _scene():
    s = DrawingScene()
    s.add_polyline([(0, 0), (100, 0), (100, 80), (0, 80)], layer="CUTTING", closed=True)
    s.add_polyline([(10, 20), (30, 20), (30, 40), (10, 40)], layer="CUTTING", closed=True)
    s.add_circle((50, 60), 5, layer="BLIND_HOLE")
    s.add_circle((70, 70), 3, layer="DATUM")
    return s


def _values():
    return {"w": 500, "h": 600, "d": 200, "t": 2, "fw": 25}


def test_engine_public_source_hole_rows_and_original_gui_shape():
    assert fold_designer_secondary_scene_rows is manufacturing_api.fold_designer_secondary_scene_rows
    assert query_fold_designer_baseline_rows is manufacturing_api.query_fold_designer_baseline_rows
    expected = [
        {"kind": "方孔", "layer": "CUTTING", "x": 20.0, "y": 30.0, "d1": 20.0, "d2": 20.0},
        {"kind": "圓孔", "layer": "BLIND_HOLE", "x": 50.0, "y": 60.0, "d1": 10.0, "d2": 0.0},
    ]
    assert fold_designer_secondary_scene_rows(_scene()) == expected
    assert adapter._fold_designer_secondary_scene_rows(_scene()) == expected


@pytest.mark.parametrize("part,is_tail", [("head", False), ("tail", True)])
def test_real_endcap_source_is_engine_only(monkeypatch, part, is_tail):
    calls = []
    def endcap(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(scene=_scene())
    monkeypatch.setattr(owner.ae, "get_stretched_end_cap_data", endcap)
    assert query_fold_designer_baseline_rows(part, "金庫型", _values())[0]["x"] == 20
    assert calls == [(("金庫型", 500., 600., 200., 2.),
                      {"FW_val": 25., "is_tail": is_tail})]


def test_door_width_and_baseline_transform_owned_by_engine(monkeypatch):
    calls = []
    monkeypatch.setattr(owner.ae, "has_baseline_part", lambda *a: True)
    def fw(source, *, frame_width, thickness):
        calls.append(("fw", source, frame_width, thickness))
        return 23.
    def door(*args, **kw):
        calls.append(("door", args, kw))
        return SimpleNamespace(scene=_scene())
    monkeypatch.setattr(owner.cabinet_family_policy, "door_material_frame_width", fw)
    monkeypatch.setattr(owner.ae, "get_stretched_door_data", door)
    assert query_fold_designer_baseline_rows("door", "受電箱", _values())[1]["d1"] == 10.
    assert calls[0] == ("fw", "受電箱", 25., 2.)
    assert calls[1][1][:5] == ("受電箱", 500., 600., 2., 23.)
    assert calls[1][2]["frame_edges"] == owner.DoorFrameEdges()


def test_gui_forwards_inputs_and_never_fabricates_optional_baseline(monkeypatch):
    class Var:
        def __init__(self, value):
            self.value = value
        def get(self):
            return self.value
    host = SimpleNamespace(w_var=Var("500"), h_var=Var("600"), d_var=Var("200"),
                           t_var=Var("2"), fw_z_var=Var("25"))
    calls = []
    def api(part, model, inputs):
        calls.append((part, model, dict(inputs)))
        return [{"kind": "sentinel"}]
    monkeypatch.setattr(manufacturing_api, "query_fold_designer_baseline_rows", api)
    assert adapter._query_fold_designer_baseline_data(host, "head", "金庫型", {}) == [{"kind": "sentinel"}]
    assert calls == [("head", "金庫型", {"w": "500", "h": "600", "d": "200",
                                      "t": "2", "fw": "25"})]
    monkeypatch.setattr(manufacturing_api, "query_fold_designer_baseline_rows",
                        lambda *a: (_ for _ in ()).throw(ValueError("no source")))
    assert adapter._query_fold_designer_baseline_data(host, "head", "金庫型", {}) == []
    assert query_fold_designer_baseline_rows("door", "", _values()) == []
    assert "manufacturing_api.query_fold_designer_baseline_rows(" in inspect.getsource(adapter._query_fold_designer_baseline_data)
    assert "get_stretched_door_data(" not in inspect.getsource(adapter._query_fold_designer_baseline_data)
    assert "manufacturing_api.fold_designer_secondary_scene_rows(" in inspect.getsource(adapter._fold_designer_secondary_scene_rows)

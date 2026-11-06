# -*- coding: utf-8 -*-
"""#2517: all Receiving multi settings version labels use public Engine API."""
import inspect
from ae_engine import manufacturing_api
from gui_modules.application import receiving_multi_settings_window as multi


class _Canvas:
    def __init__(self):
        self.labels = []
    def delete(self, *_args):
        pass
    def winfo_width(self):
        return 400
    def winfo_height(self):
        return 300
    def cget(self, key):
        return {"width": "400", "height": "300"}[key]
    def create_rectangle(self, *_args, **_kwargs):
        pass
    def create_line(self, *_args, **_kwargs):
        pass
    def create_text(self, *_args, **kwargs):
        self.labels.append(kwargs.get("text"))
        return len(self.labels)


def test_multi_bay_2d_labels_are_actual_public_engine_candidate_names(monkeypatch):
    calls = []
    original = manufacturing_api.receiving_candidate_version_label
    def public_label(version):
        calls.append(version)
        return original(version)
    monkeypatch.setattr(manufacturing_api, "receiving_candidate_version_label", public_label)
    canvas = _Canvas()
    multi.paint_connected_bays(
        canvas, 1, version_labels=({
            "head": "head-v1",
            "tail": "tail-v2",
            "inner-door": "",
        },),
    )
    assert calls == ["head-v1", "tail-v2"]
    assert "封頭：版本一" in canvas.labels
    assert "封尾：版本二" in canvas.labels
    assert "內門：即時" in canvas.labels


def test_multi_settings_no_longer_imports_private_candidate_label_owner():
    source = inspect.getsource(multi)
    assert "from ae_engine.receiving_hole_candidates import version_label" not in source
    assert source.count("manufacturing_api.receiving_candidate_version_label(") == 4

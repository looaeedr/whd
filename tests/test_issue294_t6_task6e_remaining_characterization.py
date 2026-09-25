from __future__ import annotations

from types import SimpleNamespace

import gui


class Var:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def test_task6e_draw_preview_routes_only_visible_corner_data_view():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)

    assert gui.Phase6ApplicationHost.draw_preview(host) is None

    calls = []
    designer = SimpleNamespace(
        _phase6_3d_display_mode="assembly",
        corner_data_canvas=object(),
        _phase6_refresh_corner_data_unfold_view=lambda: calls.append("refresh") or "REFRESHED",
    )
    host.fold_designer_app = designer
    assert gui.Phase6ApplicationHost.draw_preview(host) is None
    assert calls == []

    designer._phase6_3d_display_mode = "corner_data"
    designer.corner_data_canvas = None
    assert gui.Phase6ApplicationHost.draw_preview(host) is None
    assert calls == []

    designer.corner_data_canvas = object()
    assert gui.Phase6ApplicationHost.draw_preview(host) == "REFRESHED"
    assert calls == ["refresh"]


def test_task6e_box_body_baseline_faces_preserve_cache_and_ae_inputs(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host._box_body_baseline_face_cache = {}
    host._baseline_source_model = lambda: "MODEL"
    host._box_body_corner_policies = lambda fw: ("HEAD-POLICY", "TAIL-POLICY")

    val = {
        "w": 1000.0,
        "h": 2000.0,
        "d": 350.0,
        "t": 2.0,
        "fw": 62.0,
        "zl1": 20.0,
        "zl2": 25.0,
        "zr1": 20.0,
        "zr2": 25.0,
        "z_comp": 3.0,
    }
    resolved = {"left": ["L"], "back": ["B"], "right": ["R"]}
    calls = []

    monkeypatch.setattr(gui.ae, "has_baseline_part", lambda model, name: (model, name) == ("MODEL", "箱身.dxf"))
    monkeypatch.setattr(gui.ae, "baseline_expected_path", lambda model, name: f"/{model}/{name}")
    monkeypatch.setattr(gui.ae, "baseline_source_fingerprint", lambda path: f"FP:{path}")

    def fake_faces(model, **kwargs):
        calls.append((model, kwargs))
        return resolved

    monkeypatch.setattr(gui.ae, "get_box_body_baseline_face_features", fake_faces)

    first = gui.Phase6ApplicationHost._box_body_baseline_faces(host, val)
    second = gui.Phase6ApplicationHost._box_body_baseline_faces(host, val)

    assert first is resolved
    assert second is resolved
    assert len(calls) == 1
    model, kwargs = calls[0]
    assert model == "MODEL"
    assert kwargs == {
        "w": 1000.0,
        "h": 2000.0,
        "d": 350.0,
        "t": 2.0,
        "fw": 62.0,
        "zl1": 20.0,
        "zl2": 25.0,
        "zr1": 20.0,
        "zr2": 25.0,
        "z_comp": 3.0,
        "head_corner_policy": "HEAD-POLICY",
        "tail_corner_policy": "TAIL-POLICY",
    }


def test_task6e_box_body_baseline_faces_missing_model_is_empty(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host._box_body_baseline_face_cache = {}
    host._baseline_source_model = lambda: None

    monkeypatch.setattr(
        gui.ae,
        "get_box_body_baseline_face_features",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not acquire baseline")),
    )

    actual = gui.Phase6ApplicationHost._box_body_baseline_faces(host, {"fw": 62.0})

    assert actual == {"left": [], "back": [], "right": []}


def test_task6e_open_box_body_face_editor_preserves_editor_payload(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    val = {"w": 1000.0, "h": 2000.0, "d": 350.0, "t": 2.0, "fw": 62.0}
    host.get_float_values = lambda: val
    host._box_body_corner_policies = lambda fw: ("HEAD", "TAIL")
    host.box_body_face_selected_var = Var()
    host.box_body_face_features = {
        "left": ["LEFT-FEATURE"],
        "back": [],
        "right": [],
    }
    host._box_body_face_baseline_scene = lambda face_key, actual_val: (
        "BASELINE-SCENE",
        face_key,
        actual_val,
    )
    host.baseline_var = Var("MODEL")
    editor_calls = []
    redraw_calls = []
    host._open_unified_hole_editor = lambda *args, **kwargs: editor_calls.append((args, kwargs))
    host.draw_box_body = lambda actual_val: redraw_calls.append(actual_val)

    monkeypatch.setattr(
        gui,
        "box_body_face_dimensions",
        lambda **kwargs: {"left": (350.0, 2000.0), "back": (1000.0, 2000.0), "right": (350.0, 2000.0)},
    )
    monkeypatch.setattr(
        gui,
        "box_body_vertical_offsets",
        lambda thickness, *, head_corner_policy, tail_corner_policy: (10.0, 20.0),
    )
    surface_calls = []

    def fake_surface(surface_id, start, end):
        surface_calls.append((surface_id, start, end))
        return "SURFACE"

    monkeypatch.setattr(gui, "feature_surface_from_rect", fake_surface)
    monkeypatch.setattr(
        gui,
        "RectGuide",
        lambda start, end, label: ("GUIDE", start, end, label),
    )
    monkeypatch.setattr(gui.ae, "box_body_baseline_source_label", lambda model: f"STATUS:{model}")

    gui.Phase6ApplicationHost.open_box_body_face_editor(host, "left")

    assert host.box_body_face_selected_var.get() == "left"
    assert len(surface_calls) == 1
    surface_id, start, end = surface_calls[0]
    assert surface_id == "box_body_left"
    assert (start.x, start.y) == (2.0, 10.0)
    assert (end.x, end.y) == (348.0, 1980.0)

    assert len(editor_calls) == 1
    args, kwargs = editor_calls[0]
    assert args[:5] == ("box_body_left", "箱身左側", "SURFACE", 350.0, 2000.0)
    assert kwargs["feature_list_override"] == ["LEFT-FEATURE"]
    assert kwargs["baseline_scene"] == ("BASELINE-SCENE", "left", val)
    assert kwargs["baseline_status_text"] == "STATUS:MODEL"
    guide = kwargs["reference_guide"]
    assert guide[0] == "GUIDE"
    assert (guide[1].x, guide[1].y) == (0.0, 0.0)
    assert (guide[2].x, guide[2].y) == (350.0, 2000.0)
    assert guide[3] == "enclosure_boundary"

    kwargs["on_close"]()
    assert redraw_calls == [val]


def test_task6e_open_box_body_face_editor_rejects_unknown_face(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda title, message: errors.append((title, message)))

    gui.Phase6ApplicationHost.open_box_body_face_editor(host, "roof")

    assert errors == [("開孔失敗", "未知箱身面: roof")]

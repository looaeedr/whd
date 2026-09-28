from __future__ import annotations

import inspect

import gui_modules.application.fold_designer_adapter as fold_adapter
import phase6_final_scene_renderer as renderer_module
from phase6_final_scene_renderer import Phase6FinalSceneRenderer


def test_issue928_deleted_assembly_bridge_port_is_not_a_live_consumer():
    source = inspect.getsource(
        fold_adapter.Phase6FoldDesignerComposition.final_scene_ports
    )
    assert "_phase6_query_assembly_render_data" not in source
    assert "query_assembly_render_data()" in source


def test_issue928_composition_routes_final_scene_errors_to_runtime_log():
    source = inspect.getsource(
        fold_adapter.Phase6FoldDesignerComposition.final_scene_renderer
    )
    assert '"3d_final_scene_render"' in source
    assert "write_runtime_exception(" in source
    assert "error_reporter=report_render_error" in source


class _FakeCanvas:
    def __init__(self):
        self.draw_calls = 0

    def draw(self):
        self.draw_calls += 1

    def mpl_connect(self, *_args):
        return 1


class _FakeAxis:
    def __init__(self):
        self.elev = 30
        self.azim = -45
        self.transAxes = object()
        self.figure = None
        self.messages = []

    def clear(self):
        return None

    def text2D(self, *_args, **_kwargs):
        if len(_args) >= 3:
            self.messages.append(_args[2])
        return None

    def view_init(self, *, elev, azim):
        self.elev = elev
        self.azim = azim


class _FakeRawRenderer:
    def __init__(self):
        self.canvas = _FakeCanvas()
        self.ax3d = _FakeAxis()
        self.ax2d = None
        self.render = lambda: None


def test_issue928_swallowed_final_scene_exception_calls_error_reporter(monkeypatch):
    raw = _FakeRawRenderer()
    reported = []
    view = Phase6FinalSceneRenderer(raw, error_reporter=reported.append)
    monkeypatch.setattr(view, "configure_3d_only_figure", lambda: None)
    monkeypatch.setattr(renderer_module, "apply_mpl_dark_theme", lambda *_a, **_k: None)

    def fail_request():
        raise RuntimeError("live Windows FinalScene failure")

    view.install(fail_request)
    raw.render()

    assert len(reported) == 1
    assert isinstance(reported[0], RuntimeError)
    assert str(reported[0]) == "live Windows FinalScene failure"
    assert view.cutting_mesh_error == "live Windows FinalScene failure"
    assert raw.canvas.draw_calls == 1
    assert any("live Windows FinalScene failure" in text for text in raw.ax3d.messages)

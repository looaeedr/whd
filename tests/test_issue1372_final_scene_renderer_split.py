from __future__ import annotations

import inspect

import phase6_final_scene_renderer
import phase6_final_scene_render_helpers


def test_issue1372_renderer_uses_one_way_helper_mixin():
    assert issubclass(
        phase6_final_scene_renderer.Phase6FinalSceneRenderer,
        phase6_final_scene_render_helpers.Phase6FinalSceneRenderHelpersMixin,
    )
    facade = inspect.getsource(phase6_final_scene_renderer)
    owner = inspect.getsource(phase6_final_scene_render_helpers)
    assert len(facade.splitlines()) < 700
    assert "from phase6_final_scene_renderer import" not in owner
    assert "import phase6_final_scene_renderer" not in owner


def test_issue1372_render_and_runtime_lifecycle_stay_on_public_renderer():
    names = set(phase6_final_scene_renderer.Phase6FinalSceneRenderer.__dict__)
    assert {"render", "configure_3d_only_figure", "scale_current_3d_limits", "adjust_zoom_scale", "on_scroll", "install"} <= names

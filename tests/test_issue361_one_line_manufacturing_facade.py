import ast
import inspect
from pathlib import Path
from types import SimpleNamespace


def _tree(path):
    return ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))


def _function(tree, name):
    return next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _class_wiring(tree):
    out = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "Phase6FoldDesignerApp"
                ):
                    out.add(target.attr)
            continue
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not (
            isinstance(call.func, ast.Name)
            and call.func.id == "install_fold_designer_bridge_facade"
        ):
            continue
        bindings = call.args[1] if len(call.args) >= 2 else None
        if bindings is None:
            for keyword in call.keywords:
                if keyword.arg == "bindings":
                    bindings = keyword.value
                    break
        if not isinstance(bindings, ast.Dict):
            continue
        for key in bindings.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                out.add(key.value)
    return out



def test_issue361_bridge_manufacturing_facade_is_one_line_adapter_call():
    tree = _tree("fold_designer_bridge.py")
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "_phase6_resolve_manufacturing_geometry"
            for target in node.targets
        )
    )
    assert isinstance(assignment.value, ast.Name)
    assert assignment.value.id == "resolve_for_app"

def test_issue361_adapter_owns_app_to_service_provider_wiring(monkeypatch):
    import phase6_manufacturing_adapter as adapter

    captured = {}

    def fake_resolve(app, **kwargs):
        captured.update(kwargs)
        return "geometry"

    monkeypatch.setattr(adapter, "resolve_manufacturing_for_app", fake_resolve)

    published = []
    app = SimpleNamespace(
        _scene_query_callback=lambda key, payload: ("render", key, payload),
        _part_spec_query_callback=lambda key, payload: ("spec", "ctx"),
        _phase6_publish_live_state=lambda force=False: published.append(force),
    )

    monkeypatch.setattr(
        adapter,
        "build_scene_payload_for_app",
        lambda _app, key: {"part_key": key},
    )
    monkeypatch.setattr(
        adapter,
        "operator_finished_dimensions_for_app",
        lambda _app, key=None, triangles=None: ("dims", key),
    )

    assert adapter.resolve_for_app(app) == "geometry"
    assert callable(captured["scene_payload_builder"])
    assert captured["render_data_provider"] is app._scene_query_callback
    assert captured["part_spec_provider"] is app._part_spec_query_callback
    assert callable(captured["finished_dimensions_provider"])
    assert captured["publish_live_state"] is app._phase6_publish_live_state
    assert captured["scene_payload_builder"]("head") == {"part_key": "head"}
    assert captured["finished_dimensions_provider"]("head") == ("dims", "head")


def test_issue361_bridge_scene_payload_helper_is_compatibility_wrapper():
    import fold_designer_bridge

    source = inspect.getsource(fold_designer_bridge._phase6_scene_query_payload_for_part)
    assert "build_scene_payload_for_app" in source
    assert "designer_workspace.features_for" not in source
    assert "read_endcap_xy_profiles" not in source


def test_issue361_bridge_finished_dimensions_helper_is_compatibility_wrapper():
    import fold_designer_bridge

    source = inspect.getsource(fold_designer_bridge._phase6_operator_finished_dimensions)
    assert "operator_finished_dimensions_for_app" in source
    assert "resolve_operator_finished_dimensions" not in source


def test_issue361_adapter_contains_no_solver_ownership():
    tree = _tree("phase6_manufacturing_adapter.py")
    source = Path("phase6_manufacturing_adapter.py").read_text(encoding="utf-8")

    forbidden = {
        "_phase6_resolve_explicit_joint_reliefs",
        "_phase6_resolve_family_divider_reliefs",
        "_phase6_build_joint_world_geometry",
        "solve_world_backprojected_endcap_relief",
        "discover_joint_relief_candidate",
        "project_joint_interference_to_relief_owner",
    }
    loaded = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert not (loaded & forbidden)
    assert "fold_designer_bridge" not in source


def test_issue361_phase6_app_keeps_legacy_method_entry():
    tree = _tree("fold_designer_bridge.py")
    wired = _class_wiring(tree)
    assert "_phase6_resolve_manufacturing_geometry" in wired

def test_issue362_facade_preserves_provider_missing_fail_closed_after_cache_miss():
    from types import SimpleNamespace

    import pytest

    from phase6_manufacturing_adapter import resolve_manufacturing_for_app
    from phase6_manufacturing_cache import ManufacturingCacheService

    app = SimpleNamespace(
        _phase6_input_snapshot={},
        _settings_values={},
        _phase6_box_whd={},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
        _phase6_endcap_bottom_wrap_state={},
        _phase6_assembly_type="",
        _phase6_sync_revision="",
        designer_workspace=SimpleNamespace(available_parts=()),
    )

    with pytest.raises(RuntimeError, match="3D final-scene provider is not connected"):
        resolve_manufacturing_for_app(
            app,
            scene_payload_builder=lambda key: {},
            render_data_provider=None,
            cache_service=ManufacturingCacheService(),
            require_render_provider=True,
        )


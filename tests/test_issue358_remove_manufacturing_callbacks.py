import ast
from pathlib import Path


CALLBACK_REGISTRY_NAMES = {
    "_PHASE6_BRIDGE_CALLBACKS",
    "_phase6_bind_bridge_callbacks",
    "_phase6_call_bridge",
}
PHASE1_ONLY_CLASS_WIRING = {
    "_phase6_mesh_profiles_for_part",
    "_phase6_operator_finished_dimensions",
    "_phase6_scene_query_payload_for_part",
}


def _tree(path):
    return ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))


def _defined(tree):
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _loaded_names(tree):
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


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


def test_issue358_manufacturing_owner_has_zero_bridge_callback_registry_refs():
    owner_tree = _tree("phase6_manufacturing_geometry.py")
    source = Path("phase6_manufacturing_geometry.py").read_text(encoding="utf-8")

    assert not (CALLBACK_REGISTRY_NAMES & _defined(owner_tree))
    assert not (CALLBACK_REGISTRY_NAMES & _loaded_names(owner_tree))

    reverse_imports = []
    for node in ast.walk(owner_tree):
        if isinstance(node, ast.Import):
            reverse_imports.extend(
                alias.name for alias in node.names
                if alias.name == "fold_designer_bridge"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "fold_designer_bridge":
            reverse_imports.append(node.module)
    assert reverse_imports == []


def test_issue358_owner_resolver_consumes_request_and_returns_explicit_result():
    service_tree = _tree("phase6_manufacturing_service.py")
    resolver = next(
        node
        for node in service_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "resolve"
    )
    assert [arg.arg for arg in resolver.args.args] == ["request"]

    segment = ast.get_source_segment(
        Path("phase6_manufacturing_service.py").read_text(encoding="utf-8"),
        resolver,
    ) or ""
    assert "ManufacturingResolveResult" in segment
    assert "_phase6_call_bridge" not in segment
    assert "_phase6_publish_live_state" not in segment
    assert "self" not in {node.id for node in ast.walk(resolver) if isinstance(node, ast.Name)}


def test_issue358_phase1_only_class_wiring_is_removed_but_publish_wiring_remains():
    bridge_tree = _tree("fold_designer_bridge.py")
    wired = _class_wiring(bridge_tree)

    assert not (PHASE1_ONLY_CLASS_WIRING & wired)
    assert "_phase6_publish_live_state" in wired

    source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    assert "_phase6_bind_bridge_callbacks(" not in source


def test_issue358_bridge_facade_routes_ui_inputs_through_adapter():
    import inspect
    import fold_designer_bridge

    source = inspect.getsource(fold_designer_bridge._phase6_resolve_manufacturing_geometry)
    assert "resolve_for_app" in source
    assert "_phase6_call_bridge" not in source
    assert "_phase6_scene_query_payload_for_part" not in source
    assert "_phase6_operator_finished_dimensions" not in source


def test_issue358_adapter_preserves_active_unsaved_profiles():
    from types import SimpleNamespace

    from phase6_manufacturing_adapter import build_manufacturing_request

    class Workspace:
        available_parts = ("head",)
        active_part = "head"

        def profiles_for(self, key, default):
            return {"X": [{"len": 1}], "Y": [{"len": 2}]}

        def features_for(self, key):
            return ()

        def face_features_for(self, key):
            return {}

        def box_body_structure_state(self):
            return {}

    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "受電箱"},
        _settings_values={"t": 2.0},
        _phase6_box_whd={},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
        _phase6_endcap_bottom_wrap_state={},
        _phase6_assembly_type=SimpleNamespace(value="INSERT_OVERLAY"),
        assembly_ignore_fixed_corner_var=None,
        assembly_relief_clearance_var=None,
        baseline_model_var=None,
        _phase6_sync_revision=1,
        designer_workspace=Workspace(),
        state=SimpleNamespace(
            profiles_vault={},
            profiles={"X": [{"len": 99}], "Y": [{"len": 88}]},
        ),
    )

    request = build_manufacturing_request(
        app,
        scene_payload_builder=lambda key: {"part_key": key},
        finished_dimensions_provider=lambda key=None: (100.0, 50.0),
    )
    head = request.parts[0]
    assert head.x_profile[0]["len"] == 99.0
    assert head.y_profile[0]["len"] == 88.0


def test_issue358_resolve_for_app_keeps_signature_first_cache_hit_before_request_build(monkeypatch):
    from types import SimpleNamespace

    import phase6_manufacturing_adapter as adapter
    from phase6_manufacturing_cache import ManufacturingCacheService
    from phase6_manufacturing_contracts import (
        ManufacturingCacheReceipt,
        ManufacturingDiagnosticsResult,
        ManufacturingEffects,
        ManufacturingMutationResult,
        ManufacturingResolveResult,
    )

    app = SimpleNamespace()
    cached = object()
    key = adapter.build_manufacturing_cache_key
    fingerprint = "a" * 64
    service = ManufacturingCacheService()
    service.store(
        adapter.ManufacturingCacheKey(fingerprint),
        ManufacturingResolveResult(
            geometry=cached,
            diagnostics=ManufacturingDiagnosticsResult(),
            mutations=ManufacturingMutationResult(),
            effects=ManufacturingEffects(),
            cache=ManufacturingCacheReceipt(signature=fingerprint, hit=False, stored=True),
        ),
    )

    monkeypatch.setattr(
        adapter,
        "_legacy_manufacturing_signature",
        lambda _app: fingerprint,
    )
    monkeypatch.setattr(
        adapter,
        "build_manufacturing_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cache hit must not build full request")
        ),
    )

    assert adapter.resolve_manufacturing_for_app(app, cache_service=service) is cached






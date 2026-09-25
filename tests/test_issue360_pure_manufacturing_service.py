import ast
from pathlib import Path
from types import SimpleNamespace


FORBIDDEN_IMPORT_ROOTS = {
    "fold_designer_bridge",
    "tkinter",
    "gui",
    "gui_modules",
}
FORBIDDEN_NAMES = {
    "designer_workspace",
    "_scene_query_callback",
    "_PHASE6_BRIDGE_CALLBACKS",
    "_phase6_bind_bridge_callbacks",
    "_phase6_call_bridge",
}


def _tree(path):
    return ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))


def test_issue360_service_has_zero_app_ui_static_dependencies():
    path = Path("phase6_manufacturing_service.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    roots = {name.split(".", 1)[0] for name in imports}
    assert not (roots & FORBIDDEN_IMPORT_ROOTS)

    loaded_names = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    attrs = {
        node.attr for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }
    assert "self" not in loaded_names
    assert not (FORBIDDEN_NAMES & (loaded_names | attrs))
    assert "designer_workspace" not in source


def test_issue360_service_entry_is_resolve_request_only():
    tree = _tree("phase6_manufacturing_service.py")
    resolver = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve"
    )
    assert [arg.arg for arg in resolver.args.args] == ["request"]
    assert resolver.args.vararg is None
    assert resolver.args.kwarg is None


def test_issue360_adapter_routes_domain_inputs_before_service(monkeypatch):
    import phase6_manufacturing_adapter as adapter
    import phase6_manufacturing_service as service
    from phase6_manufacturing_cache import ManufacturingCacheService
    from ae_engine.manufacturing_api import PartRenderData
    from ae_engine.sheetmetal_drawing import DrawingScene
    from shapely.geometry import box

    class Var:
        def __init__(self, value):
            self.value = value
        def get(self):
            return self.value

    class Workspace:
        available_parts = ("box_body",)
        active_part = "box_body"
        def profiles_for(self, key, default): return default
        def features_for(self, key): return ()
        def face_features_for(self, key): return {}
        def box_body_structure_state(self): return {"piece_count": 1}

    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "金庫型", "w": 800, "h": 1800, "d": 400, "t": 2.0},
        _settings_values={"t": 2.0},
        _phase6_box_whd={"w": 800, "h": 1800, "d": 400},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
        _phase6_endcap_bottom_wrap_state={},
        _phase6_assembly_type=SimpleNamespace(value="INSERT_OVERLAY"),
        assembly_ignore_fixed_corner_var=Var(False),
        assembly_relief_clearance_var=Var("0"),
        baseline_model_var=Var("金庫型"),
        _phase6_sync_revision=1,
        designer_workspace=Workspace(),
        state=SimpleNamespace(
            profiles_vault={"箱身": [{"len": 800.0, "core": True}]},
            profiles={"X": (), "Y": ()},
        ),
    )
    render = PartRenderData(
        scene=DrawingScene(),
        material=box(0, 0, 800, 400),
    )
    captured = []

    from phase6_manufacturing_contracts import (
        ManufacturingCacheReceipt,
        ManufacturingDiagnosticsResult,
        ManufacturingEffects,
        ManufacturingMutationResult,
        ManufacturingResolveResult,
    )

    monkeypatch.setattr(
        service,
        "resolve",
        lambda request: captured.append(request) or ManufacturingResolveResult(
            geometry=object(),
            diagnostics=ManufacturingDiagnosticsResult(),
            mutations=ManufacturingMutationResult(),
            effects=ManufacturingEffects(),
            cache=ManufacturingCacheReceipt(
                signature=request.cache_key_fingerprint,
                hit=False,
                stored=False,
            ),
        ),
    )
    monkeypatch.setattr(
        adapter,
        "apply_manufacturing_result",
        lambda app, result: result.geometry,
    )

    adapter.resolve_manufacturing_for_app(
        app,
        cache_service=ManufacturingCacheService(),
        scene_payload_builder=lambda key: {"part_key": key},
        render_data_provider=lambda key, payload: render,
        finished_dimensions_provider=lambda key=None: (800.0, 1800.0, 400.0),
    )

    assert len(captured) == 1
    request = captured[0]
    assert request.parts[0].render_data is render
    assert request.cache_key_fingerprint
    assert not callable(request.parts[0].render_data)


def test_issue360_adapter_calls_service_resolve_request_not_geometry_owner():
    source = Path("phase6_manufacturing_adapter.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="phase6_manufacturing_adapter.py")
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "resolve_manufacturing_for_app"
    )
    segment = ast.get_source_segment(source, fn) or ""
    assert "phase6_manufacturing_service" in segment
    assert "_phase6_resolve_manufacturing_result" not in segment
    assert "service.resolve" in segment


def test_issue360_geometry_owner_no_longer_owns_orchestration_entry():
    tree = _tree("phase6_manufacturing_geometry.py")
    names = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "_phase6_resolve_manufacturing_result" not in names

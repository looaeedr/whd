"""DM8-B2: structural ownership invariants replace obsolete split-size oracles.

The mechanical split's 100-route floor and 1000-line ceiling prevented caller
migration and said nothing about responsibility or public interface quality.
"""
from __future__ import annotations

import ast
from pathlib import Path

from tools.phase6_bridge_anti_regrowth_guard import (
    composition_root_locations,
    full_app_interfaces,
    imports_bridge,
)

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "gui_modules" / "application"
BRIDGE = ROOT / "fold_designer_bridge.py"
ADAPTER = APP / "fold_designer_adapter.py"
CAPABILITIES = APP / "fold_designer_capability_owners.py"
IMPLEMENTATIONS = tuple(
    APP / f"fold_designer_composition_{name}.py"
    for name in (
        "state", "settings", "receiving",
        "registry_edges", "assembly_corner", "shell_settings",
    )
)
PROJECTIONS = (
    APP / "fold_designer_manufacturing_projection.py",
    APP / "fold_designer_snapshot_projection.py",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _root_class():
    roots = composition_root_locations(
        {str(path): path.read_text(encoding="utf-8")
         for path in (ADAPTER, BRIDGE, CAPABILITIES, *IMPLEMENTATIONS)},
        "Phase6FoldDesignerComposition",
    )
    assert roots == (str(ADAPTER),), f"Second composition root: {roots}"
    return next(
        node for node in _tree(ADAPTER).body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )


def test_issue1341_only_one_root_and_explicit_capability_bootstrap():
    cls = _root_class()
    methods = {
        node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)
    }
    init = ast.unparse(methods["__init__"])
    assert "_composition_state.build_capability_owners(self)" in init
    assert "def capabilities" in ADAPTER.read_text("utf-8")
    # These migration-only public trampolines have no remaining callers.
    assert "workspace_navigation" not in methods
    assert "registry_diagnostics" not in methods


def test_issue1341_capability_owners_have_bounded_ports_not_a_service_bag():
    source = CAPABILITIES.read_text("utf-8")
    assert not full_app_interfaces(source, ("app", "host", "application", "services"))
    assert not imports_bridge(source)
    tree = _tree(CAPABILITIES)
    owners = [
        x for x in tree.body if isinstance(x, ast.ClassDef)
        and x.name.endswith("CapabilityOwner")
    ]
    assert {x.name for x in owners} >= {
        "ProjectCapabilityOwner", "SettingsCapabilityOwner",
        "WorkspaceCapabilityOwner", "RegistryCapabilityOwner",
        "ReceivingCapabilityOwner", "AssemblyCornerCapabilityOwner",
    }
    for cls in owners:
        for node in ast.walk(cls):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                assert not (node.value.id == "self" and node.attr in {
                    "app", "_app", "host", "_host", "services", "_services",
                }), cls.name


def test_issue1341_extracted_owners_are_one_way_and_do_not_construct_root():
    for path in (*IMPLEMENTATIONS, *PROJECTIONS, CAPABILITIES):
        assert path.is_file(), path
        source = path.read_text(encoding="utf-8")
        assert not imports_bridge(source), path
        assert "class Phase6FoldDesignerComposition" not in source


def test_issue1341_primary_bridge_callers_use_capabilities_directly():
    source = BRIDGE.read_text("utf-8")
    tree = _tree(BRIDGE)
    functions = {
        x.name: ast.unparse(x)
        for x in tree.body if isinstance(x, ast.FunctionDef)
    }
    for name, capability in (
        ("_phase6_workspace_navigation", "workspace.navigation"),
        ("_phase6_settings_service", "settings.service"),
        ("_phase6_registry_diagnostics", "registry.diagnostics"),
    ):
        assert f".capabilities.{capability}()" in functions[name], name
    # Legacy host contract aliases stay until migration evidence permits removal.
    assert "_phase6_composition" in functions
    assert "_phase6_settings_transactions" in functions
    assert "_phase6_receiving_adapter" in functions
    assert "install_fold_designer_bridge_facade" in source


def test_issue1341_existing_subowners_call_capabilities_not_old_thin_routes():
    for name in ("assembly_corner", "registry_edges"):
        source = (APP / f"fold_designer_composition_{name}.py").read_text("utf-8")
        assert "self.capabilities.registry.diagnostics()" in source
        assert "self.registry_diagnostics()" not in source
    source = (APP / "fold_designer_composition_shell_settings.py").read_text("utf-8")
    assert "self.capabilities.workspace.navigation()" in source
    assert "def workspace_navigation(self)" not in source
    assert "def registry_diagnostics(self)" not in source


def test_issue1341_no_numeric_route_count_or_loc_migration_oracle():
    # The checks above constrain actual ownership instead of an arbitrary
    # number of routes/lines which prevented a smaller composition API.
    tree = _tree(Path(__file__))
    assertions = [
        node for func in tree.body
        if isinstance(func, ast.FunctionDef)
        and func.name.startswith("test_issue1341_")
        and func.name != "test_issue1341_no_numeric_route_count_or_loc_migration_oracle"
        for node in ast.walk(func)
        if isinstance(node, ast.Compare)
    ]
    for check in assertions:
        assert not any(
            isinstance(value, ast.Constant) and isinstance(value.value, int)
            and value.value >= 100
            for value in (check.left, *check.comparators)
        ), "Migration-only route/LOC numeric oracle regrew"

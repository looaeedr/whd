"""DM8-B1: test real capability owner behavior using bounded fake ports only."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from gui_modules.application.fold_designer_capability_owners import (
    AssemblyCornerCapabilityOwner,
    AssemblyCornerCapabilityPorts,
    ProjectCapabilityOwner,
    ProjectCapabilityPorts,
    ReceivingCapabilityOwner,
    ReceivingCapabilityPorts,
    RegistryCapabilityOwner,
    RegistryCapabilityPorts,
    SettingsCapabilityOwner,
    SettingsCapabilityPorts,
    WorkspaceCapabilityOwner,
    WorkspaceCapabilityPorts,
)

APP = Path(__file__).resolve().parents[1] / "gui_modules" / "application"


class StubController:
    def __init__(self, workspace, *, remembered_box_body_child=None):
        self.workspace = workspace
        self.remembered_box_body_child = remembered_box_body_child


class StubRegistry:
    def __init__(self, **kwargs):
        self.seed = kwargs


class StubReceivingAdapter:
    def __init__(self, layout, *, persisted_ids, confirm_destructive):
        self.layout = layout
        self.persisted_ids = persisted_ids
        self.confirm_destructive = confirm_destructive


class BoundedOwnerTests(unittest.TestCase):
    def test_project_export_routes_only_explicit_callbacks(self):
        calls = []
        cb = lambda: "exported"
        flush = lambda: calls.append("flush")
        def route_export(export_callback, flush_callback):
            self.assertIs(export_callback, cb)
            flush_callback()
            return export_callback()
        owner = ProjectCapabilityOwner(ProjectCapabilityPorts(
            export_callback=lambda: cb,
            flush_pending_settings=flush,
            route_export=route_export,
        ))
        self.assertEqual(owner.export_selected_dxf(), "exported")
        self.assertEqual(calls, ["flush"])

    def test_settings_service_is_singleton_from_current_explicit_snapshot(self):
        requested = []
        sources = [{"w": 800}, {"part": "box"}, {"d": 300}, {"fw": 25}]
        def service_factory(**kwargs):
            requested.append(kwargs)
            return object()
        owner = SettingsCapabilityOwner(SettingsCapabilityPorts(
            settings_values=lambda: sources[0],
            input_snapshot=lambda: sources[1],
            box_whd=lambda: sources[2],
            pending_settings=lambda: sources[3],
            service_factory=service_factory,
        ))
        one = owner.service()
        self.assertIs(one, owner.service())
        self.assertEqual(len(requested), 1)
        self.assertIs(requested[0]["settings_values"], sources[0])
        self.assertIs(requested[0]["pending_settings"], sources[3])

    def test_workspace_reuses_identity_and_rebuilds_only_if_workspace_changes(self):
        first, second = object(), object()
        state = {"workspace": first, "current": None}
        published = []
        def publish(value):
            state["current"] = value
            published.append(value)
        owner = WorkspaceCapabilityOwner(WorkspaceCapabilityPorts(
            workspace=lambda: state["workspace"],
            current_controller=lambda: state["current"],
            remembered_child=lambda: "box_body:left",
            publish_controller=publish,
            controller_type=StubController,
        ))
        a = owner.navigation()
        self.assertIs(a, owner.navigation())
        self.assertEqual(a.remembered_box_body_child, "box_body:left")
        self.assertEqual(len(published), 1)
        state["workspace"] = second
        b = owner.navigation()
        self.assertIsNot(a, b)
        self.assertIs(b.workspace, second)
        self.assertEqual(len(published), 2)

    def test_workspace_reuses_existing_canonical_host_controller(self):
        workspace = object()
        existing = StubController(workspace)
        published = []
        owner = WorkspaceCapabilityOwner(WorkspaceCapabilityPorts(
            workspace=lambda: workspace,
            current_controller=lambda: existing,
            remembered_child=lambda: None,
            publish_controller=published.append,
            controller_type=StubController,
        ))
        self.assertIs(owner.navigation(), existing)
        self.assertEqual(published, [existing])

    def test_registry_caches_canonical_controller_with_bounded_seed(self):
        published = []
        seed = {"candidate_id": "cert-A", "rule_records": {"a": 1}}
        owner = RegistryCapabilityOwner(RegistryCapabilityPorts(
            current_controller=lambda: None,
            diagnostics_seed=lambda: seed,
            publish_controller=published.append,
            controller_type=StubRegistry,
        ))
        first = owner.diagnostics()
        self.assertIs(first, owner.diagnostics())
        self.assertEqual(first.seed, seed)
        self.assertEqual(published, [first])

    def test_receiving_adapter_is_fail_closed_and_reuses_stable_identity(self):
        state = {"source": {"model": "金庫型"}, "adapter": None}
        owner = ReceivingCapabilityOwner(ReceivingCapabilityPorts(
            input_snapshot=lambda: state["source"],
            current_adapter=lambda: state["adapter"],
            publish_adapter=lambda value: state.__setitem__("adapter", value),
            canonical_family_name=lambda data: data.get("model"),
        ))
        factory = lambda source: {"receiving_layout": {"bays": [1, 2]}}
        kwargs = dict(ensure_layout=factory, stable_ids=lambda layout: ("stable",),
                      adapter_type=StubReceivingAdapter,
                      confirm_destructive=lambda x: True)
        self.assertIsNone(owner.adapter(reset=False, **kwargs))
        state["source"] = {"model": "受電箱"}
        first = owner.adapter(reset=False, **kwargs)
        self.assertEqual(first.persisted_ids, ("stable",))
        self.assertIs(first, owner.adapter(reset=False, **kwargs))
        self.assertIsNot(first, owner.adapter(reset=True, **kwargs))

    def test_assembly_corner_only_updates_in_assembly_mode(self):
        calls = []
        state = {"mode": "single"}
        owner = AssemblyCornerCapabilityOwner(AssemblyCornerCapabilityPorts(
            display_mode=lambda: state["mode"],
            submit_update_intent=lambda: lambda *args, **kwargs: calls.append(
                (args, kwargs)
            ),
        ))
        self.assertFalse(owner.refresh_if_assembly())
        state["mode"] = "assembly"
        self.assertTrue(owner.refresh_if_assembly())
        self.assertEqual(calls, [(("display",), {"commit": True})])

    def test_callable_gate_rejects_unbounded_values(self):
        with self.assertRaisesRegex(TypeError, "port"):
            ProjectCapabilityPorts(export_callback=object(),
                                   flush_pending_settings=lambda: None,
                                   route_export=lambda *a: None)

    def test_only_existing_root_constructs_capability_bundle(self):
        adapter = (APP / "fold_designer_adapter.py").read_text("utf-8")
        cls = next(x for x in ast.parse(adapter).body
                   if isinstance(x, ast.ClassDef)
                   and x.name == "Phase6FoldDesignerComposition")
        initializer = next(x for x in cls.body
                           if isinstance(x, ast.FunctionDef)
                           and x.name == "__init__")
        self.assertIn("build_capability_owners(app)", ast.unparse(initializer))
        for name in ("state", "receiving", "shell_settings", "assembly_corner"):
            path = APP / f"fold_designer_composition_{name}.py"
            source = path.read_text("utf-8")
            self.assertIn("self._capabilities.", source)
            self.assertNotIn("from fold_designer_bridge import", source)
        capabilities = (APP / "fold_designer_capability_owners.py").read_text("utf-8")
        self.assertNotIn("import fold_designer_bridge", capabilities)
        self.assertEqual(capabilities.count("def build_capability_owners("), 1)
        cap_tree = ast.parse(capabilities)
        for cls in (node for node in cap_tree.body if isinstance(node, ast.ClassDef)
                    and node.name.endswith("CapabilityOwner")):
            for node in ast.walk(cls):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    self.assertFalse(node.value.id == "self" and node.attr in
                                     {"app", "_app", "host", "_host"}, cls.name)
        self.assertLessEqual(len(adapter.splitlines()), 1000)


if __name__ == "__main__":
    unittest.main()

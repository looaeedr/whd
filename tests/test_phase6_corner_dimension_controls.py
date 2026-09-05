from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import box
from shapely.ops import unary_union

import ae_engine.assembly_collision as collision
import fold_designer_bridge as bridge
from ae_engine.sheetmetal_drawing import DrawingScene
from phase6_designer_workspace import Phase6DesignerWorkspace


class Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def test_measure_material_corner_reliefs_reports_single_and_two_stage_physical_cuts():
    blank = box(0, 0, 100, 80)
    top_left_two_stage = unary_union([
        box(0, 60, 20, 80),
        box(0, 50, 10, 60),
    ])
    top_right_single = box(85, 65, 100, 80)
    material = blank.difference(unary_union([top_left_two_stage, top_right_single]))

    measured = {
        item.corner_name: item
        for item in collision.measure_material_corner_reliefs(material)
    }

    left = measured["top_left"]
    assert left.primary_u == 20.0
    assert left.primary_v == 20.0
    assert left.secondary_u == 10.0
    assert left.secondary_depth == 10.0

    right = measured["top_right"]
    assert right.primary_u == 15.0
    assert right.primary_v == 15.0
    assert right.secondary_u is None
    assert right.secondary_depth is None
    assert "bottom_left" not in measured
    assert "bottom_right" not in measured


def test_corner_dimension_text_comes_from_authoritative_render_material():
    blank = box(0, 0, 100, 80)
    material = blank.difference(box(0, 60, 20, 80))
    render_data = SimpleNamespace(scene=DrawingScene(), material=material, fold_guides=())

    text = bridge._phase6_render_data_corner_dimension_text(render_data)

    assert text.startswith("截角尺寸：")
    assert "左上 20×20" in text
    assert "左下" not in text


def test_assembly_query_includes_all_available_sheet_parts_and_honors_view_only_visibility(monkeypatch):
    parts = ["box_body", "head", "tail", "door", "base_plate"]
    flat_x = [{"len": 100.0, "core": True}]
    flat_y = [{"len": 80.0, "core": True}]
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": parts,
        "active_part": "box_body",
        "part_profiles": {
            key: {"X": flat_x, "Y": flat_y}
            for key in parts if key != "box_body"
        },
    })
    raw = {
        key: SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
        for key in parts
    }
    calls = []

    def callback(part_key, payload):
        calls.append(part_key)
        return raw[part_key]

    app = SimpleNamespace(
        designer_workspace=workspace,
        state=SimpleNamespace(profiles={"X": flat_x, "Y": flat_y}, profiles_vault={"箱身": flat_x}),
        _scene_query_callback=callback,
        _phase6_input_snapshot={"t": 2.0},
        _settings_values={"t": 2.0},
        _phase6_box_whd={"w": 100.0, "h": 80.0, "d": 40.0},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
        assembly_ignore_fixed_corner_var=Var(False),
        assembly_show_interference_var=Var(False),
        assembly_part_visible_vars={
            "box_body": Var(True),
            "head": Var(True),
            "tail": Var(True),
            "door": Var(False),
            "base_plate": Var(True),
        },
    )
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))

    bundle = bridge._phase6_query_assembly_render_data(app)

    assert [part.part_key for part in bundle.assembly_parts] == [
        "box_body", "head", "tail", "base_plate"
    ]
    # Door is still queried so its canonical corner-size row can be updated,
    # but view-only filtering keeps it out of the combined renderer.
    # Raw parts are queried first; certified Head/Tail relief is then replayed
    # through the same canonical scene callback.  Door remains view-only hidden.
    assert calls == parts + ["head", "tail"]
    summary = app._phase6_last_assembly_corner_dimension_texts
    assert set(summary) == set(parts)


def test_return_2d_corner_publishes_current_part_before_callback():
    events = []
    app = SimpleNamespace(
        designer_workspace=SimpleNamespace(active_part="tail"),
        _phase6_pending_settings={"fw": 25.0},
        flush_pending_settings=lambda: events.append("flush"),
        _save_current_part=lambda: events.append("save"),
        _return_2d_callback=lambda key: events.append(("return", key)),
    )

    # Keep the unit test focused on ordering, not serialization internals.
    original_publish = bridge._phase6_publish_live_state
    try:
        bridge._phase6_publish_live_state = lambda self, force=False: events.append(("publish", force))
        assert bridge._phase6_return_to_2d_corner(app) is True
    finally:
        bridge._phase6_publish_live_state = original_publish

    assert events == ["flush", "save", ("publish", True), ("return", "tail")]


def test_single_part_3d_request_carries_same_corner_dimension_text(monkeypatch):
    material = box(0, 0, 100, 80).difference(box(0, 60, 20, 80))
    render_data = SimpleNamespace(scene=DrawingScene(), material=material, fold_guides=())
    app = SimpleNamespace(
        designer_workspace=SimpleNamespace(active_part="tail"),
        _phase6_input_snapshot={"t": 2.0},
        _settings_values={"t": 2.0},
        _phase6_3d_display_mode="single",
        state=SimpleNamespace(alpha_bend=0.85),
    )
    monkeypatch.setattr(bridge, "_phase6_query_final_render_data", lambda self: render_data)
    monkeypatch.setattr(bridge, "_phase6_active_mesh_profiles", lambda self, material: ((), ()))
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))

    request = bridge._phase6_final_scene_view_request(app)

    assert request.corner_dimension_text == "截角尺寸：左上 20×20"


def test_2d_corner_dimension_overlay_uses_render_data_not_corner_state():
    import gui

    class Canvas:
        def __init__(self):
            self.calls = []
        def create_text(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return len(self.calls)

    material = box(0, 0, 100, 80).difference(box(85, 65, 100, 80))
    render_data = SimpleNamespace(scene=DrawingScene(), material=material, fold_guides=())
    canvas = Canvas()

    text = gui._draw_phase6_corner_dimension_overlay(canvas, render_data, 800)

    assert text == "截角尺寸：右上 15×15"
    assert any("右上 15×15" in call[1].get("text", "") for call in canvas.calls)


def test_committed_relief_ignores_removed_optional_ytop1_scalar_when_profile_topology_matches():
    import hashlib
    import json
    import gui
    from ae_engine.assembly_joint import migrate_legacy_snapshot_joints, resolved_joint_graph_fingerprint
    from ae_engine.certified_relief_registry import RELIEF_CONTRACT_VERSION

    joint_state = migrate_legacy_snapshot_joints({
        "assembly_type": "INSERT",
        "existing_parts": ["box_body", "head", "tail"],
    })
    graph_fp = resolved_joint_graph_fingerprint(joint_state)
    structure = {}
    structure_fp = hashlib.sha256(
        json.dumps(structure, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    cuts = (((0.0, 0.0), (0.0, 27.0), (39.0, 27.0), (39.0, 0.0)),)
    x_profile = [
        {"len": 15.0, "angle": -90.0, "phase6_key": "yl1"},
        {"len": 392.0, "angle": -90.0, "phase6_key": "endcap_w_core", "core": "W-2T"},
        {"len": 15.0, "phase6_key": "yr1"},
    ]
    # ytop1 is intentionally absent: the current box topology removed that fold.
    y_profile = [
        {"len": 25.0, "angle": -90.0, "phase6_key": "fw"},
        {"len": 244.0, "angle": -90.0, "phase6_key": "endcap_d_core", "core": "D-T"},
        {"len": 15.0, "phase6_key": "ybottom1"},
    ]
    holder = SimpleNamespace(
        assembly_relief_state={
            "enabled": True,
            "source": {
                "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
                "zl1": 15.0, "zr1": 15.0, "yl1": 15.0, "yr1": 15.0,
                # Legacy scalar remains 16 even though the authoritative Y profile removed it.
                "ytop1": 16.0, "ybottom1": 15.0, "assembly_type": "INSERT",
                "relief_contract_version": RELIEF_CONTRACT_VERSION,
                "joint_graph_fingerprint": graph_fp,
                "family_structure_fingerprint": structure_fp,
                "cabinet_family": "金庫型",
                "part_profiles": {"head": {"X": x_profile, "Y": y_profile}},
            },
            "parts": {"head": {"verified": True, "cuts": cuts}},
        },
        assembly_joint_state=joint_state,
        workspace_controller=SimpleNamespace(
            box_body_structure_state=lambda: structure,
            box_body_profile=lambda: (),
        ),
        _current_box_assembly_type=lambda: SimpleNamespace(value="INSERT"),
        _baseline_source_model=lambda: "金庫型",
        _phase6_relief_profile_signature=gui.BoxCalculatorGUI._phase6_relief_profile_signature,
    )
    current = {
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zr1": 15.0, "yl1": 15.0, "yr1": 15.0,
        "ytop1": 0.0, "ybottom1": 15.0,
    }

    resolved = gui.BoxCalculatorGUI._resolved_committed_assembly_relief_cuts(
        holder, "head", current, {"X": x_profile, "Y": y_profile}
    )

    assert resolved == cuts

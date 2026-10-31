"""#2517: Family transition manufacturing state belongs to Engine public API."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

from ae_engine import manufacturing_api as api
from ae_engine import cabinet_family_model_transition as owner
from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part
import phase6_settings_transitions as phase6


def _snapshot(model="金庫型"):
    return {
        "model": model, "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 25.0, "ui_text_size": "large",
        "factory_defaults": {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0, "fw": 25.0},
    }


def _call(new_model, old_model, snapshot, **kwargs):
    return api.plan_cabinet_family_model_transition(
        new_model, old_model,
        new_editable=False, old_editable=False,
        input_snapshot=snapshot,
        settings_values={"w": 800.0, "h": 1600.0, "d": 350.0, "ui_text_size": "large"},
        corner_state=kwargs.pop("corner_state", {}),
        corner_pair_same=kwargs.pop("corner_pair_same", {}),
        endcap_bottom_wrap_state=kwargs.pop("endcap_bottom_wrap_state", {}),
        assembly_type=kwargs.pop("assembly_type", "INSERT_OVERLAY"),
        available_parts=("box_body", "head", "tail"),
        **kwargs,
    )


def test_public_engine_owns_family_transition_and_phase6_is_adapter_only():
    assert api.plan_cabinet_family_model_transition is owner.plan_cabinet_family_model_transition
    assert phase6.FamilyModelPlan is owner.FamilyModelPlan
    assert phase6.FamilyModelTransition is owner.FamilyModelTransition
    assert "manufacturing_api.plan_cabinet_family_model_transition(" in inspect.getsource(phase6.family_model_transition)
    assert "from phase6_" not in inspect.getsource(owner)


def test_real_fresh_receiving_has_one_csv_submitted_nfb_and_joint_wrap(tmp_path):
    original = _snapshot()
    before = deepcopy(original)
    result = _call("受電箱", "金庫型", original)
    assert original == before
    assert result.input_snapshot["model"] == "受電箱"
    assert result.input_snapshot["active_mode"] == "set_bay"
    assert "quantity" not in result.input_snapshot
    assert result.input_snapshot["ui_text_size"] == "large"
    layout = result.input_snapshot["receiving_layout"]
    assert len(layout["sets"]) == 1
    assert len(layout["sets"][0]["bays"]) == 1
    bay = layout["sets"][0]["bays"][0]
    assert bay["nfb_config_submitted"] is True
    assert bay["nfb_config"]
    assert result.input_snapshot["assembly_type"] == "WRAP_OVERLAY"
    assert result.assembly_type == "WRAP_OVERLAY"
    assert result.desired_structure is not None
    for part in ("head", "tail"):
        assert edge_relation_for_part(result.input_snapshot, part, "BOTTOM") is AssemblyJointRelation.WRAP
    # Persist using the real P6FOLD project serializer: the source's
    # ProfileFeature is a typed manufacturing feature, not plain JSON data.
    from ae_engine.receiving_layout import normalize_receiving_layout
    import phase6_project_file as project
    payload = {
        "schema": project.PROJECT_SCHEMA_V2,
        "snapshot": {"model": "受電箱", "t": 2.0, "receiving_layout": layout},
        "final_geometry": {},
    }
    project_path = project.write_project(tmp_path / "fresh-receiving.p6fold", payload)
    saved = project.read_project(project_path)["snapshot"]["receiving_layout"]
    assert saved == normalize_receiving_layout(layout)
    assert saved["sets"][0]["bays"][0]["nfb_config_submitted"] is True


def test_receiving_family_alias_keeps_saved_operator_changes_not_fresh_reseed():
    saved = _snapshot("受電箱")
    saved["active_mode"] = "quantity"
    saved["quantity"] = {"operator": "persist"}
    original_corners = {"head": {"top_left": {"type_id": "OVERLAY", "amount_t": 1.75}}}
    result = _call("RECEIVING", "受電箱", saved, corner_state=original_corners)
    assert result.input_snapshot["active_mode"] == "quantity"
    assert result.input_snapshot["quantity"] == {"operator": "persist"}
    assert result.corner_state == original_corners
    assert result.input_snapshot["model"] == "RECEIVING"


def test_return_to_vault_clears_receiving_door_topology_not_unrelated_ui_preferences():
    state = _snapshot("受電箱")
    state.update({
        "multi_door_enabled": True,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "door_layout_scope": "receiving-main",
        "door_handle_edges": {"outer": "left"},
        "inner_doors": [{"stable_id": "upper"}],
        "door_nameplate_center_datum_top": 120.0,
    })
    result = _call("金庫型", "受電箱", state)
    assert result.input_snapshot["multi_door_enabled"] is False
    assert result.input_snapshot["door_layout_columns"] == []
    assert result.input_snapshot["door_layout_scope"] == "main"
    assert result.input_snapshot["door_handle_edges"] == {}
    assert result.input_snapshot["inner_doors"] == []
    assert result.input_snapshot["door_nameplate_center_datum_top"] is None
    assert result.input_snapshot["ui_text_size"] == "large"


def test_phase6_and_headless_family_plans_are_identical_after_json_reload():
    current = json.loads(json.dumps(_snapshot(), ensure_ascii=False))
    kwargs = dict(
        new_editable=False, old_editable=False,
        input_snapshot=current,
        settings_values={"w": 800.0, "h": 1600.0, "d": 350.0, "ui_text_size": "large"},
        corner_state={}, corner_pair_same={},
        endcap_bottom_wrap_state={}, assembly_type="INSERT_OVERLAY",
        available_parts=("box_body", "head", "tail"),
    )
    engine = api.plan_cabinet_family_model_transition("金庫型", "金庫型", **kwargs)
    gui = phase6.family_model_transition("金庫型", "金庫型", **kwargs)
    assert engine == gui
    assert engine.input_snapshot == current

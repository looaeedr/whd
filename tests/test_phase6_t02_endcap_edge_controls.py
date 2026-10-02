from __future__ import annotations

import os
import pytest

from ae_engine.assembly_joint import (
    AssemblyJointRelation,
    edge_relation_for_part,
    migrate_legacy_snapshot_joints,
    set_part_edge_relation,
    sync_snapshot_intent_joints,
)


def _snap(intent="WRAP_OVERLAY"):
    return {
        "assembly_type": intent,
        "existing_parts": ["box_body", "head", "tail"],
    }


def test_edge_editor_accepts_only_registry_allowed_relations_and_keeps_head_tail_independent():
    state = migrate_legacy_snapshot_joints(_snap("WRAP_OVERLAY"))
    changed = set_part_edge_relation(state, "head", "LEFT", AssemblyJointRelation.WRAP)
    assert edge_relation_for_part(changed, "head", "LEFT") is AssemblyJointRelation.WRAP
    assert edge_relation_for_part(changed, "tail", "LEFT") is AssemblyJointRelation.INSERT

    changed = set_part_edge_relation(changed, "head", "RIGHT", AssemblyJointRelation.OVERLAY)
    assert edge_relation_for_part(changed, "head", "RIGHT") is AssemblyJointRelation.OVERLAY
    assert edge_relation_for_part(changed, "head", "LEFT") is AssemblyJointRelation.WRAP

    with pytest.raises(ValueError, match="not allowed"):
        set_part_edge_relation(changed, "head", "TOP", AssemblyJointRelation.WRAP)
    with pytest.raises(ValueError, match="not allowed"):
        set_part_edge_relation(changed, "head", "BOTTOM", AssemblyJointRelation.INSERT)


def test_overlay_bottom_is_editable_insert_or_overlay_but_never_wrap():
    state = migrate_legacy_snapshot_joints(_snap("OVERLAY"))
    assert edge_relation_for_part(state, "head", "BOTTOM") is AssemblyJointRelation.INSERT
    changed = set_part_edge_relation(state, "head", "BOTTOM", AssemblyJointRelation.OVERLAY)
    assert edge_relation_for_part(changed, "head", "BOTTOM") is AssemblyJointRelation.OVERLAY
    with pytest.raises(ValueError, match="not allowed"):
        set_part_edge_relation(changed, "head", "BOTTOM", AssemblyJointRelation.WRAP)


def test_selecting_a_preset_resets_canonical_edges_to_registry_defaults():
    state = migrate_legacy_snapshot_joints(_snap("WRAP_OVERLAY"))
    state = set_part_edge_relation(state, "head", "LEFT", AssemblyJointRelation.WRAP)
    state = set_part_edge_relation(state, "tail", "RIGHT", AssemblyJointRelation.OVERLAY)
    assert edge_relation_for_part(state, "head", "LEFT") is AssemblyJointRelation.WRAP
    assert edge_relation_for_part(state, "tail", "RIGHT") is AssemblyJointRelation.OVERLAY

    reset = sync_snapshot_intent_joints(state, "WRAP_OVERLAY")
    expected = {
        "TOP": AssemblyJointRelation.OVERLAY,
        "BOTTOM": AssemblyJointRelation.WRAP,
        "LEFT": AssemblyJointRelation.INSERT,
        "RIGHT": AssemblyJointRelation.INSERT,
    }
    for part in ("head", "tail"):
        for edge, relation in expected.items():
            assert edge_relation_for_part(reset, part, edge) is relation


def test_v2_illegal_fixed_edge_payload_is_sanitized_but_legal_editable_override_survives_reload():
    state = migrate_legacy_snapshot_joints(_snap("OVERLAY"))
    rows = []
    for row in state["assembly_joints"]:
        row = dict(row)
        if row["subject_part"] == "head" and row["edge"] == "TOP":
            row["relation"] = "WRAP"  # illegal fixed edge injection
            row["source"] = "USER_ADDED"
        if row["subject_part"] == "head" and row["edge"] == "BOTTOM":
            row["relation"] = "OVERLAY"  # legal editable override
            row["source"] = "USER_ADDED"
        rows.append(row)
    state["assembly_joints"] = rows

    loaded = migrate_legacy_snapshot_joints(state)
    assert edge_relation_for_part(loaded, "head", "TOP") is AssemblyJointRelation.OVERLAY
    assert edge_relation_for_part(loaded, "head", "BOTTOM") is AssemblyJointRelation.OVERLAY


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_head_settings_publish_four_edge_controls_directly_from_registry():
    import tkinter as tk
    import fold_designer_bridge as bridge
    from test_phase6_settings_center_bridge import _snapshot

    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root)
    snap = _snapshot()
    snap.update({
        "existing_parts": ["box_body", "head", "tail"],
        "assembly_type": "WRAP_OVERLAY",
    })
    app = bridge.Phase6FoldDesignerApp(win, snap)
    try:
        app._phase6_parameters_unlocked = True
        app.activate_part("head")
        win.update_idletasks(); win.update()
        assert set(app.endcap_joint_vars) == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
        assert app.endcap_joint_allowed["TOP"] == ("貼外",)
        assert app.endcap_joint_allowed["BOTTOM"] == ("包覆",)
        assert app.endcap_joint_allowed["LEFT"] == ("嵌入", "貼外", "包覆")
        assert app.endcap_joint_allowed["RIGHT"] == ("嵌入", "貼外", "包覆")
        assert str(app.endcap_joint_widgets["TOP"].cget("state")) == "disabled"
        assert str(app.endcap_joint_widgets["BOTTOM"].cget("state")) == "disabled"
        assert str(app.endcap_joint_widgets["LEFT"].cget("state")) == "normal"
        assert str(app.endcap_joint_widgets["RIGHT"].cget("state")) == "normal"

        app.endcap_joint_vars["LEFT"].set("包覆")
        bridge._phase6_on_endcap_edge_relation_selected(app, "head", "LEFT")
        assert edge_relation_for_part(app._phase6_input_snapshot, "head", "LEFT") is AssemblyJointRelation.WRAP
        assert edge_relation_for_part(app._phase6_input_snapshot, "tail", "LEFT") is AssemblyJointRelation.INSERT
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass

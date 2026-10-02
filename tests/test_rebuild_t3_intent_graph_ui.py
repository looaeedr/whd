# -*- coding: utf-8 -*-
from copy import deepcopy
from types import SimpleNamespace

import fold_designer_bridge as bridge
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection
from phase6_endcap_semantics import resolve_box_assembly_type


def _raw(sel):
    return {"type_id": sel.type_id.value, "amount_t": sel.amount_t}


def test_persisted_intent_mirror_wins_over_legacy_top_corner_projection():
    snapshot = {
        "assembly_type": "OVERLAY",
        "corner_state": {
            "head": {"top_left": _raw(CornerTypeSelection(CornerTypeId.INSERT)),
                     "top_right": _raw(CornerTypeSelection(CornerTypeId.INSERT))},
        },
    }
    assert getattr(resolve_box_assembly_type(snapshot), "value", resolve_box_assembly_type(snapshot)) == "OVERLAY"


def test_fold_designer_preset_selection_updates_graph_but_preserves_corner_state(monkeypatch):
    original = {
        "head": {"top_left": _raw(CornerTypeSelection(CornerTypeId.INSERT, amount_t=3.0)),
                 "top_right": _raw(CornerTypeSelection(CornerTypeId.INSERT, amount_t=4.0))},
        "tail": {"top_left": _raw(CornerTypeSelection(CornerTypeId.INSERT, amount_t=5.0)),
                 "top_right": _raw(CornerTypeSelection(CornerTypeId.INSERT, amount_t=6.0))},
    }
    class Var:
        def get(self): return "貼外"
    app = SimpleNamespace(
        _phase6_settings_rendering=False,
        assembly_type_var=Var(),
        _phase6_corner_state=deepcopy(original),
        _phase6_corner_pair_same={"head":{"top":True,"bottom":True},"tail":{"top":True,"bottom":True}},
        _phase6_input_snapshot={"existing_parts":["box_body","head","tail"], "assembly_type":"INSERT", "corner_state":deepcopy(original)},
        designer_workspace=SimpleNamespace(available_parts=("box_body","head","tail"), mark_dirty=lambda: None),
        do_update=lambda: None,
    )
    monkeypatch.setattr(bridge, "_phase6_invalidate_settings_page", lambda *_a, **_k: None)
    monkeypatch.setattr(bridge, "_phase6_rebuild_linked_endcaps", lambda *_a, **_k: None)
    bridge._phase6_on_assembly_type_selected(app)
    assert app._phase6_corner_state == original
    assert app._phase6_input_snapshot["assembly_type"] == "OVERLAY"
    assert {row["edge"] for row in app._phase6_input_snapshot["assembly_joints"] if row["subject_part"] == "head"} == {"TOP","BOTTOM","LEFT","RIGHT"}


def test_formal_wrap_overlay_preset_is_exposed_without_standalone_wrap_selector():
    from phase6_endcap_semantics import ASSEMBLY_TYPE_LABELS, ASSEMBLY_LABEL_TO_TYPE
    assert "包覆貼外" in set(ASSEMBLY_TYPE_LABELS.values())
    assert "WRAP" not in {getattr(k, "value", k) for k in ASSEMBLY_TYPE_LABELS}
    assert ASSEMBLY_LABEL_TO_TYPE["包覆貼外"] == "WRAP_OVERLAY"

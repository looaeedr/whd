from __future__ import annotations

import os
import pytest

pytestmark = pytest.mark.skipif(
    not (os.name == "nt" or os.environ.get("DISPLAY")),
    reason="需要 Tk 顯示環境",
)

def _pump(root):
    root.update_idletasks()
    root.update()

@pytest.mark.parametrize("part",["head","tail"])
def test_endcap_four_direction_selectors_are_width_5_or_less_and_semantics_still_apply(part):
    import tkinter as tk
    import gui
    from ae_engine.assembly_joint import edge_relation_for_part

    root=tk.Tk(); root.withdraw()
    designer=None
    try:
        app=gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        _pump(root)
        designer=app.open_original_fold_designer()
        designer._ui_text_size_change_callback = lambda value: app._apply_ui_text_size_preference(
            value, persist=False, notify_designer=False
        )
        designer.activate_part(part)
        designer.ui_text_size_var.set("中")
        _pump(root)

        assert tuple(designer.endcap_joint_widgets) == ("TOP","BOTTOM","LEFT","RIGHT")
        for edge,widget in designer.endcap_joint_widgets.items():
            assert int(widget.cget("width")) <= 5, (
                f"{part} {edge} width={widget.cget('width')} exceeds requested max 5"
            )

        editable=[edge for edge,allowed in designer.endcap_joint_allowed.items() if len(allowed)>1]
        assert editable
        edge=editable[0]
        current=designer.endcap_joint_vars[edge].get()
        alt=next(v for v in designer.endcap_joint_allowed[edge] if v != current)
        before=dict(designer._phase6_input_snapshot)
        designer.endcap_joint_vars[edge].set(alt)
        relation=designer._phase6_on_endcap_edge_relation_selected(part,edge)
        assert relation is not None
        assert edge_relation_for_part(designer._phase6_input_snapshot,part,edge)==relation

        # Width is UI-only: changing widget width must not mutate unrelated
        # cabinet dimensions / topology.
        for key in ("w","h","d","fw","model","box_body_structure"):
            if key in before:
                assert designer._phase6_input_snapshot.get(key)==before.get(key)
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

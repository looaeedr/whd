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

def _open(part):
    import tkinter as tk
    import gui
    root=tk.Tk(); root.withdraw()
    app=gui.BoxCalculatorGUI(root)
    app.baseline_var.set("受電箱")
    _pump(root)
    designer=app.open_original_fold_designer()
    designer.root.deiconify()
    designer.root.geometry("1120x720+0+0")
    designer.activate_part(part)
    designer.ui_text_size_var.set("中")
    _pump(root)
    if not bool(getattr(designer,"_phase6_parameters_unlocked",False)):
        designer.parameter_lock_button.invoke()
    _pump(root)
    return root,designer

def _close(root,designer):
    try: designer.root.destroy()
    except Exception: pass
    try: root.destroy()
    except Exception: pass

@pytest.mark.parametrize("part",["head","tail"])
def test_medium_unlocked_endcap_edge_hosts_are_fully_inside_canvas(part):
    root,designer=_open(part)
    try:
        hosts=designer.drawing_edge_hosts
        assert hosts is not None
        renderer=designer.renderer.canvas.get_tk_widget()
        assert renderer.winfo_height() >= 80
        for edge in ("TOP","BOTTOM","LEFT","RIGHT"):
            host=getattr(hosts,edge.lower())
            parent=host.master
            assert host.winfo_viewable()==1, f"{part} {edge} host not viewable"
            x,y,w,h=host.winfo_x(),host.winfo_y(),host.winfo_width(),host.winfo_height()
            pw,ph=parent.winfo_width(),parent.winfo_height()
            assert x >= 0, f"{part} {edge} x={x}"
            assert y >= 0, f"{part} {edge} y={y}"
            assert x+w <= pw+1, f"{part} {edge} right={x+w} parent={pw}"
            assert y+h <= ph+1, f"{part} {edge} bottom={y+h} parent={ph}"
    finally:
        _close(root,designer)

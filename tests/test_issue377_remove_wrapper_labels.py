# -*- coding: utf-8 -*-
import os
import tkinter as tk
import pytest
import fold_designer_bridge as bridge

pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="#377 requires Xvfb")

def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)

def test_old_content_switch_wrapper_is_not_user_visible_and_main_selector_owns_modes():
    root=tk.Tk()
    try:
        app=bridge.Phase6FoldDesignerApp(root,{
            "w":500,"h":600,"d":200,
            "existing_parts":["box_body","head","tail"],
            "active_part":"box_body",
            "settings":{"t":2.0,"fw":24.0},
        })
        root.update_idletasks(); root.update()
        frame=getattr(app,"content_switch_frame",None)
        assert frame is None or frame.winfo_manager()==""
        visible_text=[]
        for w in _walk(app.left):
            if not w.winfo_ismapped():
                continue
            try:
                text=str(w.cget("text"))
            except tk.TclError:
                text=""
            if text:
                visible_text.append(text)
        assert "輸入區" not in visible_text
        assert "顯示區" not in visible_text

        menu=app.part_choice_menu
        values=[]
        end=menu.index("end")
        for i in range((end if end is not None else -1)+1):
            try: values.append(str(menu.entrycget(i,"value")))
            except tk.TclError: pass
        assert values[0]=="組合體"
        assert values[-1]=="截角資料"

        app.activate_part("head")
        root.update_idletasks()
        assert app._phase6_3d_display_mode=="single"
        assert app.part_var.get()=="封頭"
        assert app.fold_editor_host.winfo_manager()!=""

        bridge._phase6_show_assembly(app)
        root.update_idletasks()
        assert app._phase6_3d_display_mode=="assembly"
        assert app.part_var.get()=="組合體"

        bridge._phase6_show_corner_data(app)
        root.update_idletasks()
        assert app._phase6_3d_display_mode=="corner_data"
        assert app.part_var.get()=="截角資料"
    finally:
        root.destroy()

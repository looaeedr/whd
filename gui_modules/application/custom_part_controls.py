"""Tk-only custom sheet metadata controls over explicit workspace callbacks."""
import tkinter as tk
from tkinter import ttk, messagebox

def metadata_fields(parent, descriptor=None, *, compact=False):
    row=dict(descriptor or {})
    values={key:tk.StringVar(master=parent,value=str(row.get(key,default)))
            for key,default in (("display_name","自訂板件"),("fold_axis","X"),
                                ("transverse_length",""),("per_box_count",1))}
    labels=(("display_name","板件名稱"),("fold_axis","折法方向"),
            ("transverse_length","另一軸尺寸 (mm)"),("per_box_count","每箱片數"))
    for i,(key,label) in enumerate(labels):
        if compact:
            # The inline editor shares vertical space with the 3D canvas.
            # Two short label-over-entry columns leave the Save/Holes buttons
            # on-screen without widening beyond narrow designer viewports.
            column = i % 2
            label_row = (i // 2) * 2
            ttk.Label(parent,text=label).grid(
                row=label_row,column=column,sticky="w",padx=4,pady=(3,0))
        else:
            column = 1
            label_row = i
            ttk.Label(parent,text=label).grid(
                row=i,column=0,sticky="w",padx=8,pady=6)
        if key=="fold_axis":
            widget=ttk.Combobox(
                parent,textvariable=values[key],values=("X","Y"),
                state="readonly",width=(12 if compact else 20))
        else:
            widget=ttk.Entry(parent,textvariable=values[key],
                             width=(12 if compact else 20))
        widget.grid(row=(label_row+1 if compact else i),
                    column=column,sticky="ew",
                    padx=(4 if compact else 8),
                    pady=((0,3) if compact else 6))
    if compact:
        parent.columnconfigure(0,weight=1)
    parent.columnconfigure(1,weight=1)
    ttk.Label(parent,text="包外 17／100，X 或 Y 單軸折彎；另一軸由你輸入。",
              wraplength=(260 if compact else 380)).grid(
                  row=4,column=0,columnspan=2,sticky="w",
                  padx=(4 if compact else 8),pady=(3 if compact else 8))
    parent._custom_values=values
    return values

def open_custom_part_creation(parent, *, add_part, on_created):
    win=tk.Toplevel(parent)
    win.title("新增頂層自訂板件")
    win.transient(parent)
    frame=ttk.Frame(win,padding=10);frame.pack(fill=tk.BOTH,expand=True)
    values=metadata_fields(frame)
    def apply():
        try:
            key=add_part(**{k:v.get() for k,v in values.items()})
        except ValueError as exc:
            messagebox.showerror("未新增",str(exc),parent=win)
            return None
        win.destroy()
        on_created(key)
        return key
    frame._custom_apply=apply
    ttk.Button(frame,text="新增",command=apply).grid(row=5,column=1,sticky="e",padx=8,pady=8)
    ttk.Button(frame,text="取消",command=win.destroy).grid(row=5,column=0,sticky="w",padx=8,pady=8)
    win._custom_form=frame
    win.grab_set()
    return win

def build_custom_part_editor(parent, *, descriptor, update_part, on_changed, open_holes=None):
    frame=ttk.LabelFrame(parent,text="頂層自訂板件",padding=8)
    values=metadata_fields(frame,descriptor,compact=True)
    ttk.Label(frame,text="獨立板件：可預覽與輸出 DXF；尚未指定箱體安裝位置。",
              wraplength=260).grid(
                  row=5,column=0,columnspan=2,sticky="w",padx=4,pady=(2,3))
    def apply():
        try:
            changed=update_part(**{k:v.get() for k,v in values.items()})
        except ValueError as exc:
            messagebox.showerror("設定未套用",str(exc),parent=parent)
            return False
        if changed:
            on_changed()
        return True
    frame._custom_apply=apply
    ttk.Button(frame,text="套用設定",command=apply).grid(
        row=6,column=1,sticky="e",padx=4,pady=(3,4))
    if open_holes is not None:
        ttk.Button(frame,text="2D 孔位設定",command=open_holes).grid(
            row=6,column=0,sticky="w",padx=4,pady=(3,4))
        frame._custom_open_holes=open_holes
    return frame

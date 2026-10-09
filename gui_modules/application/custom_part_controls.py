"""Tk-only custom sheet metadata controls over explicit workspace callbacks."""
import tkinter as tk
from tkinter import ttk, messagebox

def metadata_fields(parent, descriptor=None):
    row=dict(descriptor or {})
    values={key:tk.StringVar(master=parent,value=str(row.get(key,default)))
            for key,default in (("display_name","自訂板件"),("fold_axis","X"),
                                ("transverse_length",""),("per_box_count",1))}
    labels=(("display_name","板件名稱"),("fold_axis","折法方向"),
            ("transverse_length","另一軸尺寸 (mm)"),("per_box_count","每箱片數"))
    for i,(key,label) in enumerate(labels):
        ttk.Label(parent,text=label).grid(row=i,column=0,sticky="w",padx=8,pady=6)
        if key=="fold_axis":
            widget=ttk.Combobox(parent,textvariable=values[key],values=("X","Y"),state="readonly")
        else:
            widget=ttk.Entry(parent,textvariable=values[key])
        widget.grid(row=i,column=1,sticky="ew",padx=8,pady=6)
    parent.columnconfigure(1,weight=1)
    ttk.Label(parent,text="包外 17／100，X 或 Y 單軸折彎；另一軸由你輸入。",
              wraplength=380).grid(row=4,column=0,columnspan=2,sticky="w",padx=8,pady=8)
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
    frame=ttk.LabelFrame(parent,text="頂層自訂板件",padding=12)
    values=metadata_fields(frame,descriptor)
    ttk.Label(frame,text="獨立板件：可預覽與輸出 DXF；尚未指定箱體安裝位置。",
              wraplength=420).grid(row=5,column=0,columnspan=2,sticky="w",padx=8,pady=8)
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
    ttk.Button(frame,text="套用設定",command=apply).grid(row=6,column=1,sticky="e",padx=8,pady=8)
    if open_holes is not None:
        ttk.Button(frame,text="2D 孔位設定",command=open_holes).grid(row=6,column=0,sticky="w",padx=8,pady=8)
        frame._custom_open_holes=open_holes
    return frame

"""Quantity presentation delegates edits to the existing version owner."""
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk, messagebox


@dataclass
class QuantityVersionControls:
    frame: object
    versions: object
    count_var: object
    totals_var: object
    ports: object
    refreshing: bool = False

    def refresh(self):
        payload = self.ports["snapshot"]()
        if payload is None:
            self.frame.pack_forget()
            return
        self.refreshing = True
        try:
            self.versions.delete(*self.versions.get_children())
            rows = payload["versions"]
            for index, row in enumerate(rows, 1):
                self.versions.insert("", "end", iid=row["version_id"],
                                     values=(f"孔型版本 {index}", row["piece_count"]))
            selected = payload["selected_version_id"]
            self.versions.selection_set(selected)
            self.versions.focus(selected)
            row = next(row for row in rows if row["version_id"] == selected)
            self.count_var.set(str(row["piece_count"]))
            self.totals_var.set(f"版本數：{len(rows)}    總件數：{sum(row['piece_count'] for row in rows)}")
        finally:
            self.refreshing = False

    def select(self, event=None):
        ids = self.versions.selection()
        payload = self.ports["snapshot"]()
        if not self.refreshing and payload and ids and ids[0] != payload["selected_version_id"]:
            self.ports["select"](ids[0])
            self.refresh()

    def add(self):
        self.ports["add"]()
        self.refresh()

    def delete(self):
        payload = self.ports["snapshot"]()
        if len(payload["versions"]) == 1:
            messagebox.showinfo("孔型版本", "至少保留一個孔型版本", parent=self.frame)
            return False
        confirmed = messagebox.askyesno("刪除孔型版本", "刪除目前選取的孔型版本？", parent=self.frame)
        result = self.ports["delete"](confirmed)
        self.refresh()
        return result

    def commit_count(self, event=None):
        try:
            self.ports["count"](self.count_var.get())
        except ValueError as exc:
            messagebox.showwarning("件數未更新", str(exc), parent=self.frame)
            self.refresh()
            return False
        self.refresh()
        return True


def build_quantity_controls(parent, ports):
    frame = ttk.Frame(parent)
    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X)
    tree = ttk.Treeview(frame, columns=("version", "count"), show="headings", height=3, selectmode="browse")
    for key, label, width in (("version", "孔型版本", 140), ("count", "件數", 70)):
        tree.heading(key, text=label)
        tree.column(key, width=width)
    tree.pack(fill=tk.X)
    count = tk.StringVar(master=frame)
    totals = tk.StringVar(master=frame)
    controls = QuantityVersionControls(frame, tree, count, totals, ports)
    ttk.Button(buttons, text="－孔型版本", command=controls.delete).pack(side=tk.LEFT)
    ttk.Button(buttons, text="＋孔型版本", command=controls.add).pack(side=tk.LEFT)
    row = ttk.Frame(frame)
    row.pack(fill=tk.X)
    ttk.Label(row, text="件數").pack(side=tk.LEFT)
    entry = ttk.Entry(row, textvariable=count, width=8)
    entry.pack(side=tk.LEFT)
    entry.bind("<Return>", controls.commit_count)
    entry.bind("<FocusOut>", controls.commit_count)
    controls.count_entry = entry
    for role, label in (("head", "封頭孔"), ("tail", "封尾孔")):
        ttk.Button(row, text=label, command=lambda role=role: ports["holes"](role)).pack(side=tk.LEFT)
    ttk.Label(frame, textvariable=totals).pack(anchor="w")
    tree.bind("<<TreeviewSelect>>", controls.select)
    return controls

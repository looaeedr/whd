# -*- coding: utf-8 -*-
"""Embedded two-step candidate quantity UI for the original Receiving modal.

Keeps all temporary quantities and Bay picks outside project authority.
Uses native ttk controls and the existing right-hand 2D Canvas; no popup.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ae_engine.receiving_hole_candidates import version_label
from ae_engine.receiving_quantity_allocation import (
    AllocationDraft, validate_quantity_allocation,
)


class ReceivingQuantityAllocationUI:
    def __init__(self, window, canvas, *, get_counts, get_ports,
                 get_marks=None, on_render=None, warn=None,
                 roles=("head", "tail"), validate_role=None):
        self.window = window
        self.canvas = canvas
        self.get_counts = get_counts
        self.get_ports = get_ports
        self.get_marks = get_marks
        self.on_render = on_render or (lambda: None)
        self.warn = warn or (lambda exc: None)
        from ae_engine.receiving_hole_candidates import role_key
        self.roles = tuple(roles)
        self.draft = AllocationDraft(
            get_counts(), roles=self.roles, validate_role=validate_role or role_key,
        )
        self.role = self.roles[0]
        self.host = None
        self.success = {role: False for role in self.roles}
        self._mark_cache = {}
        self._hitboxes = ()

    def reconcile(self):
        ports = self.get_ports()
        available = {
            role: [item["id"] for item in ports["versions"](role)]
            for role in self.roles
        }
        before_counts = self.draft.counts
        self.draft.reconcile(self.get_counts(), available)
        if self.draft.counts != before_counts:
            self.success = {role: False for role in self.roles}
        return available

    def show(self, host, role):
        self.host = host
        self.role = role
        self.draw_controls()

    def _schedule(self):
        if self.window.winfo_exists():
            # Do not destroy Tk Buttons inside their own invoke callbacks.
            self.window.after_idle(self.draw_controls)
            self.window.after_idle(self.on_render)

    def _operation(self, callback):
        try:
            callback()
            self.success[self.role] = False
            self._schedule()
        except (ValueError, IndexError, RuntimeError) as exc:
            self.warn(exc)

    def _add(self):
        available = self.reconcile()[self.role]
        remaining = [item for item in available
                     if item not in self.draft.quantities[self.role]]
        if not remaining:
            return
        self.draft.add_version(self.role, remaining[0])

    def _replace_version(self, old, new):
        current = self.draft.quantities[self.role]
        if new == old:
            return
        if new not in self.reconcile()[self.role] or new in current:
            raise ValueError("版本不存在或已加入配置")
        # Keep the row order, but replace only its candidate identity.
        self.draft.quantities[self.role] = {
            (new if key == old else key): count
            for key, count in current.items()
        }
        self.draft.assigned[self.role].clear()
        self.draft.step[self.role] = 1
        self.draft.active_version[self.role] = new

    def _count(self, version_id, delta):
        current = self.draft.quantities[self.role][version_id]
        self.draft.set_quantity(self.role, version_id, max(0, current + delta))

    def draw_controls(self):
        host = self.host
        if host is None or not host.winfo_exists():
            return
        available = self.reconcile()
        for widget in host.winfo_children():
            widget.destroy()
        role = self.role
        total = sum(self.draft.counts)
        quantities = self.draft.quantities[role]
        assigned = self.draft.assigned[role]
        step = self.draft.step[role]
        if step == 1:
            ttk.Label(host, text="1. 決定數量｜全部套共 " + str(total) + " 連").pack(anchor="w", pady=(5, 4))
            labels = {version_label(k): k for k in available[role]}
            for version_id, count in tuple(quantities.items()):
                row = ttk.Frame(host)
                row.pack(anchor="w", pady=2)
                current = tk.StringVar(master=self.window, value=version_label(version_id))
                picker = ttk.Combobox(
                    row, textvariable=current, values=tuple(labels),
                    state="readonly", width=11,
                )
                picker.pack(side="left", padx=(0, 7))
                picker.bind(
                    "<<ComboboxSelected>>",
                    lambda _e, old=version_id, variable=current:
                    self._operation(lambda: self._replace_version(old, labels[variable.get()])),
                )
                ttk.Button(
                    row, text="－", width=3,
                    command=lambda key=version_id: self._operation(lambda: self._count(key, -1)),
                ).pack(side="left")
                ttk.Label(row, text=str(count), width=4, anchor="center").pack(side="left")
                ttk.Button(
                    row, text="＋", width=3,
                    command=lambda key=version_id: self._operation(lambda: self._count(key, 1)),
                ).pack(side="left")
                ttk.Button(
                    row, text="移除",
                    command=lambda key=version_id: self._operation(
                        lambda: self.draft.remove_version(role, key)
                    ),
                ).pack(side="left", padx=(5, 0))
            subtotal = sum(quantities.values())
            ttk.Label(host, text=f"配置總數：{subtotal} / {total} 連").pack(anchor="w", pady=(6, 3))
            ttk.Button(
                host, text="＋加入版本",
                state="normal" if len(quantities) < len(available[role]) else "disabled",
                command=lambda: self._operation(self._add),
            ).pack(anchor="w")
            ttk.Button(
                host, text="下一步：指定配置",
                state="normal" if self.draft.ready_for_positioning(role) else "disabled",
                command=lambda: self._operation(lambda: self.draft.step.__setitem__(role, 2)),
            ).pack(anchor="e", pady=(5, 0))
        else:
            ttk.Label(host, text="2. 指定配置｜先選版本，再點簡易 2D 的連").pack(
                anchor="w", pady=(5, 4)
            )
            selected = tk.StringVar(
                master=self.window, value=self.draft.active_version[role] or ""
            )
            for version_id, count in quantities.items():
                used = sum(value == version_id for value in assigned.values())
                ttk.Radiobutton(
                    host, text=f"{version_label(version_id)}　{used} / {count} 連",
                    variable=selected, value=version_id,
                    command=lambda key=version_id: self._select_version(key),
                ).pack(anchor="w", pady=2)
            ttk.Label(
                host, text=f"已指定：{len(assigned)} / {total} 連"
            ).pack(anchor="w", pady=(5, 2))
            row = ttk.Frame(host)
            row.pack(anchor="e", pady=(4, 0))
            ttk.Button(
                row, text="返回數量",
                command=lambda: self._operation(lambda: self.draft.step.__setitem__(role, 1)),
            ).pack(side="left", padx=(0, 5))
            can_apply = self._ready_to_apply()
            ttk.Button(
                row, text="確認套用配置",
                state="normal" if can_apply else "disabled",
                command=self._commit,
            ).pack(side="left")
            if self.success[role]:
                ttk.Label(host, text="配置已套用").pack(anchor="w")

    def _select_version(self, key):
        self.draft.active_version[self.role] = key
        self.on_render()

    def _ready_to_apply(self):
        try:
            # Pure validation only: this never writes selected Bay features.
            from ae_engine.receiving_hole_candidates import normalize_candidates
            ports = self.get_ports()
            custom_validator = ports.get("validate_quantity")
            if custom_validator is not None:
                custom_validator(
                    dict(self.draft.quantities[self.role]),
                    dict(self.draft.assigned[self.role]),
                    self.draft.counts,
                )
                return True
            library = normalize_candidates()
            # Validator needs the available IDs and their feature values.
            for role in ("head", "tail"):
                entries = ports["versions"](role)
                highest = max((int(item["id"].split("-v")[1]) for item in entries), default=0)
                library[role] = {
                    "versions": entries,
                    "next_number": highest + 1,
                }
            layout = {"sets": [{"bays": [None] * n} for n in self.draft.counts]}
            validate_quantity_allocation(
                layout, library, self.role,
                self.draft.quantities[self.role], self.draft.assigned[self.role],
                expected_counts=self.get_counts(),
            )
        except (ValueError, IndexError, TypeError):
            return False
        return True

    def _commit(self):
        try:
            self.reconcile()
            if self.draft.step[self.role] != 2 or not self._ready_to_apply():
                raise ValueError("配置尚未完成，或總連數已變動")
            ports = self.get_ports()
            ports["apply_quantity"](
                self.role, dict(self.draft.quantities[self.role]),
                dict(self.draft.assigned[self.role]), self.draft.counts,
            )
            self.success[self.role] = True
            self._schedule()
        except (ValueError, IndexError, RuntimeError) as exc:
            self.warn(exc)

    def click(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for si, bi, x0, y0, x1, y1 in self._hitboxes:
            if x0 <= x <= x1 and y0 <= y <= y1:
                self._operation(lambda: self.draft.assign(self.role, si, bi))
                return True
        return False

    def paint(self):
        """Draw all Sets, not just the highlighted/current Set, into same 2D."""
        self.reconcile()
        canvas = self.canvas
        canvas.delete("all")
        counts = self.draft.counts
        role = self.role
        canvas._receiving_bay_hitboxes = ()
        canvas._receiving_selected_bays = frozenset()
        canvas._receiving_selected_bay = None
        width = max(int(canvas.winfo_width()), int(canvas.cget("width")))
        height = max(int(canvas.winfo_height()), int(canvas.cget("height")))
        row_h = 148
        canvas.configure(scrollregion=(0, 0, width, max(height, len(counts) * row_h + 10)))
        hitboxes = []
        assigned = self.draft.assigned[role]
        active = self.draft.active_version[role]
        for si, count in enumerate(counts):
            top = si * row_h + 27
            max_width = width - 30
            bay_w = min(max_width / count, 62.0)
            bay_h = 105.0
            left = (width - bay_w * count) / 2.0
            canvas.create_text(
                12, top - 13, text=f"第 {si + 1} 套（{count} 連）",
                fill="#dde6ef", anchor="w",
            )
            for bi in range(count):
                x0, x1 = left + bi * bay_w, left + (bi + 1) * bay_w
                choice = assigned.get((si, bi))
                highlight = choice is not None and choice == active
                canvas.create_rectangle(
                    x0, top, x1, top + bay_h,
                    fill="#315775" if highlight else ("#293f51" if choice else "#263a4d"),
                    outline="#42bdf4" if highlight else "#8faec4",
                    width=3 if highlight else 1,
                )
                inset = min(6.0, max(2.0, bay_w * .08))
                split = top + bay_h * 1100.0 / 1600.0
                faces = (
                    (x0 + inset, top + inset, x1 - inset, split - 2),
                    (x0 + inset, split + 2, x1 - inset, top + bay_h - inset),
                )
                for face in faces:
                    canvas.create_rectangle(*face, outline="#c3d1dc", width=1)
                canvas.create_line(x0 + inset, split, x1 - inset, split,
                                   fill="#e0c487", width=1)
                self._draw_original_door_marks(si, bi, faces)
                canvas.create_text(
                    (x0 + x1) / 2, top + bay_h + 11,
                    text=f"{bi + 1}：{version_label(choice) if choice else '未配置'}",
                    fill="#e4edf6" if choice else "#a8b8c6",
                )
                hitboxes.append((si, bi, x0, top, x1, top + bay_h))
        self._hitboxes = tuple(hitboxes)
        canvas._receiving_allocation_hitboxes = self._hitboxes

    def _draw_original_door_marks(self, set_index, bay_index, faces):
        if self.get_marks is None:
            return
        key = (set_index, bay_index)
        if key not in self._mark_cache:
            self._mark_cache[key] = self.get_marks(set_index, bay_index)
        for row_index, face in enumerate(faces):
            marks = self._mark_cache[key]
            if row_index >= len(marks) or not marks[row_index]:
                continue
            entry = marks[row_index]
            fx0, fy0, fx1, fy1 = face
            dw, dh = fx1 - fx0, fy1 - fy0
            if dw <= 0 or dh <= 0:
                continue
            handle = entry.get("handle") or ()
            if len(handle) >= 3:
                coords = [
                    value for px, py in handle
                    for value in (fx0 + px * dw, fy0 + py * dh)
                ]
                self.canvas.create_polygon(*coords, fill="", outline="#f7c66f", width=1)
            for cx, cy, rx, ry in entry.get("nameplate") or ():
                px, py = fx0 + cx * dw, fy0 + cy * dh
                sx, sy = max(1.0, rx * dw), max(1.0, ry * dh)
                self.canvas.create_oval(px - sx, py - sy, px + sx, py + sy,
                                        outline="#f7c66f", width=1)

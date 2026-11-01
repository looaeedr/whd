# -*- coding: utf-8 -*-
"""Phase6 BendingUI presentation owner.

Issue #444 extracts the fold editor UI owner without creating a reverse import
to fold_designer_bridge. Bridge-owned transactions remain owner instance
actions reached through update_cb.__self__.
"""
from __future__ import annotations

from typing import Mapping

import fold_designer_original as original
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine import manufacturing_api
from phase6_fold_profiles import (
    _num,
    _ui_len,
    apply_outside_dimension_compensation,
    engine_angle_to_ui,
    engine_segment_length_to_ui,
)


def resolve_profile_key(active_dict: Mapping[str, object], requested: object) -> str:
    """Resolve a stale notebook/renderer label to a real editable profile key."""
    key = str(requested)
    if key in active_dict:
        return key
    if "X" in active_dict:
        return "X"
    try:
        return next(iter(active_dict))
    except StopIteration:
        raise KeyError(key)


def _phase6_box_symmetry_allowed(owner) -> bool:
    """Resolve the current family symmetry capability from live/snapshot state."""
    snapshot = dict(getattr(owner, "_phase6_input_snapshot", {}) or {})
    model = str(snapshot.get("model") or snapshot.get("cabinet_type") or "").strip()
    model_var = getattr(owner, "baseline_model_var", None)
    if model_var is not None:
        try:
            live = str(model_var.get() or "").strip()
        except Exception:
            live = ""
        if live:
            model = live
    return cabinet_family_policy.box_body_symmetry_allowed(model)


def _phase6_legacy_symmetry_widgets(owner, *, exclude=None):
    """Capture original Designer symmetry widgets so Receiving can hide them too."""
    cached = getattr(owner, "_phase6_legacy_symmetry_widgets", None)
    if cached is not None:
        return cached
    found = []

    def walk(parent):
        try:
            children = tuple(parent.winfo_children())
        except Exception:
            return
        for child in children:
            if child is exclude:
                continue
            try:
                text = str(child.cget("text") or "")
            except Exception:
                text = ""
            if text == "對稱折彎":
                try:
                    info = dict(child.pack_info()) if child.winfo_manager() == "pack" else None
                    siblings = list(child.master.pack_slaves()) if info is not None else []
                    idx = siblings.index(child) if child in siblings else -1
                    next_widget = siblings[idx + 1] if idx >= 0 and idx + 1 < len(siblings) else None
                except Exception:
                    info = None
                    next_widget = None
                found.append((child, info, next_widget))
            walk(child)

    left = getattr(owner, "left", None)
    if left is not None:
        walk(left)
    owner._phase6_legacy_symmetry_widgets = found
    return found


def _phase6_set_legacy_symmetry_visibility(owner, allowed: bool, *, exclude=None):
    for widget, info, next_widget in _phase6_legacy_symmetry_widgets(owner, exclude=exclude):
        try:
            managed = bool(widget.winfo_manager())
        except Exception:
            continue
        if allowed:
            if not managed and info is not None:
                opts = {k: v for k, v in info.items() if k != "in"}
                try:
                    if next_widget is not None and next_widget.winfo_manager():
                        widget.pack(in_=widget.master, before=next_widget, **opts)
                    else:
                        widget.pack(in_=widget.master, **opts)
                except Exception:
                    pass
        elif managed:
            try:
                widget.pack_forget()
            except Exception:
                pass


def _phase6_apply_box_symmetry_policy(owner, *, bending_ui=None) -> bool:
    """Normalize state/UI so a disallowed family can never have effective symmetry."""
    allowed = _phase6_box_symmetry_allowed(owner)
    if not allowed:
        try:
            owner.state.symmetric = False
        except Exception:
            pass
        var = getattr(owner, "v_sy", None)
        if var is not None:
            try:
                if bool(var.get()):
                    var.set(False)
            except Exception:
                pass
    ui = bending_ui if bending_ui is not None else getattr(owner, "bend_ui", None)
    if ui is not None:
        phase_var = getattr(ui, "phase6_symmetry_var", None)
        if not allowed and phase_var is not None:
            try:
                if bool(phase_var.get()):
                    phase_var.set(False)
            except Exception:
                pass
        _phase6_set_legacy_symmetry_visibility(
            owner, allowed, exclude=getattr(ui, "phase6_symmetry_check", None)
        )
    return allowed



class Phase6BendingUI(original.BendingUI):
    """Original BendingUI with Phase6 metadata and boundary-only conversion."""

    def __init__(self, parent, state, update_cb):
        super().__init__(parent, state, update_cb)
        owner = getattr(update_cb, "__self__", None)
        self.phase6_symmetry_bar = original.ttk.Frame(parent)
        self.phase6_symmetry_var = getattr(owner, "v_sy", None)
        if self.phase6_symmetry_var is None:
            self.phase6_symmetry_var = original.tk.BooleanVar(value=bool(getattr(state, "symmetric", True)))
        self.phase6_symmetry_check = original.ttk.Checkbutton(
            self.phase6_symmetry_bar,
            text="對稱折彎",
            variable=self.phase6_symmetry_var,
            command=self._phase6_on_symmetry_toggle,
        )
        self.phase6_symmetry_check.pack(side=original.tk.LEFT, padx=(0, 8))
        original.ttk.Label(
            self.phase6_symmetry_bar,
            text="開啟時，箱身兩側對應折彎同步修改／刪除",
        ).pack(side=original.tk.LEFT)
        self._phase6_refresh_symmetry_bar()

    def _phase6_on_symmetry_toggle(self):
        owner = getattr(self.update_cb, "__self__", None)
        if owner is not None and hasattr(owner, "v_sy"):
            owner._phase6_on_box_symmetry_changed()
        else:
            self.state.symmetric = bool(self.phase6_symmetry_var.get())
            self._mark_workspace_dirty()
            self.update_cb()

    def _phase6_refresh_symmetry_bar(self):
        bar = getattr(self, "phase6_symmetry_bar", None)
        if bar is None:
            return
        owner = getattr(self.update_cb, "__self__", None)
        allowed = _phase6_apply_box_symmetry_policy(owner, bending_ui=self) if owner is not None else True
        show = (
            allowed
            and getattr(self.state, "phase6_fold_ui_vault_key", None) == "箱身"
        )
        if show:
            if not bar.winfo_manager():
                bar.pack(fill=original.tk.X, pady=(0, 4), before=self.container)
            try:
                self.phase6_symmetry_var.set(bool(getattr(self.state, "symmetric", True)))
            except Exception:
                pass
        elif bar.winfo_manager():
            bar.pack_forget()

    def rebuild_tabs(self):
        custom_tabs = getattr(self.state, "phase6_fold_ui_tabs", None)
        if not custom_tabs:
            return super().rebuild_tabs()
        for tab in self.nb.tabs():
            self.nb.forget(tab)
        self.tabs.clear()
        labels = {"X": " X 軸折彎 ", "Y": " Y 軸折彎 "}
        for key in custom_tabs:
            self.nb.add(original.ttk.Frame(self.nb), text=labels.get(key, f" {key} "))
            self.tabs.append(key)
        if self.state.active_bend not in self.tabs:
            self.state.active_bend = self.tabs[0]
        self.nb.select(self.tabs.index(self.state.active_bend))
        self.render()
        self._phase6_refresh_symmetry_bar()


    def activate_standard_part_controls(self, mode_var):
        """Rebind this editor to a custom sheet's one-axis source after activation.

        Custom sheet navigation has its own early-return path. It must not
        reuse the hidden box-body vault key or its old Tk bend row controls.
        Only the BendingUI presentation owner changes tabs; manufacturing and
        profile data remain under the existing Workspace/PartSession owners.
        """
        if self.state.struct_mode != "standard":
            raise ValueError("自訂板件折彎編輯器未切換至標準模式")
        self.state.phase6_fold_ui_vault_key = None
        if mode_var.get() != "standard":
            mode_var.set("standard")
        # Rebuild even if row counts match: metadata edits can change axis or
        # fixed fold values while preserving the same number of segments.
        self.rebuild_tabs()


    def _mark_workspace_dirty(self):
        owner = getattr(self.update_cb, "__self__", None)
        if owner is not None and hasattr(owner, "designer_workspace"):
            owner.designer_workspace.mark_dirty()

    def apply_mirror(self, idx, key):
        if getattr(self, "_phase6_refreshing_controls", False):
            return
        self._mark_workspace_dirty()
        owner = getattr(self.update_cb, "__self__", None)
        symmetry_allowed = _phase6_box_symmetry_allowed(owner) if owner is not None else True
        if symmetry_allowed and getattr(self.state, "symmetric", False):
            active = self.get_active_dict()
            segs = active.get(self._active_profile_key(active), ())
            try:
                plan = manufacturing_api.plan_operator_fold_mirror_target(
                    segs, idx, key,
                    is_box_body=(
                        getattr(self.state, "phase6_fold_ui_vault_key", None)
                        == "箱身"
                    ),
                )
                target_idx = plan.target_index
                if (
                    target_idx is not None and target_idx != idx
                    and key in self.controls[target_idx]
                ):
                    value = original.get_int(self.controls[idx][key].get())
                    self.controls[target_idx][key].set(str(value))
                    self.save()
                    self.update_cb()
                    return None
                if plan.block_legacy_fallback:
                    self.save()
                    self.update_cb()
                    return None
            except (TypeError, ValueError, IndexError, KeyError):
                pass
            return super().apply_mirror(idx, key)
        # With symmetry off, still commit every typed outside Fold edit.
        self.save()
        self.update_cb()
        return None

    def refresh_active_profile(self):
        """Refresh existing editor vars when the X/Y widget topology is unchanged."""
        active_dict = self.get_active_dict()
        active_key = self._active_profile_key(active_dict)
        segs = active_dict[active_key]
        apply_outside_dimension_compensation(segs, getattr(self.state, "phase6_thickness", 2.0))
        if len(self.controls) != len(segs):
            self.render(); return False
        for ctrl, seg in zip(self.controls, segs):
            if (("angle" in ctrl) != ("angle" in seg)) or "len" not in ctrl:
                self.render(); return False
        self._phase6_refreshing_controls = True
        try:
            for index, (ctrl, seg) in enumerate(zip(self.controls, segs)):
                if "angle" in ctrl:
                    text = str(original.get_int(engine_angle_to_ui(seg.get("angle", 0))))
                    if ctrl["angle"].get() != text:
                        ctrl["angle"].set(text)
                operator_length = engine_segment_length_to_ui(seg)
                if float(seg.get("phase6_ui_sign", 1.0) or 1.0) < 0.0:
                    operator_length = -operator_length
                length_text = str(original.get_int(operator_length))
                if ctrl["len"].get() != length_text:
                    ctrl["len"].set(length_text)
                labels = self.container.grid_slaves(row=index + 1, column=5)
                if labels:
                    core = seg.get("core")
                    material_text = f"料 {_ui_len(seg.get('len'))}"
                    labels[0].configure(text=f"{material_text} / {core}" if core else material_text)
        finally:
            self._phase6_refreshing_controls = False
        return True

    def get_active_dict(self):
        custom = getattr(self.state, "phase6_fold_ui_profiles", None)
        if custom is not None:
            return custom
        return super().get_active_dict()

    def on_tab(self, event):
        # Programmatic tab selection during part switching already renders the
        # selected profile in rebuild_tabs().  Tk still emits TabChanged later;
        # do not redraw/schedule another full 3D update when the key did not
        # actually change.  Real operator tab clicks still follow the original
        # path below.
        try:
            idx = self.nb.index("current")
        except Exception:
            return
        if not (0 <= idx < len(self.tabs)):
            return
        key = self.tabs[idx]
        if key == self.state.active_bend:
            return
        self.state.active_bend = key
        self.render()
        self._phase6_refresh_symmetry_bar()
        self.update_cb()

    def _active_profile_key(self, active_dict=None):
        active_dict = self.get_active_dict() if active_dict is None else active_dict
        key = resolve_profile_key(active_dict, self.state.active_bend)
        if self.state.active_bend != key:
            self.state.active_bend = key
        return key

    def render(self):
        active_dict = self.get_active_dict()
        active_key = self._active_profile_key(active_dict)
        segs = active_dict[active_key]
        apply_outside_dimension_compensation(segs, getattr(self.state, "phase6_thickness", 2.0))
        saved = []
        for seg in segs:
            original_values = {}
            if "angle" in seg:
                original_values["angle"] = seg["angle"]
                seg["angle"] = engine_angle_to_ui(seg["angle"])
            if _num(seg.get("ui_len_add")):
                original_values["len"] = seg["len"]
                operator_length = engine_segment_length_to_ui(seg)
                if float(seg.get("phase6_ui_sign", 1.0) or 1.0) < 0.0:
                    operator_length = -operator_length
                seg["len"] = operator_length
            if original_values:
                saved.append((seg, original_values))
        try:
            super().render()
        finally:
            for seg, values in saved:
                seg.update(values)

        for index, seg in enumerate(segs):
            row = index + 1
            # The editable value is always operator outside dimension; show the
            # authoritative material segment beside it for cutting/corner work.
            length_labels = self.container.grid_slaves(row=row, column=3)
            if length_labels:
                try:
                    length_labels[0].configure(text="包外:")
                except Exception:
                    pass
            core = seg.get("core")
            material_text = f"料 {_ui_len(seg.get('len'))}"
            label = f"{material_text} / {core}" if core else material_text
            original.ttk.Label(self.container, text=label).grid(row=row, column=5, padx=4)
            if core:
                delete_widgets = self.container.grid_slaves(row=row, column=6)
                if delete_widgets:
                    delete_widgets[0].configure(state="disabled")

    def save(self):
        active_dict = self.get_active_dict()
        active_key = self._active_profile_key(active_dict)
        old_segments = active_dict[active_key]
        thickness = getattr(self.state, "phase6_thickness", 2.0)

        # Tk only parses the operator's typed values. Engine alone determines
        # the new adjacent-BEND topology, material lengths and structural keys.
        edits = []
        for ctrl in self.controls:
            row = {}
            if "angle" in ctrl:
                row["angle"] = original.get_int(ctrl["angle"].get())
            edits.append(row)
        for row, ctrl in zip(edits, self.controls):
            row["len"] = original.get_int(ctrl["len"].get())

        new_segments = manufacturing_api.commit_operator_fold_editor_rows(
            old_segments, edits, thickness,
        )
        active_dict[active_key] = new_segments
        vault_key = getattr(self.state, "phase6_fold_ui_vault_key", None)
        if vault_key and active_key == "X":
            self.state.profiles_vault[vault_key] = new_segments

    def add(self, pos):
        self._mark_workspace_dirty()
        self.save()
        active = self.get_active_dict()
        segs = active[self._active_profile_key(active)]
        # Keep the bound list identity shared with the existing Profiles Vault.
        segs[:] = manufacturing_api.operator_fold_editor_add_segment(
            segs, pos, getattr(self.state, "phase6_thickness", 2.0),
        )
        self.render()
        self.update_cb()

    def remove(self, idx):
        self._mark_workspace_dirty()
        self.save()
        active = self.get_active_dict()
        segs = active[self._active_profile_key(active)]
        owner = getattr(self.update_cb, "__self__", None)
        symmetry_allowed = _phase6_box_symmetry_allowed(owner) if owner is not None else True
        symmetric_box = (
            symmetry_allowed
            and bool(getattr(self.state, "symmetric", False))
            and getattr(self.state, "phase6_fold_ui_vault_key", None) == "箱身"
        )
        updated = manufacturing_api.operator_fold_editor_remove_segment(
            segs, idx, getattr(self.state, "phase6_thickness", 2.0),
            symmetric_box_body=symmetric_box,
        )
        if updated is None:
            return
        segs[:] = updated
        self.render()
        self.update_cb()

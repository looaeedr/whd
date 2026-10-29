"""Global Phase6 project-file action wrappers.

These functions remain methods of Phase6ApplicationHost through explicit aliasing in
``gui.py``. ProjectController/ProjectSession retain all persistence and transaction
authority; this module owns only the existing GUI action wrappers.
"""
from pathlib import Path
from tkinter import filedialog, messagebox

from phase6_project_file import PROJECT_EXTENSION as PHASE6_PROJECT_EXTENSION


def save_phase6_project_as(self, *, _active_part_hint=None):
        """把 committed 全專案另存到使用者選擇的 .p6fold 路徑。"""
        model = self.baseline_var.get().strip() or "自訂"
        safe_model = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in model)
        current = self.project_controller.project_path
        initial = Path(current).name if current else f"{safe_model}{PHASE6_PROJECT_EXTENSION}"
        path = filedialog.asksaveasfilename(
            parent=self.root, title="另存新檔：Phase6 專案",
            defaultextension=PHASE6_PROJECT_EXTENSION,
            filetypes=[("Phase6 折彎專案", f"*{PHASE6_PROJECT_EXTENSION}"), ("所有檔案", "*.*")],
            initialfile=initial,
        )
        if not path:
            return None
        self._flush_phase6_authoritative_state()
        try:
            return self.project_controller.save(
                path,
                self._compose_phase6_project_snapshot_from_main_gui,
                active_part_hint=_active_part_hint,
            )
        except Exception as exc:
            messagebox.showerror("存檔失敗", f"無法儲存 Phase6 專案：\n{exc}", parent=self.root)
            return None

def save_phase6_project(self, *, _active_part_hint=None):
        """儲存到目前專案路徑；尚無路徑時改走另存新檔。"""
        current = self.project_controller.project_path
        if not current:
            return self.save_phase6_project_as(_active_part_hint=_active_part_hint)
        self._flush_phase6_authoritative_state()
        try:
            return self.project_controller.save(
                current,
                self._compose_phase6_project_snapshot_from_main_gui,
                active_part_hint=_active_part_hint,
            )
        except Exception as exc:
            messagebox.showerror("存檔失敗", f"無法儲存 Phase6 專案：\n{exc}", parent=self.root)
            return None

def open_phase6_project(self):
        """把完整專案載入 committed 主 GUI，不強制開啟 3D。"""
        path = filedialog.askopenfilename(
            parent=self.root, title="開啟專案：Phase6",
            filetypes=[("Phase6 折彎專案", f"*{PHASE6_PROJECT_EXTENSION}"), ("所有檔案", "*.*")],
        )
        if not path:
            return None
        try:
            self.load_phase6_project(path, open_designer=False)
            return str(Path(path))
        except Exception as exc:
            messagebox.showerror("讀檔失敗", f"無法讀取 Phase6 專案：\n{exc}", parent=self.root)
            return None

def _discard_previous_project_designer_caches(designer):
        """Retire prior .p6fold scenes, not the immutable DXF source cache."""
        if designer is None:
            return
        composition = getattr(designer, "_phase6_composition_owner", None)
        if composition is not None:
            for name in (
                "_receiving_bay_preview_cache",
                "_receiving_bay_virtual_preview_cache",
                "_receiving_raw_divider_history",
                "_receiving_raw_inner_door_frame_history",
                "_receiving_raw_inner_door_panel_history",
            ):
                cache = getattr(composition, name, None)
                clear = getattr(cache, "clear", None)
                if callable(clear):
                    clear()
        owner = getattr(designer, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("family-structure")
        manufacturing = getattr(designer, "_phase6_manufacturing_cache_service", None)
        if manufacturing is not None:
            manufacturing.clear()


def load_phase6_project(self, path, *, open_designer=True):
        """載入 .p6fold 專案，並可選擇進入其保存的 3D 板件。"""
        previous_designer = getattr(self, "fold_designer_app", None)
        payload, committed = self.project_controller.load(path)
        snapshot = self._apply_phase6_project_snapshot(committed)
        # A reused Designer's geometry cache is scoped to the *previous*
        # project. Only clear after the new canonical load succeeds.
        _discard_previous_project_designer_caches(previous_designer)
        if not open_designer:
            return payload
        designer = self.open_original_fold_designer()
        from ae_engine.cabinet_types.receiving import is_receiving_snapshot
        if designer is previous_designer and is_receiving_snapshot(snapshot):
            # An already-open Designer must replace its previous project's
            # receiving mode; a NEW Designer has already consumed the
            # committed main-GUI snapshot. Forcing _apply_mode_snapshot on
            # fresh legacy projects recalculates invalid old NFB depth source
            # too early and incorrectly BLOCKS opening an editable project.
            # Keep invalid manufacturing source unapproved, but loadable.
            import fold_designer_bridge as bridge
            from gui_modules.application.fold_designer_composition_receiving import _apply_mode_snapshot
            previous_guard = designer._phase6_baseline_guard
            designer._phase6_baseline_guard = True
            try:
                designer.baseline_model_var.set(snapshot["model"])
                designer._phase6_baseline_last_model = snapshot["model"]
            finally:
                designer._phase6_baseline_guard = previous_guard
            _apply_mode_snapshot(bridge._phase6_composition(designer), vars(bridge), snapshot)
            designer._refresh_part_buttons()
            designer._phase6_current_project_path = str(Path(path))
        # #1503 real Windows saved v3: the authoritative project's original
        # Receiving BasePlate mapping is persisted in .p6fold but the newly
        # created designer initially projects only visible UI knobs and loses
        # this source. Restore its original mapping into the effective
        # designer snapshot BEFORE any assembly geometry is consumed.
        # No new data or missing BasePlate is invented; source CSV and
        # manufacturing checks still have to prove the part independently.
        if (snapshot.get("model") in ("受電箱", "RECEIVING")
                and "receiving_base_plate" in snapshot):
            from copy import deepcopy
            effective = getattr(designer, "_phase6_input_snapshot", None)
            if isinstance(effective, dict):
                effective["receiving_base_plate"] = deepcopy(
                    snapshot["receiving_base_plate"]
                )
        # Rebuild the operator 2D navigator AFTER the saved physical source
        # reaches the effective Designer. Original Designer initialization
        # happens before this restore, so its first derived sync sees only
        # box_body and silently omits both the base and per-tier child parts.
        # An unsubmitted or unresolvable source cannot gain new presence.
        effective = getattr(designer, "_phase6_input_snapshot", None)
        if (isinstance(effective, dict)
                and effective.get("model") in ("受電箱", "RECEIVING")
                and effective.get("nfb_config_submitted") is True):
            from ae_engine.receiving_base_plate_config import receiving_base_plate_values
            try:
                verified_source = receiving_base_plate_values(effective)
            except (ValueError, TypeError, KeyError):
                verified_source = None
            if verified_source is not None:
                import fold_designer_bridge as bridge
                bridge._phase6_sync_authoritative_derived_parts(designer)
                designer._refresh_part_buttons()
        active = snapshot.get("active_part") or (snapshot.get("workspace") or {}).get("active_part")
        if active in getattr(designer, "available_parts", ()):
            designer.activate_part(active)
        return designer

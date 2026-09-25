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

def load_phase6_project(self, path, *, open_designer=True):
        """載入 .p6fold 專案，並可選擇進入其保存的 3D 板件。"""
        payload, committed = self.project_controller.load(path)
        snapshot = self._apply_phase6_project_snapshot(committed)
        if not open_designer:
            return payload
        designer = self.open_original_fold_designer()
        active = snapshot.get("active_part") or (snapshot.get("workspace") or {}).get("active_part")
        if active in getattr(designer, "available_parts", ()):
            designer.activate_part(active)
        return designer

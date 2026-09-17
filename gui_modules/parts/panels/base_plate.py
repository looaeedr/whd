"""Base-plate input-panel presentation and thin routing only.

Workspace/manufacturing state remains authoritative outside this module.
"""

import tkinter as tk


def setup_tab_base_plate_ui(self):
    # 底板收縮/折邊已集中到 3D 設定中心；此頁只保留預覽/開孔入口。
    canvas_frame = tk.Frame(self.tab_base_plate, bg=self.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

    self.canvas_base_plate = tk.Canvas(canvas_frame, bg=self.COLOR_CANVAS_BG, highlightthickness=0)
    self.canvas_base_plate.pack(fill=tk.BOTH, expand=True)
    self.canvas_base_plate.bind("<Configure>", lambda e: self.draw_preview())
    self._attach_part_hole_entrypoint(self.canvas_base_plate, "base_plate", allow_double=True)

    # 舊版 draw_base_plate 會查這兩個容器；保留空容器避免相容路徑失效。
    self.canvas_frames = {}
    self.canvas_window_ids = {}

def sync_base_plate_shrink(host, *args):
    if host.base_plate_all_same_var.get():
        val = host.base_plate_shrink_same_var.get()
        host.base_plate_shrink_top_var.set(val)
        host.base_plate_shrink_bottom_var.set(val)
        host.base_plate_shrink_left_var.set(val)
        host.base_plate_shrink_right_var.set(val)

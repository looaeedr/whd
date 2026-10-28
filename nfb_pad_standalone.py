# -*- coding: utf-8 -*-
"""獨立 NFB 墊高片草稿工具：python nfb_pad_standalone.py

Only needs Python/Tkinter for the interactive 2D/3D schematic preview.
Draft DXF export additionally needs ezdxf. Source CSV/tooling stays in WHD.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ae_engine.receiving_nfb_numeric_catalog import BRANDS, model_choices
from ae_engine.receiving_nfb_pad_standalone import (
    PadSelection, build_pad_preview, export_draft_pad_dxf,
)


class StandalonePadWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WHD｜NFB 墊高片獨立預覽（非製造核准）")
        self.geometry("1050x720")
        self.minsize(760, 540)
        self.selected: list[PadSelection] = []
        self.plan = None
        self.brand = tk.StringVar(value=BRANDS[0])
        self.model = tk.StringVar()
        self.tier = tk.StringVar(value="1")
        self.thickness = tk.StringVar(value="2")
        self.view = tk.StringVar(value="2D 展開")
        self._make_layout()
        # Any thickness edit invalidates the previously computed drawing.
        self.thickness.trace_add("write", lambda *_: self._invalidate())
        self._refresh_models()

    def _make_layout(self):
        bar = ttk.Frame(self, padding=10)
        bar.pack(fill="x")
        ttk.Label(bar, text="實體層").grid(row=0, column=0)
        ttk.Entry(bar, textvariable=self.tier, width=5).grid(row=0, column=1, padx=5)
        ttk.Label(bar, text="廠牌").grid(row=0, column=2)
        brands = ttk.Combobox(
            bar, textvariable=self.brand, values=BRANDS, width=8, state="readonly",
        )
        brands.grid(row=0, column=3, padx=5)
        brands.bind("<<ComboboxSelected>>", lambda _event: self._refresh_models())
        ttk.Label(bar, text="型號").grid(row=0, column=4)
        self.models = ttk.Combobox(
            bar, textvariable=self.model, width=22, state="readonly",
        )
        self.models.grid(row=0, column=5, padx=5)
        ttk.Button(bar, text="加入 NFB", command=self._add).grid(row=0, column=6)
        ttk.Label(bar, text="板厚 mm").grid(row=0, column=7, padx=(14, 2))
        ttk.Entry(bar, textvariable=self.thickness, width=6).grid(row=0, column=8)

        middle = ttk.PanedWindow(self, orient="horizontal")
        middle.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        left = ttk.Frame(middle, padding=6)
        right = ttk.Frame(middle, padding=6)
        middle.add(left, weight=1)
        middle.add(right, weight=4)
        ttk.Label(left, text="已選 NFB（同層深度自動比較）").pack(anchor="w")
        self.items = tk.Listbox(left, width=27, height=14, exportselection=False)
        self.items.pack(fill="both", expand=True, pady=5)
        ttk.Button(left, text="移除選中", command=self._remove).pack(fill="x")
        ttk.Button(left, text="計算墊高片", command=self._calculate).pack(
            fill="x", pady=(8, 0),
        )
        ttk.Button(
            left, text="輸出草稿 DXF（非加工）", command=self._export,
        ).pack(fill="x", pady=(8, 0))
        ttk.Label(
            left, text="正式 DXF／NC 需回到 WHD\n驗證底板、接觸與裝配。", foreground="#9b3d00",
            justify="left",
        ).pack(anchor="w", pady=12)

        switches = ttk.Frame(right)
        switches.pack(fill="x")
        ttk.Label(switches, text="墊高片").pack(side="left")
        self.parts = ttk.Combobox(switches, width=46, state="readonly")
        self.parts.pack(side="left", padx=8, fill="x", expand=True)
        self.parts.bind("<<ComboboxSelected>>", lambda _event: self._draw())
        mode = ttk.Combobox(
            switches, textvariable=self.view, values=("2D 展開", "3D 折彎示意"),
            state="readonly", width=13,
        )
        mode.pack(side="right")
        mode.bind("<<ComboboxSelected>>", lambda _event: self._draw())
        self.canvas = tk.Canvas(right, background="white", highlightthickness=1)
        self.canvas.pack(fill="both", expand=True, pady=8)
        self.canvas.bind("<Configure>", lambda _event: self._draw())
        self.info = tk.StringVar(value="加入同一層至少兩顆 NFB，再按「計算墊高片」。")
        ttk.Label(
            right, textvariable=self.info, justify="left", wraplength=650,
        ).pack(fill="x")

    def _refresh_models(self):
        try:
            choices = model_choices(self.brand.get())
        except (OSError, ValueError) as exc:
            messagebox.showerror("CSV V5 讀取失敗", str(exc))
            choices = ()
        self.models["values"] = choices
        self.model.set(choices[0] if choices else "")

    def _invalidate(self):
        self.plan = None
        self.parts["values"] = ()
        self.parts.set("")
        self.canvas.delete("all")
        self.info.set("選取內容已變更，請重新計算。")

    def _add(self):
        try:
            layer = int(self.tier.get().strip())
            if str(layer) != self.tier.get().strip() or not 1 <= layer <= 32:
                raise ValueError("實體層必須為 1～32 的整數")
            if not self.model.get():
                raise ValueError("請先選擇 CSV V5 NFB 型號")
            item = PadSelection(layer, self.brand.get(), self.model.get())
            self.selected.append(item)
            self.items.insert("end", f"第{layer}層  {item.brand} / {item.model}")
            self._invalidate()
        except ValueError as exc:
            messagebox.showerror("NFB 選取錯誤", str(exc))

    def _remove(self):
        indexes = self.items.curselection()
        if not indexes:
            return
        index = indexes[0]
        self.selected.pop(index)
        self.items.delete(index)
        self._invalidate()

    def _calculate(self):
        try:
            self.plan = build_pad_preview(
                self.selected, plate_thickness_mm=float(self.thickness.get()),
            )
            descriptions = [
                f"第{j.tier}層　第{j.selected_index + 1}顆 "
                f"{j.pattern.brand}/{j.pattern.model}  墊高 {j.pattern.rise_mm:g} mm"
                for j in self.plan.jobs
            ]
            self.parts["values"] = descriptions
            if descriptions:
                self.parts.current(0)
                self._draw()
            else:
                self.parts.set("")
                self.canvas.delete("all")
                self.info.set("各層 NFB 深度相同，無需墊高片。")
        except (ValueError, OSError, OverflowError) as exc:
            self._invalidate()
            messagebox.showerror("無法產生墊高片", str(exc))

    def _draw(self):
        if self.plan is None or not self.plan.jobs:
            return
        index = self.parts.current()
        if not 0 <= index < len(self.plan.jobs):
            return
        pad = self.plan.jobs[index].pattern
        cv = self.canvas
        cv.delete("all")
        width = max(cv.winfo_width(), 350)
        height = max(cv.winfo_height(), 280)
        if self.view.get() == "3D 折彎示意":
            self._draw_3d(pad, width, height)
        else:
            self._draw_2d(pad, width, height)
        self.info.set(
            f"{pad.brand}/{pad.model}  基準深 {pad.reference_depth_mm:g} mm｜"
            f"NFB 深 {pad.switch_depth_mm:g} mm｜墊高 {pad.rise_mm:g} mm\n"
            f"板厚 {pad.plate_thickness_mm:g} mm｜展開寬 "
            f"{pad.blank_width_mm:g} mm｜成型寬 {pad.formed_width_mm:g} mm\n"
            "僅幾何草稿：尚未驗證底板接觸、實體 Z、焊接、NC 製造。"
        )

    def _draw_2d(self, pad, width, height):
        cv = self.canvas
        pts = pad.unfolded_outline_xy_mm
        x0 = min(p[0] for p in pts)
        x1 = max(p[0] for p in pts)
        y0 = min(p[1] for p in pts)
        y1 = max(p[1] for p in pts)
        scale = min((width - 90) / (x1-x0), (height-90) / (y1-y0))
        def pos(x, y):
            return (45+(x-x0)*scale, height-45-(y-y0)*scale)
        polygon = [v for x,y in pts for v in pos(x,y)]
        cv.create_polygon(polygon, fill="#eff6fc", outline="#173d5d", width=2)
        for x in pad.bend_stations_x_mm:
            x_start,y_start = pos(x, 0)
            x_end,y_end = pos(x, pad.formed_height_mm)
            cv.create_line(x_start,y_start,x_end,y_end,fill="#d66a14",width=2,dash=(6,3))
        for x,y in pad.pad_unfolded_screw_centres_xy_mm:
            px,py=pos(x,y)
            r=max(2,pad.screw_diameter_mm*scale/2)
            cv.create_oval(px-r,py-r,px+r,py+r,outline="#007c8a",width=2)
        cv.create_text(
            12,12,anchor="nw",text="2D 展開草稿｜藍：輪廓  橙：折線  青：螺絲孔",
            fill="#444",
        )

    def _draw_3d(self, pad, width, height):
        cv = self.canvas
        # A U-channel schematic only: excludes tooling radii, material
        # thickness compensation, base placement and actual 3D collision.
        web = pad.centre_web_blank_mm
        rise = pad.rise_mm
        h = pad.formed_height_mm
        def project(x,y,z):
            return (x+0.46*y, 0.28*x-0.46*y-0.85*z)
        faces = (
            ([(-web/2,0,0),(-web/2,h,0),(-web/2,h,rise),(-web/2,0,rise)],"#d4e2ef"),
            ([(web/2,0,0),(web/2,h,0),(web/2,h,rise),(web/2,0,rise)],"#9dc3da"),
            ([(-web/2,0,rise),(web/2,0,rise),(web/2,h,rise),(-web/2,h,rise)],"#eef4fa"),
        )
        all_points = [project(*p) for face,_ in faces for p in face]
        xmin=min(p[0] for p in all_points);xmax=max(p[0] for p in all_points)
        ymin=min(p[1] for p in all_points);ymax=max(p[1] for p in all_points)
        scale=min((width-110)/max(1,xmax-xmin),(height-120)/max(1,ymax-ymin))
        def screen(p):
            x,y=project(*p)
            return ((width-(xmax-xmin)*scale)/2+(x-xmin)*scale,
                    (height-(ymax-ymin)*scale)/2+(y-ymin)*scale)
        for face,color in faces:
            cv.create_polygon(
                [v for p in face for v in screen(p)],
                fill=color,outline="#173d5d",width=2,
            )
        cv.create_text(
            12,12,anchor="nw",text="3D 折彎結構示意｜非真實裝配驗證",
            fill="#9b3d00",
        )

    def _export(self):
        if self.plan is None or not self.plan.jobs:
            messagebox.showwarning("無草稿", "請先計算出墊高片。")
            return
        destination = filedialog.askdirectory(title="選擇草稿 DXF 輸出位置")
        if not destination:
            return
        try:
            taipei = ZoneInfo("Asia/Taipei")
        except ZoneInfoNotFoundError:
            # Windows Python may lack the optional IANA tzdata wheel.
            taipei = timezone(timedelta(hours=8), name="Asia/Taipei")
        folder = Path(destination) / (
            "NFB_PAD_DRAFT_" + datetime.now(taipei).strftime("%Y%m%d_%H%M%S")
        )
        try:
            paths = export_draft_pad_dxf(self.plan, folder)
        except (OSError, ValueError, ImportError, FileExistsError) as exc:
            messagebox.showerror("草稿 DXF 輸出失敗", str(exc))
            return
        messagebox.showinfo(
            "草稿 DXF 已輸出",
            f"輸出 {len(paths)} 個非製造 DXF：\n{folder}\n"
            "必須回 WHD 驗證底板／裝配，才可進行正式加工。",
        )


def main():
    StandalonePadWindow().mainloop()


if __name__ == "__main__":
    main()

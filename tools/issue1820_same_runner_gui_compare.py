"""Summarize #1820 observed real WHD and CADCraft GUI sessions on one runner.

An observation report is not a choice to replace the original Hole Editor.
Never create synthetic or substituted source measurements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path


def describe(label, values):
    if len(values) != 3 or any(not isinstance(v, (int, float)) or v <= 0 for v in values):
        raise ValueError(f"INCOMPLETE_ACTUAL_GUI_MEASUREMENTS {label}: {values!r}")
    return {"each_ms": values, "median_ms": statistics.median(values),
            "min_ms": min(values), "max_ms": max(values)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    args=p.parse_args()
    root=args.root
    source=root/"source.dxf"
    if not source.is_file():
        raise FileNotFoundError(source)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    whd_first=[]
    whd_primary=[]
    cad_first=[]
    cad_control=[]
    whd_rss=[]
    cad_rss=[]
    observations=[]
    for i in range(3):
        wd=root/f"whd-{i}"
        cd=root/f"cadcraft-{i}"
        w=json.loads((wd/"whd-real-gui.json").read_text(encoding="utf-8"))
        c=json.loads((cd/"native-gui.json").read_text(encoding="utf-8"))
        if w.get("drawing_sha256")!=digest or c.get("drawing_sha256")!=digest:
            raise ValueError(f"DIFFERENT_DXF_USED_FOR_GUI_COMPARISON round {i}")
        if w.get("kind")!="REAL_WHD_PRIMARY_APP_ORIGINAL_2D_HOLE_EDITOR":
            raise ValueError("NOT_REAL_PRIMARY_WHD_EDITOR")
        if w.get("worker_exit_code")!=0 or w.get("tk_canvas_item_count",0)<5:
            raise ValueError("WHD_FIRST_FRAME_NOT_VALID")
        if c.get("kind")!="REAL_LINUX_CADCRAFT_DESKTOP_EGUI_NOT_WHD_GUI_AB":
            raise ValueError("NOT_NATIVE_CADCRAFT_GUI")
        if not (wd/"whd-real-editor-first-frame.png").is_file() or not (cd/"first-actual-desktop-frame.png").is_file():
            raise ValueError("MISSING_NATIVE_GUI_SCREENSHOT")
        if not (cd/"desktop-after-zoom.png").is_file():
            raise ValueError("MISSING_CADCRAFT_ZOOM_SCREENSHOT")
        if w.get("max_50ms_sampled_process_rss_bytes") is None or c.get("max_sampled_rss_bytes") is None:
            raise ValueError("RSS_MEASUREMENT_MISSING")
        whd_first.append(w["subprocess_spawn_to_first_painted_ms"])
        whd_primary.append(w["primary_to_editor_first_frame_ms"])
        cad_first.append(c["first_frame_wall_ms"])
        cad_control.append(c["process_spawn_to_control_ms"])
        whd_rss.append(w["max_50ms_sampled_process_rss_bytes"])
        cad_rss.append(c["max_sampled_rss_bytes"])
        observations.append({
            "trial":i,
            "sequence":("WHD first, CADCraft second" if i!=1 else "CADCraft first, WHD second"),
            "whd_first_frame_ms":whd_first[-1],
            "cadcraft_first_frame_ms":cad_first[-1],
            "whd_peak_sampled_rss_bytes":whd_rss[-1],
            "cadcraft_peak_sampled_rss_bytes":cad_rss[-1],
        })
    report={
        "kind":"SAME_LINUX_RUNNER_REAL_DESKTOP_GUI_OBSERVATION_NOT_WINDOWS_PRODUCT_COMPARISON",
        "source_dxf_sha256":digest,
        "trials":observations,
        "whd_python_process_to_original_hole_editor_first_frame":describe("whd",whd_first),
        "whd_primary_ready_to_original_hole_editor":describe("whd-editor",whd_primary),
        "cadcraft_native_process_to_actual_desktop_first_screenshot":describe("cadcraft",cad_first),
        "cadcraft_native_process_to_control_ping":describe("cadcraft-control",cad_control),
        "whd_max_50ms_sampled_process_rss_bytes":whd_rss,
        "cadcraft_max_50ms_sampled_process_rss_bytes":cad_rss,
        "limitations":[
            "Same Linux GitHub runner and same DXF, but software Xvfb/Mesa not Windows hardware.",
            "WHD opening entire production app + editor while CADCraft opening standalone viewer. User tasks and rendering engines differ.",
            "CADCraft must also pay WHD DXF preparation, temporary-file, subprocess, IPC and mode switching costs to integrate.",
            "CADCraft GUI zoom performed by engine API, not physical zoom/pan gesture; WHD editing latency and drag/pan are not matched here.",
            "Sample size 3 per option, OS caches and display startup not fully controlled.",
            "Not sufficient for an adoption or replacement decision. Original WHD 2D editor retained.",
        ],
    }
    (root/"paired-observation.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print("ISSUE1820_SAME_RUNNER_ACTUAL_GUI_EVIDENCE",digest)
    print("WHD_MEDIAN_PROCESS_TO_ORIGINAL_EDITOR_FRAME_MS",report["whd_python_process_to_original_hole_editor_first_frame"]["median_ms"])
    print("CADCRAFT_MEDIAN_PROCESS_TO_NATIVE_FIRST_FRAME_MS",report["cadcraft_native_process_to_actual_desktop_first_screenshot"]["median_ms"])
    print("NOT_WINDOWS_ADOPTION_EVIDENCE")


if __name__=="__main__":
    main()

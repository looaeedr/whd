"""#1820: observational same-DXF CADCraft CLI vs real WHD Tk 2D view.

These measurements are *not* a desktop UX A/B score. CADCraft's CLI may
rasterize to PNG while WHD Tk renders editable Canvas items, and the CADCraft
desktop GUI and pointer gestures are separate acceptance gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import threading


def _read_fixture(path: Path):
    """Read exact DXF into WHD DrawingScene, reject unsupported arc shapes."""
    import ezdxf
    from ae_engine.sheetmetal_drawing import DrawingScene
    doc = ezdxf.readfile(path)
    if doc.units != ezdxf.units.MM:
        raise ValueError("WHD_CADCRAFT_BENCH_REQUIRES_MILLIMETRES")
    scene = DrawingScene()
    counts = {}
    for e in doc.modelspace():
        kind = e.dxftype()
        layer = e.dxf.layer
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "LINE":
            scene.add_line(tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2], layer=layer)
        elif kind == "CIRCLE":
            scene.add_circle(tuple(e.dxf.center)[:2], float(e.dxf.radius), layer=layer)
        elif kind == "LWPOLYLINE":
            items = list(e.get_points("xyb"))
            if any(abs(float(z[2])) > 1e-12 for z in items):
                raise ValueError("BULGE_ARC_NOT_SUPPORTED_BY_CURRENT_WHD_VIEW_WITNESS")
            scene.add_polyline(tuple((float(x),float(y)) for x,y,_ in items), layer=layer,closed=bool(e.closed))
        else:
            # Never silently omit entities to make an incomplete drawing look fast.
            raise ValueError(f"UNSUPPORTED_DXF_SHAPE_FOR_WHD_CANVAS_BENCH: {kind}")
    if not counts:
        raise ValueError("BENCHMARK_DXF_NO_ENTITIES")
    bounds = doc.header.get("$EXTMIN"), doc.header.get("$EXTMAX")
    return scene, counts, bounds


def whd_tk_worker(source, output):
    """Invoke production HoleEditorCanvasView.render + real Tk main-thread flush."""
    import tkinter as tk
    import gui
    from ae_engine.sheetmetal_features import Vec2,feature_surface_from_rect
    from phase6_hole_editor_canvas_view import HoleEditorCanvasFrame,Phase6HoleEditorCanvasView

    scene, counts, _ = _read_fixture(source)
    # Actual source geometry under WHD rendering: no reauthored approximation.
    # The harness's example is 100 x 80 mm, includes BEND/CUTTING/CHECK.
    root = tk.Tk()
    try:
        root.title("WHD #1820 real Canvas 2D performance witness")
        root.geometry("1200x850+0+0")
        canvas = tk.Canvas(root,width=1120,height=740,bg="#101010")
        canvas.pack(fill="both",expand=True)
        root.update()
        surface = feature_surface_from_rect("cadcraft-ci-part",Vec2(0,0),Vec2(100,80))
        guide=type("BoundsGuide",(),{
            "min_point":Vec2(0,0),"max_point":Vec2(100,80),
            "width":100.0,"height":80.0,
        })()
        view=Phase6HoleEditorCanvasView(
            canvas,draw_grid=lambda widget,cw,ch: None,
            render_secondary_scene=gui.render_secondary_scene,
            render_resolved_features=gui.render_resolved_features,
            overlay_widgets={}
        )
        frame=HoleEditorCanvasFrame(
            surface=surface,features=(),width=100.0,height=80.0,
            reference_guide=guide,selected_index=-1,baseline_scene=scene
        )
        times=[]
        for _ in range(6):
            started=time.perf_counter_ns()
            view.render(frame)
            root.update()
            times.append((time.perf_counter_ns()-started)/1_000_000)
        if not canvas.find_all():
            raise RuntimeError("WHD_TK_RENDERED_EMPTY_CANVAS")
        output.write_text(json.dumps({
            "type":"WHD_REAL_HOLE_EDITOR_CANVAS_2D_SUBVIEW",
            "first_render_ms":times[0],"warm_render_ms":times[1:],
            "canvas_items":len(canvas.find_all()),
            "primitive_counts":counts,"note":"Component-level actual Tk canvas only, excludes full WHD app startup and other editing controls; no pan/zoom claim.",
        },indent=2),encoding="utf-8")
    finally:
        root.destroy()


def run_observed(argv, *, cwd=None, timeout=60):
    """Actual process wall and RSS peak, never fabricated when psutil unavailable."""
    try:
        import psutil
    except ImportError:
        psutil=None
    start=time.perf_counter_ns()
    p=subprocess.Popen(argv,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    maxima=[]
    if psutil is not None:
        try:
            monitor=psutil.Process(p.pid)
        except psutil.Error:
            monitor=None
    else:
        monitor=None
    def watch():
        if monitor is None:
            return
        while p.poll() is None:
            try:
                maxima.append(monitor.memory_info().rss)
            except psutil.Error:
                break
            time.sleep(0.02)
    thread=threading.Thread(target=watch,daemon=True)
    thread.start()
    try:
        stdout,stderr=p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        raise RuntimeError("ISSUE1820_PROCESS_TIMED_OUT: "+" ".join(map(str,argv)))
    thread.join(timeout=2)
    wall=(time.perf_counter_ns()-start)/1_000_000
    if p.returncode:
        raise RuntimeError(f"ISSUE1820_FAILED_EXIT_{p.returncode}: {argv}\n{stderr[-1800:]}")
    return {"wall_ms":wall,"max_sampled_rss_bytes":max(maxima) if maxima else None,
            "sample_count":len(maxima),"stderr_tail":stderr[-250:]}


def run_benchmark(source: Path, cli: Path, output: Path):
    output.mkdir(parents=True,exist_ok=True)
    source=source.resolve();cli=cli.resolve()
    if not source.is_file() or not cli.is_file():
        raise FileNotFoundError("the same DXF and pinned CADCraft CLI executable are required")
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    _,counts,_=_read_fixture(source)  # strict geometry / mm witness
    evidence={"source_sha256":digest,"source_bytes":source.stat().st_size,
              "entity_counts":counts,"cadcraft_cli":str(cli),"python":sys.version,
              "platform":platform.platform(),"samples":[]}
    for n in range(3):
        whd_output=output/f"whd-{n}.json"
        whd=run_observed([sys.executable,str(Path(__file__).resolve()),"tk-worker",str(source),str(whd_output)])
        cad_info=run_observed([str(cli),"info",str(source)])
        png=output/f"cadcraft-fit-{n}.png"
        cad_fit=run_observed([str(cli),"convert",str(source),str(png)])
        if not png.is_file() or png.stat().st_size==0:
            raise RuntimeError("CADCRAFT_RENDER_NOT_CREATED")
        zoom=output/f"cadcraft-detail-{n}.png"
        cad_zoom=run_observed([str(cli),"convert",str(source),str(zoom),
                               "--window","15,15,85,65"])
        if not zoom.is_file() or zoom.stat().st_size==0:
            raise RuntimeError("CADCRAFT_DETAIL_RENDER_NOT_CREATED")
        evidence["samples"].append({
            "whd_process_start_plus_render":whd,
            "whd_renderer_detail":json.loads(whd_output.read_text(encoding="utf-8")),
            "cadcraft_cli_start_plus_open_info":cad_info,
            "cadcraft_cli_start_plus_open_fit_export_png":cad_fit,
            "cadcraft_cli_start_plus_open_detail_export_png":cad_zoom,
        })
        (output/"raw.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding="utf-8")
    evidence["interpretation"]={
        "valid":"Both consume the exact SHA256-matched inspection DXF, real WHD HoleEditorCanvasView/Tk and real pinned CADCraft CLI renderer, subprocess wall timing includes startup and load.",
        "not_comparable":"CADCraft CLI image export is not CADCraft desktop first frame/pointer pan/zoom; WHD test is component-level and does not include entire WHD main app startup, while CLI exports PNG. These cannot be ranked as user-perceived GUI latency.",
        "pending":"Real native CADCraft GUI control channel first displayed frame, physical pan/zoom, Windows RSS total wait, visual full geometry parity across arcs/text/complex production drawings. No adoption decision."
    }
    (output/"raw.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding="utf-8")
    print("ISSUE1820_CROSS_ENGINE_OBSERVATION_ONLY",digest)
    print("WHD_COMPONENT_FIRST_RENDER_MS",statistics.median(x["whd_renderer_detail"]["first_render_ms"] for x in evidence["samples"]))
    print("CADCRAFT_CLI_LOAD_EXPORT_MEDIAN_MS",statistics.median(x["cadcraft_cli_start_plus_open_fit_export_png"]["wall_ms"] for x in evidence["samples"]))


def main():
    p=argparse.ArgumentParser()
    s=p.add_subparsers(dest="mode",required=True)
    worker=s.add_parser("tk-worker");worker.add_argument("source",type=Path);worker.add_argument("output",type=Path)
    bench=s.add_parser("compare");bench.add_argument("source",type=Path);bench.add_argument("cli",type=Path);bench.add_argument("output",type=Path)
    a=p.parse_args()
    if a.mode=="tk-worker":
        whd_tk_worker(a.source,a.output)
    else:
        run_benchmark(a.source,a.cli,a.output)


if __name__=="__main__":
    main()

"""#1820: time the REAL WHD primary app -> unified 2D Hole Editor first view.

This is not a fake Tk Canvas microbenchmark: use Phase6PrimaryApplication
and its actual _open_unified_hole_editor entry, existing geometry model and
DrawingScene. Separate each worker, record process start to usable canvas.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def true_whd_worker(source:Path, output_dir:Path):
    started=time.perf_counter_ns()
    import tkinter as tk
    import gui
    from PIL import ImageGrab
    from ae_engine.sheetmetal_features import (
        CircleFeature, RectFeature, FeatureAnchor, Vec2, feature_surface_from_rect,
    )
    from tools.issue1820_whd_cadcraft_dxf_benchmark import _read_fixture

    output_dir.mkdir(parents=True,exist_ok=True)
    drawing, counts, _=_read_fixture(source)
    from ae_engine.sheetmetal_drawing import DrawingScene
    baseline=DrawingScene()
    baseline.extend(tuple(p for p in drawing.primitives if p.layer != 'CHECK'))
    root=tk.Tk()
    try:
        root.geometry("1600x1000+0+0")
        root.update()
        # Production 3D entry, not the legacy BoxCalculatorGUI compatibility host.
        app=gui.Phase6PrimaryApplication(root)
        root.update()
        primary_ready_ms=(time.perf_counter_ns()-started)/1e6
        surface=feature_surface_from_rect("issue1820-actual-door",Vec2(0,0),Vec2(100,80))
        features=[
            CircleFeature(diameter=10,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                          offset=Vec2(25,30),layer="CUTTING"),
            RectFeature(width=20,height=12,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                        offset=Vec2(70,45),layer="CUTTING"),
        ]
        app._open_unified_hole_editor(
            "door","WHD 2D 開孔原視窗",surface,100.0,80.0,
            feature_list_override=features,baseline_scene=baseline,
        )
        root.update()
        # The real editor schedules its first render in after(50); wait for
        # that original callback rather than bypassing the production wiring.
        time.sleep(.085)
        root.update()
        editor=app.last_unified_hole_editor
        canvas=app.last_hole_editor_canvas
        if editor is None or canvas is None or not editor.winfo_viewable():
            raise RuntimeError("WHD_REAL_UNIFIED_2D_EDITOR_NOT_VISIBLE")
        item_count=len(canvas.find_all())
        if item_count<5:
            raise RuntimeError(f"WHD_REAL_2D_CANVAS_IS_EMPTY: {item_count}")
        first_painted_ms=(time.perf_counter_ns()-started)/1e6
        # Print marker immediately: parent measures process spawn to the
        # actual first useful frame, including interpreter/module startup.
        print("FIRST_WHD_EDITOR_FRAME_READY",flush=True)
        x,y=editor.winfo_rootx(),editor.winfo_rooty()
        w,h=editor.winfo_width(),editor.winfo_height()
        if w<100 or h<100:
            raise RuntimeError("WHD_REAL_UNIFIED_2D_EDITOR_INVALID_RECT")
        shot=output_dir/"whd-real-editor-first-frame.png"
        ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(shot)
        if not shot.is_file() or shot.stat().st_size<1000:
            raise RuntimeError("WHD_REAL_UNIFIED_2D_SCREENSHOT_MISSING")
        (output_dir/"worker.json").write_text(json.dumps({
            "kind":"REAL_WHD_PRIMARY_APP_ORIGINAL_2D_HOLE_EDITOR",
            "primary_app_ready_ms":primary_ready_ms,
            "primary_to_editor_first_frame_ms":first_painted_ms-primary_ready_ms,
            "python_start_to_editor_first_frame_ms":first_painted_ms,
            "drawing_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "dxf_entities":counts,"tk_canvas_item_count":item_count,
            "editor_rect":[x,y,w,h],
            "contains_real_existing_holes":len(features)==2,
            "baseline_scene_is_real_DXF_loaded":True,
            "comment":"Actually opened WHD Phase6PrimaryApplication and original Hole Editor. Xvfb first displayed frame, not the user's Windows session. Pan/zoom physical gesture acceptance is separate.",
        },indent=2,ensure_ascii=False),encoding="utf-8")
    finally:
        root.destroy()


def measured_worker(source:Path,dest:Path):
    import psutil
    source=source.resolve();dest=dest.resolve()
    dest.mkdir(parents=True,exist_ok=True)
    cmd=[sys.executable,str(Path(__file__).resolve()),"worker",str(source),str(dest)]
    launched=time.perf_counter_ns()
    samples=[]
    with (dest/"worker-stderr.log").open("w",encoding="utf-8") as err:
        process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err,text=True)
        handle=psutil.Process(process.pid)
        stop=threading.Event()
        descendant_samples=[]
        process_count_samples=[]
        def watch():
            # Windows venv/Scripts/python.exe can be a small redirector that
            # owns a SECOND actual Tk Python process. Sampling only the parent
            # reported ~6.8 MiB while the real renderer was still alive.
            # Include its recursively owned process tree, on both OSes.
            while not stop.is_set():
                try:
                    members=[handle,*handle.children(recursive=True)]
                    values=[]
                    for proc in members:
                        try:
                            values.append((proc.pid,proc.memory_info().rss))
                        except (psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess):
                            pass
                    if values:
                        samples.append(sum(rss for _pid,rss in values))
                        descendant_samples.append(sum(rss for pid,rss in values if pid!=handle.pid))
                        process_count_samples.append(len(values))
                except (psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess):
                    break
                stop.wait(.05)
        t=threading.Thread(target=watch,daemon=True);t.start()
        first_visible=None;stdout=[]
        # Read stdout off the supervising thread: a wedged GUI can hold its
        # pipe open forever, so a wait() placed after a blocking read is inert.
        def collect_stdout():
            nonlocal first_visible
            for line in process.stdout:
                stdout.append(line)
                if "FIRST_WHD_EDITOR_FRAME_READY" in line and first_visible is None:
                    first_visible=(time.perf_counter_ns()-launched)/1e6

        reader=threading.Thread(target=collect_stdout,daemon=True)
        reader.start()
        try:
            remaining=max(0.0,15.0-(time.perf_counter_ns()-launched)/1e9)
            reader.join(timeout=remaining)
            if reader.is_alive():
                # Terminate descendants first, including a Windows venv
                # redirector's actual Tk process, then reap the launcher.
                try:
                    descendants=handle.children(recursive=True)
                except (psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess):
                    descendants=[]
                for child in reversed(descendants):
                    try:
                        child.kill()
                    except (psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess):
                        pass
                if process.poll() is None:
                    process.kill()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
                reader.join(timeout=2)
                raise TimeoutError("WHD_REAL_EDITOR_TIMEOUT: worker stdout did not close within 15s")
            rc=process.wait(timeout=3)
        finally:
            stop.set();t.join(timeout=2)
            if process.stdout is not None:
                process.stdout.close()
        (dest/"worker-stdout.log").write_text("".join(stdout),encoding="utf-8")
        if rc!=0 or first_visible is None or not (dest/"worker.json").is_file():
            raise RuntimeError(f"WHD_REAL_EDITOR_FAILURE rc={rc} frame={first_visible}; see worker-stderr.log")
        detail=json.loads((dest/"worker.json").read_text(encoding="utf-8"))
        detail["subprocess_spawn_to_first_painted_ms"]=first_visible
        detail["max_50ms_sampled_process_rss_bytes"]=max(samples) if samples else None
        detail["rss_samples"]=len(samples)
        detail["rss_is_process_tree_not_launcher_only"]=True
        detail["max_50ms_sampled_descendant_rss_bytes"]=max(descendant_samples,default=0)
        detail["max_sampled_process_count"]=max(process_count_samples,default=0)
        detail["worker_exit_code"]=rc
        (dest/"whd-real-gui.json").write_text(json.dumps(detail,indent=2,ensure_ascii=False),encoding="utf-8")
        print("WHD_REAL_ORIGINAL_2D_FIRST_FRAME_PASS",round(first_visible,2),
              "items",detail["tk_canvas_item_count"],"rss",detail["max_50ms_sampled_process_rss_bytes"])


def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("run","worker"))
    p.add_argument("source",type=Path)
    p.add_argument("output_dir",type=Path)
    args=p.parse_args()
    if args.mode=="worker":
        true_whd_worker(args.source,args.output_dir)
    else:
        measured_worker(args.source,args.output_dir)


if __name__=="__main__":
    main()

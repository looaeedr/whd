"""#1820 actual CADCraft desktop-egui timing via its pinned native control port.

Uses the pinned release's native control protocol (current workflow: v0.8.0); no interaction with WHD project or
production DXF and no made-up timings. This is Linux Xvfb GUI evidence,
not Windows operator acceptance and not a replacement for the 2D Hole Editor.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time


def control(port, method, params=None, *, timeout=12.0):
    req={"id":1, "method":method}
    if params is not None:
        req["params"]=params
    with socket.create_connection(("127.0.0.1",int(port)),timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall((json.dumps(req,separators=(",",":"))+"\n").encode("utf-8"))
        with sock.makefile("rb") as stream:
            response=stream.readline()
    if not response:
        raise RuntimeError(f"CADCRAFT_CONTROL_NO_RESPONSE {method}")
    reply=json.loads(response)
    if not reply.get("ok"):
        raise RuntimeError(f"CADCRAFT_CONTROL_ERROR {method}: {reply.get('error')} ({reply.get('state')})")
    return reply.get("result")


def timed_request(port, method, params=None, timeout=12.0):
    start=time.perf_counter_ns()
    result=control(port,method,params,timeout=timeout)
    return (time.perf_counter_ns()-start)/1e6, result


def await_control(port, process, *, timeout=50):
    started=time.perf_counter()
    while time.perf_counter()-started < timeout:
        if process.poll() is not None:
            raise RuntimeError(f"CADCRAFT_GUI_EARLY_EXIT_{process.returncode}")
        try:
            duration,result=timed_request(port,"ping",timeout=2)
            if result=="pong":
                return {"elapsed_ms":(time.perf_counter()-started)*1000,
                        "control_roundtrip_ms":duration}
        except (OSError,TimeoutError,ValueError,RuntimeError):
            pass
        time.sleep(0.12)
    raise RuntimeError("CADCRAFT_GUI_CONTROL_NOT_READY_IN_50_SECONDS")


def native_gui_probe(gui:Path, drawing:Path, dest:Path,port:int):
    import psutil
    gui=gui.resolve();drawing=drawing.resolve();dest=dest.resolve()
    dest.mkdir(parents=True,exist_ok=True)
    if not gui.is_file() or not drawing.is_file():
        raise FileNotFoundError("CADCRAFT_NATIVE_GUI_BINARY_OR_WHD_DXF_MISSING")
    profile=dest/"cadcraft-private-profile"
    profile.mkdir(exist_ok=True)
    env=os.environ.copy()
    env["CADCRAFT_CONFIG_DIR"]=str(profile)
    env.setdefault("LIBGL_ALWAYS_SOFTWARE","1")
    result={"kind":"REAL_LINUX_CADCRAFT_DESKTOP_EGUI_NOT_WHD_GUI_AB",
            "drawing_sha256":hashlib.sha256(drawing.read_bytes()).hexdigest(),
            "gui_executable":str(gui),"port":port,"observations":[],
            "windows_uat":"NOT_RUN","whd_2d_authority":"UNCHANGED"}
    with (dest/"desktop-stdout.log").open("w",encoding="utf-8") as so, (dest/"desktop-stderr.log").open("w",encoding="utf-8") as se:
        launched=time.perf_counter_ns()
        proc=subprocess.Popen([str(gui),"--control",str(port)],stdout=so,stderr=se,env=env)
        measurements=[]
        stop=threading.Event()
        ps=psutil.Process(proc.pid)
        def watch():
            while not stop.is_set():
                try:
                    measurements.append((time.perf_counter_ns(),ps.memory_info().rss))
                except psutil.Error:
                    break
                stop.wait(.05)
        thread=threading.Thread(target=watch,daemon=True)
        thread.start()
        try:
            ready=await_control(port,proc)
            result["control_ready"]=ready
            result["process_spawn_to_control_ms"]=(time.perf_counter_ns()-launched)/1e6
            for method,params in (
                ("ui.inspect",None),
                ("app.open",{"path":str(drawing)}),
                ("drawing.inspect",{"entities":False}),
                ("ui.inspect",None),
            ):
                elapsed,data=timed_request(port,method,params,timeout=30)
                result["observations"].append({"method":method,"time_ms":elapsed,"response":data})
            # A successful desktop screenshot is evidence of a presented
            # native egui frame, unlike CADCraft CLI headless PNG export.
            shot=dest/"first-actual-desktop-frame.png"
            for attempt in range(10):
                try:
                    elapsed,data=timed_request(port,"ui.screenshot",{"path":str(shot)},timeout=20)
                    if shot.is_file() and shot.stat().st_size>100:
                        result["first_frame_wall_ms"]=(time.perf_counter_ns()-launched)/1e6
                        result["observations"].append({"method":"ui.screenshot","time_ms":elapsed,"response":data})
                        break
                except (RuntimeError,OSError):
                    if attempt==9:
                        raise
                time.sleep(.2)
            if not shot.exists() or shot.read_bytes()[:8]!=b"\x89PNG\r\n\x1a\n":
                raise RuntimeError("CADCRAFT_DESKTOP_SCREENSHOT_NOT_PRODUCED")
            # Use command registry from the ACTUAL desktop session to change
            # the current view (not an invented transform or image rescale).
            zoom_params={"command":"zoom","params":{"mode":"window","p1":[15,15],"p2":[85,65]}}
            elapsed,data=timed_request(port,"engine.execute",zoom_params,timeout=30)
            result["observations"].append({"method":"engine.execute","params":zoom_params,"time_ms":elapsed,"response":data})
            elapsed,data=timed_request(port,"ui.inspect",timeout=20)
            result["observations"].append({"method":"ui.inspect.after_zoom","time_ms":elapsed,"response":data})
            zoom_shot=dest/"desktop-after-zoom.png"
            elapsed,data=timed_request(port,"ui.screenshot",{"path":str(zoom_shot)},timeout=20)
            if not zoom_shot.exists() or zoom_shot.read_bytes()[:8]!=b"\x89PNG\r\n\x1a\n":
                raise RuntimeError("CADCRAFT_DESKTOP_AFTER_ZOOM_SCREENSHOT_MISSING")
            result["observations"].append({"method":"ui.screenshot.after_zoom","time_ms":elapsed,"response":data})
            # The view command is an actual desktop engine action, not a
            # synthetic physical mouse wheel; report that distinction.
            result["zoom_verified"]="desktop_engine_zoom_and_presented_frame; physical_mouse_gesture_not_yet_tested"
            result["drawing_integrity"]="source_read_only; no save command invoked"
        finally:
            stop.set();thread.join(timeout=2)
            result["rss_samples"]=len(measurements)
            result["max_sampled_rss_bytes"]=max((v for _,v in measurements),default=None)
            try:
                result["final_rss_bytes"]=ps.memory_info().rss
            except psutil.Error:
                result["final_rss_bytes"]=None
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait(timeout=5)
            result["app_exit_code"]=proc.returncode
            (dest/"native-gui.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print("CADCRAFT_NATIVE_DESKTOP_CONTROL_AND_FRAME_PASS",result.get("first_frame_wall_ms"),"RSS",result["max_sampled_rss_bytes"])


def main():
    p=argparse.ArgumentParser()
    p.add_argument("cadcraft_gui",type=Path)
    p.add_argument("dxf",type=Path)
    p.add_argument("result_dir",type=Path)
    p.add_argument("--port",type=int,default=19779)
    a=p.parse_args()
    native_gui_probe(a.cadcraft_gui,a.dxf,a.result_dir,a.port)


if __name__=="__main__":
    main()

"""#3415 isolated Windows-only control: native vendor DXF read in worker vs Tk.

This file is a temporary NON-MERGE diagnostic on the clean localX control PR.
It neither changes WHD production code nor weakens the existing native gate.
"""
from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path

from tools.issue1959_whd_cadcraft_command_draw import (
    demo_instructions, run_proof,
)


def _vendor_cli():
    path = Path(os.environ["CADCRAFT_CLI"])
    assert path.is_file() and path.name.casefold() == "cadcraft-cli.exe"
    return str(path)


def _prove_in_worker(directory: Path, root=None):
    cli = _vendor_cli()
    output = directory / "native-gc-worker.dxf"
    preview = directory / "native-gc-worker.png"
    results = queue.Queue(maxsize=1)

    def execute():
        try:
            print("MINIMAL_WORKER_BEFORE_VENDOR", threading.get_ident(), flush=True)
            proof = run_proof(cli, demo_instructions()[:1], output, preview)
            results.put(("ok", proof))
            print("MINIMAL_WORKER_AFTER_EZDXF", threading.get_ident(), flush=True)
        except Exception as exc:
            results.put(("err", repr(exc)))
            print("MINIMAL_WORKER_EXCEPTION", repr(exc), flush=True)

    thread = threading.Thread(target=execute, name="isolated-native-cadcraft-worker")
    print("MINIMAL_MAIN_BEFORE_THREAD", threading.get_ident(), "tk=", root is not None, flush=True)
    thread.start()
    deadline = time.monotonic() + 80
    while thread.is_alive() and time.monotonic() < deadline:
        if root is not None:
            root.update()
        time.sleep(0.01)
    thread.join(timeout=1.0)
    assert not thread.is_alive(), "MINIMAL_NATIVE_WORKER_TIMEOUT"
    kind, value = results.get_nowait()
    assert kind == "ok", value
    assert value["status"] == "PASS" and value["entity_count"] == 1
    assert output.is_file() and preview.is_file()
    print("MINIMAL_NATIVE_WORKER_GREEN", "tk=", root is not None, flush=True)


def test_native_cadcraft_worker_without_tk(tmp_path):
    print("MINIMAL_CONTROL_NO_TK_START", flush=True)
    _prove_in_worker(tmp_path)


def test_native_cadcraft_worker_with_plain_tk(tmp_path):
    print("MINIMAL_CONTROL_PLAIN_TK_START", flush=True)
    root = tk.Tk()
    try:
        root.geometry("480x320+0+0")
        root.update_idletasks()
        _prove_in_worker(tmp_path, root=root)
    finally:
        root.destroy()


def test_native_cadcraft_worker_with_real_hole_editor_shell(tmp_path):
    print("MINIMAL_CONTROL_REAL_EDITOR_START", flush=True)
    from test_issue1959_cadcraft_command_button_live_tk import _tk_shell
    root, _editor, _canvas, _session, _features, _dialogs = _tk_shell()
    try:
        _prove_in_worker(tmp_path, root=root)
    finally:
        root.destroy()



def test_real_cadcraft_bridge_worker_with_editor_but_without_button(tmp_path):
    """Same GUI bridge, same one-hole source and native CLI; only Button.invoke
    and its pending GUI lifecycle callbacks are absent.
    """
    from ae_engine.sheetmetal_features import (
        CircleFeature, FeatureAnchor, Vec2, feature_surface_from_rect,
    )
    from gui_modules.editors.cadcraft_command_preview_bridge import (
        draw_whd_commands_with_cadcraft, prepare_whd_cadcraft_commands,
    )
    from test_issue1959_cadcraft_command_button_live_tk import _tk_shell

    root, editor, _canvas, _session, features, _dialogs = _tk_shell()
    features.append(CircleFeature(
        10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40, 40)
    ))
    surface = feature_surface_from_rect(
        "1959-tk", Vec2(0, 0), Vec2(200, 200)
    )
    instructions = prepare_whd_cadcraft_commands(
        surface=surface, features=features, width=200., height=200.
    )
    assert len(instructions) == 1
    cli = _vendor_cli()
    result = queue.Queue(maxsize=1)

    def execute():
        try:
            print("MINIMAL_REAL_BRIDGE_WORKER_START", threading.get_ident(), flush=True)
            evidence = draw_whd_commands_with_cadcraft(
                instructions=instructions, executable=cli, output_dir=tmp_path,
            )
            result.put(("ok", evidence))
            print("MINIMAL_REAL_BRIDGE_WORKER_FINISH", flush=True)
        except Exception as exc:
            result.put(("error", repr(exc)))
            print("MINIMAL_REAL_BRIDGE_WORKER_ERROR", repr(exc), flush=True)

    try:
        thread = threading.Thread(target=execute, name="native-bridge-no-button")
        thread.start()
        limit = time.monotonic() + 80
        while thread.is_alive() and time.monotonic() < limit:
            root.update()
            time.sleep(0.01)
        thread.join(1)
        assert not thread.is_alive(), "REAL_BRIDGE_NO_BUTTON_TIMEOUT"
        status, output = result.get_nowait()
        assert status == "ok", output
        assert output.geometry_evidence["status"] == "PASS"
        assert output.output_dxf.is_file() and output.preview_png.is_file()
        assert editor.winfo_exists()
        print("MINIMAL_REAL_BRIDGE_WITH_EDITOR_NO_BUTTON_GREEN", flush=True)
    finally:
        root.destroy()

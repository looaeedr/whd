#!/usr/bin/env python3
"""#1816: real Receiving three-bay .p6fold save and fresh-process GUI reload.

This is not a substitute for Windows UAT, and does not clear OS file caches.
All test files are written within an isolated CI checkout.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.whd_performance_baseline import settle, button, percentile95


def bays_in(snapshot):
    layout = (snapshot or {}).get('receiving_layout') or {}
    sets = layout.get('sets') or ()
    if len(sets) != 1:
        raise AssertionError(f'expected one Receiving set, got {len(sets)}')
    bays = sets[0].get('bays') or ()
    if len(bays) != 3:
        raise AssertionError(f'expected 3 saved Receiving bays, got {len(bays)}')
    return bays


def gui_session():
    import tkinter as tk
    import gui
    root = tk.Tk()
    root.geometry('1400x900+0+0')
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    if designer is None:
        raise AssertionError('real Fold Designer was not constructed')
    designer.root.deiconify()
    designer.root.geometry('1400x900+0+0')
    settle(root, (app, designer))
    return root, app, designer


def prepare(project_path):
    import fold_designer_bridge as bridge
    from phase6_project_file import read_project
    root, app, designer = gui_session()
    try:
        designer.baseline_model_var.set('受電箱')
        settle(root, (app, designer))
        modal = bridge._phase6_open_receiving_multi_settings(designer)
        settle(root, (app, designer))
        for _ in range(2):
            button(modal._receiving_multi_rows_host, '＋連').invoke()
        modal._receiving_multi_apply(0)
        modal._receiving_multi_close()
        settle(root, (app, designer))
        # Real product save path, without OS file picker (which is not part of
        # the project's cold-load latency). Save uses committed authority.
        app._flush_phase6_authoritative_state()
        result = app.project_controller.save(
            project_path, app._compose_phase6_project_snapshot_from_main_gui)
        saved = read_project(result)
        bays_in(saved['snapshot'])
        return dict(project=str(result), source_sha256=hashlib.sha256(
            Path(result).read_bytes()).hexdigest(), saved_schema=saved['schema'])
    finally:
        root.destroy()


def measure(project_path, sample_id):
    import fold_designer_bridge as bridge
    from phase6_project_file import read_project
    saved = read_project(project_path)
    bays_in(saved['snapshot'])
    start = time.perf_counter()
    root, app, _designer = gui_session()
    initialized = time.perf_counter()
    try:
        designer = app.load_phase6_project(project_path, open_designer=True)
        if designer is None:
            raise AssertionError('load_phase6_project returned no designer')
        settle(root, (app, designer))
        loaded = time.perf_counter()
        bays_in(getattr(designer, '_phase6_input_snapshot', {}))
        scene = designer.final_scene_view
        if scene.cutting_mesh_error or not scene.last_cutting_mesh:
            raise AssertionError(scene.cutting_mesh_error or 'loaded 3D scene mesh empty')
        open_started = time.perf_counter()
        modal = bridge._phase6_open_receiving_multi_settings(designer)
        settle(root, (app, designer))
        opened = time.perf_counter()
        bays_in(getattr(designer, '_phase6_input_snapshot', {}))
        modal._receiving_multi_close()
        settle(root, (app, designer))
        if root.grab_current() is not None:
            raise AssertionError('orphan Tk grab after project cold load')
        return dict(status='ok', sample_id=sample_id,
                    cache_state='fresh_python_process_os_cache_not_cleared',
                    bays=3,
                    app_startup_ms=(initialized-start)*1000,
                    project_load_to_scene_settle_ms=(loaded-initialized)*1000,
                    first_open_multi_to_settle_ms=(opened-open_started)*1000,
                    sample_project_sha256=hashlib.sha256(
                        Path(project_path).read_bytes()).hexdigest())
    finally:
        root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--project', help='isolated .p6fold path')
    parser.add_argument('--mode', choices=('driver','prepare','cold'), default='driver')
    parser.add_argument('--sample-id', type=int, default=0)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('samples must be >= 1')
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    project = Path(args.project).resolve() if args.project else output.with_suffix('.p6fold')
    if args.mode == 'prepare':
        print(json.dumps(prepare(project), ensure_ascii=False), flush=True)
        return
    if args.mode == 'cold':
        started = time.perf_counter()
        try:
            row = measure(project, args.sample_id)
        except Exception as exc:
            row = dict(status='failed', sample_id=args.sample_id, bays=3,
                       wall_ms=(time.perf_counter()-started)*1000,
                       error=f'{type(exc).__name__}: {exc}')
        with output.open('a', encoding='utf-8') as file:
            file.write(json.dumps(row, ensure_ascii=False)+'\n')
        if row['status'] == 'failed':
            raise RuntimeError(row['error'])
        return

    import platform
    meta = dict(created_at=datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
                source_sha=subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                platform=platform.platform(), python=sys.version,
                cache_state='fresh Python per load; OS filesystem cache untouched',
                windows_uat='PENDING', samples=args.samples, workers=[])
    prepare_log = output.with_name(output.stem+'-prepare.log')
    with prepare_log.open('w', encoding='utf-8') as log:
        prepared = subprocess.run([sys.executable, __file__, '--mode','prepare',
                                   '--output',str(output),'--project',str(project)],
                                  cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=180)
    if prepared.returncode:
        raise RuntimeError(f'3-bay real UI project preparation failed: see {prepare_log}')
    meta['project_sha256'] = hashlib.sha256(project.read_bytes()).hexdigest()
    rows=[]
    journal=output.with_suffix('.jsonl')
    journal.write_text('', encoding='utf-8')
    for i in range(args.samples):
        log=output.with_name(f'{output.stem}-cold-{i}.log')
        with log.open('w', encoding='utf-8') as dest:
            proc=subprocess.run([sys.executable,__file__,'--mode','cold',
                                 '--sample-id',str(i),'--project',str(project),
                                 '--output',str(journal)],
                                cwd=ROOT,stdout=dest,stderr=subprocess.STDOUT,
                                timeout=180)
        new_rows=[json.loads(line) for line in journal.read_text(
            encoding='utf-8').splitlines()]
        rows=new_rows
        meta['workers'].append(dict(sample_id=i,returncode=proc.returncode,log=log.name))
        valid=[row for row in rows if row.get('status')=='ok']
        report={}
        for key in ('app_startup_ms','project_load_to_scene_settle_ms',
                    'first_open_multi_to_settle_ms'):
            vals=[row[key] for row in valid]
            report[key]=dict(n=len(vals),
                             median_ms=statistics.median(vals) if vals else None,
                             p95_ms=percentile95(vals) if vals else None)
        output.write_text(json.dumps(dict(metadata=meta, summary=report,
                                         rows=rows),indent=2,ensure_ascii=False),
                          encoding='utf-8')
        print(f'cold reload sample {i}: status={proc.returncode}',flush=True)
        if proc.returncode:
            raise RuntimeError(f'cold reload failed for sample {i}; see {log}')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()

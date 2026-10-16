#!/usr/bin/env python3
"""Real Tk benchmark. Observational wrappers only; never substitutes geometry.

Run from an isolated checkout with a display. Each worker is a fresh process;
OS filesystem caches are NOT cleared. JSONL is written after every operation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import importlib.metadata
import statistics
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def percentile95(values):
    return sorted(values)[max(0, math.ceil(len(values) * .95) - 1)]


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['bays'], row['operation'], row['cache_state'])].append(row)
    result = []
    for (bays, operation, cache), group in sorted(groups.items()):
        valid = [r for r in group if r['status'] == 'ok']
        times = [r['wall_ms'] for r in valid]
        result.append(dict(bays=bays, operation=operation, cache_state=cache,
                           n=len(valid), failed=len(group)-len(valid),
                           median_ms=statistics.median(times) if times else None,
                           p95_ms=percentile95(times) if times else None))
    return result


def rss_bytes():
    # psutil is optional; unsupported platforms report null, never fake zero.
    try:
        import psutil
        return psutil.Process().memory_info().rss
    except ImportError:
        if sys.platform.startswith('linux'):
            return int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
        return None


class RSSSampler:
    """Sample process RSS independently of Tk; no claiming exact high-water peak.

    The sampler never touches GUI objects. Short operations may contain zero
    periodic samples and must report null rather than fabricated zero.
    """

    def __init__(self, interval_ms=50, *, reader=rss_bytes, clock=time.perf_counter):
        if not 10 <= interval_ms <= 1000:
            raise ValueError('RSS interval must be between 10 and 1000 milliseconds')
        self.interval_ms = interval_ms
        self.reader = reader
        self.clock = clock
        self.samples = []
        self.error = None
        self._stop = threading.Event()
        self._thread = None

    def _capture(self):
        try:
            rss = self.reader()
            if rss is not None:
                self.samples.append((self.clock(), int(rss)))
        except (OSError, ValueError, RuntimeError) as exc:
            self.error = f'{type(exc).__name__}: {exc}'
            self._stop.set()

    def _loop(self):
        while not self._stop.wait(self.interval_ms / 1000):
            self._capture()

    def start(self):
        if self._thread is not None:
            raise RuntimeError('RSS sampler already started')
        self._capture()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                raise RuntimeError('RSS sampler thread did not finish')
        self._capture()

    def window(self, started, ended):
        values = [rss for ts, rss in self.samples if started <= ts <= ended]
        return dict(rss_peak_sampled_bytes=max(values) if values else None,
                    rss_samples_in_operation=len(values),
                    rss_sample_error=self.error)


def memory_trends(rows):
    """One-program RSS checkpoints; observational growth, NOT leak diagnosis."""
    by_worker = defaultdict(list)
    for row in rows:
        if (row.get('operation') == 'return_3d'
                and row.get('status') == 'ok'
                and row.get('rss_after') is not None):
            by_worker[(row['bays'], row.get('worker_sample', 0))].append(
                int(row['rss_after']))
    result = []
    for (bays, sample), rss_values in sorted(by_worker.items()):
        result.append(dict(bays=bays, worker_sample=sample,
                           completed_cycles=len(rss_values),
                           first_rss_bytes=rss_values[0],
                           last_rss_bytes=rss_values[-1],
                           delta_bytes=rss_values[-1]-rss_values[0],
                           max_checkpoint_rss_bytes=max(rss_values),
                           interpretation='same_process_observation_not_leak_proof'))
    return result


def physical_world_skin_keys(world_map):
    """Actual world-skin output keys, excluding duplicate BoxBody aggregate.

    This measures rematerialized world-coordinate surfaces per physical piece,
    NOT flat-material geometry builds, manufacturing cache misses or CNC parts.
    """
    if not isinstance(world_map, dict) or not isinstance(world_map.get('world_triangles_by_part'), dict):
        raise ValueError('world skin result lacks expected physical part evidence')
    by_part=world_map['world_triangles_by_part']
    visible={str(key) for key,triangles in by_part.items() if triangles}
    if any(key.startswith('box_body:') for key in visible):
        visible.discard('box_body')  # aggregate of physically distinct children
    return tuple(sorted(visible))


class Probe:
    def __init__(self):
        self.counts = Counter()
        self.milliseconds = Counter()
        self.parts = Counter()
        self.world_skin_parts = Counter()
        self.stack = ExitStack()

    def wrap(self, owner, name, label, part_arg=None):
        original = getattr(owner, name)
        @wraps(original)
        def measured(*args, **kwargs):
            started = time.perf_counter()
            self.counts[label] += 1
            if part_arg is not None:
                self.parts[str(args[part_arg])] += 1
            try:
                return original(*args, **kwargs)
            finally:
                self.milliseconds[label] += (time.perf_counter()-started)*1000
        self.stack.enter_context(patch.object(owner, name, measured))

    def observe_world_skin(self, owner, name):
        """Wrap the real Receiving world-coordinate materializer, no fake mesh."""
        original = getattr(owner, name)
        @wraps(original)
        def measured(*args, **kwargs):
            started = time.perf_counter()
            try:
                result = original(*args, **kwargs)
                keys = physical_world_skin_keys(result)
                self.counts['world_skin_builds'] += 1
                self.world_skin_parts.update(keys)
                return result
            finally:
                self.milliseconds['world_skin_builds'] += (time.perf_counter()-started)*1000
        self.stack.enter_context(patch.object(owner, name, measured))

    def reset(self):
        self.counts.clear()
        self.milliseconds.clear()
        self.parts.clear()
        self.world_skin_parts.clear()


def settle(root, owners, timeout=30):
    """Drain actual scheduled work, including debounce; no forced solve/draw.

    Two idle turns are needed for callbacks scheduling another idle draw. This
    measures Tk completion, not physical monitor scan-out or compositor latency.
    """
    deadline = time.perf_counter()+timeout
    idle = 0
    while time.perf_counter() < deadline:
        root.update_idletasks()
        root.update()
        busy = False
        for owner in owners:
            scheduler = getattr(owner, '_phase6_update_scheduler', None)
            busy |= bool(scheduler and (scheduler.dirty or scheduler._after_job or scheduler._flushing))
            canvas = getattr(getattr(owner, 'renderer', None), 'canvas', None)
            busy |= bool(getattr(canvas, '_idle_draw_id', None))
        idle = 0 if busy else idle+1
        if idle >= 2:
            return
        if busy:
            time.sleep(.001)
    raise TimeoutError('GUI did not settle; this sample is not a latency success')


def button(parent, text):
    todo = [parent]
    while todo:
        widget = todo.pop(0)
        try:
            if widget.cget('text') == text and hasattr(widget, 'invoke'):
                return widget
        except Exception:
            pass
        todo.extend(widget.winfo_children())
    raise LookupError(text)


def worker(args):
    import tkinter as tk
    from tkinter import messagebox
    import gui
    import fold_designer_bridge as bridge
    import ezdxf
    import phase6_manufacturing_adapter as adapter
    import phase6_manufacturing_service as service
    from phase6_final_scene_renderer import Phase6FinalSceneRenderer
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from gui_modules.application.receiving_nfb_source_preview import NfbDxfSourcePreviewPanel

    rows = []
    errors = []
    probe = Probe()
    root = tk.Tk()
    sampler = RSSSampler(args.memory_interval_ms).start()
    root.geometry('1400x900+0+0')
    root.report_callback_exception = lambda typ, value, tb: errors.append(str(value))
    def dialog(*a, **kw):
        errors.append(str(a))
    for name in ('showerror', 'showwarning', 'showinfo'):
        probe.stack.enter_context(patch.object(messagebox, name, dialog))
    try:
        app = gui.Phase6PrimaryApplication(root)
        designer = app.fold_designer_app
        designer.root.deiconify()
        designer.root.geometry('1400x900+0+0')
        owners = (app, designer)
        settle(root, owners)
        designer.baseline_model_var.set('受電箱')
        settle(root, owners)
        probe.wrap(service, 'resolve', 'manufacturing_solve')
        probe.observe_world_skin(service, '_phase6_build_joint_world_geometry')
        probe.wrap(adapter, '_domain_inputs_for_part', 'part_materialization', part_arg=1)
        probe.wrap(Phase6FinalSceneRenderer, 'render', 'scene_render')
        probe.wrap(FigureCanvasTkAgg, 'draw', 'canvas_draw')
        probe.wrap(ezdxf, 'readfile', 'dxf_readfile')
        # Executor wrappers count actual calculation dispatch, not inferred solves.
        for index, owner in enumerate(owners):
            scheduler = getattr(owner, '_phase6_update_scheduler', None)
            if scheduler and callable(scheduler.executor):
                probe.wrap(scheduler, 'executor', f'executor_{index}')

        def record(operation, action, cache='warm', validate=None):
            probe.reset()
            errors.clear()
            before = rss_bytes()
            schedulers = [getattr(o, '_phase6_update_scheduler', None) for o in owners]
            calc_before = sum(s._metrics['calculation_flushes'] for s in schedulers if s)
            started = time.perf_counter()
            elapsed_ms = None
            status, error, value = 'ok', None, None
            try:
                value = action()
                settle(root, owners)
                elapsed_ms = (time.perf_counter()-started)*1000
                if errors:
                    raise RuntimeError('; '.join(errors))
                if validate:
                    validate(value)
            except Exception as exc:
                status, error = 'failed', f'{type(exc).__name__}: {exc}'
            ended = time.perf_counter()
            rss_window = sampler.window(started, ended)
            row = dict(bays=args.bays, worker_sample=args.worker_sample,
                       operation=operation, cache_state=cache,
                       status=status, error=error, wall_ms=elapsed_ms if elapsed_ms is not None else (time.perf_counter()-started)*1000,
                       counts=dict(probe.counts), inclusive_ms=dict(probe.milliseconds),
                       materialized_parts=dict(probe.parts),
                       world_skin_physical_pieces=dict(probe.world_skin_parts),
                       world_skin_physical_rematerializations=sum(probe.world_skin_parts.values()),
                       rss_before=before,
                       rss_after=rss_bytes(), **rss_window, calculation_flushes=sum(
                           s._metrics['calculation_flushes'] for s in schedulers if s)-calc_before)
            rows.append(row)
            with Path(args.output).open('a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=False)+'\n')
            if status != 'ok':
                raise RuntimeError(error)
            return value

        def check_mesh(_=None):
            scene = designer.final_scene_view
            if scene.cutting_mesh_error or not scene.last_cutting_mesh:
                raise AssertionError(scene.cutting_mesh_error or 'empty assembly mesh')
            if designer._phase6_last_resolved_manufacturing_signature != adapter.build_manufacturing_cache_key(designer).fingerprint:
                raise AssertionError('stale manufacturing receipt')

        def open_modal():
            return bridge._phase6_open_receiving_multi_settings(designer)

        # Establish topology before measured first open for the 3-bay case.
        if args.bays > 1:
            win = open_modal()
            settle(root, owners)
            for _ in range(args.bays-1):
                button(win._receiving_multi_rows_host, '＋連').invoke()
            win._receiving_multi_apply(0)
            win._receiving_multi_close()
            settle(root, owners)
        first_state = 'first_entry' if args.bays == 1 else 'first_after_topology_setup'
        win = record('open_multi', open_modal, first_state)
        record('close_multi', win._receiving_multi_close, validate=check_mesh)
        for cycle in range(args.cycles):
            win = record('open_multi', open_modal)
            win._receiving_multi_apply(0)
            settle(root, owners)
            values = win._receiving_dimension_group_input
            width = 820 if cycle % 2 == 0 else 800
            def edit():
                for key, value in dict(width=width, height=1400, depth=350, count=1).items():
                    values[key].set(str(value))
                if win._receiving_dimension_group_confirm() is not True:
                    raise AssertionError('dimension edit rejected')
            record('edit_one_bay_in_modal', edit)
            def close_check(_):
                check_mesh()
                if float(designer._phase6_box_whd['w']) != width:
                    raise AssertionError('wrong final width')
                xs = [float(p[0]) for tri in designer.final_scene_view.last_cutting_mesh for p in tri]
                if abs(max(xs)-min(xs)-width) > .01:
                    raise AssertionError('visible assembly width differs from committed input')
            # Re-select the modified Bay; confirmation may select the next Bay.
            win._receiving_multi_apply(0)
            record('close_after_edit', win._receiving_multi_close, validate=close_check)
            for label, text in (('add_bay', '＋連'), ('remove_bay', '－連')):
                win = open_modal()
                settle(root, owners)
                def resize():
                    button(win._receiving_multi_rows_host, text).invoke()
                    win._receiving_multi_apply(0)
                    win._receiving_multi_close()
                record(label+'_apply_close', resize, validate=check_mesh)
            win = open_modal()
            win._receiving_multi_apply(0)
            settle(root, owners)
            def preview_check(popup):
                if not getattr(popup, '_receiving_real_preview_request', None):
                    raise AssertionError('2D preview not ready')
            record('open_true_2d', lambda: win._receiving_multi_show_real_preview('head'), validate=preview_check)
            def back():
                win._receiving_multi_close_real_preview()
                win._receiving_multi_close()
            record('return_3d', back, validate=check_mesh)
            if root.grab_current() is not None:
                raise AssertionError('orphan Tk grab')

        # True source DXF preview; absence is explicit, not substituted with a toy.
        if args.dxf_index:
            panel_window = tk.Toplevel(root)
            panel = NfbDxfSourcePreviewPanel(panel_window, index_path=args.dxf_index)
            settle(root, owners)
            def source_check(_):
                if not panel.viewport.preview or not panel.viewport.preview.strokes:
                    raise AssertionError(panel.reason.get())
            record('dxf_load', lambda: panel.show(args.brand, args.filename), 'first_entry', source_check)
            for _ in range(args.cycles):
                record('dxf_load', lambda: panel.show(args.brand, args.filename), validate=source_check)
                record('dxf_zoom', lambda: panel.zoom(1.02), validate=source_check)
                def pan():
                    panel._press(SimpleNamespace(x=100,y=100))
                    panel._move(SimpleNamespace(x=110,y=105))
                    panel._release()
                record('dxf_pan', pan, validate=source_check)
            panel_window.destroy()
        return rows
    finally:
        sampler.stop()
        probe.stack.close()
        root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--cycles', type=int, default=10)
    parser.add_argument('--memory-interval-ms', type=int, default=50,
                        help='RSS polling interval; sampled maximum is NOT exact peak')
    parser.add_argument('--worker-sample', type=int, default=0)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--bays', type=int, choices=(1,3), default=1)
    parser.add_argument('--dxf-index')
    parser.add_argument('--brand', default='士林')
    parser.add_argument('--filename', default='400_140X257_107.dxf')
    args = parser.parse_args()
    if min(args.samples, args.cycles) < 1:
        parser.error('samples and cycles must be positive')
    if not 10 <= args.memory_interval_ms <= 1000:
        parser.error('memory-interval-ms must be between 10 and 1000')
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.worker:
        worker(args)
        return
    metadata = dict(created_at=datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
                    source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    platform=platform.platform(), python=sys.version, cpu=platform.processor(),
                    cpu_count=os.cpu_count(), display=os.environ.get('DISPLAY'),
                    packages={name: importlib.metadata.version(name) for name in ('matplotlib','numpy','shapely','ezdxf')},
                    config_sha256=hashlib.sha256((ROOT/'config.ini').read_bytes()).hexdigest(),
                    harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    samples=args.samples, cycles=args.cycles,
                    memory_interval_ms=args.memory_interval_ms,
                    memory_peak_definition='maximum sampled RSS, not instantaneous peak',
                    cold_definition='fresh Python process; OS file cache not cleared',
                    pending=[] if args.dxf_index else ['DXF source index/path not supplied; no DXF latency claim'],
                    windows_uat='PENDING', workers=[])
    all_rows=[]
    for bays in (1,3):
        for sample in range(args.samples):
            journal=output.with_name(f'{output.stem}-b{bays}-s{sample}.jsonl')
            journal.write_text('',encoding='utf-8')
            command=[sys.executable,__file__,'--worker','--bays',str(bays),
                     '--worker-sample',str(sample),'--cycles',str(args.cycles),
                     '--memory-interval-ms',str(args.memory_interval_ms),
                     '--output',str(journal)]
            if args.dxf_index:
                command += ['--dxf-index',args.dxf_index,'--brand',args.brand,'--filename',args.filename]
            with journal.with_suffix('.log').open('w',encoding='utf-8') as log:
                run=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=900)
            all_rows.extend(json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines())
            metadata['workers'].append(dict(bays=bays,sample=sample,returncode=run.returncode,journal=journal.name))
            output.write_text(json.dumps(dict(metadata=metadata,summary=summarize(all_rows),
                                              memory_trends=memory_trends(all_rows),
                                              rows=all_rows),ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'bays={bays} sample={sample} exit={run.returncode}',flush=True)
            if run.returncode:
                raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()

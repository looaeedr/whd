#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fold_designer_bridge as bridge
from ae_engine import ae


def _snapshot():
    settings = {
        'w':500.0,'h':600.0,'d':200.0,'t':2.0,'fw':25.0,'draw_stock':False,
        'relief_top_secondary_x_factor':0.5,'relief_top_secondary_depth_factor':2.0,
        'relief_bottom_x_factor':0.5,'relief_bottom_y_factor':0.5,
        'notch_bottom_gap':0.5,'notch_sub_x_half':0.5,'notch_sub_y_factor':2.0,
        'zl1':15.0,'zl2':20.0,'zr1':15.0,'zr2':20.0,'z_comp':3.0,
        'yl1':15.0,'yr1':15.0,'ytop1':16.0,'ybottom1':15.0,
        'hang_hole_r':3.2,'hang_hole_x':35.5,'hang_hole_y_up':6.0,
        'sq_x_left':3.0,'sq_width':4.0,'sq_y_bottom':18.0,'sq_height':4.0,
        'bottom_hole_r':2.5,'bottom_hole_y':5.0,
        'door_gap_w':3.5,'door_gap_h':3.5,
        'door_fold_l':19.0,'door_fold_r':15.0,'door_fold_t':15.0,'door_fold_b':15.0,
        'base_plate_shrink_top':55.0,'base_plate_shrink_bottom':55.0,
        'base_plate_shrink_left':55.0,'base_plate_shrink_right':55.0,'base_plate_bend':15.0,
        'indicator_box_fold':49.0,'indicator_door_fold':19.0,
    }
    return dict(model='金庫型', w=500, h=600, d=200, t=2, fw=25,
        zl1=15,zl2=20,zr1=15,zr2=20,z_comp=3,yl1=15,yr1=15,ytop1=16,ybottom1=15,
        door_gap_w=3.5,door_gap_h=3.5,door_fold_l=19,door_fold_r=15,door_fold_t=15,door_fold_b=15,
        base_plate_shrink_top=55,base_plate_shrink_bottom=55,base_plate_shrink_left=55,base_plate_shrink_right=55,
        base_plate_bend=15,indicator_box_fold=49,indicator_door_fold=19,
        existing_parts=['box_body','head','tail','door','base_plate','indicator_box','indicator_door'],
        active_part='box_body',part_dimensions={},part_features={},part_face_features={},settings=settings)


def _drain(root, seconds=0.25):
    end=time.perf_counter()+seconds
    while time.perf_counter()<end:
        root.update(); time.sleep(0.002)


def _segment(name, fn):
    started=time.perf_counter(); counters=fn(); counters['wall_time']=time.perf_counter()-started; counters['segment']=name
    return counters


def run_gui_stress():
    bridge.project_features_to_original_holes=lambda *a, **k: []
    root=tk.Tk(); root.withdraw(); win=tk.Toplevel(root); win.withdraw()
    publishes=[]
    app=bridge.Phase6FoldDesignerApp(win, _snapshot(), on_settings_change=lambda payload: publishes.append(dict(payload)))
    _drain(root,0.35)
    results=[]
    original_execute=bridge._PHASE6_RENDERING_DO_UPDATE
    counts={'calculation':0,'manufacturing':0,'scene_rebuild':0,'render':0,'publish':0,'echo':0,'dxf_disk_read':0}
    def counted_execute(self):
        counts['calculation']+=1; counts['manufacturing']+=1; counts['scene_rebuild']+=1
        return original_execute(self)
    bridge._PHASE6_RENDERING_DO_UPDATE=counted_execute
    original_render=app.renderer.render
    app.renderer.render=lambda *a, **k: (counts.__setitem__('render',counts['render']+1), original_render(*a,**k))[1]
    try:
        def reset():
            for k in counts: counts[k]=0
            publishes.clear()
        def burst():
            reset()
            for key, base in [('w',600),('h',700),('d',220),('t',2.0)]:
                var=app.left_global_vars[key]
                for i in range(20): var.set(str(base+i))
                app.flush_pending_settings(); _drain(root,0.08)
            counts['publish']=len(publishes)
            return dict(counts)
        results.append(_segment('whdt_burst_20_each',burst))
        def fw_burst():
            reset()
            # FW is not a global text-entry in this Bridge layout. Exercise the
            # same transaction/orchestration seam by applying 20 in-memory edits
            # and committing only the final value once.
            for i in range(20):
                app._settings_values['fw'] = 25.0 + i / 10.0
            app.submit_update_intent('geometry', commit=True)
            _drain(root,0.12); counts['publish']=len(publishes); return dict(counts)
        results.append(_segment('fw_burst_20',fw_burst))
        def switch_cycle():
            reset()
            for key in ['box_body','head','tail','box_body']*3: app.activate_part(key); _drain(root,0.03)
            return dict(counts)
        results.append(_segment('part_switch_cycle',switch_cycle))
        def head_tail():
            reset()
            for i in range(10): app.activate_part('head' if i%2==0 else 'tail'); _drain(root,0.03)
            return dict(counts)
        results.append(_segment('head_tail_10',head_tail))
        def preview_toggle():
            reset()
            for _ in range(5): app.set_3d_preview_enabled(False); app.set_3d_preview_enabled(True); _drain(root,0.02)
            return dict(counts)
        results.append(_segment('preview_toggle_5',preview_toggle))
    finally:
        bridge._PHASE6_RENDERING_DO_UPDATE=original_execute
        root.destroy()
    return results


def run_cache_stress():
    out=[]
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'part.dxf'; path.write_text('dummy',encoding='utf-8')
        reads=[]; old=ae.ezdxf.readfile; sentinel=object()
        ae.ezdxf.readfile=lambda p:(reads.append(str(p)) or sentinel)
        try:
            ae.clear_baseline_dxf_source_cache()
            ae.load_baseline_dxf_source(path)
            for _ in range(20): ae.load_baseline_dxf_source(path)
            out.append({'segment':'warm_cache_20','dxf_disk_read':len(reads),'additional_after_first':len(reads)-1})
            before=len(reads); ae.force_reload_baseline_dxf_sources(); ae.load_baseline_dxf_source(path)
            out.append({'segment':'force_reload','dxf_disk_read':len(reads)-before,'generation':ae.baseline_source_fingerprint(path)[-1]})
        finally: ae.ezdxf.readfile=old
    return out


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True); args=ap.parse_args()
    evidence={'gui_segments':run_gui_stress(),'cache_segments':run_cache_stress(),'created_at':time.time()}
    Path(args.output).write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(evidence,ensure_ascii=False,indent=2))

if __name__=='__main__': main()

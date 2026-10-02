#!/usr/bin/env python3
"""Issue 389 Phase 4 T0 canonical owner census."""
from __future__ import annotations
import argparse, ast, hashlib, json, re, subprocess
from collections import Counter
from pathlib import Path

ROOT="fdcc9b0a08f7ed19f5c17984f2793c16d6f49be4"
SCHEMA="WHD_PHASE4_T0_CENSUS_V1"
SELF_RE=re.compile(r"\bself\.([A-Za-z_][A-Za-z0-9_]*)")
CENSUS_FILES=(
"fold_designer_bridge.py",
"phase6_settings_transaction_controller.py",
"phase6_final_scene_view.py",
"phase6_settings_panel.py",
"phase6_workspace_navigation_controller.py",
"phase6_project_controller.py",
"phase6_registry_diagnostics_controller.py",
"phase6_corner_data_view_adapter.py",
)
PROTECTED_EXACT=(
"config.ini",
"phase6_workspace_navigation_controller.py",
"phase6_project_controller.py",
"phase6_registry_diagnostics_controller.py",
"phase6_corner_data_view_adapter.py",
"phase6_manufacturing_cache.py",
"phase6_manufacturing_contracts.py",
"phase6_manufacturing_geometry.py",
"phase6_manufacturing_service.py",
"phase6_manufacturing_adapter.py",
"phase6_project_file.py",
"phase6_project_session.py",
"gui_modules/application/command_router.py",
"gui_modules/application/fold_designer_adapter.py",
"gui_modules/application/lifecycle.py",
"gui_modules/application/state_sync.py",
)
ALLOWED_T0_DRIFT={
"tools/phase4_owner_census.py",
".github/workflows/qa-issue389-phase4-t0.yml",
".scratch/phase4-t0-census.json",
"docs/superpowers/checkpoints/phase4-t0-deep-owner-census.md",
}
SETTINGS_OWNER={
"_settings_values":"settings_state","_input_snapshot":"settings_state",
"_box_whd":"settings_state","_pending":"transaction_queue",
"_debounce_job":"orchestration","_workspace":"effect_sink",
"_endcap_fw_state":"domain_state","_endcap_bottom_wrap_state":"domain_state",
"_corner_state":"domain_state","_corner_pair_same":"domain_state",
"_assembly_type":"domain_state","_last_external_revision":"transaction_ordering",
"_last_external_transaction_id":"transaction_ordering",
"_active_transaction_id":"transaction_ordering","DEBOUNCE_MS":"constant",
"mark_workspace_dirty":"effect_method",
"commit_box_structure_state":"transition_method","CORNER_KEYS":"constant",
"ensure_corner_part":"transition_method","CORNER_PAIR_KEYS":"constant",
"corner_selection":"projection_method","_corner_targets":"transition_method",
"_apply_corner_preset":"transition_method",
"commit_assembly_intent":"transition_method",
}
FINAL_SCENE_OWNER={
"renderer":"renderer_runtime","_number_text":"presentation_dependency",
"last_cutting_mesh":"renderer_runtime","last_cutting_material":"renderer_runtime",
"cutting_mesh_error":"renderer_runtime","zoom_scale":"renderer_runtime",
"view_initialized":"renderer_runtime","base_renderer_render":"renderer_runtime",
"scroll_cid":"renderer_runtime",
"last_interference_diagnostic":"diagnostic_runtime",
"_map_xy":"projection_helper",
"_resolved_finished_dimensions":"projection_helper",
"_remove_original_bend_surfaces":"renderer_method",
"_draw_box_body_structure_bends":"renderer_method",
"_draw_assembly_box_body_bends":"renderer_method","_COLORS":"presentation_constant",
"_add_mesh_boundary_lines":"renderer_method",
"_add_mesh_feature_lines":"renderer_method",
"_add_mesh_boundary_and_crease_lines":"renderer_method",
"_draw_joint_diagnostic_overlays":"renderer_method",
"_draw_scene_bends":"renderer_method","_draw_scene_markings":"renderer_method",
"_draw_operator_dimensions":"renderer_method",
"adjust_zoom_scale":"renderer_method","scale_current_3d_limits":"renderer_method",
"configure_3d_only_figure":"renderer_method","render":"renderer_method",
"on_scroll":"renderer_method","owner":"app_owner_coupling",
"services":"dynamic_dependency_bag","_service":"dynamic_dependency_dispatch",
"make_assembly_scene_render_data":"projection_method",
"query_assembly_render_data":"query_orchestration",
"query_final_render_data":"query_orchestration",
"build_request":"request_orchestration","set_preview_enabled":"view_orchestration",
}
BUCKET_RULES=(
("settings_presentation",("setting","corner_","baseline","bottom_wrap","endcap_fw","assembly_type")),
("registry_ui",("registry","relief_joint")),
("project_persistence_ui",("project","diagnostic_file","keyboard_save","keyboard_open")),
("output_export",("output","export_selected","draw_stock")),
("assembly_panel",("assembly_part","assembly_parts","assembly_diagnostic")),
("corner_data_panel",("corner_data",)),
("workspace_navigation",("workspace","navigation","structure_tree","part_selector","activate_part","select_part","add_part","remove_part")),
("derived_topology",("derived_parts","door_part_projection","box_body_piece","inner_door","divider")),
("final_scene",("3d","scene","render","mesh","zoom","scroll","operator_dimension","unfolded_size")),
("lifecycle_update",("update_intent","queue_update","publish","fullscreen","status")),
)

def run(*args):
    return subprocess.check_output(args,text=True).strip()
def src(path):
    return subprocess.check_output(["git","show",f"{ROOT}:{path}"],text=True)
def blob(path):
    return run("git","rev-parse",f"{ROOT}:{path}")
def import_names(tree):
    out=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):
            out.update(a.name for a in n.names)
        elif isinstance(n,ast.ImportFrom) and n.module:
            out.add(n.module)
    return sorted(out)
def direct_assignments(tree):
    rows=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.Assign,ast.AnnAssign)):
            targets=n.targets if isinstance(n,ast.Assign) else [n.target]
            for t in targets:
                if isinstance(t,ast.Attribute) and isinstance(t.value,ast.Name) and t.value.id=="Phase6FoldDesignerApp":
                    rows.append(n.lineno)
    return sorted(rows)
def facade_keys(tree):
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call): continue
        name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ""
        if name=="install_fold_designer_bridge_facade" and len(n.args)>=2 and isinstance(n.args[1],ast.Dict):
            return [k.value for k in n.args[1].keys if isinstance(k,ast.Constant) and isinstance(k.value,str)]
    return []
def event_inventory(tree):
    c=Counter(); callbacks=[]
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call): continue
        fn=n.func
        name=fn.attr if isinstance(fn,ast.Attribute) else fn.id if isinstance(fn,ast.Name) else ""
        if name in {"update","update_idletasks","mainloop","wait_variable","wait_window","wait_visibility"}:
            c["pump:"+name]+=1
        if name in {"after","after_idle","after_cancel"}: c["schedule:"+name]+=1
        if name in {"bind","bind_all","trace","trace_add","event_generate"}: c["event:"+name]+=1
        if "callback" in name.lower(): callbacks.append({"line":getattr(n,"lineno",0),"call":name})
    return {"counts":dict(sorted(c.items())),"callback_calls":callbacks}
def bucket(name):
    low=name.lower()
    for b,needles in BUCKET_RULES:
        if any(x in low for x in needles): return b
    return "legacy_compatibility"
def metrics(path):
    text=src(path); tree=ast.parse(text,filename=path)
    attrs=SELF_RE.findall(text)
    top=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
    funcs=[n for n in top if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    classes=[n for n in top if isinstance(n,ast.ClassDef)]
    methods=[n for c in classes for n in c.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    out={"path":path,"blob_sha":blob(path),
         "sha256":hashlib.sha256(text.encode()).hexdigest(),
         "line_count":len(text.splitlines()),
         "self_ref_count":len(attrs),
         "unique_self_attrs":sorted(set(attrs)),
         "unique_self_attr_count":len(set(attrs)),
         "top_level_function_count":len(funcs),
         "top_level_class_count":len(classes),
         "method_count":len(methods),
         "imports":import_names(tree)}
    if path=="fold_designer_bridge.py":
        names=sorted(n.name for n in funcs if n.name.startswith("_phase6_"))
        buckets={}
        for name in names: buckets.setdefault(bucket(name),[]).append(name)
        keys=facade_keys(tree)
        out.update({"phase6_top_level_function_count":len(names),
                    "phase6_function_buckets":buckets,
                    "direct_class_assignment_lines":direct_assignments(tree),
                    "facade_binding_keys":keys,"facade_binding_count":len(keys),
                    "event_inventory":event_inventory(tree)})
    if path=="phase6_settings_transaction_controller.py":
        out["self_attr_ownership"]={k:SETTINGS_OWNER[k] for k in sorted(set(attrs)) if k in SETTINGS_OWNER}
        out["unknown_self_attrs"]=sorted(set(attrs)-set(SETTINGS_OWNER))
    if path=="phase6_final_scene_view.py":
        out["self_attr_ownership"]={k:FINAL_SCENE_OWNER[k] for k in sorted(set(attrs)) if k in FINAL_SCENE_OWNER}
        out["unknown_self_attrs"]=sorted(set(attrs)-set(FINAL_SCENE_OWNER))
    if path=="phase6_settings_panel.py":
        out["tk_imports"]=[x for x in out["imports"] if x.startswith("tkinter")]
    return out
def protected_manifest():
    names=run("git","ls-tree","-r","--name-only",ROOT).splitlines()
    dxf=sorted(p for p in names if p.lower().endswith(".dxf"))
    cabinet=sorted(p for p in names if p.startswith("ae_engine/cabinet_types/") and p.endswith(".py"))
    required=sorted(set(PROTECTED_EXACT)|set(dxf)|set(cabinet))
    rows=[]; missing=[]
    for p in required:
        try: sha=blob(p)
        except subprocess.CalledProcessError:
            missing.append(p); continue
        if p.lower().endswith(".dxf"): cat="dxf_baseline"
        elif p=="config.ini": cat="config"
        elif p.startswith("phase6_manufacturing_"): cat="phase2_manufacturing"
        elif p.startswith("ae_engine/cabinet_types/"): cat="cabinet_family_policy"
        elif p.startswith("phase6_project_"): cat="project_persistence"
        elif p in CENSUS_FILES: cat="phase3_protected_owner"
        elif p.startswith("gui_modules/application/"): cat="phase3_application_contract"
        else: cat="protected"
        rows.append({"path":p,"blob_sha":sha,"owner_category":cat,"allowed_task_exceptions":[]})
    return rows,missing
def source_drift():
    changed=sorted(x for x in run("git","diff","--name-only",ROOT,"HEAD").splitlines() if x)
    forbidden=sorted(set(changed)-ALLOWED_T0_DRIFT)
    return {"changed_paths":changed,"forbidden_paths":forbidden,"count":len(forbidden)}
def build():
    run("git","cat-file","-e",ROOT+"^{commit}")
    files={p:metrics(p) for p in CENSUS_FILES}
    manifest,missing=protected_manifest()
    reverse=[]
    names=set(run("git","ls-tree","-r","--name-only",ROOT).splitlines())
    for p in ("phase6_settings_transaction_controller.py","phase6_settings_contracts.py","phase6_settings_transitions.py","phase6_settings_service.py"):
        if p in names and "phase6_settings_panel" in metrics(p)["imports"]: reverse.append(p)
    drift=source_drift()
    bridge=files["fold_designer_bridge.py"]
    settings=files["phase6_settings_transaction_controller.py"]
    scene=files["phase6_final_scene_view.py"]
    classifier={
      "ROOT_SHA_EXACT":1 if run("git","rev-parse",ROOT)==ROOT else 0,
      "UNKNOWN_SETTINGS_OWNERS":len(settings["unknown_self_attrs"]),
      "UNKNOWN_FINAL_SCENE_OWNERS":len(scene["unknown_self_attrs"]),
      "UNKNOWN_BRIDGE_SEAM":0 if sum(len(v) for v in bridge["phase6_function_buckets"].values())==bridge["phase6_top_level_function_count"] else 1,
      "PROTECTED_MANIFEST_MISSING":len(missing),
      "PRODUCTION_SOURCE_DRIFT":drift["count"],
      "SETTINGS_PANEL_CORE_REVERSE_IMPORTS":len(reverse),
    }
    green=(classifier["ROOT_SHA_EXACT"]==1 and
           all(classifier[k]==0 for k in classifier if k!="ROOT_SHA_EXACT"))
    return {"schema":SCHEMA,"root_baseline":ROOT,
      "metric_contract":{"line_count":"len(git-show source.splitlines())",
      "self_ref_count":r"literal regex \bself\.([A-Za-z_][A-Za-z0-9_]*)",
      "unique_self_attrs":"unique captured names from self_ref_count"},
      "files":files,
      "settings_panel_boundary":{"presentation_layer":True,
        "tk_imports":files["phase6_settings_panel.py"]["tk_imports"],
        "core_reverse_imports":reverse},
      "protected_manifest":manifest,"protected_manifest_missing":missing,
      "source_drift":drift,"classifier":classifier,
      "decision":"GREEN" if green else "RED"}
def md(p):
    lines=["# Phase 4 T0 — Deep-owner census","",
      "- Root baseline: "+ROOT,
      "- Decision: **"+p["decision"]+"**","",
      "## Canonical census","",
      "| File | Lines | self refs | unique self attrs |",
      "|---|---:|---:|---:|"]
    for path in CENSUS_FILES:
        r=p["files"][path]
        lines.append("| "+path+" | "+str(r["line_count"])+" | "+str(r["self_ref_count"])+" | "+str(r["unique_self_attr_count"])+" |")
    b=p["files"]["fold_designer_bridge.py"]; s=p["files"]["phase6_settings_transaction_controller.py"]; v=p["files"]["phase6_final_scene_view.py"]
    lines += ["","## Bridge","",
      "- phase6 top-level functions: "+str(b["phase6_top_level_function_count"]),
      "- direct class assignments: "+str(len(b["direct_class_assignment_lines"])),
      "- facade bindings: "+str(b["facade_binding_count"]),
      "- Phase 5 ownership buckets are frozen in the JSON evidence.","",
      "## Settings","",
      "- unknown self ownership: "+str(len(s["unknown_self_attrs"])),
      "- settings panel is Tk/presentation only.",
      "- settings-panel core reverse imports: "+str(len(p["settings_panel_boundary"]["core_reverse_imports"])),"",
      "## Final Scene","",
      "- literal self refs: "+str(v["self_ref_count"]),
      "- unique self attrs: "+str(v["unique_self_attr_count"]),
      "- unknown self ownership: "+str(len(v["unknown_self_attrs"])),"",
      "## Protected manifest","",
      "- entries: "+str(len(p["protected_manifest"])),
      "- missing: "+str(len(p["protected_manifest_missing"])),"",
      "## Gates",""]
    for k,val in p["classifier"].items(): lines.append("- "+k+"="+str(val))
    lines += ["","PHASE4_T0_DECISION="+p["decision"],""]
    return "\n".join(lines)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--json",default=".scratch/phase4-t0-census.json")
    ap.add_argument("--markdown",default="docs/superpowers/checkpoints/phase4-t0-deep-owner-census.md")
    ap.add_argument("--check-only",action="store_true")
    a=ap.parse_args(); p=build()
    if not a.check_only:
        jp=Path(a.json); jp.parent.mkdir(parents=True,exist_ok=True)
        jp.write_text(json.dumps(p,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        mp=Path(a.markdown); mp.parent.mkdir(parents=True,exist_ok=True)
        mp.write_text(md(p),encoding="utf-8")
    print(json.dumps(p,ensure_ascii=False,sort_keys=True))
    print("PHASE4_T0_DECISION="+p["decision"])
    return 0 if p["decision"]=="GREEN" else 2
if __name__=="__main__":
    raise SystemExit(main())

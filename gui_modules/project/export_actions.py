# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Project/export GUI actions for #295/T7.

This module owns only operator-facing export orchestration and indicator editor
state projection. Project persistence remains Phase6ProjectController authority;
manufacturing geometry/DXF generation remains manufacturing_api authority.
"""
import os
import shutil
import tempfile
from dataclasses import replace
from collections.abc import Mapping
from tkinter import filedialog, messagebox

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_part_adapters import door_layout_export_filename


def export_multi_door_layout_dxfs(self, folder, val, *, draw_stock=False):
    """Export one Door DXF per validated layout cell through the headless API."""
    exported = []
    context = self._manufacturing_context(draw_stock=draw_stock)
    for cell in self.get_door_layout_cells():
        filename = door_layout_export_filename(cell)
        filepath = os.path.join(folder, filename)
        self._export_authoritative_part(self._door_layout_part_spec(cell, val), filepath, context)
        exported.append(filename)
    return exported


def export_multi_door_indicator_box_parts(
    self, folder, val, *, draw_stock=False, export_box=True, export_door=True
):
    """Export each per-cell Indicator-Box assembly through the headless API."""
    exported = []
    context = self._manufacturing_context(draw_stock=draw_stock)
    for cell in self.get_door_layout_cells():
        key = self._door_layout_cell_key(cell)
        state = self._door_layout_indicator_state_for_key(key)
        if state.get("mode") != "indicator_box":
            continue
        self._validate_door_layout_indicator_fit(cell, state, val)
        layers = max(1, min(6, int(state.get("layers", 1))))
        groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
        stem = f"c{cell.column_index + 1}_r{cell.row_index + 1}"

        if export_box:
            filename = f"indicator_box_{stem}.dxf"
            spec = self._indicator_box_part_spec(
                val, groups, features=self.door_layout_indicator_box_features.get(key, [])
            )
            self._export_authoritative_part(spec, os.path.join(folder, filename), context)
            exported.append(filename)

        if export_door:
            filename = f"indicator_door_{stem}.dxf"
            spec = self._indicator_door_part_spec(
                val, groups, features=self.door_layout_indicator_door_features.get(key, [])
            )
            self._export_authoritative_part(spec, os.path.join(folder, filename), context)
            exported.append(filename)
    return exported


def _selected_export_flags(self, existing_parts, has_indicator_box):
    return {
        "box_body": bool(self.export_z_var.get() and "box_body" in existing_parts),
        "head": bool(self.export_head_var.get() and "head" in existing_parts),
        "tail": bool(self.export_tail_var.get() and "tail" in existing_parts),
        "door": bool(
            self.export_door_var.get()
            and self._phase6_logical_part_present(existing_parts, "door")
        ),
        "base_plate": bool(
            self.export_base_plate_var.get()
            and self._phase6_logical_part_present(existing_parts, "base_plate")
        ),
        "indicator_box": bool(
            self.export_ib_var.get()
            and "indicator_box" in existing_parts
            and has_indicator_box
        ),
        "indicator_door": bool(
            self.export_ib_door_var.get()
            and "indicator_door" in existing_parts
            and has_indicator_box
        ),
    }


def _validate_selected_indicator_exports(self, flags, val):
    if not (flags["door"] or flags["indicator_box"] or flags["indicator_door"]):
        return
    if self.multi_door_enabled_var.get():
        for cell in self.get_door_layout_cells():
            key = self._door_layout_cell_key(cell)
            state = self._door_layout_indicator_state_for_key(key)
            if state.get("mode") != "none":
                self._validate_door_layout_indicator_fit(cell, state, val)
    else:
        self._validate_single_door_indicator_fit(val)


def _resolved_export_intention_key(part_key):
    """Map canonical physical identity to the existing operator export intention."""
    key = str(part_key or "").strip()
    if key == "box_body" or key.startswith("box_body:"):
        return "box_body"
    if key == "head":
        return "head"
    if key == "tail":
        return "tail"
    if key == "door" or key.startswith("door_") or key.startswith("inner_door:"):
        return "door"
    if (key == "base_plate" or key.startswith("base_plate_")
            or key.startswith("base_plate:nfb_layer:")):
        return "base_plate"
    if key == "indicator_box" or key.startswith("indicator_box_"):
        return "indicator_box"
    if key == "indicator_door" or key.startswith("indicator_door_"):
        return "indicator_door"
    return None



def _has_submitted_nfb_in_current_snapshot(payload):
    """Read persisted NFB submission from nested project/quantity snapshots."""
    seen=set()
    def walk(node,depth):
        if depth>32:
            raise ValueError("NFB project export nesting exceeds safe bound")
        if isinstance(node,Mapping):
            if id(node) in seen:
                return False
            seen.add(id(node))
            if "nfb_config_submitted" in node:
                fact=node["nfb_config_submitted"]
                if type(fact) is not bool:
                    raise ValueError("NFB saved submission flag must be boolean")
                if fact:
                    return True
            return any(walk(value,depth+1) for value in node.values())
        if isinstance(node,(list,tuple)):
            if id(node) in seen:
                return False
            seen.add(id(node))
            return any(walk(value,depth+1) for value in node)
        return False
    return walk(payload,0)


def _assert_legacy_nfb_export_scope_safe(self, flags):
    """Block stale legacy door/body/base but not demonstrably independent parts.

    Submitted NFB requires current actual part+source verification; an old
    resolved geometry cannot silently replace missing NFB CUTTING. This
    guard never creates a second export authority and only protects the
    legacy GUI pipeline until the scoped partial dispatcher is wired.
    """
    affected=("door","base_plate","box_body")
    if not any(bool(flags.get(k)) for k in affected):
        return
    designer=getattr(self,"fold_designer_app",None)
    sources=(
        getattr(self,"_phase6_input_snapshot",None),
        getattr(designer,"_phase6_input_snapshot",None),
    )
    workspace=getattr(designer,"designer_workspace",None)
    other=()
    if workspace is not None:
        snapshot=getattr(workspace,"snapshot",None)
        if callable(snapshot):
            other=(snapshot(),)
    if any(_has_submitted_nfb_in_current_snapshot(source)
           for source in (*sources,*other)):
        raise ValueError(
            "已提交 NFB：舊式內門／箱身／底板 DXF 無法證明 NFB 孔位，"
            "不得忽略 NFB 配置直接完整出圖；須使用逐板件來源驗證"
        )

def _selected_resolved_geometry(resolved_geometry, flags):
    """Filter presence by export intention without inventing a physical-part list."""
    selected = tuple(
        part
        for part in tuple(getattr(resolved_geometry, "parts", ()) or ())
        if bool(flags.get(_resolved_export_intention_key(part.part_key), False))
    )
    return replace(resolved_geometry, parts=selected)


def _export_selected_resolved_parts(self, folder, flags):
    """Export the primary GUI's canonical resolved physical inventory when available."""
    designer = getattr(self, "fold_designer_app", None)
    resolver = getattr(designer, "_phase6_resolve_manufacturing_geometry", None)
    if not callable(resolver):
        _assert_legacy_nfb_export_scope_safe(self, flags)
        return None

    workspace = getattr(designer, "designer_workspace", None)
    from phase6_quantity_model import normalize_quantity_snapshot
    # Family switches may retain a workspace quantity seed. The canonical
    # input's existing migration rule owns legacy Receiving mode selection.
    mode_source = dict(getattr(designer, "_phase6_input_snapshot", {}) or {})
    active_mode = normalize_quantity_snapshot(mode_source)["active_mode"]
    if workspace is not None and active_mode == "quantity":
        from phase6_manufacturing_adapter import (
            build_manufacturing_request, build_scene_payload_for_app,
            operator_finished_dimensions_for_app,
        )
        from phase6_quantity_manufacturing import (
            resolve_quantity_manufacturing, quantity_manufacturing_groups,
            quantity_nfb_checked_manufacturing_groups,
        )
        request = build_manufacturing_request(
            designer,
            scene_payload_builder=lambda key: build_scene_payload_for_app(designer, key),
            render_data_provider=designer._scene_query_callback,
            part_spec_provider=designer._part_spec_query_callback,
            finished_dimensions_provider=lambda key=None: operator_finished_dimensions_for_app(designer, key),
        )
        workspace_snapshot = workspace.snapshot()
        quantity = workspace_snapshot.get("quantity") or {}
        input_quantity = mode_source.get("quantity") or {}
        def submitted_facts(payload):
            return {row["version_id"]: row.get("nfb_config")
                    for row in payload.get("versions", ())
                    if row.get("nfb_config_submitted") is True}
        if submitted_facts(input_quantity) != submitted_facts(quantity):
            raise ValueError("NFB 數量版本與目前工作狀態不一致，請重新套用後再出圖")
        batch = resolve_quantity_manufacturing(request, workspace_snapshot)
        nfb_selection = None
        if any(row.get("nfb_config_submitted") is True
               for row in quantity.get("versions", ())):
            from gui_modules.application.receiving_nfb_quantity_partial import (
                select_quantity_nfb_partial, QuantityNfbPartialSelection,
                quantity_partial_live_manifests,
            )
            full = select_quantity_nfb_partial(batch, workspace_snapshot)
            selected_reports = tuple(row for row in full.rows
                if row["source_part_id"].startswith("custom:")
                or bool(flags.get(_resolved_export_intention_key(row["source_part_id"]), False)))
            selected_keys = {(row["version_id"], row["part_id"]) for row in selected_reports}
            nfb_selection = QuantityNfbPartialSelection(tuple(d for d in full.demands
                if (d.version_id, d.physical_id) in selected_keys), selected_reports)
        selected_demands = tuple(
            row for row in (nfb_selection.demands if nfb_selection else batch.demands)
            if row.source_part_id.startswith("custom:")
            or bool(flags.get(_resolved_export_intention_key(row.source_part_id), False))
        )
        if not selected_demands:
            if nfb_selection is not None:
                self._phase6_nfb_partial_export_report = nfb_selection.report()
                diagnostics = [
                    f"{row['version_id']} / {row['part_id']}：受阻 {row['actual_count']} 片；"
                    + ", ".join(
                        f"{source['physical_hole_id']} / {source['source_brand']} / "
                        f"{source['model_filename']} / datum {source['datum_revision']}"
                        for source in row["source_dependencies"])
                    + "；" + row["reason"]
                    for row in nfb_selection.rows
                ]
                return ([], [f"NFB 選中板件全數受阻（共 {nfb_selection.held_piece_count} 片），未輸出檔案。",
                             *diagnostics])
            return ([], ["canonical quantity export: no selected physical parts"])
        if nfb_selection is not None:
            selected_versions = {row["version_id"] for row in selected_reports}
            updated = {(d.version_id, d.physical_id): d for d in full.demands}
            checked_batch = replace(
                batch,
                versions=tuple(v for v in batch.versions if v.version_id in selected_versions),
                requests=tuple(r for r in batch.requests if r[0] in selected_versions),
                demands=tuple(updated.get((d.version_id, d.physical_id), d)
                              for d in batch.demands
                              if (d.version_id, d.physical_id) in selected_keys),
            )
            live_manifests = quantity_partial_live_manifests(
                full, workspace_snapshot, selected_reports)
            groups, gate = quantity_nfb_checked_manufacturing_groups(
                checked_batch, live_manifest_provider=lambda vid, _request: live_manifests[vid],
                partial=True,
            )
            if gate.permitted_total_pieces != nfb_selection.exported_piece_count:
                raise ValueError("NFB live manifest and selected physical pieces disagree")
        else:
            groups = quantity_manufacturing_groups(batch, demands=selected_demands)
        if sum(group.quantity for group in groups) != sum(row.quantity for row in selected_demands):
            raise ValueError("NFB CHECK actual piece count not conserved")
        outputs = manufacturing_api.save_quantity_manufacturing_groups_dxf(
            groups, folder, overwrite=True,
        )
        names = [os.path.basename(path) for path in outputs.values()]
        if nfb_selection is not None:
            import json
            from pathlib import Path
            report = nfb_selection.report()
            report["outputs"] = names
            report_name = "nfb_partial_manifest.json"
            Path(folder, report_name).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            names.append(report_name)
            self._phase6_nfb_partial_export_report = report
        return (names, [])

    # #1503: the original selected-DXF action applies authenticated EAR
    # positioning marks to LEFT/RIGHT physical side plates automatically.
    # No extra operator button or forged cabinet/PAD release.
    receiving_snapshot = dict(getattr(designer, "_phase6_input_snapshot", {}) or {})
    auto_side = (
        bool(flags.get("box_body"))
        and receiving_snapshot.get("model") == "受電箱"
        and receiving_snapshot.get("nfb_config_submitted") is True
    )
    committed_csv = ()
    if (receiving_snapshot.get("model") == "受電箱"
            and receiving_snapshot.get("nfb_config_submitted") is True):
        from ae_engine.receiving_nfb_committed_final_scene import (
            _submitted_csv_holes,
        )
        committed_csv = _submitted_csv_holes(receiving_snapshot)
    if auto_side:
        if receiving_snapshot.get("active_mode") == "quantity":
            raise ValueError("EAR_SIDE_NORMAL_EXPORT_QUANTITY_NOT_VERIFIED")
        # For current CSV, the SAME atomic exporter independently proves the
        # real door, both tier bases, signed formed EARs and side marks. The
        # obsolete old-supplier-DXF gate must NOT preempt that proof.
        if not committed_csv:
            _assert_legacy_nfb_export_scope_safe(self, {**flags, "box_body": False})
    elif committed_csv and bool(flags.get("door") or flags.get("base_plate")):
        # Individual CSV sheets use the same current source proof path and
        # must not be routed back to the obsolete DXF-only legacy guard.
        pass
    else:
        _assert_legacy_nfb_export_scope_safe(self, flags)
    resolved = resolver()
    if auto_side:
        from ae_engine.receiving_ear_side_manufacturing_marking import (
            with_verified_receiving_ear_side_markings,
        )
        dimensions = tuple(
            float(receiving_snapshot[key]) for key in ("w", "h", "d")
        )
        sheet_thickness = float(receiving_snapshot["t"])
        unmarked = resolved
        resolved = with_verified_receiving_ear_side_markings(
            receiving_snapshot, unmarked,
            dimensions=dimensions, sheet_thickness=sheet_thickness,
        )
    selected = _selected_resolved_geometry(resolved, flags)
    if not tuple(getattr(selected, "parts", ()) or ()):
        return ([], ["canonical resolved export: no selected physical parts"])

    # Current submitted Receiving Base Plates own physical fixing sheets.
    # Validate real signed folds / side weld contact before committing those
    # source CUTTING/BEND sheets WITH the ordinary SIDE MARKING in one batch.
    # Historical side-only scenes without an installed base stay compatible.
    physical_base_present = auto_side and any(
        str(getattr(part, "part_key", "")) == "base_plate"
        or str(getattr(part, "part_key", "")).startswith("base_plate:nfb_layer:")
        for part in tuple(getattr(unmarked, "parts", ()) or ())
    )
    if physical_base_present:
        from ae_engine.receiving_fixed_plate_formed_manufacturing import (
            save_verified_receiving_formed_fixing_plate_bundle,
        )
        bundle = save_verified_receiving_formed_fixing_plate_bundle(
            receiving_snapshot, unmarked, selected, folder,
            dimensions=dimensions, sheet_thickness=sheet_thickness,
            overwrite=True,
        )
        outputs = dict(bundle.output_paths)
    elif committed_csv and bool(flags.get("door") or flags.get("base_plate")):
        from ae_engine.receiving_fixed_plate_formed_manufacturing import (
            save_verified_receiving_csv_selected_sheets,
        )
        outputs = save_verified_receiving_csv_selected_sheets(
            receiving_snapshot, resolved, selected, folder,
            overwrite=True,
        )
    else:
        outputs = manufacturing_api.save_resolved_manufacturing_geometry_dxf(
            selected, folder, overwrite=True,
        )
    if auto_side:
        # Independently reopen the actual serialized SIDE drawings and compare
        # every source-world-derived MARKING coordinate before the outer
        # selected-DXF batch can be committed to the operator's folder.
        from ae_engine.receiving_fixed_plate_side_check_dxf import (
            _verified_pair, _readback_marking_lines,
        )
        from ae_engine.manufacturing_scene_access import owner_render_data
        from ae_engine.manufacturing_api import verify_saved_part_render_data_dxf
        receipts, _, _, _ = _verified_pair(
            receiving_snapshot, unmarked,
            dimensions=dimensions, sheet_thickness=sheet_thickness,
        )
        for side in ("box_body:left_side", "box_body:right_side"):
            physical = owner_render_data(resolved, side)
            # Resolve the actual canonical physical row by its immutable
            # render-data identity, not by a fabricated part_id/filename:
            # BoxBody composite role keys are e.g. box_body:box_body_left_side.
            from ae_engine.manufacturing_export import (
                resolved_physical_render_parts,
            )
            matching_keys = tuple(
                part_id for part_id, render_data
                in resolved_physical_render_parts(selected)
                if render_data is physical and part_id.startswith("box_body:")
            )
            if physical is None or len(matching_keys) != 1:
                raise ValueError("EAR_SIDE_NORMAL_EXPORT_SIDE_OWNER_AMBIGUOUS")
            target = outputs.get(matching_keys[0])
            if not target:
                raise ValueError("EAR_SIDE_NORMAL_EXPORT_SIDE_OUTPUT_MISSING")
            if not verify_saved_part_render_data_dxf(physical, target).ok:
                raise ValueError("EAR_SIDE_NORMAL_EXPORT_SAVED_DXF_INVALID")
            _readback_marking_lines(
                target, (
                    segment
                    for row in receipts if row.side_piece_id == side
                    for segment in row.marking_segments
                ),
            )
    return ([os.path.basename(path) for path in outputs.values()], [])


def _export_selected_parts(self, folder, val, flags, draw_stock):
    # Primary Phase6 UI already owns one canonical ResolvedManufacturingGeometry.
    # Export its physical inventory directly; logical checkboxes only filter
    # operator intention and never become a second physical-part authority.
    self._phase6_nfb_partial_export_report = None
    try:
        canonical = _export_selected_resolved_parts(self, folder, flags)
    except Exception as ex:
        return [], [f"canonical resolved export: {ex}"]
    if canonical is not None:
        return canonical

    # Legacy compatibility callers without an attached Phase6 designer retain
    # the historical PartSpec export path.
    context = self._manufacturing_context(draw_stock=draw_stock)
    exported = []
    errors = []

    def run_part(filename, spec):
        fp = os.path.join(folder, filename)
        result = self._export_authoritative_part(spec, fp, context)
        if isinstance(result, tuple):
            exported.extend(os.path.basename(item.output_path) for item in result)
        else:
            exported.append(filename)

    if flags["box_body"]:
        try:
            run_part("box_body_z.dxf", self._box_body_part_spec(val))
        except Exception as ex:
            errors.append(f"box_body_z.dxf: {ex}")

    if flags["head"]:
        try:
            run_part("end_cap_head.dxf", self._end_cap_part_spec(val, is_tail=False))
        except Exception as ex:
            errors.append(f"end_cap_head.dxf: {ex}")

    if flags["tail"]:
        try:
            run_part("end_cap_tail.dxf", self._end_cap_part_spec(val, is_tail=True))
        except Exception as ex:
            errors.append(f"end_cap_tail.dxf: {ex}")

    indicator_hole = None
    if self.is_indicator_box_var.get():
        try:
            layers = int(self.indicator_l_var.get())
            groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
            indicator_hole = manufacturing_api.indicator_box_opening_size(
                groups, thickness=val["t"]
            )
        except Exception:
            pass

    if flags["door"]:
        try:
            if self.multi_door_enabled_var.get():
                exported.extend(
                    self.export_multi_door_layout_dxfs(folder, val, draw_stock=draw_stock)
                )
            else:
                door_indicator = None
                if self.is_door_indicator_var.get():
                    try:
                        layers = int(self.door_indicator_l_var.get())
                        door_indicator = tuple(
                            int(self.door_indicator_layer_g_vars[i].get())
                            for i in range(layers)
                        )
                    except Exception:
                        pass
                run_part(
                    "door_unfold.dxf",
                    self._single_door_part_spec(
                        val,
                        indicator_hole=indicator_hole,
                        door_indicator=door_indicator,
                    ),
                )
        except Exception as ex:
            target = (
                "multi-door layout"
                if self.multi_door_enabled_var.get()
                else "door_unfold.dxf"
            )
            errors.append(f"{target}: {ex}")

    if flags["base_plate"]:
        try:
            run_part("base_plate.dxf", self._base_plate_part_spec(val))
        except Exception as ex:
            errors.append(f"base_plate.dxf: {ex}")

    if self.multi_door_enabled_var.get() and (
        flags["indicator_box"] or flags["indicator_door"]
    ):
        try:
            exported.extend(
                self.export_multi_door_indicator_box_parts(
                    folder,
                    val,
                    draw_stock=draw_stock,
                    export_box=flags["indicator_box"],
                    export_door=flags["indicator_door"],
                )
            )
        except Exception as ex:
            errors.append(f"multi-door indicator box parts: {ex}")

    if flags["indicator_box"] and not self.multi_door_enabled_var.get():
        try:
            layers = int(self.indicator_l_var.get())
            groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
            run_part(
                "indicator_box.dxf",
                self._indicator_box_part_spec(
                    val,
                    groups,
                    features=self.surface_features["indicator_box"],
                ),
            )
        except Exception as ex:
            errors.append(f"indicator_box.dxf: {ex}")

    if flags["indicator_door"] and not self.multi_door_enabled_var.get():
        try:
            layers = int(self.indicator_l_var.get())
            groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
            run_part(
                "indicator_door.dxf",
                self._indicator_door_part_spec(
                    val,
                    groups,
                    features=self.surface_features["indicator_door"],
                ),
            )
        except Exception as ex:
            errors.append(f"indicator_door.dxf: {ex}")

    return exported, errors




def _commit_staged_project_export(stage_folder, output_folder):
    """Commit one already-successful export batch with rollback on move failure."""
    stage_root = os.path.abspath(stage_folder)
    output_root = os.path.abspath(output_folder)
    entries = [
        name for name in sorted(os.listdir(stage_root))
        if os.path.isfile(os.path.join(stage_root, name))
    ]
    backup_root = tempfile.mkdtemp(prefix=".whd-export-backup-", dir=output_root)
    committed = []
    backups = {}
    try:
        for name in entries:
            destination = os.path.join(output_root, name)
            if os.path.exists(destination):
                backup = os.path.join(backup_root, name)
                os.replace(destination, backup)
                backups[destination] = backup
        for name in entries:
            source = os.path.join(stage_root, name)
            destination = os.path.join(output_root, name)
            os.replace(source, destination)
            committed.append(destination)
        return tuple(os.path.basename(path) for path in committed)
    except Exception:
        for destination in reversed(committed):
            try:
                os.remove(destination)
            except FileNotFoundError:
                pass
        for destination, backup in backups.items():
            if os.path.exists(backup):
                os.replace(backup, destination)
        raise
    finally:
        shutil.rmtree(backup_root, ignore_errors=True)

def export_receiving_ear_side_manufacturing_dxf(self):
    """#1503: signed geometry-only production MARKING for TWO side sheets.

    Normal full cabinet manufacturing, unverified PAD/EAR parts and NC remain
    blocked by the existing export. Only physical LEFT/RIGHT side DXFs get
    the genuine 3D-contact-derived, backprojected MARKING coordinates.
    """
    try:
        self._flush_phase6_authoritative_state()
        designer = getattr(self, "fold_designer_app", None)
        resolver = getattr(designer, "_phase6_resolve_manufacturing_geometry", None)
        if not callable(resolver):
            raise ValueError("側板正式 MARKING 缺少現行製造幾何")
        snapshot = dict(getattr(designer, "_phase6_input_snapshot", {}) or {})
        if (snapshot.get("model") != "受電箱"
                or snapshot.get("nfb_config_submitted") is not True
                or snapshot.get("active_mode") == "quantity"):
            raise ValueError("側板製造 MARKING 限已提交的單只／套連實體，數量版本須逐版核對")
        dimensions = tuple(float(snapshot[key]) for key in ("w", "h", "d"))
        thickness = float(snapshot["t"])
        # Contact, folded source and side material must all agree; W800
        # is a reference value, not a mandatory cabinet width.
        if dimensions[0] <= 0 or thickness <= 0:
            raise ValueError("側板 MARKING 箱寬與側板厚度必須為正")
        geometry = resolver()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        messagebox.showerror("固定片側板 MARKING 不可輸出", str(exc))
        return None

    folder = filedialog.askdirectory(
        title="選擇左右側板正式 MARKING DXF 資料夾（僅側板，非整箱）",
    )
    if not folder:
        return None
    try:
        from ae_engine.receiving_ear_side_manufacturing_marking import (
            export_receiving_ear_side_manufacturing_marking_dxf,
        )
        receipt = export_receiving_ear_side_manufacturing_marking_dxf(
            snapshot, geometry, folder, dimensions=dimensions,
            sheet_thickness=thickness, overwrite=False,
        )
    except (ValueError, FileExistsError, OSError, TypeError) as exc:
        messagebox.showerror(
            "側板製造 MARKING 驗證失敗",
            str(exc) + "\n任一側板驗證失敗，整組側板 DXF 不發布。",
        )
        return None
    messagebox.showinfo(
        "左右側板正式 MARKING DXF 已驗證（僅側板）",
        "已驗證來源物理貼合、展開 UV、MARKING 及 DXF 回讀。"
        "\n僅左右側板正式製造圖；整箱、EAR 獨立件、PAD 和焊接工藝不因此放行。"
        f"\nEAR 接觸片數：{len(receipt.physical_ear_ids)}"
        f"\nMARKING：{receipt.marking_lines_verified} 線"
        + "\n" + "\n".join(path for _side, path in receipt.output_paths),
    )
    return receipt


def export_receiving_ear_side_check_dxf(self):
    """Source-backed SIDE contact CHECK-only export, not production DXF."""
    try:
        self._flush_phase6_authoritative_state()
        designer = getattr(self, "fold_designer_app", None)
        resolver = getattr(designer, "_phase6_resolve_manufacturing_geometry", None)
        if not callable(resolver):
            raise ValueError("固定片側板 CHECK 缺少現行製造幾何")
        snapshot = dict(getattr(designer, "_phase6_input_snapshot", {}) or {})
        if (snapshot.get("model") != "受電箱"
                or snapshot.get("nfb_config_submitted") is not True
                or snapshot.get("active_mode") == "quantity"):
            raise ValueError("固定片 CHECK 限受電箱已提交的單只／套連實體；數量版本須逐版驗證")
        dimensions = tuple(float(snapshot[key]) for key in ("w", "h", "d"))
        thickness = float(snapshot["t"])
        if dimensions[0] <= 0 or thickness <= 0:
            raise ValueError("固定片側板 CHECK 箱寬與側板厚度必須為正")
        geometry = resolver()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        messagebox.showerror("固定片 CHECK 不可用", str(exc))
        return None

    folder = filedialog.askdirectory(
        title="選擇固定片側板 CHECK 專用資料夾（非製造）",
    )
    if not folder:
        return None

    try:
        from ae_engine.receiving_fixed_plate_side_check_dxf import (
            export_receiving_ear_side_check_only_dxf,
        )
        receipt = export_receiving_ear_side_check_only_dxf(
            snapshot, geometry, folder,
            dimensions=dimensions, sheet_thickness=thickness,
            overwrite=False,
        )
    except (ValueError, FileExistsError, OSError, TypeError) as exc:
        messagebox.showerror(
            "固定片側板 CHECK 未通過",
            str(exc) + "\n未放行正式製造 DXF。",
        )
        return None

    messagebox.showinfo(
        "固定片側板 CHECK 輸出成功（非製造）",
        "左右側板 CHECK 專用 DXF 已逐檔回讀驗證。"
        "\n此檔案不可作為焊道或正式製造放行。"
        f"\n接觸片數：{len(receipt.part_ids)}"
        f"\nMARKING 線段：{receipt.marking_lines_verified}"
        + "\n" + "\n".join(path for _owner, path in receipt.output_paths),
    )
    return receipt


def _is_unconfigured_receiving_base_export_error(errors):
    """Match only the explicit missing-plate-pattern guard, never arbitrary DXF failures."""
    return tuple(str(error) for error in errors) == (
        "canonical resolved export: "
        "RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING: base_plate",
    )


def export_selected_dxf(self):
    """Batch export selected existing parts through authoritative manufacturing APIs."""
    self._flush_phase6_authoritative_state()
    existing_parts = self._phase6_current_existing_parts()
    flags = _selected_export_flags(self, existing_parts, self._has_any_indicator_box())
    if not any(flags.values()):
        messagebox.showwarning("未選擇零件", "請至少勾選一個要輸出的零件。")
        return

    try:
        val = self.get_float_values()
    except ValueError as ex:
        messagebox.showerror("輸入錯誤", str(ex))
        return

    try:
        _validate_selected_indicator_exports(self, flags, val)
    except ValueError as ex:
        messagebox.showerror("指示燈配置無法套用", str(ex))
        return

    folder = filedialog.askdirectory(title="選擇 DXF 檔案儲存資料夾")
    if not folder:
        return

    # T-012 project-batch atomicity: serialize every requested file into an
    # isolated staging directory first. Any validation/serialization failure
    # leaves the operator-selected destination untouched.
    skipped_unconfigured_base = False
    with tempfile.TemporaryDirectory(prefix=".whd-export-stage-", dir=folder) as stage_folder:
        exported, errors = _export_selected_parts(
            self, stage_folder, val, flags, bool(self.draw_stock_var.get())
        )
        if flags.get("base_plate", False) and _is_unconfigured_receiving_base_export_error(errors):
            other_flags = {**flags, "base_plate": False}
            if not any(other_flags.values()):
                errors = [
                    "受電箱底板尚未設定實體板型與尺寸。"
                    "請到「底板」設定選擇左／中／右板型、填妥尺寸並套用，再輸出。"
                ]
            elif not messagebox.askyesno(
                "受電箱底板尚未配置",
                "選取的受電箱底板尚未設定實體板型與尺寸，不能製造 DXF。\n\n"
                "是否只輸出其餘已選取、通過驗證的板件？\n"
                "底板不會輸出，這不是整箱製造完成。",
                default="no",
            ):
                return
            else:
                # Re-run through the same manufacturing authority with only
                # the explicitly excluded base plate removed from selection.
                # Other source/provenance failures must continue to block.
                exported, errors = _export_selected_parts(
                    self, stage_folder, val, other_flags, bool(self.draw_stock_var.get())
                )
                skipped_unconfigured_base = bool(exported) and not errors
        if errors:
            messagebox.showerror("輸出失敗", "\n".join(errors))
            return
        if not exported:
            messagebox.showerror("輸出失敗", "沒有產生任何 DXF 檔案。")
            return
        partial_report = getattr(self, "_phase6_nfb_partial_export_report", None)
        if partial_report is not None:
            details = "\n".join(
                f"{row['version_id']} / {row['part_id']}：{row['status']}，"
                f"{row['actual_count']} 片" + (f"（{row['reason']}）" if row['reason'] else "")
                for row in partial_report["rows"])
            if not messagebox.askyesno(
                    "NFB 僅部分匯出",
                    f"可出 {partial_report['actual_export_count']} 片；"
                    f"受阻 {partial_report['held_actual_count']} 片。\n"
                    "此批不是整套完成；PAD／耳朵裝配尚未驗收。\n\n"
                    + details + "\n\n是否匯出以上合法板件與清單？"):
                return
        try:
            committed = _commit_staged_project_export(stage_folder, folder)
        except Exception as ex:
            messagebox.showerror("輸出失敗", f"批次提交失敗：{ex}")
            return

    messagebox.showinfo(
        ("部分 DXF 輸出完成" if skipped_unconfigured_base
         else "NFB 部分匯出完成" if partial_report is not None else "輸出成功"),
        ("受電箱底板尚未配置，已排除底板；僅輸出其他已驗證板件，並非整箱完成。\n"
         if skipped_unconfigured_base else "")
        + ("僅完成已驗證板件，整套尚未完成。\n" if partial_report is not None else "")
        + f"已成功輸出 {len(committed)} 個檔案至：\n{folder}\n\n"
        + "\n".join(f"  • {name}" for name in committed),
    )


def _single_door_indicator_state_snapshot(self):
    if self.is_indicator_box_var.get():
        mode = "indicator_box"
        layer_var = self.indicator_l_var
        group_vars = self.indicator_layer_g_vars
    else:
        mode = "indicator" if self.is_door_indicator_var.get() else "none"
        layer_var = self.door_indicator_l_var
        group_vars = self.door_indicator_layer_g_vars
    try:
        layers = max(1, min(6, int(layer_var.get())))
    except ValueError:
        layers = 1
    groups = []
    for index in range(6):
        try:
            groups.append(int(group_vars[index].get()))
        except ValueError:
            groups.append(2)
    return self._normalize_door_indicator_state({
        "mode": mode,
        "layers": layers,
        "groups": groups,
        "offset_x": float(self.door_indicator_offset_x),
        "offset_y": float(self.door_indicator_offset_y),
        "is_box_dist": bool(self.is_box_dist_var.get()),
    })


def _apply_single_door_indicator_state(self, state):
    state = self._normalize_door_indicator_state(state)
    mode = state["mode"]
    self.is_door_indicator_var.set(mode == "indicator")
    self.is_indicator_box_var.set(mode == "indicator_box")
    layers = state["layers"]
    groups = state["groups"]
    self.door_indicator_l_var.set(str(layers))
    self.indicator_l_var.set(str(layers))
    for index in range(6):
        self.door_indicator_layer_g_vars[index].set(str(int(groups[index])))
        self.indicator_layer_g_vars[index].set(str(int(groups[index])))
    self.door_indicator_offset_x = float(state.get("offset_x", 0.0))
    self.door_indicator_offset_y = float(state.get("offset_y", 0.0))
    self.is_box_dist_var.set(bool(state.get("is_box_dist", False)))
    self._request_phase6_update("geometry")


def _apply_multi_door_indicator_state(self, key, state):
    normalized = self._normalize_door_indicator_state(state)
    target = self.door_layout_indicator_states.get(key)
    if target is None:
        self.door_layout_indicator_states[key] = normalized
    else:
        target.clear()
        target.update(normalized)

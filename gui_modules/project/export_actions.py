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
from copy import deepcopy
from collections.abc import Mapping
from tkinter import filedialog, messagebox

from ae_engine import manufacturing_api


def export_multi_door_layout_dxfs(self, folder, val, *, draw_stock=False):
    """Export one Door DXF per validated layout cell through the headless API."""
    exported = []
    context = self._manufacturing_context(draw_stock=draw_stock)
    for cell in self.get_door_layout_cells():
        filename = manufacturing_api.door_layout_export_filename(cell)
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
    # Main GUI's old presence mirror does not contain the physical Receiving
    # tier owners committed in FoldDesigner's authoritative workspace.
    # Read just these live derived IDs for the EXISTING checkbox rather than
    # silently dropping both actual Base Plate sheets from the original
    # button. The normal FinalScene export still checks each real source.
    real_parts = set(existing_parts or ())
    designer = getattr(self, "fold_designer_app", None)
    snapshot = getattr(designer, "_phase6_input_snapshot", None)
    if (isinstance(snapshot, Mapping)
            and snapshot.get("model") in ("受電箱", "RECEIVING")
            and snapshot.get("nfb_config_submitted") is True):
        workspace = getattr(designer, "designer_workspace", None)
        if workspace is not None:
            real_parts.update(
                part for part in workspace.available_parts
                if str(part).startswith(("base_plate:nfb_layer:", "inner_door:"))
            )
    return {
        "box_body": bool(self.export_z_var.get() and "box_body" in existing_parts),
        "head": bool(self.export_head_var.get() and "head" in existing_parts),
        "tail": bool(self.export_tail_var.get() and "tail" in existing_parts),
        "door": bool(
            self.export_door_var.get()
            and self._phase6_logical_part_present(real_parts, "door")
        ),
        "base_plate": bool(
            self.export_base_plate_var.get()
            and self._phase6_logical_part_present(real_parts, "base_plate")
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
    """Compatibility for operator checkboxes; Engine owns part identity."""
    return manufacturing_api.resolved_export_intention_key(part_key)


def _has_submitted_nfb_in_current_snapshot(payload):
    """Compatibility call: Engine owns the saved NFB submission contract."""
    return manufacturing_api.has_submitted_nfb_in_current_snapshot(payload)


def _assert_legacy_nfb_export_scope_safe(self, flags):
    """Collect GUI project sources, then ask the Engine whether export is safe."""
    designer = getattr(self, "fold_designer_app", None)
    sources = (
        getattr(self, "_phase6_input_snapshot", None),
        getattr(designer, "_phase6_input_snapshot", None),
    )
    workspace = getattr(designer, "designer_workspace", None)
    other = ()
    if workspace is not None:
        snapshot = getattr(workspace, "snapshot", None)
        if callable(snapshot):
            other = (snapshot(),)
    return manufacturing_api.assert_legacy_nfb_export_scope_safe(
        flags, (*sources, *other),
    )


def _selected_resolved_geometry(resolved_geometry, flags):
    """Forward GUI selection intent to the engine physical inventory."""
    return manufacturing_api.select_resolved_export_geometry(
        resolved_geometry, flags,
    )


def _current_authoritative_export_guard(designer, snapshot):
    """GUI snapshots only the input revision; Engine owns all manufacturing."""
    witness = deepcopy(snapshot)
    def verify():
        if getattr(designer, "_phase6_input_snapshot", None) != witness:
            raise ValueError("DXF 出圖來源已變更，請重新確認盤名與板件")
    return verify


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
    chosen = getattr(self, "receiving_dxf_group_mode_var", None)
    group_mode = chosen.get() if chosen is not None else None
    if group_mode is not None and group_mode not in {
        "PER_SET", "ALL", "END_VS_MIDDLE",
    }:
        raise ValueError("未知的 DXF 合併模式")
    source_guard = _current_authoritative_export_guard(designer, mode_source)
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
        # #2517: Engine determines whether saved/live NFB sources match and
        # whether numeric CSV versions can use a single verified batch route.
        # GUI owns only operator intent and the snapshot passed to the API.
        source_policy = manufacturing_api.plan_quantity_export_source(
            mode_source, workspace_snapshot,
        )
        batch = resolve_quantity_manufacturing(request, workspace_snapshot)
        if source_policy.use_current_csv_export:
            outputs = manufacturing_api.export_current_csv_quantity_manufacturing(
                batch, folder, flags=flags, overwrite=True,
            )
            return ([os.path.basename(path) for path in outputs.values()], [])
        selection = manufacturing_api.plan_quantity_operator_export_selection(
            batch, workspace_snapshot, flags,
        )
        nfb_selection = selection.partial_selection
        selected_demands = selection.selected_demands
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
            # Source IDs, report selection and checked physical-demand batch
            # are all projected by Engine, never reconstructed in GUI.
            checked_batch = selection.checked_batch
            live_manifests = manufacturing_api.quantity_partial_live_manifests(
                selection.full_selection, workspace_snapshot,
                selection.selected_reports,
            )
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

    # A Set/Bay production run must output EVERY physical Bay, not merely
    # the currently selected Bay. Reuse precisely the same current Bay
    # resolver that feeds the ordinary 2D/3D preview, de-translate its world
    # assembly anchor back to local sheet coordinates, then validate/serialize
    # each Bay under its stable Set/Bay namespace in ONE atomic transaction.
    receiving_live = dict(getattr(designer, "_phase6_input_snapshot", {}) or {})
    raw_layout = receiving_live.get("receiving_layout") or {}
    raw_sets = raw_layout.get("sets", ()) if isinstance(raw_layout, dict) else ()
    # Only a real multi-Bay topology enters the multi-Bay machinery.
    # Older single-Bay NFB snapshots legitimately lack canonical schema/
    # dimensions; validating those through the multi-Bay path would break
    # previously verified ordinary single-box exports.
    physical_count = sum(
        len(row.get("bays", ())) for row in raw_sets
        if isinstance(row, dict)
    ) if isinstance(raw_sets, (list, tuple)) else 0
    # Legacy one-Bay projects with unconfigured Base still use the
    # established selection-scoped PART_ONLY compatibility route. Grouped
    # single-Bay export is available only for NFB-independent real sheets;
    # never turn missing Base into a synthetic whole-cabinet approval.
    safe_single_bay_group = bool(
        physical_count == 1 and group_mode
        and any(flags.get(key) for key in ("head", "tail", "door"))
        and not any(value for key, value in flags.items()
                    if key not in {"head", "tail", "door"})
    )
    if (receiving_live.get("model") in {"受電箱", "RECEIVING"}
            and receiving_live.get("active_mode", "set_bay") == "set_bay"
            and (physical_count > 1 or safe_single_bay_group)):
        saved_layout = manufacturing_api.normalize_receiving_layout(raw_layout)
        if physical_count != sum(len(s["bays"]) for s in saved_layout["sets"]):
            raise ValueError("多連實體連數與目前標準組合體資料不一致")
        if physical_count > 1 or group_mode is not None:
            import fold_designer_bridge as receiving_bridge
            composition = receiving_bridge._phase6_composition(designer)
            # AC-09/24: HEAD/TAIL/outer DOOR have no NFB source dependency.
            # Preview an isolated Bay whose unselected NFB is unsubmitted;
            # the actual saved source still owns every manufacturing gate.
            independent_only = (
                any(bool(flags.get(key)) for key in ("head", "tail", "door"))
                and not any(bool(value) for key, value in flags.items()
                            if key not in {"head", "tail", "door"})
            )
            def actual_bay_geometry(set_index, bay_index):
                if independent_only:
                    preview_layout=dict(saved_layout)
                    preview_sets=list(saved_layout["sets"])
                    preview_set=dict(preview_sets[set_index])
                    preview_bays=list(preview_set["bays"])
                    preview_bay=dict(preview_bays[bay_index])
                    preview_bay["nfb_config_submitted"]=False
                    preview_bays[bay_index]=preview_bay
                    preview_set["bays"]=preview_bays
                    preview_sets[set_index]=preview_set
                    preview_layout["sets"]=preview_sets
                    current=composition.receiving_bay_preview_request(
                        vars(receiving_bridge), set_index, bay_index,
                        preview_layout=preview_layout,
                    )
                else:
                    current=composition.receiving_bay_preview_request(
                        vars(receiving_bridge), set_index, bay_index,
                    )
                return manufacturing_api.resolve_receiving_bay_local_export_geometry(
                    current.render_data.assembly_parts, saved_layout,
                    set_index=set_index, bay_index=bay_index,
                )
            if group_mode is not None:
                outputs = manufacturing_api.export_grouped_receiving_multibay_dxf(
                    receiving_live,
                    physical_bay_geometry_provider=actual_bay_geometry,
                    flags=flags, output_dir=folder, group_mode=group_mode,
                    pre_commit_guard=source_guard, overwrite=True,
                )
            else:
                outputs = manufacturing_api.export_current_receiving_multibay_dxf(
                    receiving_live,
                    physical_bay_geometry_provider=actual_bay_geometry,
                    flags=flags,output_dir=folder,overwrite=True,
                )
            return ([os.path.basename(path) for path in outputs.values()], [])

    if mode_source.get("model") == "金庫型" and group_mode is not None:
        # GUI never projects/serializes manufacturing geometry.
        _assert_legacy_nfb_export_scope_safe(self, flags)
        resolved = resolver()
        selected = manufacturing_api.select_resolved_export_geometry(
            resolved, flags,
        )
        filename = manufacturing_api.vault_panel_dxf_filename(
            mode_source.get("panel_name", ""),
        )
        manufacturing_api.save_composed_panel_dxf(
            ((filename[:-4], selected),),
            os.path.join(folder, filename),
            pre_commit_guard=source_guard, overwrite=False,
        )
        return ([filename], [])

    # #1503: the original selected-DXF action applies authenticated EAR
    # positioning marks to LEFT/RIGHT physical side plates automatically.
    # No extra operator button or forged cabinet/PAD release.
    receiving_snapshot = dict(getattr(designer, "_phase6_input_snapshot", {}) or {})
    auto_side, committed_csv = manufacturing_api.selected_export_manufacturing_policy(
        receiving_snapshot, flags,
    )
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
    outputs = manufacturing_api.save_selected_resolved_manufacturing_dxf(
        receiving_snapshot, resolved, flags, folder,
    )
    if not outputs:
        return ([], ["canonical resolved export: no selected physical parts"])
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
        receipt = manufacturing_api.export_receiving_ear_side_manufacturing_marking_dxf(
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
        receipt = manufacturing_api.export_receiving_ear_side_check_only_dxf(
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
        # Named outputs must not silently overwrite a previous export.
        designer = getattr(self, "fold_designer_app", None)
        live = getattr(designer, "_phase6_input_snapshot", None) or {}
        mode_field = getattr(self, "receiving_dxf_group_mode_var", None)
        new_named_mode = (
            mode_field is not None and
            isinstance(live, Mapping) and
            live.get("model") in {"受電箱", "RECEIVING", "金庫型"}
        )
        if new_named_mode:
            existing = [
                name for name in exported
                if os.path.isfile(os.path.join(folder, name))
            ]
            if existing and not messagebox.askyesno(
                "DXF 檔名已存在",
                "以下 DXF 已存在，確定要覆寫嗎？\n" + "\n".join(existing),
                default="no",
            ):
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


def export_receiving_pad_base_part_only_dxf(self):
    """One explicit operator action for source-verified PAD+Base paired Q DXF.

    Full cabinet batch manufacturing is independent and remains guarded.
    Material/process and quantity must be provided by the operator, not
    inferred from an NFB model name or baked in as a supplier default.
    """
    from pathlib import Path
    from tkinter import simpledialog
    try:
        self._flush_phase6_authoritative_state()
        designer = getattr(self, "fold_designer_app", None)
        snapshot = getattr(designer, "_phase6_input_snapshot", None)
        if (not isinstance(snapshot, Mapping)
                or snapshot.get("model") not in ("受電箱", "RECEIVING")
                or snapshot.get("nfb_config_submitted") is not True):
            raise ValueError("須在受電箱提交 NFB 後，才能輸出 PAD＋底板")
        if not manufacturing_api.committed_nfb_pad_draft_parts(snapshot):
            raise ValueError("目前沒有已提交且具已確認孔位的 PAD 實體板件")
        from fold_designer_bridge import _phase6_final_scene_adapter
        scene = _phase6_final_scene_adapter(designer).query_assembly_render_data()
        parts=tuple(scene.assembly_parts)
        if not parts:
            raise ValueError("PAD＋底板沒有已核對的 3D 實體裝配")
        material=simpledialog.askstring(
            "PAD＋底板材質", "輸入本批材質／規格（例如專案既有的材質代號）：")
        if material is None:
            return
        material=material.strip()
        if not material:
            raise ValueError("PAD＋底板出圖需要明確材質，不可使用預設猜測")
        process=simpledialog.askstring(
            "PAD＋底板製程", "輸入本批製程或製造路線：")
        if process is None:
            return
        process=process.strip()
        if not process:
            raise ValueError("PAD＋底板出圖需要明確製程")
        qty=simpledialog.askinteger(
            "PAD＋底板版本件數", "這個箱體版本的數量：",
            initialvalue=1,minvalue=1)
        if qty is None:
            return
        # A Quantity version is never a persistent Set/Bay identity.
        # Derive source proof from exactly its submitted version.
        quantity_version = None
        if snapshot.get("active_mode") == "quantity":
            from phase6_quantity_model import QuantityModel
            model = QuantityModel.from_payload(snapshot.get("quantity"))
            quantity_version = model.selected_version_id
            committed = model.nfb_config_for_version(quantity_version)
            if (committed.get("nfb_config_submitted") is not True
                    or committed.get("nfb_config") != snapshot.get("nfb_config")):
                raise ValueError("PAD＋底板數量版本的 NFB 來源已失效")
            snapshot = manufacturing_api.project_common_box(snapshot)
        runtime=snapshot.get("_receiving_runtime_selection")
        if quantity_version is None and not isinstance(runtime, Mapping):
            # Recover the exact one-Bay source identity only from the current
            # saved singleton. Never borrow another Bay or a previous selector.
            layout=snapshot.get("receiving_layout")
            sets=layout.get("sets") if isinstance(layout, Mapping) else None
            if (snapshot.get("active_mode", "set_bay") != "set_bay"
                    or not isinstance(sets, (list, tuple)) or len(sets) != 1
                    or not isinstance(sets[0].get("bays"), (list, tuple))
                    or len(sets[0]["bays"]) != 1
                    or sets[0]["bays"][0].get("nfb_config_submitted") is not True
                    or sets[0]["bays"][0].get("nfb_config") != snapshot.get("nfb_config")):
                raise ValueError("PAD＋底板沒有目前 Set／Bay 的實體選取")
            runtime={
                "set_id": sets[0]["stable_id"],
                "bay_id": sets[0]["bays"][0]["stable_id"],
                "set_index": 0, "bay_index": 0,
            }
            snapshot={**snapshot, "_receiving_runtime_selection": runtime}
        if quantity_version is not None:
            version_id = quantity_version
        else:
            set_id=str(runtime.get("set_id") or "").strip()
            bay_id=str(runtime.get("bay_id") or "").strip()
            if not set_id or not bay_id:
                raise ValueError("PAD＋底板缺少 Set／Bay 實際識別碼")
            version_id=f"{set_id}__{bay_id}"
        root=filedialog.askdirectory(title="選擇 PAD＋底板 CHECK/Q 輸出資料夾")
        if not root:
            return
        output=Path(root)/(manufacturing_api.safe_dxf_part_stem(version_id)+"__PAD_BASE_PAIR_CHECK_Q")
        result=manufacturing_api.export_verified_pad_base_part_only(
            snapshot,parts,output,version_id=version_id,box_count=qty,
            parameters=manufacturing_api.ManufacturingParameters(material,float(snapshot["t"]),process),
        )
    except (ValueError, TypeError, KeyError, FileExistsError, OSError) as exc:
        messagebox.showerror("PAD＋底板無法製造輸出", str(exc))
        return
    messagebox.showinfo(
        "PAD＋底板 CHECK/Q 部分出圖完成",
        f"已核對並輸出 PAD {result.pad_piece_count} 片、"
        f"底板 {result.base_piece_count} 片。\\n"
        f"資料夾：{result.output_directory}\\n"
        "此出圖只包含 PAD＋底板；不代表整箱製造已驗收。",
    )
    return result


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
    designer = getattr(self, "fold_designer_app", None)
    if designer is not None and isinstance(getattr(designer, "_phase6_input_snapshot", None), dict):
        designer._phase6_input_snapshot["door_layout_indicator_states"] = {
            k: dict(v) for k, v in self.door_layout_indicator_states.items()
        }
    self._request_phase6_update("geometry")

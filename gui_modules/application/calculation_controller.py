"""Calculation orchestration extracted from gui.py.

Formula/manufacturing authority remains in AE and existing application owners.
This module only coordinates authoritative inputs/results and UI projection.
"""
import ae_engine.ae as ae


def update_calculations(self):
    try:
        val = self.get_float_values()
        # 1. 箱身結果尺寸只量 authoritative canonical Z Fold Chain。
        # Multi-piece render_data.material 是 exploded preview envelope；
        # summary 必須改量同一 spec 的 canonical strip，不得退回固定段數公式。
        z_spec = self._box_body_part_spec(val)
        z_render = self._authoritative_render_data(
            z_spec, self._manufacturing_context(draw_stock=False)
        )
        z_dimension_render = getattr(z_render, "canonical_strip_render_data", z_render)
        z_minx, z_miny, z_maxx, z_maxy = (
            float(v) for v in z_dimension_render.material.bounds
        )
        z_len = z_maxx - z_minx
        z_h = z_maxy - z_miny
        
        # 2. 封頭／封尾結果尺寸。Phase6 一旦提交 linked Fold Profile，
        # 主 2D 必須直接量同一份 authoritative FinalScene；不得再回到
        # ytop1 + FW + D 的 legacy 公式，否則 3D 自動刪折後主畫面仍會
        # 顯示舊 300 mm。
        baseline = self._baseline_source_model()
        existing_parts = self._phase6_current_existing_parts()
        committed_profiles = self.workspace_controller.part_profiles_snapshot()
        summary_part = next((
            k for k in ("head", "tail")
            if k in existing_parts and committed_profiles.get(k)
        ), None)
        has_endcap = bool({"head", "tail"} & existing_parts)
        if not has_endcap:
            y_w = y_d = None
        elif summary_part is not None:
            y_spec = self._end_cap_part_spec(val, is_tail=(summary_part == "tail"))
            y_render = self._authoritative_render_data(
                y_spec, self._manufacturing_context(draw_stock=False)
            )
            y_minx, y_miny, y_maxx, y_maxy = (float(v) for v in y_render.material.bounds)
            y_w = y_maxx - y_minx
            y_d = y_maxy - y_miny
        else:
            if baseline:
                geom = ae.get_stretched_end_cap_data(
                    baseline, val['w'], val['h'], val['d'], val['t'],
                    FW_val=val['fw'], is_tail=False
                )
                y_w = geom.params['total_width']
                y_d = geom.params['total_depth']
            else:
                y_w = ae.calculate_y_width(val['yl1'], val['yr1'], val['w'], val['t'])
                y_d = ae.calculate_y_depth(
                    val['ytop1'], val['ybottom1'], val['d'], val['t'], val['fw']
                )
        
        # 3. 計算門 Door。不存在的板件不建立/計算預覽資料。
        door_material_fw = self._door_material_frame_width(val['fw'], val['t'])
        if not self._phase6_logical_part_present(existing_parts, "door"):
            door_w = door_h = None
        elif self.multi_door_enabled_var.get():
            cell = self.get_selected_door_layout_cell()
            door_w, door_h = ae.calculate_door_blank_size(
                cell.start_width, cell.start_height, val['t'], door_material_fw,
                val['door_gap_w'], val['door_gap_h'],
                val['door_fold_l'], val['door_fold_r'],
                val['door_fold_t'], val['door_fold_b'],
                frame_edges=cell.edges,
            )
        elif baseline:
            try:
                geom_door = ae.get_stretched_door_data(baseline, val['w'], val['h'], val['t'], door_material_fw,
                                                      val['door_gap_w'], val['door_gap_h'],
                                                      val['door_fold_l'], val['door_fold_r'],
                                                      val['door_fold_t'], val['door_fold_b'])
                door_w = geom_door.params['total_width']
                door_h = geom_door.params['total_depth']
            except Exception:
                door_w, door_h = ae.calculate_door_blank_size(
                    val['w'], val['h'], val['t'], door_material_fw,
                    val['door_gap_w'], val['door_gap_h'],
                    val['door_fold_l'], val['door_fold_r'],
                    val['door_fold_t'], val['door_fold_b']
                )
        else:
            door_w, door_h = ae.calculate_door_blank_size(
                val['w'], val['h'], val['t'], door_material_fw,
                val['door_gap_w'], val['door_gap_h'],
                val['door_fold_l'], val['door_fold_r'],
                val['door_fold_t'], val['door_fold_b']
            )
        
        # 3.5 計算底板
        if self._phase6_logical_part_present(existing_parts, "base_plate"):
            base_plate_w = val['w'] - val['base_plate_shrink_left'] - val['base_plate_shrink_right'] + 2.0 * val['base_plate_bend']
            base_plate_h = val['h'] - val['base_plate_shrink_top'] - val['base_plate_shrink_bottom'] + 2.0 * val['base_plate_bend']
        else:
            base_plate_w = base_plate_h = None
        
        self.result_z_var.set(f"{z_len:.2f} mm")
        self.result_z_h_var.set(f"{z_h:.2f} mm")
        self.result_y_w_var.set("-" if y_w is None else f"{y_w:.2f} mm")
        self.result_y_d_var.set("-" if y_d is None else f"{y_d:.2f} mm")
        self.result_door_w_var.set("-" if door_w is None else f"{door_w:.2f} mm")
        self.result_door_h_var.set("-" if door_h is None else f"{door_h:.2f} mm")
        self.result_base_plate_w_var.set("-" if base_plate_w is None else f"{base_plate_w:.2f} mm")
        self.result_base_plate_h_var.set("-" if base_plate_h is None else f"{base_plate_h:.2f} mm")
        
        # 只有存在的指示燈板件才計算；不存在就保持完全空白。
        if {"indicator_box", "indicator_door"} & existing_parts:
            try:
                self._refresh_indicator_box_result_values(val)
            except Exception:
                self._clear_indicator_box_result_values()
        else:
            self._clear_indicator_box_result_values()
        self._phase6_refresh_presence_ui(existing_parts)
        
        # 重新繪製預覽
        self.draw_preview()
        
    except Exception:
        # 數值尚未輸入完整時，不顯示錯誤，只把計算結果顯示為 "-"
        self.result_z_var.set("-")
        self.result_z_h_var.set("-")
        self.result_y_w_var.set("-")
        self.result_y_d_var.set("-")
        self.result_door_w_var.set("-")
        self.result_door_h_var.set("-")
        self.result_base_plate_w_var.set("-")
        self.result_base_plate_h_var.set("-")
        self.result_ib_w_var.set("-")
        self.result_ib_h_var.set("-")
        self.result_ib_door_w_var.set("-")
        self.result_ib_door_h_var.set("-")

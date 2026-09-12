import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import fold_designer_bridge as bridge
import phase6_settings_panel as settings_panel
from phase6_settings_center import SettingSpec


def _spec(key: str, label: str, group: str, *, kind: str = "float") -> SettingSpec:
    return SettingSpec(
        key=key,
        label=label,
        contexts=("demo",),
        section="DEMO",
        option=key,
        default=False if kind == "bool" else 10.0,
        kind=kind,
        group=group,
    )


def _panel(specs, values=None, staged=None, flushes=None):
    values = dict(values or {spec.key: spec.default for spec in specs})
    staged = staged if staged is not None else []
    flushes = flushes if flushes is not None else []
    return settings_panel.Phase6SettingsPanel(
        values_snapshot=lambda: dict(values),
        stage_setting_update=lambda key, value: staged.append((key, value)),
        flush_settings=lambda: flushes.append("flush"),
        save_defaults=lambda _context: None,
        specs_provider=lambda _context: tuple(specs),
        part_labels={"demo": "測試板件"},
    )


def test_inspector_group_projection_uses_existing_setting_spec_group_order():
    specs = (
        _spec("fold_l", "左折", "折彎"),
        _spec("fold_r", "右折", "折彎"),
        _spec("gap", "間隙", "門縫"),
        _spec("comp", "補料", "補償"),
        _spec("fold_t", "上折", "折彎"),
    )
    helper = getattr(settings_panel, "inspector_setting_groups", None)
    assert callable(helper), "#125 requires schema-group projection instead of the 5-column card grid"

    groups = helper(specs)
    assert tuple(name for name, _rows in groups) == ("折彎", "門縫", "補償")
    assert tuple(spec.key for spec in groups[0][1]) == ("fold_l", "fold_r", "fold_t")
    assert tuple(spec.key for _name_rows in groups for spec in _name_rows[1]) == (
        "fold_l", "fold_r", "fold_t", "gap", "comp"
    )


def test_property_row_is_label_value_unit_grid_and_keeps_existing_edit_contract():
    root = tk.Tk()
    try:
        staged = []
        flushes = []
        spec = _spec("fold_l", "左折", "折彎")
        panel = _panel((spec,), {"fold_l": 15.0}, staged, flushes)
        host = ttk.Frame(root)
        host.pack(fill=tk.X)

        builder = getattr(panel, "_add_inspector_property_row", None)
        assert callable(builder), "#125 requires one aligned engineering property-row builder"
        row = builder(host, spec, 0)
        root.update_idletasks()

        children = row.winfo_children()
        assert len(children) == 3
        label, editor, unit = children
        assert label.winfo_class() == "TLabel"
        assert editor.winfo_class() == "TEntry"
        assert unit.winfo_class() == "TLabel"
        assert int(label.grid_info()["column"]) == 0
        assert int(editor.grid_info()["column"]) == 1
        assert int(unit.grid_info()["column"]) == 2
        assert unit.cget("text") == "mm"
        assert int(row.grid_columnconfigure(1)["weight"]) == 1
        assert str(editor.cget("state")) not in {"disabled", "readonly"}
        assert editor.bind("<Return>")
        assert editor.bind("<FocusOut>")

        panel.setting_vars["fold_l"].set("21")
        root.update_idletasks()
        assert staged[-1] == ("fold_l", 21.0)
        editor.focus_force()
        root.update()
        editor.event_generate("<KeyPress-Return>", when="tail")
        root.update()
        assert flushes
    finally:
        root.destroy()


def test_inspector_scroll_body_can_reach_last_property_group_when_height_is_small():
    root = tk.Tk()
    try:
        specs = tuple(
            _spec(f"v{i}", f"欄位 {i}", "折彎" if i < 8 else "固定孔")
            for i in range(16)
        )
        panel = _panel(specs)
        panel.build_settings_center(root)
        panel.settings_scroll_canvas.configure(height=100)
        panel.render_context("demo")
        root.geometry("520x220+0+0")
        root.update_idletasks()
        root.update()

        canvas = panel.settings_scroll_canvas
        scrollregion = tuple(float(v) for v in str(canvas.cget("scrollregion")).split())
        assert len(scrollregion) == 4
        assert scrollregion[3] - scrollregion[1] > canvas.winfo_height()
        canvas.yview_moveto(1.0)
        root.update_idletasks()
        assert canvas.yview()[1] >= 0.99
    finally:
        root.destroy()


def test_existing_numeric_fields_remain_normal_tk_variables_not_readonly_masking():
    root = tk.Tk()
    try:
        specs = (_spec("gap", "門縫", "門縫"), _spec("bend", "折邊", "折彎"))
        panel = _panel(specs)
        panel.build_settings_center(root)
        panel.render_context("demo")
        root.update_idletasks()

        assert set(panel.setting_vars) == {"gap", "bend"}
        for var in panel.setting_vars.values():
            assert isinstance(var, tk.StringVar)

        entries = []
        stack = [panel.page_cache["demo"]["frame"]]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            if widget.winfo_class() == "TEntry":
                entries.append(widget)
        assert len(entries) >= 2
        assert all(str(entry.cget("state")) not in {"disabled", "readonly"} for entry in entries)
    finally:
        root.destroy()


def test_global_whdt_cells_match_label_value_unit_engineering_row_contract():
    root = tk.Tk()
    try:
        staged = []
        values = {"w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0}
        panel = _panel((), values, staged, [])
        host = ttk.Frame(root)
        host.pack(fill=tk.X)
        panel.build_left_global_controls(host, baseline_models=("受電箱",), initial_model="受電箱")
        root.update_idletasks()

        for key in ("w", "h", "d", "t"):
            cell = panel.left_global_cells[key]
            children = cell.winfo_children()
            assert len(children) == 3, f"#125 global {key.upper()} requires label/value/unit columns"
            label, editor, unit = children
            assert (label.winfo_class(), editor.winfo_class(), unit.winfo_class()) == (
                "TLabel", "TEntry", "TLabel"
            )
            assert tuple(int(widget.grid_info()["column"]) for widget in children) == (0, 1, 2)
            assert unit.cget("text") == "mm"
            assert int(cell.grid_columnconfigure(1)["weight"]) == 1
            assert editor.bind("<Return>") and editor.bind("<FocusOut>")

        panel.left_global_vars["w"].set("420")
        root.update_idletasks()
        assert staged[-1] == ("w", 420.0)
    finally:
        root.destroy()


def test_endcap_fw_extension_uses_plain_inspector_section_and_keeps_fw_entry_editable():
    root = tk.Tk()
    try:
        dummy = SimpleNamespace(
            _phase6_input_snapshot={"fw": 25.0},
            _settings_values={"fw": 25.0},
            _phase6_endcap_fw_state={},
        )
        next_row, follow_var, value_var, entry = bridge._phase6_build_endcap_fw_settings(
            dummy, root, "head", 0
        )
        root.update_idletasks()

        assert next_row == 1
        section = root.winfo_children()[0]
        assert section.winfo_class() == "TFrame", "#125 FW section must not remain a LabelFrame card"
        assert str(entry.cget("state")) == "normal"
        assert entry.bind("<Return>") and entry.bind("<FocusOut>")
        assert float(value_var.get()) == 25.0
        assert follow_var.get() is True

        labels = []
        separators = []
        stack = [section]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            if widget.winfo_class() == "TLabel":
                labels.append(str(widget.cget("text")))
            elif widget.winfo_class() == "TSeparator":
                separators.append(widget)
        assert "邊框寬度 FW" in labels
        assert separators, "#125 FW group requires title + separator hierarchy"
    finally:
        root.destroy()

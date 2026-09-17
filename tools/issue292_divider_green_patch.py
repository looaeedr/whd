from pathlib import Path

p = Path('gui.py')
text = p.read_text(encoding='utf-8')
import_anchor = 'from gui_modules.parts.panels.base_plate import setup_tab_base_plate_ui as _setup_tab_base_plate_ui_impl\n'
import_line = 'from gui_modules.parts.panels.divider import collect_divider_input\n'
if import_line not in text:
    if import_anchor not in text:
        raise SystemExit('base-plate import anchor missing')
    text = text.replace(import_anchor, import_anchor + '\n' + import_line, 1)
old = '''            data = dict(payload or {})
            columns = tuple(
                (float(row[0]), tuple(float(value) for value in row[1]))
                for row in tuple(data.get("door_layout_columns") or ())
            )
            if not columns:
                raise ValueError(f"中隔缺少 authoritative multi-door topology: {key}")
            dividers = derive_box_body_dividers(
                columns,
                depth=float(data.get("d", ae.D)),
                thickness=float(data.get("t", ae.T)),
                layout_scope=str(data.get("door_layout_scope") or "main").strip() or "main",
                handle_edges=dict(data.get("door_handle_edges") or {}),
                model_name=str(data.get("model") or "").strip() or None,
            )
'''
new = '''            divider_input = collect_divider_input(
                key,
                payload,
                default_depth=ae.D,
                default_thickness=ae.T,
            )
            dividers = derive_box_body_dividers(
                divider_input["columns"],
                depth=divider_input["depth"],
                thickness=divider_input["thickness"],
                layout_scope=divider_input["layout_scope"],
                handle_edges=divider_input["handle_edges"],
                model_name=divider_input["model_name"],
            )
'''
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit('divider host block anchor missing')
p.write_text(text, encoding='utf-8')

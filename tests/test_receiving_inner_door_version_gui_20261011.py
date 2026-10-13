"""Inner-door version UI is separate from endcap data but reuses manager/2D."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from ae_engine.receiving_inner_door_candidates import (
    ROLE, create_inner_candidate, inner_versions, inner_config,
    duplicate_inner_candidate, delete_inner_candidate,
)
from ae_engine.receiving_inner_door_pairing import validate_inner_door_allocation
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from ae_engine.receiving_shared_settings import edit_setting
from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def test_inner_version_selector_manager_quantity_and_real_highlights():
    root = tk.Tk()
    root.withdraw()
    layout = {
        "value": resize_receiving_bays(
            new_receiving_layout(width=800, height=1600, depth=350),
            set_index=0, bay_count=2,
        )
    }
    lib, v1 = create_inner_candidate(
        None, {"layers": 1, "models": ["BH_25X95.dxf", ""]}
    )
    lib, v2 = create_inner_candidate(
        lib, {"layers": 2, "models": ["BH_25X95_02.dxf", "BH_25X95_03.dxf"]}
    )
    library = {"value": lib}
    selected = {"bay": 0}
    events = []

    def ports():
        def apply(role, version, si, bays):
            assert role == ROLE
            events.append(("apply", si, tuple(bays), version))
        def validate_quantity(qty, assigned, expected):
            return validate_inner_door_allocation(
                layout["value"], library["value"], qty, assigned,
                expected_counts=expected,
            )
        def apply_quantity(role, qty, assigned, expected):
            assert role == ROLE
            validate_quantity(qty, assigned, expected)
            events.append(("quantity", dict(assigned)))
        return {
            "versions": lambda role: inner_versions(library["value"]) if role == ROLE else (),
            "edit": lambda role, version_id, after_saved:
                events.append(("edit", version_id)),
            "copy": lambda role, version_id, destination: copy(version_id),
            "delete": lambda role, version_id: remove(version_id),
            "apply": apply,
            "validate_quantity": validate_quantity,
            "apply_quantity": apply_quantity,
        }

    def copy(version_id):
        library["value"], new_version = duplicate_inner_candidate(
            library["value"], version_id,
        )
        return new_version

    def remove(version_id):
        library["value"] = delete_inner_candidate(library["value"], version_id)

    def settings_ports(_si):
        def change(kind, value, indices=()):
            for bi in indices or (selected["bay"],):
                layout["value"] = edit_setting(
                    layout["value"], set_index=0, bay_index=bi,
                    kind=kind, value=value,
                )
        return {
            "row": lambda: layout["value"]["sets"][0],
            "select": lambda bi: selected.__setitem__("bay", bi),
            "change": change,
        }

    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (2,)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_args: False,
            get_candidate_ports=lambda: {
                "versions": lambda role: (),
                "edit": lambda *_args: None,
            },
            get_inner_candidate_ports=ports,
            get_settings_ports=settings_ports,
            select_bay=lambda _si, bi: selected.__setitem__("bay", bi),
        )
        root.update()
        assert win._receiving_multi_apply(0)
        listing = win._receiving_multi_setting_list
        listing.selection_set(1)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        selector = win._receiving_multi_candidate_combos[ROLE]
        assert tuple(selector.cget("values")) == ("即時", "版本一", "版本二")
        selector.set("版本二")
        selector.event_generate("<<ComboboxSelected>>")
        root.update()
        assert win._receiving_multi_candidate_selected[ROLE] == v2

        hitbox = win._receiving_multi_canvas._receiving_bay_hitboxes[1]
        x0, y0, x1, y1 = hitbox
        win._receiving_multi_canvas.event_generate(
            "<Button-1>", x=int((x0+x1)/2), y=int((y0+y1)/2),
        )
        root.update()
        host = win._receiving_multi_settings_host
        row = next(
            frame for frame in host.winfo_children()
            if isinstance(frame, ttk.Frame) and any(
                isinstance(child, ttk.Label)
                and child.cget("text") == "內門版本"
                for child in frame.winfo_children()
            )
        )
        apply_button = next(child for child in row.winfo_children()
                            if isinstance(child, ttk.Button)
                            and child.cget("text") == "套用")
        apply_button.invoke()
        assert events[-1] == ("apply", 0, (0, 1), v2)

        manager_button = next(
            child for child in host.winfo_children()
            if isinstance(child, ttk.Button) and child.cget("text") == "版本管理"
        )
        manager_button.invoke()
        root.update()
        manager = win._receiving_multi_manager_window["win"]
        assert manager.title() == "內門版本管理"
        assert [w.cget("text") for w in manager._receiving_manager_buttons] == [
            "複製為新版本", "刪除目前版本",
        ]
        assert manager._receiving_manager_state["role"] == ROLE
        manager._receiving_manager_page_var.set("quantity")
        tabs = manager._receiving_manager_tabs
        next(w for w in tabs.winfo_children() if isinstance(w, ttk.Radiobutton)
             and w.cget("text") == "數量配置").invoke()
        root.update()
        draft = manager._receiving_quantity_ui.draft
        draft.add_version(ROLE, v1)
        draft.set_quantity(ROLE, v1, 1)
        draft.add_version(ROLE, v2)
        draft.set_quantity(ROLE, v2, 1)
        draft.active_version[ROLE] = v1
        draft.assign(ROLE, 0, 0)
        draft.active_version[ROLE] = v2
        draft.assign(ROLE, 0, 1)
        draft.step[ROLE] = 2
        assert manager._receiving_quantity_ui._ready_to_apply()
        manager._receiving_quantity_ui._commit()
        root.update()
        assert events[-1] == ("quantity", {(0, 0): v1, (0, 1): v2})
        win._receiving_multi_close()
    finally:
        root.destroy()

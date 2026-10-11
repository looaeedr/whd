"""Regression: 每次從即時確認編輯都建立新候選版本，且不覆寫既有版本。"""

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from ae_engine.receiving_hole_candidates import (
    create_candidate, candidates_for, update_candidate, version_label,
)
from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def test_domain_versions_increment_independently_without_overwriting():
    library = None
    for role in ("head", "tail"):
        library, first = create_candidate(library, role, [{"hole": "first"}])
        library, second = create_candidate(library, role, [{"hole": "second"}])
        assert first == f"{role}-v1"
        assert second == f"{role}-v2"
        assert version_label(second) == "版本二"
        assert [item["id"] for item in candidates_for(library, role)] == [first, second]
        assert [item["features"] for item in candidates_for(library, role)] == [
            [{"hole": "first"}], [{"hole": "second"}],
        ]
        library = update_candidate(library, role, second, [{"hole": "edited"}])
        assert candidates_for(library, role)[0]["features"] == [{"hole": "first"}]
        assert candidates_for(library, role)[1]["features"] == [{"hole": "edited"}]


def test_live_editor_twice_creates_v1_v2_but_selected_version_updates_in_place():
    root = tk.Tk()
    root.withdraw()
    library = {"value": None}
    calls = []
    confirm = {"value": True}

    def candidate_ports():
        def editor(role, version_id, on_saved):
            calls.append((role, version_id))
            if not confirm["value"]:  # Cancel must not create a version.
                return
            if version_id is None:
                library["value"], created = create_candidate(
                    library["value"], role, [{"edit": len(calls)}]
                )
            else:
                library["value"] = update_candidate(
                    library["value"], role, version_id, [{"edit": len(calls)}]
                )
                created = version_id
            on_saved(created)

        return {
            "versions": lambda role: candidates_for(library["value"], role),
            "edit": editor,
            "copy": lambda *_args: None,
            "delete": lambda *_args: None,
            "apply": lambda *_args: None,
        }

    def edit_button(win, role):
        # Candidate control rows are fixed: head first, tail second.
        row = win._receiving_multi_settings_host.winfo_children()[
            0 if role == "head" else 1
        ]
        return next(child for child in row.winfo_children()
                    if isinstance(child, ttk.Button) and
                    child.cget("text") == "編輯")

    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_args: False,
            get_settings_ports=lambda _set: {"select": lambda _bay: None},
            get_candidate_ports=candidate_ports,
        )
        root.update()
        assert win._receiving_multi_apply(0)
        category = win._receiving_multi_setting_list
        category.selection_set(0)  # 封頭尾
        category.event_generate("<<ListboxSelect>>")
        root.update()

        for role in ("head", "tail"):
            for number in (1, 2):
                combo = win._receiving_multi_candidate_combos[role]
                assert combo.get() == "即時"
                edit_button(win, role).invoke()
                root.update()
                assert calls[-1] == (role, None)
                assert len(candidates_for(library["value"], role)) == number
                combo = win._receiving_multi_candidate_combos[role]
                assert combo.get() == "即時"
            assert tuple(combo.cget("values")) == ("即時", "版本一", "版本二")

        # An explicit old-version selection means UPDATE the original, not v3.
        combo = win._receiving_multi_candidate_combos["head"]
        combo.set("版本一")
        combo.event_generate("<<ComboboxSelected>>")
        root.update()
        edit_button(win, "head").invoke()
        root.update()
        assert calls[-1] == ("head", "head-v1")
        assert len(candidates_for(library["value"], "head")) == 2
        assert candidates_for(library["value"], "head")[0]["features"] == [
            {"edit": len(calls)}
        ]
        assert win._receiving_multi_candidate_combos["head"].get() == "版本一"

        # Returning to live makes the next confirmed edit version THREE.
        combo = win._receiving_multi_candidate_combos["head"]
        combo.set("即時")
        combo.event_generate("<<ComboboxSelected>>")
        root.update()
        confirm["value"] = False
        edit_button(win, "head").invoke()
        root.update()
        assert len(candidates_for(library["value"], "head")) == 2
        confirm["value"] = True
        edit_button(win, "head").invoke()
        root.update()
        assert [entry["id"] for entry in candidates_for(library["value"], "head")] == [
            "head-v1", "head-v2", "head-v3"
        ]
        assert win._receiving_multi_candidate_combos["head"].get() == "即時"
        assert all(button.cget("text") != "新增版本"
                   for button in win._receiving_multi_settings_host.winfo_children()
                   if isinstance(button, ttk.Button))
        win._receiving_multi_close()
    finally:
        root.destroy()

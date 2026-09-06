from __future__ import annotations

import os
import re

import pytest

pytestmark = pytest.mark.skipif(
    not (os.name == "nt" or os.environ.get("DISPLAY")),
    reason="需要 Tk 顯示環境",
)


def _pump(root):
    root.update_idletasks()
    root.update()


def _open_receiving_designer():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("受電箱")
    _pump(root)

    designer = app.open_original_fold_designer()
    try:
        designer.root.deiconify()
        designer.root.geometry("1120x720+0+0")
    except Exception:
        pass
    _pump(root)
    return root, app, designer


def _close(root, designer):
    try:
        if designer is not None:
            designer.root.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass


def _dynamic_doors(designer):
    return tuple(sorted(
        key for key in tuple(designer.available_parts)
        if re.fullmatch(r"door_c\d+_r\d+", str(key))
    ))


def test_guard_receiving_dynamic_doors_are_individually_selector_addressable():
    import fold_designer_bridge as bridge

    root, _app, designer = _open_receiving_designer()
    try:
        doors = _dynamic_doors(designer)
        assert len(doors) >= 2, f"Receiving should expose multiple physical doors, got {doors!r}"

        menu = designer.part_choice_menu
        end = menu.index("end")
        entries = []
        for index in range((end if end is not None else -1) + 1):
            try:
                entries.append((index, str(menu.entrycget(index, "value"))))
            except Exception:
                pass

        for key in doors:
            label = bridge._phase6_part_label(key)
            matches = [index for index, value in entries if value == label]
            assert matches, f"selector is missing dynamic Door {key} ({label})"
            menu.invoke(matches[0])
            _pump(root)
            assert designer.active_part_key == key, (
                f"selector invoked {label} but active part is {designer.active_part_key!r}, expected {key!r}"
            )
    finally:
        _close(root, designer)


def test_red_rbp1_receiving_materializes_exactly_one_base_plate_per_door_cell():
    root, _app, designer = _open_receiving_designer()
    try:
        doors = _dynamic_doors(designer)
        assert len(doors) >= 2, f"precondition: Receiving Door topology missing: {doors!r}"

        expected = tuple(sorted(
            key.replace("door_", "base_plate_", 1)
            for key in doors
        ))
        actual = tuple(sorted(
            str(key) for key in tuple(designer.available_parts)
            if str(key) == "base_plate" or re.fullmatch(r"base_plate_c\d+_r\d+", str(key))
        ))
        assert actual == expected, (
            "Receiving contract is one Door : one Base Plate; "
            f"expected {expected!r}, got {actual!r}"
        )
    finally:
        _close(root, designer)


def test_red_rbp2_every_per_door_base_plate_has_authoritative_nonfallback_placement():
    from ae_engine.assembly_placement import resolve_assembly_placement

    root, _app, designer = _open_receiving_designer()
    try:
        doors = _dynamic_doors(designer)
        assert len(doors) >= 2
        snapshot = dict(designer._phase6_input_snapshot)

        placements = []
        for door_key in doors:
            base_key = door_key.replace("door_", "base_plate_", 1)
            try:
                placement = resolve_assembly_placement(snapshot, base_key)
            except ValueError as exc:
                pytest.fail(
                    f"missing authoritative Base Plate placement for {base_key}: {exc}"
                )
            assert placement.stable_id == base_key
            assert placement.placement_kind != "offset", (
                f"{base_key} fell back to generic offset placement"
            )
            placements.append(tuple(float(v) for v in placement.world_offset))

        assert len(set(placements)) == len(placements), (
            "per-Door Base Plates must not collapse to one shared assembly position"
        )
    finally:
        _close(root, designer)


def test_red_rui1_medium_unlocked_settings_has_real_vertical_scroll_owner():
    import tkinter as tk

    root, _app, designer = _open_receiving_designer()
    try:
        designer.activate_part("head")
        designer.ui_text_size_var.set("中")
        _pump(root)
        if not bool(getattr(designer, "_phase6_parameters_unlocked", False)):
            designer.parameter_lock_button.invoke()
        _pump(root)

        scrollbars = []
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.ttk.Scrollbar):
                    try:
                        if str(child.cget("orient")) == "vertical":
                            scrollbars.append(child)
                    except Exception:
                        pass
                walk(child)

        walk(designer.settings_center)
        assert scrollbars, (
            "Medium + parameter unlock requires a real vertical scroll owner "
            "inside the settings panel"
        )
    finally:
        _close(root, designer)


def test_probe_medium_unlocked_bottom_edge_control_is_fully_inside_its_host():
    root, _app, designer = _open_receiving_designer()
    try:
        designer.activate_part("head")
        designer.ui_text_size_var.set("中")
        _pump(root)
        if not bool(getattr(designer, "_phase6_parameters_unlocked", False)):
            designer.parameter_lock_button.invoke()
        _pump(root)

        hosts = designer.drawing_edge_hosts
        bottom = hosts.bottom
        parent = bottom.master
        assert bottom.winfo_viewable() == 1, "BOTTOM edge host is not viewable"
        assert bottom.winfo_y() >= 0
        assert bottom.winfo_y() + bottom.winfo_height() <= parent.winfo_height(), (
            "BOTTOM edge host is clipped by its drawing host"
        )
    finally:
        _close(root, designer)


def test_red_rui2_endcap_direction_selectors_are_narrower_than_previous_width_7():
    root, _app, designer = _open_receiving_designer()
    try:
        designer.activate_part("head")
        _pump(root)
        widths = {
            edge: int(widget.cget("width"))
            for edge, widget in designer.endcap_joint_widgets.items()
        }
        assert set(widths) == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
        assert all(width <= 5 for width in widths.values()), (
            f"four-direction selectors must be narrowed to <= 5, got {widths!r}"
        )
    finally:
        _close(root, designer)

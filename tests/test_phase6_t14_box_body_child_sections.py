from __future__ import annotations

import os
from types import SimpleNamespace

import pytest


def _piece(role, formed=(100.0, 200.0), blank=(120.0, 220.0)):
    return SimpleNamespace(
        role=role,
        formed_outer_dimensions=formed,
        material_dimensions=blank,
        render_data=SimpleNamespace(material=None),
    )


def _render(*roles):
    return SimpleNamespace(pieces=tuple(_piece(role) for role in roles))


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_r11_box_body_child_sections_follow_authoritative_physical_piece_topology():
    import tkinter as tk
    from tkinter import ttk
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw()
    try:
        host = ttk.Frame(root)
        host.pack()
        fake = SimpleNamespace(
            assembly_box_body_piece_host=host,
            assembly_part_formed_vars={},
            assembly_part_blank_vars={},
            assembly_part_corner_vars={},
        )

        bridge._phase6_refresh_box_body_piece_info_rows(fake, _render("left", "right"))
        assert tuple(fake.assembly_box_body_piece_sections) == (
            "box_body:left", "box_body:right",
        )
        assert len(host.winfo_children()) == 2
        first_sections = dict(fake.assembly_box_body_piece_sections)
        for stable_id, section in first_sections.items():
            assert getattr(section, "_phase6_part_key") == stable_id
            assert section.winfo_exists() == 1

        bridge._phase6_refresh_box_body_piece_info_rows(
            fake, _render("left", "middle", "right")
        )
        assert tuple(fake.assembly_box_body_piece_sections) == (
            "box_body:left", "box_body:middle", "box_body:right",
        )
        assert len(host.winfo_children()) == 3
        assert all(section.winfo_exists() == 0 for section in first_sections.values())
        for stable_id, section in fake.assembly_box_body_piece_sections.items():
            assert getattr(section, "_phase6_part_key") == stable_id
    finally:
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_r11_real_structure_switch_and_project_reload_rebuild_child_sections_from_physical_pieces(tmp_path):
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    import phase6_project_file as project
    from phase6_box_body_structure import BoxBodyStructureType

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    designer = None
    root2 = None
    designer2 = None
    try:
        designer = app.open_original_fold_designer()
        designer.activate_part("box_body")
        root.update_idletasks(); root.update()

        designer.structure_type_var.set("二件式（W 二分）")
        bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
        bridge._phase6_show_assembly(designer)
        bridge._phase6_query_assembly_render_data(designer)
        root.update_idletasks(); root.update()
        assert designer.designer_workspace.box_body_structure_state()["active_type"] == (
            BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
        )
        assert tuple(designer.assembly_box_body_piece_sections) == (
            "box_body:left", "box_body:right",
        )

        designer.structure_type_var.set("三件式（W 三分）")
        bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
        bridge._phase6_query_assembly_render_data(designer)
        root.update_idletasks(); root.update()
        assert designer.designer_workspace.box_body_structure_state()["active_type"] == (
            BoxBodyStructureType.THREE_PIECE_W_SPLIT.value
        )
        assert tuple(designer.assembly_box_body_piece_sections) == (
            "box_body:left", "box_body:middle", "box_body:right",
        )

        snap = designer.export_phase6_snapshot()
        path = tmp_path / "t14_child_sections.p6fold"
        project.write_project(path, {
            "schema": project.PROJECT_SCHEMA,
            "saved_at": "2026-09-06T16:40:00+08:00",
            "snapshot": snap,
            "final_geometry": {},
        })

        root2 = tk.Tk(); root2.withdraw()
        app2 = gui.BoxCalculatorGUI(root2)
        designer2 = app2.load_phase6_project(path, open_designer=True)
        bridge._phase6_show_assembly(designer2)
        bridge._phase6_query_assembly_render_data(designer2)
        root2.update_idletasks(); root2.update()
        assert designer2.designer_workspace.box_body_structure_state()["active_type"] == (
            BoxBodyStructureType.THREE_PIECE_W_SPLIT.value
        )
        assert tuple(designer2.assembly_box_body_piece_sections) == (
            "box_body:left", "box_body:middle", "box_body:right",
        )
    finally:
        try:
            if designer2 is not None:
                designer2.root.destroy()
        except Exception:
            pass
        try:
            if root2 is not None:
                root2.destroy()
        except Exception:
            pass
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass

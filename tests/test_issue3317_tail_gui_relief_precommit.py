# -*- coding: utf-8 -*-
"""#3317: native Tk V selector must validate the *resolved* Tail sheet first.

This tests the real selector callback and menu invocation against a physical
CUTTING notch made by the existing Engine joint-cut owner. The independent
project codec is exercised as a separate persistence seam; Windows UAT and
full GUI project toolbar are not claimed by this focused test.
"""
from types import SimpleNamespace
import tkinter as tk

import pytest
from shapely.geometry import box

from ae_engine import manufacturing_api as api
from ae_engine.assembly_collision import apply_verified_joint_cut_to_part
from ae_engine.assembly_scene_part import AssemblyScenePart
from ae_engine.sheetmetal_geometry_core import GeometryError
from gui_modules.application.fold_designer_composition_settings import (
    select_tail_lower_v_choice,
)
from phase6_settings_panel_primitives import build_choice_menubutton
import phase6_project_file as project
from tests.test_issue3317_tail_gui_lower_v import _real_source

VALUES = {
    "model": "金庫型", "w": 620., "h": 600., "d": 185.,
    "t": 2., "fw": 25., "yl1": 15., "yr1": 15.,
    "ytop1": 16., "ybottom1": 48.,
}


def _existing_engine_cut(raw, cut):
    source = AssemblyScenePart(
        part_key="tail", render_data=raw, x_profile=(), y_profile=(),
        placement="tail", offset=(0., 0., 0.),
    )
    return apply_verified_joint_cut_to_part(source, cut).render_data


def _gui_owner(root, source, spec, raw, resolved):
    submitted = []
    status = tk.StringVar(master=root, value="")
    app = SimpleNamespace(
        _phase6_input_snapshot=dict(source),
        _settings_values={},
        _phase6_box_whd={"w": 620., "h": 600., "d": 185.},
        baseline_model_var=tk.StringVar(master=root, value="金庫型"),
        _phase6_endcap_fw_state=api.normalize_endcap_fw_state(source),
        _phase6_endcap_bottom_wrap_state=api.normalize_endcap_bottom_wrap_state(source),
        _phase6_corner_state={},
        state=SimpleNamespace(profiles={}, profiles_vault={}),
        designer_workspace=SimpleNamespace(
            active_part="tail", profiles_for=lambda _key, _default: {},
            features_for=lambda _key: (), face_features_for=lambda _key: {},
            box_body_structure_state=lambda: {}, available_parts=("tail",),
        ),
        _part_spec_query_callback=lambda _key, _payload: (spec, None),
        _scene_query_callback=lambda _key, _payload: raw,
        _phase6_resolve_manufacturing_geometry=lambda: SimpleNamespace(
            part=lambda key: SimpleNamespace(render_data=resolved)
            if key == "tail" else None,
        ),
        submit_update_intent=lambda *args, **kwargs: submitted.append((args, kwargs)),
        settings_status_var=status,
    )
    return SimpleNamespace(app=app), submitted


def _actual_menu(root, owner):
    var = tk.StringVar(master=root, value="原樣")
    menu_button = build_choice_menubutton(
        root, variable=var, values=("原樣", "V 型"),
        command=lambda: select_tail_lower_v_choice(owner, None, var),
    )
    menu_button.pack()
    root.update_idletasks()
    return var, menu_button


@pytest.mark.parametrize("cut,allowed", (
    (box(-1., 110., 6., 122.), True),   # A real independent original notch
    (box(-1., 54., 6., 60.), False),    # Existing notch overlaps the V
))
def test_native_tk_selector_consults_existing_engine_cut_before_committing(
    cut, allowed, tmp_path,
):
    root = tk.Tk()
    root.withdraw()
    try:
        spec, raw = _real_source(w=620., d=185., t=2.)
        solved = _existing_engine_cut(raw, cut)
        owner, submitted = _gui_owner(root, VALUES, spec, raw, solved)
        var, button = _actual_menu(root, owner)
        original_snapshot = dict(owner.app._phase6_input_snapshot)
        # A real Tk menu radio command, not a Python call to the selector.
        button._phase6_menu.invoke(1)
        if not allowed:
            assert var.get() == "原樣"
            assert owner.app._phase6_input_snapshot == original_snapshot
            assert not submitted
            assert "CONFLICTS_WITH_LOWER_V" in owner.app.settings_status_var.get()
            return

        assert var.get() == "V 型"
        assert owner.app._phase6_input_snapshot[api.TAIL_LOWER_V_SNAPSHOT_KEY] == "v90"
        assert len(submitted) == 1
        preview = api.project_operator_tail_lower_v_preview_render(
            spec, raw, choice="v90", resolved_render_data=solved,
        )
        assert preview.material.intersection(cut).area == pytest.approx(0.)
        assert preview.metadata["tail_lower_v_independent_relief_replayed"]
        assert api.tail_lower_v_preview_mesh(preview)

        path = project.write_project(tmp_path / "native-selector-v.p6fold", {
            "schema": project.PROJECT_SCHEMA,
            "snapshot": owner.app._phase6_input_snapshot,
        })
        reopened = project.read_project(path)["snapshot"]
        assert reopened[api.TAIL_LOWER_V_SNAPSHOT_KEY] == "v90"
        reopened_preview = api.project_operator_tail_lower_v_preview_render(
            spec, raw, choice=reopened[api.TAIL_LOWER_V_SNAPSHOT_KEY],
            resolved_render_data=solved,
        )
        assert reopened_preview.material.equals(preview.material)
        assert api.tail_lower_v_preview_mesh(reopened_preview) == (
            api.tail_lower_v_preview_mesh(preview)
        )
        # Restore the actual Tk menu state after the saved V choice.
        owner.app._phase6_input_snapshot = dict(reopened)
        button._phase6_menu.invoke(0)
        assert var.get() == "原樣"
        assert api.TAIL_LOWER_V_SNAPSHOT_KEY not in owner.app._phase6_input_snapshot
        assert len(submitted) == 2
        assert solved.material.intersection(cut).area == pytest.approx(0.)
    finally:
        root.destroy()

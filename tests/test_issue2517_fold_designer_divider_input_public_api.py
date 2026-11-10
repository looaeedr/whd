"""#2517: one public Engine physical Divider input contract for GUI and headless."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import ezdxf
import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.fold_designer_physical_selection import (
    project_operator_fold_designer_divider_input as owner,
)
from gui_modules.application.fold_designer_manufacturing_projection import (
    _box_body_divider_from_payload,
)
from gui_modules.parts.panels.divider import collect_divider_input


_KEY = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"


def _source():
    return {
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": "350.5",
        "t": "2", "fw": 29.0,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800, [1100.25, 499.75]]],
        "door_handle_edges": {"0:0": "RIGHT"},
    }


def _project(source):
    return api.project_operator_fold_designer_divider_input(
        _KEY, source, default_depth=350.0, default_thickness=2.0,
    )


def test_public_engine_and_gui_share_one_divider_input_function():
    assert ae_engine.project_operator_fold_designer_divider_input is api.project_operator_fold_designer_divider_input
    assert inspect.getmodule(owner).__name__ == "ae_engine.fold_designer_physical_selection"
    gui_source = inspect.getsource(collect_divider_input)
    assert "manufacturing_api.project_operator_fold_designer_divider_input(" in gui_source
    assert "float(" not in gui_source and "math." not in gui_source
    original = _source()
    expected = _project(original)
    assert expected == collect_divider_input(
        _KEY, original, default_depth=350.0, default_thickness=2.0,
    )
    assert expected["columns"] == ((800.0, (1100.25, 499.75)),)
    assert expected["depth"] == 350.5 and expected["thickness"] == 2.0
    assert expected["layout_scope"] == "receiving-main"
    assert expected["handle_edges"] == {"0:0": "RIGHT"}
    assert original == _source()


def test_gui_divider_same_canonical_material_2d_as_headless_json_and_real_dxf(tmp_path):
    source = _source()
    before = deepcopy(source)
    serialized = json.loads(json.dumps(source, ensure_ascii=False))
    headless = api.resolve_fold_designer_divider_part(_KEY, _project(serialized))
    gui = _box_body_divider_from_payload(_KEY, source)
    assert gui == headless
    assert gui.stable_id == _KEY
    assert gui.axis == "HORIZONTAL"
    assert gui.blank_width == pytest.approx(sum(gui.material_lengths))
    assert all(length > 0 for length in gui.material_lengths)
    assert source == before

    render = api.build_box_body_divider_render_data(gui)
    assert render.material is not None and not render.material.is_empty
    assert render.metadata["stable_id"] == _KEY
    output = tmp_path / "source-backed-divider.dxf"
    saved = api.save_part_render_data_dxf(
        render, output, overwrite=False, verify_reopen=True,
    )
    assert api.verify_saved_part_render_data_dxf(render, saved).ok
    reopened = ezdxf.readfile(output)
    assert any(ent.dxf.layer == "CUTTING" for ent in reopened.modelspace())


def test_saved_receiving_divider_source_projects_identical_engine_part(tmp_path):
    import phase6_project_file as project
    from ae_engine.receiving_layout import new_receiving_layout

    snapshot = _source()
    snapshot["d"] = 350.5
    snapshot["t"] = 2.0
    snapshot["receiving_layout"] = new_receiving_layout(
        width=snapshot["w"], height=snapshot["h"], depth=snapshot["d"],
    )
    path = project.write_project(
        tmp_path / "divider-source.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": snapshot},
    )
    reopened = project.read_project(path)["snapshot"]
    assert _project(reopened) == _project(snapshot)
    assert (api.resolve_fold_designer_divider_part(_KEY, _project(reopened))
            == api.resolve_fold_designer_divider_part(_KEY, _project(snapshot)))


@pytest.mark.parametrize("field,value", [
    ("door_layout_columns", [[True, [1100, 500]]]),
    ("door_layout_columns", [[800, ["NaN", 500]]]),
    ("door_layout_columns", [[800, []]]),
    ("door_layout_columns", [{"width": 800, "heights": [1100, 500]}]),
    ("door_layout_columns", "invalid"),
    ("d", True),
    ("d", "inf"),
    ("t", False),
    ("t", "0"),
    ("door_handle_edges", 42),
])
def test_malformed_physical_source_rejects_identically_from_gui_and_engine(field, value):
    snapshot = _source()
    snapshot[field] = value
    unchanged = deepcopy(snapshot)
    with pytest.raises((ValueError, TypeError)):
        _project(snapshot)
    with pytest.raises((ValueError, TypeError)):
        collect_divider_input(
            _KEY, snapshot, default_depth=350.0, default_thickness=2.0,
        )
    with pytest.raises((ValueError, TypeError)):
        _box_body_divider_from_payload(_KEY, snapshot)
    assert snapshot == unchanged


def test_stale_part_id_never_falls_back_to_a_neighboring_physical_divider():
    source = _source()
    different = "box_body:divider:receiving-main:HORIZONTAL:C0_R1|R2"
    with pytest.raises(ValueError, match="stable_id"):
        api.resolve_fold_designer_divider_part(different, _project(source))
    with pytest.raises(ValueError, match="stable_id"):
        _box_body_divider_from_payload(different, source)

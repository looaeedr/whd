"""Real Primary saved-source parity for the bounded C-divider closure."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import tkinter as tk
from tkinter import filedialog, messagebox

import ezdxf
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_equivalence import ManufacturingParameters, manufacturing_equivalence_payload
from ae_engine.manufacturing_scene_access import owner_render_data, replace_owner_render_data
from ae_engine.receiving_horizontal_divider_owner import OCCUPANCY
from ae_engine.sheetmetal_drawing import DrawingScene
from gui import BoxCalculatorGUI
from phase6_manufacturing_adapter import (build_manufacturing_request, build_scene_payload_for_app,
                                          operator_finished_dimensions_for_app)
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

KEY = 'box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1'
KEYS = ('box_body', KEY, 'inner_door:upper:left_frame', 'inner_door:upper:right_frame')


def full_request(app):
    return build_manufacturing_request(
        app, scene_payload_builder=lambda k: build_scene_payload_for_app(app, k),
        render_data_provider=app._scene_query_callback, part_spec_provider=app._part_spec_query_callback,
        finished_dimensions_provider=lambda k: operator_finished_dimensions_for_app(app, k),
    )


def equivalence(render):
    return (manufacturing_equivalence_payload(render, ManufacturingParameters('test-source', 2, None)),
            render.unfolded_topology, tuple(render.fold_guides))


@pytest.fixture(scope="module")
def actual_sources(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("native_sources")
    monkeypatch = pytest.MonkeyPatch()
    errors = []
    for name in ('showinfo', 'showwarning'):
        monkeypatch.setattr(messagebox, name, lambda *a, **k: None)
    monkeypatch.setattr(messagebox, 'showerror', lambda *a, **k: errors.append(a))
    monkeypatch.setattr(messagebox, 'askyesno', lambda *a, **k: True)
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(str(exc))
    try:
        host = BoxCalculatorGUI(root)
        result = []
        for w in (800, 900):
            draft = api.fresh_receiving_mode('set_bay', {'w': w, 'h': 1600, 'd': 350}, thickness=2)
            original = tmp_path / f'input{w}.p6fold'
            write_project(original, {'schema': PROJECT_SCHEMA, 'snapshot': draft})
            host.load_phase6_project(original, open_designer=True)
            root.update()
            saved = tmp_path / f'saved{w}.p6fold'
            monkeypatch.setattr(filedialog, 'asksaveasfilename', lambda **kw: str(saved))
            assert host.save_phase6_project_as() and saved.is_file()
            snapshot = read_project(saved)['snapshot']
            host.load_phase6_project(saved, open_designer=True)
            root.update()
            assert not errors
            req = full_request(host.fold_designer_app)
            geometry = api.resolve_manufacturing_request(req).geometry
            render = owner_render_data(geometry, KEY)
            assert Counter(p.layer for p in render.scene.primitives) == {'CUTTING':7,'BEND':3,'MARKING':2}
            result.append((snapshot, req, geometry))
        yield tuple(result)
    finally:
        root.destroy()
        monkeypatch.undo()


def test_saved_four_inputs_match_real_primary_and_reopen_dxf(actual_sources, tmp_path):
    for snapshot, native_req, native_geometry in actual_sources:
        owner, req = api.build_saved_receiving_c_divider_request(snapshot, KEY)
        assert req.canonical_part_keys == KEYS
        assert req.operator_finished_dimensions == native_req.operator_finished_dimensions
        native_parts = {p.part_key:p for p in native_req.parts}
        for p in req.parts:
            native = native_parts[p.part_key]
            assert p.x_profile == native.x_profile and p.y_profile == native.y_profile, p.part_key
            if p.part_key == 'box_body':
                assert len(p.render_data.pieces) == len(native.render_data.pieces) == 3
                for a,b in zip(p.render_data.pieces, native.render_data.pieces):
                    assert a.role == b.role
                    assert equivalence(a.render_data) == equivalence(b.render_data), a.role
            else:
                assert equivalence(p.render_data) == equivalence(native.render_data), p.part_key
        owner2, replay = api.resolve_saved_receiving_c_divider_source(snapshot, KEY)
        assert owner2 == owner
        actual = owner_render_data(replay, KEY)
        expected = owner_render_data(native_geometry, KEY)
        assert equivalence(actual) == equivalence(expected)
        assert actual.scene == expected.scene and actual.material.equals(expected.material)
        assert actual.metadata['joint_markings'] == expected.metadata['joint_markings']
        assert api.require_saved_receiving_c_divider_source(snapshot, native_geometry, KEY) == owner
        dxf = tmp_path / f"headless{snapshot['w']}.dxf"
        api.save_part_render_data_dxf(actual, dxf, verify_reopen=True)
        doc = ezdxf.readfile(dxf)
        assert doc.header['$INSUNITS'] == 4 and not doc.audit().errors
        assert Counter(e.dxf.layer for e in doc.modelspace()) == {'CUTTING':7,'BEND':3,'MARKING':2}
        assert api.verify_saved_part_render_data_dxf(expected, dxf).ok
        print('saved W', snapshot['w'], 'owner', owner.owner_id, 'raw 4 inputs / full scene parity', actual.material.area, 'DXF',Counter(e.dxf.layer for e in doc.modelspace()))


def test_foreign_render_and_missing_original_marks_reject(actual_sources):
    (s800, _, g800),(s900, _, g900) = actual_sources
    assert api.require_saved_receiving_c_divider_source(s800, g800, KEY) != api.require_saved_receiving_c_divider_source(s900, g900, KEY)
    with pytest.raises(ValueError, match='C_DIVIDER_SAVED_SOURCE_MISMATCH'):
        api.require_saved_receiving_c_divider_source(s800, g900, KEY)
    render = owner_render_data(g800, KEY)
    no_marks = replace(render, scene=DrawingScene([p for p in render.scene.primitives if p.layer != 'MARKING']))
    with pytest.raises(ValueError, match='C_DIVIDER_SAVED_SOURCE_MISMATCH'):
        api.require_saved_receiving_c_divider_source(s800, replace_owner_render_data(g800, KEY, no_marks), KEY)
    print('foreign W900 same key and removal of original two MARKING rejected')


def test_missing_saved_inputs_reject_without_minting(actual_sources):
    s, _, g = actual_sources[0]
    missing = deepcopy(s)
    missing['workspace'].pop('box_body_profile')
    with pytest.raises(ValueError, match='C_DIVIDER_SAVED_SOURCE_REQUIRED:box_body_profile'):
        api.require_saved_receiving_c_divider_source(missing,g,KEY)
    legacy = deepcopy(s)
    legacy['receiving_layout']['sets'][0]['bays'][0].pop(OCCUPANCY)
    with pytest.raises(ValueError, match='OWNER_REQUIRED'):
        api.require_saved_receiving_c_divider_source(legacy,g,KEY)
    assert OCCUPANCY not in legacy['receiving_layout']['sets'][0]['bays'][0]
    # A legacy saved C still cannot acquire a marking owner on read.
    with pytest.raises(ValueError, match='PHYSICAL_MARKING_DURABLE_OWNER_REQUIRED'):
        api.open_selected_ordinary_marking_modal_source(legacy,g,KEY)


def test_common_stock_gate_rejects_foreign_saved_c(actual_sources):
    from ae_engine.operator_persisted_marking_candidate import require_ordinary_selected_marking_stock
    (s800, _, g800),(_, _, g900) = actual_sources
    assert require_ordinary_selected_marking_stock(s800, g800, KEY)._render is owner_render_data(g800, KEY)
    with pytest.raises(ValueError, match='C_DIVIDER_SAVED_SOURCE_MISMATCH'):
        require_ordinary_selected_marking_stock(s800, g900, KEY)

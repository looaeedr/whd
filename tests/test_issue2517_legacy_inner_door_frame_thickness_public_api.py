"""#2517: public legacy frame selector cannot cast invalid physical T into 1 mm."""
from __future__ import annotations

from copy import deepcopy
import inspect

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.fold_designer_manufacturing_projection import (
    _inner_door_frame_from_payload,
)


_FRAME_ID = "inner_door:legacy-A:top_frame"


def _source():
    return {
        "model": "金庫型",
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.5,
        "inner_doors": [{
            "stable_id": "legacy-A",
            "frame_spans": {"top": 500.0, "left": 700.0},
            "included_frame_sides": ("top", "left"),
        }],
    }


def _engine(source, *, default=2.0):
    return api.resolve_fold_designer_frame_part(
        _FRAME_ID, source, default_thickness=default,
    )


def test_legacy_frame_uses_engine_strict_physical_t_and_gui_has_no_second_parser():
    source = _source()
    before = deepcopy(source)
    part = _engine(source)
    assert part == _inner_door_frame_from_payload(_FRAME_ID, source)
    assert part.stable_id == _FRAME_ID
    assert part.thickness == pytest.approx(2.5)
    assert part.span == pytest.approx(500.0)
    assert tuple(part.signed_fold_chain) == (22.0, 46.0, 22.0)
    assert tuple(part.material_lengths) == (22.0, 46.0, 22.0)
    assert source == before

    from ae_engine.fold_designer_physical_selection import resolve_fold_designer_frame_part
    owner = inspect.getsource(resolve_fold_designer_frame_part)
    assert "normalize_operator_source_dimension(" in owner
    assert 'field="t"' in owner
    assert 'float(data.get("t", default_thickness))' not in owner
    gui = inspect.getsource(_inner_door_frame_from_payload)
    assert "manufacturing_api.resolve_fold_designer_frame_part(" in gui
    assert "float(" not in gui


@pytest.mark.parametrize("bad", [
    True, False, 0, -2, "NaN", "inf", "-inf", "bad", None,
])
def test_invalid_explicit_frame_t_fails_closed_before_any_part_is_manufactured(bad):
    source = _source()
    source["t"] = bad
    before = deepcopy(source)
    with pytest.raises(ValueError):
        _engine(source)
    with pytest.raises(ValueError):
        _inner_door_frame_from_payload(_FRAME_ID, source)
    assert source == before


def test_missing_legacy_t_uses_the_same_engine_default_and_rejects_invalid_default():
    missing = _source()
    del missing["t"]
    expected = _source()
    expected["t"] = 2.0
    assert _engine(missing) == _engine(expected)
    assert _engine(missing, default=2.25).thickness == pytest.approx(2.25)
    with pytest.raises(ValueError):
        _engine(missing, default=True)
    with pytest.raises(ValueError):
        _engine(missing, default="NaN")


def test_true_project_save_reload_and_legacy_frame_dxf_share_verified_engine_t(tmp_path):
    import phase6_project_file as project

    original = _source()
    original["t"] = "2.5"
    file = project.write_project(
        tmp_path / "vault-legacy-frame.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    saved = project.read_project(file)["snapshot"]
    assert saved["t"] == original["t"]
    assert _inner_door_frame_from_payload(_FRAME_ID, saved) == _engine(original)

    frame = _inner_door_frame_from_payload(_FRAME_ID, saved)
    rendered = api.build_inner_door_frame_render_data(frame)
    assert rendered.unfolded_topology.piece_id == _FRAME_ID
    assert rendered.material is not None and not rendered.material.is_empty
    output = tmp_path / "legacy-frame.dxf"
    saved_dxf = api.save_part_render_data_dxf(
        rendered, output, overwrite=False, verify_reopen=True,
    )
    assert api.verify_saved_part_render_data_dxf(rendered, saved_dxf).ok
    reopened = ezdxf.readfile(output)
    assert any(e.dxf.layer == "CUTTING" for e in reopened.modelspace())


def test_wrong_frame_stable_id_is_not_silently_rebound_to_neighbor():
    with pytest.raises(ValueError, match="stable_id"):
        _engine({**_source(), "t": 2.5},
                default=2.0) if False else api.resolve_fold_designer_frame_part(
                    "inner_door:legacy-A:bottom_frame", _source(),
                    default_thickness=2.0,
                )

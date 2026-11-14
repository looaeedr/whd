# -*- coding: utf-8 -*-
"""#2517 Door FW/physical T stay raw until canonical Engine Family conversion."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy
from gui import Phase6ApplicationHost


@pytest.mark.parametrize("family,fw,t,expected", [
    ("受電箱", 29, 2, 25.0),
    ("RECEIVING", "29", "2", 25.0),
    ("receiving", 29.0, 2.0, 25.0),
    ("受電箱", "29", "2.125", 24.75),
    ("金庫型", 25, 2, 25.0),
    ("金庫型", "25", "2.125", 25.0),
])
def test_original_family_geometry_is_unchanged_and_serialized_sources_match(
    family, fw, t, expected,
):
    assert api.door_material_frame_width is policy.door_material_frame_width
    assert api.door_material_frame_width(
        family, frame_width=fw, thickness=t,
    ) == pytest.approx(expected)
    restored = json.loads(json.dumps({"fw": fw, "t": t}))
    assert api.door_material_frame_width(
        family, frame_width=restored["fw"], thickness=restored["t"],
    ) == pytest.approx(expected)


@pytest.mark.parametrize("field", ["fw", "t"])
@pytest.mark.parametrize("bad", [
    True, False, 0, "0", -2, "-1", None, "", "bad",
    float("nan"), float("inf"), float("-inf"), "nan", "inf",
])
def test_invalid_physical_sources_fail_before_family_dispatch(
    monkeypatch, field, bad,
):
    monkeypatch.setattr(
        policy, "_call",
        lambda *args, **kwargs: pytest.fail(
            "invalid FW/T source must fail before Family material conversion",
        ),
    )
    kwargs = {"frame_width": 29, "thickness": 2}
    kwargs[{"fw": "frame_width", "t": "thickness"}[field]] = bad
    with pytest.raises(ValueError, match=("FW" if field == "fw" else "T")):
        api.door_material_frame_width("受電箱", **kwargs)


@pytest.mark.parametrize("bad", [
    True, False, 0, -1, None, "nan", "inf", float("nan"), float("inf"),
    "bad",
])
def test_invalid_family_material_result_never_becomes_a_door_fw(monkeypatch, bad):
    # A Family plugin's malformed output must fail at the same public Engine
    # boundary, not produce NaN material face sizes or CUTTING.
    monkeypatch.setattr(policy, "_call", lambda *args, **kwargs: bad)
    with pytest.raises(ValueError, match="FW"):
        api.door_material_frame_width(
            "受電箱", frame_width=29, thickness=2,
        )


@pytest.mark.parametrize("fw,t", [
    (True, 2), (29, False), ("nan", 2), (29, "inf"),
    (0, 2), (29, -1), (29, None),
])
def test_real_gui_door_fw_adapter_rejects_bad_raw_sources(fw, t):
    # Exercise the production GUI method without instantiating a Tk window.
    with pytest.raises(ValueError):
        Phase6ApplicationHost._door_material_frame_width(
            SimpleNamespace(), fw, t, model_name="受電箱",
        )


def test_gui_forwards_uncoerced_inputs_and_model_to_public_engine(monkeypatch):
    seen = []
    def spy(source, *, frame_width, thickness):
        seen.append((source, frame_width, thickness))
        return 25.0
    monkeypatch.setattr(api, "door_material_frame_width", spy)
    # The GUI never pre-coerces the authored string/bool source (or repairs
    # it); a real Engine rejects invalid raw inputs itself.
    result = Phase6ApplicationHost._door_material_frame_width(
        SimpleNamespace(), "29", True, model_name="受電箱",
    )
    assert result == 25.0
    assert seen == [("受電箱", "29", True)]


def test_receiving_nonpositive_material_fw_still_rejects_existing_policy():
    with pytest.raises(ValueError, match="Receiving Door formed FW"):
        api.door_material_frame_width(
            "受電箱", frame_width=3, thickness=2,
        )


def test_door_family_fw_has_no_gui_or_engine_lossy_input_coercion():
    gui_source = inspect.getsource(Phase6ApplicationHost._door_material_frame_width)
    engine_source = inspect.getsource(policy.door_material_frame_width)
    assert "frame_width=frame_width, thickness=thickness" in gui_source
    assert "float(frame_width)" not in gui_source
    assert "float(thickness)" not in gui_source
    assert 'normalize_operator_source_dimension(frame_width, field="fw")' in engine_source
    assert 'normalize_operator_source_dimension(thickness, field="t")' in engine_source
    assert 'normalize_operator_source_dimension(material, field="fw")' in engine_source

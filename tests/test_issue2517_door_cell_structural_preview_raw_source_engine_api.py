"""#2517: Door-cell structural 2D must gate original physical source like DoorPartSpec."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine import operator_door_cell_projection as owner
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges


def _source():
    return {
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 4.0,
        "door_fold_l": 15.0, "door_fold_r": 17.0,
        "door_fold_t": 12.0, "door_fold_b": 14.0,
    }


def _request(values, *, family="金庫型", w=420.0, h=600.0, material_fw=None):
    kwargs = {
        "cell_width": w, "cell_height": h,
        "frame_edges": DoorFrameEdges(
            left=True, right=False, top=False, bottom=True,
        ),
    }
    if family is not None:
        kwargs["family_model"] = family
    else:
        kwargs["material_frame_width"] = material_fw
    return manufacturing_api.project_operator_door_cell_result(values, **kwargs)


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field,bad", (
    ("w", True), ("w", float("nan")), ("w", 0),
    ("h", False), ("h", float("inf")), ("h", "-3"),
    ("t", True), ("t", "nan"), ("t", 0),
    ("fw", False), ("fw", "inf"),
    ("door_gap_w", True), ("door_gap_h", float("nan")),
    ("door_fold_l", True), ("door_fold_r", "inf"),
    ("door_fold_t", False), ("door_fold_b", "bad"),
))
def test_invalid_raw_structural_sources_reject_before_geometry(
    monkeypatch, family, field, bad,
):
    monkeypatch.setattr(owner, "build_door_result", lambda **kw:
                        pytest.fail("invalid source entered Door geometry"))
    source = _source()
    opts = {}
    if field == "w":
        opts["w"] = bad
    elif field == "h":
        opts["h"] = bad
    else:
        source[field] = bad
    before = deepcopy(source)
    with pytest.raises(ValueError):
        _request(source, family=family, **opts)
    assert source == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_valid_fractional_text_matches_exact_numeric_structural_geometry(family):
    values = _source()
    values["t"] = 2.125
    values["fw"] = 29.25
    raw = {k: str(v) for k, v in values.items()}
    before = deepcopy(raw)
    a = _request(raw, family=family, w="420.125", h="600.375")
    b = _request(values, family=family, w=420.125, h=600.375)
    assert a.outline == b.outline
    assert a.bends == b.bends
    assert (a.width, a.height) == pytest.approx((b.width, b.height))
    assert raw == before


@pytest.mark.parametrize("bad", (True, False, 0, "nan", float("inf")))
def test_legacy_headless_material_frame_width_cannot_be_bool_or_nonphysical(
    monkeypatch, bad,
):
    monkeypatch.setattr(owner, "build_door_result", lambda **kw:
                        pytest.fail("invalid legacy FW entered geometry"))
    with pytest.raises(ValueError):
        _request(_source(), family=None, material_fw=bad)


def test_legacy_headless_valid_material_fw_preserves_original_geometry():
    values = _source()
    resolved_fw = manufacturing_api.door_material_frame_width(
        "受電箱", frame_width=values["fw"], thickness=values["t"],
    )
    direct = _request(values, family="受電箱")
    legacy = _request(values, family=None, material_fw=str(resolved_fw))
    assert direct.outline == legacy.outline
    assert direct.bends == legacy.bends
    assert (direct.width, direct.height) == pytest.approx(
        (legacy.width, legacy.height),
    )


def test_source_gate_forwards_canonical_numbers_to_single_existing_builder(
    monkeypatch,
):
    seen = []
    token = object()
    monkeypatch.setattr(owner, "build_door_result", lambda **kw:
                        seen.append(kw) or token)
    raw = {k: str(v) for k, v in _source().items()}
    result = _request(raw, w="420.125", h="600.375")
    assert result is token and len(seen) == 1
    forwarded = seen[0]
    assert forwarded["w"] == 420.125 and forwarded["h"] == 600.375
    assert forwarded["t"] == 2.0 and forwarded["fw"] == 29.0
    assert forwarded["gap_w"] == 3.5 and forwarded["gap_h"] == 4.0
    assert forwarded["fold_left"] == 15.0 and forwarded["fold_bottom"] == 14.0
    assert all(
        type(forwarded[k]) is float
        for k in ("w", "h", "t", "fw", "gap_w", "gap_h",
                  "fold_left", "fold_right", "fold_top", "fold_bottom")
    )

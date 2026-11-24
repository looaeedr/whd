"""Shared reopened MARKING DXF acceptance on a real Receiving LEFT physical sheet."""
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet
from tests.test_issue3414_manual_marking_batch_witness import _marked, _one


def _mutate(path, kind):
    doc = ezdxf.readfile(path)
    polylines = list(doc.modelspace().query('LWPOLYLINE[layer=="MARKING"]'))
    assert polylines
    entity = polylines[0]
    points = list(entity.get_points("xyseb"))
    if kind == "first_x_plus_half":
        x, y, sw, ew, b = points[0]
        points[0] = (x + .5, y, sw, ew, b)
    elif kind == "last_y_plus_half":
        x, y, sw, ew, b = points[-1]
        points[-1] = (x, y + .5, sw, ew, b)
    elif kind == "closed":
        entity.closed = not entity.closed
    elif kind == "layer":
        entity.dxf.layer = "DATUM"
    elif kind == "linetype":
        entity.dxf.linetype = "CENTER"
    elif kind == "layer_linetype":
        doc.layers.get("MARKING").dxf.linetype = "CENTER"
    elif kind == "start_width":
        x, y, sw, ew, b = points[0]
        points[0] = (x, y, .75, ew, b)
    elif kind == "end_width":
        x, y, sw, ew, b = points[0]
        points[0] = (x, y, sw, .75, b)
    elif kind == "bulge":
        x, y, sw, ew, b = points[0]
        points[0] = (x, y, sw, ew, .35)
    elif kind == "const_width":
        entity.dxf.const_width = .7
    elif kind == "color":
        entity.dxf.color = 7
    elif kind == "elevation":
        entity.dxf.elevation = 6.0
    elif kind == "reversed_normal":
        entity.dxf.extrusion = (0.0, 0.0, -1.0)
    else:
        raise AssertionError(kind)
    if kind in {"first_x_plus_half", "last_y_plus_half", "start_width",
                "end_width", "bulge"}:
        entity.set_points(points, format="xyseb")
    doc.saveas(path)


NINE = (
    "first_x_plus_half", "last_y_plus_half", "closed", "layer",
    "linetype", "layer_linetype", "start_width", "end_width", "bulge",
)


@pytest.mark.parametrize("kind", NINE)
def test_reopened_actual_left_rejects_nine_same_entity_count_corruptions(
    actual_sheet, tmp_path, kind,
):
    rendered = _marked(actual_sheet)
    path = tmp_path / "left.dxf"
    api.save_part_render_data_dxf(rendered, path, verify_reopen=True)
    count = len(list(ezdxf.readfile(path).modelspace()))
    assert api.verify_saved_part_render_data_dxf(rendered, path).ok
    _mutate(path, kind)
    reopened = ezdxf.readfile(path)
    assert len(list(reopened.modelspace())) == count
    assert any(e.dxf.layer == "CUTTING" for e in reopened.modelspace())
    assert any(e.dxf.layer == "BEND" for e in reopened.modelspace())
    report = api.verify_saved_part_render_data_dxf(rendered, path)
    assert not report.ok
    assert "MARKING_MISMATCH" in {e.category for e in report.issues}, report.issues


@pytest.mark.parametrize("kind", ("const_width", "color", "elevation", "reversed_normal"))
def test_other_marking_style_attributes_also_fail(actual_sheet, tmp_path, kind):
    rendered = _marked(actual_sheet)
    path = tmp_path / "left.dxf"
    api.save_part_render_data_dxf(rendered, path)
    _mutate(path, kind)
    report = api.verify_saved_part_render_data_dxf(rendered, path)
    assert "MARKING_MISMATCH" in {e.category for e in report.issues}, report.issues


def _export(route, render, folder):
    if route == "single_default":
        return api.save_part_render_data_dxf(
            render, folder / "left.dxf", overwrite=True)
    if route == "single_verified":
        return api.save_part_render_data_dxf(
            render, folder / "left.dxf", overwrite=True, verify_reopen=True)
    if route == "resolved_single":
        return api.save_resolved_manufacturing_geometry_dxf(
            _one(render), folder, overwrite=True)
    if route == "final_scene_batch":
        return api.save_verified_final_scene_batch_dxf(
            (("base_plate", render),), folder,
            overwrite=True, pre_commit_guard=lambda: None)
    raise AssertionError(route)


def _outpath(value):
    return Path(value) if isinstance(value, str) else Path(next(iter(value.values())))


@pytest.mark.parametrize("route", (
    "single_default", "single_verified", "resolved_single",
    "final_scene_batch",
))
def test_actual_left_public_normal_exports_are_reopened_and_unchanged(
    actual_sheet, tmp_path, route,
):
    render = _marked(actual_sheet)
    directory = tmp_path / route
    directory.mkdir()
    path = _outpath(_export(route, render, directory))
    doc = ezdxf.readfile(path)
    assert doc.header["$INSUNITS"] == ezdxf.units.MM
    assert api.verify_saved_part_render_data_dxf(render, path).ok
    assert {e.dxf.layer for e in doc.modelspace()} >= {"CUTTING", "BEND", "MARKING"}
    assert not list(directory.rglob(".whd-dxf-stage-*"))


@pytest.mark.parametrize("route,kind", (
    ("single_default", "first_x_plus_half"),
    ("single_verified", "linetype"),
    ("resolved_single", "bulge"),
    ("final_scene_batch", "end_width"),
    ("single_verified", "elevation"),
    ("single_verified", "reversed_normal"),
    ("final_scene_batch", "elevation"),
    ("final_scene_batch", "reversed_normal"),
))
def test_corrupted_stage_cannot_replace_preexisting_public_dxf(
    actual_sheet, tmp_path, monkeypatch, route, kind,
):
    render = _marked(actual_sheet)
    folder = tmp_path / route
    folder.mkdir()
    old = _outpath(_export(route, render, folder))
    previous = old.read_bytes()
    original_serializer = api.save_scene_dxf
    staged = []

    def corrupted_serializer(path, scene):
        original_serializer(path, scene)
        staged.append(Path(path))
        _mutate(path, kind)

    monkeypatch.setattr(api, "save_scene_dxf", corrupted_serializer)
    with pytest.raises(ValueError, match="WHD_STAGED_DXF_ROUNDTRIP_FAILED"):
        _export(route, render, folder)
    assert staged and all(path != old for path in staged)
    assert old.read_bytes() == previous
    assert not list(folder.rglob(".whd-dxf-stage-*"))
    assert not list(folder.rglob(".whd-dxf-backup-*"))


def test_unmarked_optional_verification_remains_optional(actual_sheet, tmp_path, monkeypatch):
    _, render, _ctx, _mid, _angle = actual_sheet
    unexpected = []
    def no_verification(*args, **kwargs):
        unexpected.append(True)
        raise AssertionError("unmarked optional verification unexpectedly ran")
    monkeypatch.setattr(
        "ae_engine.manufacturing_verification.verify_saved_part_render_data_dxf",
        no_verification,
    )
    api.save_part_render_data_dxf(render, tmp_path / "plain.dxf")
    result = api.save_resolved_manufacturing_geometry_batch_dxf(
        (("plain", _one(render)),), tmp_path / "plain-batch",
        verify_reopen=False)
    assert len(result) == 1 and not unexpected


def test_unverified_namespace_cannot_claim_another_real_marking_owner(
    actual_sheet, tmp_path,
):
    render = _marked(actual_sheet)
    destination = tmp_path / "wrong-owner"
    with pytest.raises(ValueError, match="MANUAL_BATCH_SELECTED_PHYSICAL_ID_MISMATCH"):
        api.save_resolved_manufacturing_geometry_batch_dxf(
            (("set1__bay1", _one(render)),), destination,
            verify_reopen=False,
        )
    assert not destination.exists()



def test_unmarked_expected_receipt_keeps_legacy_mismatch_for_extra_ink(actual_sheet, tmp_path):
    _, unmarked, _, _, _ = actual_sheet
    marked = _marked(actual_sheet)
    path = api.save_part_render_data_dxf(marked, tmp_path / "marked.dxf")
    receipt = api.verify_saved_part_render_data_dxf(unmarked, path)
    assert not receipt.ok
    assert {issue.category for issue in receipt.issues} == {"ENTITY_COUNT_MISMATCH"}

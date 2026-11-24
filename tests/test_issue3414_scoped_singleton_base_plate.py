"""Narrowed scoped LEFT BasePlate still uses the original physical DXF gate."""
from copy import deepcopy
from dataclasses import replace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import LinePrimitive
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import read_project
from tests.test_issue1502_current_csv_multi_bay_once import _provider
from tests.test_issue3414_scoped_marking_proto import _ids, _raw_write, _real_source, _resize


BASE_ONLY = {"base_plate": True}


def _narrowed(tmp_path, *, mark_bay=0):
    source = _real_source()
    first, second = _ids(source)
    editor = api.open_scoped_base_plate_editor(source, 0, mark_bay)
    bend = next(p for p in editor.context.render_data.scene.primitives
                if isinstance(p, LinePrimitive) and p.layer == "BEND")
    mark = api.create_physical_manual_marking(
        "base_plate", editor.context, (),
        midpoint=Vec2((bend.p1.x+bend.p2.x)/2, (bend.p1.y+bend.p2.y)/2),
        length=12, angle_deg=90,
    )
    source[api.SCOPED_BASE_PLATE_MARKS] = api.commit_scoped_base_plate_marks(source, editor, [mark])
    source = _resize(source, 1)
    saved = read_project(_raw_write(tmp_path / "narrowed.p6fold", source))["snapshot"]
    assert _ids(saved) == [first]
    assert set(saved[api.SCOPED_BASE_PLATE_MARKS]) == {first if mark_bay == 0 else second}
    return saved, mark


def _export(source, target, *, pre_commit_guard=lambda: None, provider=None, flags=BASE_ONLY, **kwargs):
    original, _ = _provider(source)
    return api.export_current_receiving_multibay_dxf(
        source, flags=flags, output_dir=target,
        physical_bay_geometry_provider=provider or original,
        pre_commit_guard=pre_commit_guard, **kwargs,
    )


def test_reopened_original_owner_exports_exact_mark_only_once(tmp_path):
    source, feature = _narrowed(tmp_path)
    plan = api.plan_receiving_multibay_export_source(source, BASE_ONLY)
    assert plan.use_multibay and plan.bay_count == 1
    original, calls = _provider(source)
    original_part = next(p for p in original(0, 0).parts if p.part_key == "base_plate")
    # The original provider can include an unrelated legal custom sheet.
    # A forced BasePlate-only route must not publish it.
    def with_custom(set_index, bay_index):
        actual = original(set_index, bay_index)
        return replace(actual, parts=(*actual.parts, replace(original_part, part_key="custom:unselected")))
    calls.clear()
    result = _export(
        source, tmp_path / "output", provider=with_custom,
        flags={"base_plate": "true", "box_body": "false"},
    )
    assert calls == [(0, 0)]
    assert len(result) == 1
    key, path = next(iter(result.items()))
    assert key.endswith(":base_plate")
    doc = ezdxf.readfile(path)
    assert doc.header["$INSUNITS"] == 4
    assert doc.layers.get("MARKING").dxf.linetype == "CONTINUOUS"
    ink, = (e for e in doc.modelspace() if e.dxf.layer == "MARKING")
    assert list(ink.get_points("xy")) == [pytest.approx((p.x, p.y)) for p in feature.points]
    doc.modelspace().delete_entity(ink)
    without_mark = tmp_path / "without-mark.dxf"
    doc.saveas(without_mark)
    assert api.verify_saved_part_render_data_dxf(original_part.render_data, without_mark).ok


def test_orphan_group_mixed_and_existing_unmarked_singleton_never_bypass(tmp_path):
    orphan, _ = _narrowed(tmp_path, mark_bay=1)
    assert list(api.scoped_base_plate_mark_status(orphan).values()) == ["orphaned"]
    existing = tmp_path / "existing"
    existing.mkdir()
    prior = existing / "prior.dxf"
    prior.write_bytes(b"keep previous")
    with pytest.raises(ValueError, match="SCOPED_MARK_SAVED_OWNER_ORPHANED"):
        _export(orphan, existing, overwrite=True)
    valid, _ = _narrowed(tmp_path)
    for flags, mode in ((BASE_ONLY, "ALL"), ({"base_plate": True, "head": True}, None)):
        with pytest.raises(ValueError, match="SCOPED_MARK_BASE_PLATE_EXPORT_NOT_RELEASED"):
            api.plan_scoped_base_plate_normal_output(valid, flags, mode)
    keep = deepcopy(valid)
    keep.pop(api.SCOPED_BASE_PLATE_MARKS)
    assert not api.plan_receiving_multibay_export_source(keep, BASE_ONLY).use_multibay
    with pytest.raises(ValueError, match="RECEIVING_MULTIBAY_REQUIRES_MULTIPLE_PHYSICAL_BAYS"):
        _export(keep, existing, overwrite=True)
    assert list(existing.iterdir()) == [prior]
    assert prior.read_bytes() == b"keep previous"


def test_actual_primary_export_reopens_retained_singleton_owner(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog, messagebox
    import gui
    from gui_modules.project.export_actions import export_selected_dxf

    source, feature = _narrowed(tmp_path)
    project = _raw_write(tmp_path / "single-native.p6fold", source)
    destination = tmp_path / "native-output"
    destination.mkdir()
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    failures = []
    try:
        host = gui.Phase6PrimaryApplication(root)
        designer = host.fold_designer_app
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(project))
        monkeypatch.setattr(messagebox, "showerror", lambda title, message, **kw: failures.append(message))
        monkeypatch.setattr(messagebox, "showwarning", lambda title, message, **kw: failures.append(message))
        monkeypatch.setattr(messagebox, "showinfo", lambda *a, **kw: None)
        designer.project_file_menu.invoke(0)
        root.update()
        assert host.project_controller.project_path == str(project), failures
        assert getattr(host, "receiving_dxf_group_mode_var", None) is None
        for key in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
            getattr(host, f"export_{key}_var").set(key == "base_plate")
        monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(destination))
        export_selected_dxf(host)
        outputs = list(destination.glob("*.dxf"))
        assert len(outputs) == 1 and not failures, failures
        doc = ezdxf.readfile(outputs[0])
        assert doc.header["$INSUNITS"] == 4
        ink, = (e for e in doc.modelspace() if e.dxf.layer == "MARKING")
        assert list(ink.get_points("xy")) == [pytest.approx((p.x, p.y)) for p in feature.points]
    finally:
        root.destroy()


def test_singleton_source_drift_after_move_restores_existing_dxf(tmp_path, monkeypatch):
    from ae_engine import manufacturing_export

    source, _ = _narrowed(tmp_path)
    destination = tmp_path / "publish"
    _export(source, destination)
    original = {p.name: p.read_bytes() for p in destination.iterdir()}
    replace_file = manufacturing_export.os.replace
    moved = []
    def drifting_replace(src, dst):
        result = replace_file(src, dst)
        if ".whd-multibay-csv-" in str(src) and not moved:
            moved.append(True)
            source[api.SCOPED_BASE_PLATE_MARKS].clear()
        return result
    monkeypatch.setattr(manufacturing_export.os, "replace", drifting_replace)
    with pytest.raises(ValueError, match="SCOPED_MARK_SAVED_SOURCE_CHANGED_DURING_OUTPUT"):
        _export(source, destination, overwrite=True)
    assert moved
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == original

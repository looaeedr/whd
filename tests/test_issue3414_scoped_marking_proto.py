"""Scratch native fixture: Owner-scoped straight marks, not scoped manufacturing."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import LinePrimitive
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue1502_current_csv_multi_bay_once import _multi

OWNER = "base_plate_owner_id"


def _resize(source, count):
    layout, _ = api.resize_receiving_operator_topology_with_removed_ids(
        source["receiving_layout"], set_index=0, bay_count=count,
    )
    return {**source, "receiving_layout": layout}


def _real_source():
    source = _multi()
    original_bays = source["receiving_layout"]["sets"][0]["bays"]
    source.update(active_mode="set_bay", existing_parts=["box_body", "base_plate"])
    source["receiving_layout"] = api.operator_new_receiving_layout(
        width=source["w"], height=source["h"], depth=source["d"], new_physical_board=True,
    )
    result = _resize(source, 2)
    for src, dst in zip(original_bays, result["receiving_layout"]["sets"][0]["bays"]):
        dst.update(nfb_config_submitted=True, nfb_config=deepcopy(src["nfb_config"]))
    return result


def _ids(source):
    return [b[OWNER] for b in source["receiving_layout"]["sets"][0]["bays"]]


def _raw_write(path, source):
    return write_project(path, {"schema": PROJECT_SCHEMA, "snapshot": source})


def _state(editor):
    callback = editor._manual_marking_place
    return dict(zip(callback.__code__.co_freevars, (cell.cell_contents for cell in callback.__closure__)))["s"]


def _draw(editor, dx):
    state = _state(editor)
    bend = next(p for p in state.manual_marking_draft.context.render_data.scene.primitives
                if isinstance(p, LinePrimitive) and p.layer == "BEND")
    x = (bend.p1.x + bend.p2.x) / 2 + dx
    y = (bend.p1.y + bend.p2.y) / 2
    tx = state.canvas_view.transform.world_to_canvas
    px, py = tx(Vec2(x, y))
    state.manual_mark_length.set("12")
    state.manual_mark_angle.set("90")
    state.manual_mark_draw_button.invoke()
    state.canvas.event_generate("<ButtonPress-1>", x=round(px), y=round(py))
    state.canvas.event_generate("<ButtonRelease-1>", x=round(px), y=round(py))
    editor.update()
    return tuple(state.live_context.feature_list)


def test_actual_left_boards_distinct_native_marks_save_reopen_and_stale_refusal(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog, messagebox
    import gui
    import fold_designer_bridge as bridge
    from tests.test_issue3413_primary_group_real_tk import _actual_editor_confirm

    source = _real_source()
    a, b = _ids(source)
    original = _raw_write(tmp_path / "original.p6fold", source)
    saved = tmp_path / "saved.p6fold"
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = gui.Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        menu = app.project_file_menu
        errors = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, message, **kw: errors.append(message))
        monkeypatch.setattr(messagebox, "showwarning", lambda title, message, **kw: errors.append(message))
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(original))
        menu.invoke(0)
        root.update()
        assert host.project_controller.project_path == str(original), errors
        def native_button(parent, text):
            matches = []
            def visit(widget):
                for child in widget.winfo_children():
                    if child.winfo_class() in ("TButton", "Button") and child.cget("text") == text:
                        matches.append(child)
                    visit(child)
            visit(parent)
            assert len(matches) == 1, (text, matches)
            return matches[0]

        def open_multi():
            win = bridge._phase6_open_receiving_multi_settings(app)
            root.update()
            apply = native_button(win._receiving_multi_rows_host, "套用")
            apply.invoke()
            root.update()
            return win

        def click_bay(win, index):
            canvas = win._receiving_multi_canvas
            x0, y0, x1, y1 = canvas._receiving_bay_hitboxes[index]
            canvas.event_generate("<ButtonPress-1>", x=round((x0 + x1) / 2), y=round((y0 + y1) / 2))
            canvas.event_generate("<ButtonRelease-1>", x=round((x0 + x1) / 2), y=round((y0 + y1) / 2))
            root.update()

        def open_highlighted(win, index):
            if index == 1:
                click_bay(win, 0)
                assert "disabled" in native_button(win, "底板打標").state()
                click_bay(win, 1)
            assert win._receiving_multi_applied["selected_bays"] == (index,)
            button = native_button(win, "底板打標")
            assert button.winfo_ismapped() and "disabled" not in button.state()
            button.invoke()
            root.update()
            editor = host.last_unified_hole_editor
            assert editor.winfo_exists() and f"Bay{index + 1}" in editor.title(), errors
            assert _state(editor).manual_mark_draw_button.winfo_ismapped()
            assert all(not control.winfo_ismapped() for control in editor._manual_group_controls)
            assert not hasattr(editor, "_manual_group_copy_from_saved")
            return editor

        settings = open_multi()
        marks = []
        for i, offset in ((0, -24), (1, 24)):
            editor = open_highlighted(settings, i)
            root.update()
            assert not _state(editor).live_context.feature_list
            drawn = _draw(editor, offset)
            assert len(drawn) == 1
            _actual_editor_confirm(editor)
            root.update()
            assert not editor.winfo_exists(), errors
            marks.append(drawn[0])
        assert marks[0].points != marks[1].points
        ledger = app._phase6_input_snapshot[api.SCOPED_BASE_PLATE_MARKS]
        assert {owner: row["features"] for owner, row in ledger.items()} == {a: [marks[0]], b: [marks[1]]}
        settings._receiving_multi_close()
        root.update()
        from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import _part_spec
        actual_spec = _part_spec(api.project_receiving_bay_legacy_aliases(source, set_index=0, bay_index=0))[1]
        direct = tmp_path / "direct-base.dxf"
        with pytest.raises(ValueError, match="SCOPED_MARK_BASE_PLATE_EXPORT_NOT_RELEASED"):
            host._export_authoritative_part(actual_spec, str(direct))
        assert not direct.exists()
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(saved))
        menu.invoke(2)
        root.update()
        assert saved.is_file(), errors
        reopened = read_project(saved)["snapshot"]
        assert reopened[api.SCOPED_BASE_PLATE_MARKS] == ledger
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(saved))
        menu.invoke(0)
        root.update()
        assert host.project_controller.project_path == str(saved), errors
        from gui_modules.project.export_actions import export_selected_dxf
        actual_out = tmp_path / "full-gui-output"
        actual_out.mkdir()
        for name in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
            getattr(host, f"export_{name}_var").set(name == "base_plate")
        assert getattr(host, "receiving_dxf_group_mode_var", None) is None
        monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(actual_out))
        monkeypatch.setattr(messagebox, "showinfo", lambda *a, **kw: None)
        export_selected_dxf(host)
        actual_files = sorted(actual_out.glob("*.dxf"))
        assert len(actual_files) == 2, errors
        _assert_two_distinct_marks({
            f"visible_bay_{i}:base_plate": path for i, path in enumerate(actual_files, start=1)
        }, [[marks[0]], [marks[1]]])

        settings = open_multi()
        for i in (0, 1):
            editor = open_highlighted(settings, i)
            root.update()
            restored, = _state(editor).live_context.feature_list
            assert restored.source_type == marks[i].source_type
            assert [(p.x, p.y) for p in restored.points] == [
                pytest.approx((p.x, p.y), abs=1e-10) for p in marks[i].points
            ]
            if i == 0:
                _state(editor).cancel_all()
                root.update()
        ledger_before_delete = api.normalize_scoped_base_plate_mark_ledger(
            app._phase6_input_snapshot[api.SCOPED_BASE_PLATE_MARKS],
        )
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **kw: True)
        native_button(settings, "－連").invoke()
        root.update()
        native_button(settings, "＋連").invoke()
        root.update()
        new_owner = _ids(app._phase6_input_snapshot)[1]
        assert new_owner != b
        _actual_editor_confirm(editor)
        root.update()
        assert editor.winfo_exists()
        assert errors and "SCOPED_MARK_EDITOR_OWNER_STALE" in errors[-1]
        current = app._phase6_input_snapshot
        assert api.normalize_scoped_base_plate_mark_ledger(
            current[api.SCOPED_BASE_PLATE_MARKS],
        ) == ledger_before_delete
        assert api.scoped_base_plate_mark_status(current) == {a: "present", b: "orphaned"}
        status_parent = native_button(settings, "底板打標").master
        assert any("舊打標保留且無效" in child.cget("text") for child in status_parent.winfo_children())
        _state(editor).cancel_all()
        root.update()
        settings._receiving_multi_close()
        root.update()
        orphan_project = tmp_path / "orphan.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(orphan_project))
        menu.invoke(2)
        root.update()
        persisted_orphan = read_project(orphan_project)["snapshot"]
        assert api.scoped_base_plate_mark_status(persisted_orphan) == {a: "present", b: "orphaned"}
    finally:
        if root.winfo_exists():
            root.destroy()


def test_scoped_editor_uses_exact_confirmed_current_cutting_and_batch_refuses_early(tmp_path):
    from ae_engine.operator_scoped_base_plate_marks import resolve_scoped_base_plate_render
    from ae_engine.receiving_csv_multibay_manufacturing import export_current_receiving_multibay_dxf
    from tests.test_issue1502_current_csv_multi_bay_once import _provider

    original = _real_source()
    clean_provider, _ = _provider(original)
    for i in (0, 1):
        actual = next(row.render_data for row in clean_provider(0, i).parts if row.part_key == "base_plate")
        projected = resolve_scoped_base_plate_render(original, 0, i)
        assert projected.scene == actual.scene and projected.material.equals(actual.material)
    opened = api.open_scoped_base_plate_editor(original, 0, 1)
    bend = next(p for p in opened.context.render_data.scene.primitives
                if isinstance(p, LinePrimitive) and p.layer == "BEND")
    midpoint = Vec2((bend.p1.x + bend.p2.x) / 2, (bend.p1.y + bend.p2.y) / 2)
    mark = api.create_physical_manual_marking(
        "base_plate", opened.context, (), midpoint=midpoint, length=12, angle_deg=90,
    )
    candidate = {**original, api.SCOPED_BASE_PLATE_MARKS: api.commit_scoped_base_plate_marks(original, opened, [mark])}
    destination = tmp_path / "out"
    destination.mkdir()
    sentinel = destination / "previous.dxf"
    sentinel.write_bytes(b"previous")
    provider, calls = _provider(original)
    with pytest.raises(ValueError, match="SCOPED_MARK_BASE_PLATE_EXPORT_NOT_RELEASED"):
        export_current_receiving_multibay_dxf(
            candidate, physical_bay_geometry_provider=provider, flags={"base_plate": True},
            output_dir=destination, group_mode="ALL", pre_commit_guard=lambda: None,
            overwrite=True,
        )
    assert calls == [] and sentinel.read_bytes() == b"previous"
    assert tuple(destination.iterdir()) == (sentinel,)
    live = api.project_receiving_bay_legacy_aliases(candidate, set_index=0, bay_index=0)
    assert api.plan_selected_resolved_export_route(live, {"head": True})
    head_provider, head_calls = _provider(original)
    head_only = export_current_receiving_multibay_dxf(
        candidate, physical_bay_geometry_provider=head_provider, flags={"head": True},
        output_dir=tmp_path / "head", group_mode="ALL", pre_commit_guard=lambda: None,
    )
    assert head_calls == [(0, 0), (0, 1)] and len(head_only) == 2
    with pytest.raises(ValueError, match="SCOPED_MARK_BASE_PLATE_EXPORT_NOT_RELEASED"):
        api.plan_selected_resolved_export_route(candidate, {"base_plate": True})


def test_scoped_mark_hold_reaches_all_snapshot_aware_base_plate_special_writers(tmp_path):
    from ae_engine.receiving_nfb_base_partial_export import export_verified_receiving_nfb_base_plate
    from ae_engine.receiving_nfb_pair_export import (
        export_current_csv_nfb_door_base_pair, export_verified_receiving_nfb_door_base_pair,
    )
    from ae_engine.receiving_nfb_pad_pair_manufacturing import export_verified_pad_base_part_only
    from ae_engine.receiving_nfb_v5_part_only_manufacturing import export_verified_csv_v5_single_base_part_only

    source = _real_source()
    owner = _ids(source)[0]
    opened = api.open_scoped_base_plate_editor(source, 0, 0)
    bend = next(p for p in opened.context.render_data.scene.primitives
                if isinstance(p, LinePrimitive) and p.layer == "BEND")
    mark = api.create_physical_manual_marking(
        "base_plate", opened.context, (),
        midpoint=Vec2((bend.p1.x + bend.p2.x) / 2, (bend.p1.y + bend.p2.y) / 2),
        length=12, angle_deg=90,
    )
    source[api.SCOPED_BASE_PLATE_MARKS] = {owner: [mark]}
    target = tmp_path / "previous"
    target.mkdir()
    sentinel = target / "prior.dxf"
    sentinel.write_bytes(b"known")
    for write in (
        lambda: export_verified_receiving_nfb_base_plate(
            None, layout=source["receiving_layout"], current_snapshot=source,
            base_spec=None, output_directory=target,
        ),
        lambda: export_verified_receiving_nfb_door_base_pair(
            None, layout=source["receiving_layout"], current_snapshot=source,
            base_spec=None, output_directory=target,
        ),
        lambda: export_current_csv_nfb_door_base_pair(
            source, assembly_parts=None, base_spec=None, output_directory=target,
        ),
        lambda: export_verified_pad_base_part_only(
            source, None, target, version_id="v1", box_count=1, parameters=None,
            pre_commit_guard=lambda: pytest.fail("early ledger guard ran too late"),
        ),
        lambda: export_verified_csv_v5_single_base_part_only(
            source, "inner", base_spec=None, existing_base_render_data=None,
            output_directory=target, version_id="v1", quantity=1, parameters=None,
        ),
    ):
        with pytest.raises(ValueError, match="SCOPED_MARK_BASE_PLATE_EXPORT_NOT_RELEASED"):
            write()
        assert list(target.iterdir()) == [sentinel] and sentinel.read_bytes() == b"known"


def _assert_two_distinct_marks(outputs, features_by_bay):
    import ezdxf
    assert len(outputs) == len(features_by_bay) == 2
    both = []
    for i, features in enumerate(features_by_bay, start=1):
        key, path = next((k, p) for k, p in outputs.items() if f"_bay_{i}:base_plate" in k)
        assert key.endswith(":base_plate")
        doc = ezdxf.readfile(path)
        assert doc.header["$INSUNITS"] == 4
        assert doc.layers.get("MARKING").dxf.linetype == "CONTINUOUS"
        expected = [[(p.x, p.y) for p in points] for feature in features for _, points, _ in feature.layered_profiles]
        actual = [list(e.get_points("xy")) for e in doc.modelspace() if e.dxf.layer == "MARKING"]
        assert len(actual) == len(expected)
        for row, want in zip(actual, expected):
            assert row == [pytest.approx(point, abs=1e-8) for point in want]
        both.append(actual)
    assert both[0] != both[1]


def test_scoped_export_reopens_exact_per_bay_marks_and_rolls_back_changed_source(tmp_path, monkeypatch):
    from ae_engine import manufacturing_export
    from tests.test_issue1502_current_csv_multi_bay_once import _provider

    clean = _real_source()
    pristine_provider, _ = _provider(clean)
    expected = []
    for i in (0, 1):
        editor = api.open_scoped_base_plate_editor(clean, 0, i)
        guide = next(p for p in editor.context.render_data.scene.primitives
                    if isinstance(p, LinePrimitive) and p.layer == "BEND")
        midpoint = Vec2((guide.p1.x + guide.p2.x) / 2 + i * 35, (guide.p1.y + guide.p2.y) / 2)
        feature = api.create_physical_manual_marking(
            "base_plate", editor.context, (),
            midpoint=midpoint, length=12, angle_deg=90, pattern=("solid", "dashed")[i], dash=2, gap=2,
        )
        clean[api.SCOPED_BASE_PLATE_MARKS] = api.commit_scoped_base_plate_marks(clean, editor, [feature])
        expected.append([feature])
    source = read_project(_raw_write(tmp_path / "scope.p6fold", clean))["snapshot"]
    provider, _ = _provider(source)
    destination = tmp_path / "real-flats"
    outputs = api.export_current_receiving_multibay_dxf(
        source, physical_bay_geometry_provider=provider, flags={"base_plate": True},
        output_dir=destination, pre_commit_guard=lambda: None,
    )
    _assert_two_distinct_marks(outputs, expected)
    for i, path in enumerate(outputs.values()):
        owner = next(row.render_data for row in pristine_provider(0, i).parts if row.part_key == "base_plate")
        check = api.verify_saved_part_render_data_dxf(owner, path)
        assert not check.ok and {issue.category for issue in check.issues} == {"ENTITY_COUNT_MISMATCH"}
    prior = {p.name: p.read_bytes() for p in destination.iterdir()}
    from ae_engine import dxf_serialization
    import ezdxf
    original_writer = dxf_serialization.save_scene_dxf
    def corrupt_mark(path, scene):
        result = original_writer(path, scene)
        doc = ezdxf.readfile(path)
        mark = next(entity for entity in doc.modelspace() if entity.dxf.layer == "MARKING")
        mark.translate(0.5, 0.0, 0.0)
        doc.saveas(path)
        return result
    with monkeypatch.context() as corruption:
        corruption.setattr(dxf_serialization, "save_scene_dxf", corrupt_mark)
        with pytest.raises(ValueError, match="SCOPED_MARK_DXF_POINTS_CHANGED"):
            api.export_current_receiving_multibay_dxf(
                source, physical_bay_geometry_provider=provider, flags={"base_plate": True},
                output_dir=destination, overwrite=True, pre_commit_guard=lambda: None,
            )
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == prior
    original = manufacturing_export.os.replace
    fired = []
    def move(src, dest):
        result = original(src, dest)
        if ".whd-multibay-csv-" in str(src) and not fired:
            fired.append(True)
            source[api.SCOPED_BASE_PLATE_MARKS].pop(_ids(source)[1])
        return result
    monkeypatch.setattr(manufacturing_export.os, "replace", move)
    with pytest.raises(ValueError, match="SCOPED_MARK_SAVED_SOURCE_CHANGED_DURING_OUTPUT"):
        api.export_current_receiving_multibay_dxf(
            source, physical_bay_geometry_provider=provider, flags={"base_plate": True},
            output_dir=destination, overwrite=True, pre_commit_guard=lambda: None,
        )
    assert fired and {p.name: p.read_bytes() for p in destination.iterdir()} == prior


def test_scoped_export_provider_cutting_drift_and_orphan_fail_without_output(tmp_path):
    from tests.test_issue1502_current_csv_multi_bay_once import _provider

    source = _real_source()
    editor = api.open_scoped_base_plate_editor(source, 0, 1)
    guide = next(p for p in editor.context.render_data.scene.primitives
                if isinstance(p, LinePrimitive) and p.layer == "BEND")
    feature = api.create_physical_manual_marking(
        "base_plate", editor.context, (), midpoint=Vec2((guide.p1.x+guide.p2.x)/2, (guide.p1.y+guide.p2.y)/2),
        length=12, angle_deg=90,
    )
    source[api.SCOPED_BASE_PLATE_MARKS] = api.commit_scoped_base_plate_marks(source, editor, [feature])
    changed = deepcopy(source)
    changed["receiving_layout"]["sets"][0]["bays"][1]["nfb_config"]["holes"][0]["manual_x_mm"] += 1
    provider, _ = _provider(changed)
    with pytest.raises(ValueError, match="SCOPED_MARK_SAVED_PHYSICAL_SOURCE_CHANGED"):
        api.export_current_receiving_multibay_dxf(
            changed, physical_bay_geometry_provider=provider, flags={"base_plate": True},
            output_dir=tmp_path / "drift", pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "drift").exists()
    # Swapping the exact same physical shape and raw saved feature into a
    # different owner must fail even where its machining geometry is equal.
    same_shape = _real_source()
    rows = same_shape["receiving_layout"]["sets"][0]["bays"]
    rows[0]["nfb_config"] = deepcopy(rows[1]["nfb_config"])
    opened = api.open_scoped_base_plate_editor(same_shape, 0, 1)
    b_record = api.commit_scoped_base_plate_marks(same_shape, opened, [feature])[_ids(same_shape)[1]]
    same_shape[api.SCOPED_BASE_PLATE_MARKS] = {_ids(same_shape)[0]: b_record}
    provider, _ = _provider(same_shape)
    with pytest.raises(ValueError, match="SCOPED_MARK_SAVED_PHYSICAL_SOURCE_CHANGED"):
        api.export_current_receiving_multibay_dxf(
            same_shape, physical_bay_geometry_provider=provider, flags={"base_plate": True},
            output_dir=tmp_path / "owner-swap", pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "owner-swap").exists()

    orphan = _resize(_resize(source, 1), 2)
    provider, calls = _provider(orphan)
    with pytest.raises(ValueError, match="SCOPED_MARK_SAVED_OWNER_ORPHANED"):
        api.export_current_receiving_multibay_dxf(
            orphan, physical_bay_geometry_provider=provider, flags={"base_plate": True},
            output_dir=tmp_path / "orphan-out", pre_commit_guard=lambda: None,
        )
    assert not calls and not (tmp_path / "orphan-out").exists()


def test_saved_receiving_left_copy_rechecks_bay_owners_and_exports_literal_stroke(tmp_path):
    from hashlib import sha256
    from tests.test_issue1502_current_csv_multi_bay_once import _provider

    source = _real_source()
    a, b = _ids(source)
    scopes = [api.open_physical_sheet_marking("base_plate", snapshot=source, selection=(0, i))
              for i in (0, 1)]
    centres = []
    for offset, scope in zip((0, 35), scopes):
        guide = next(p for p in scope.context.render_data.scene.primitives
                     if isinstance(p, LinePrimitive) and p.layer == "BEND")
        centres.append(Vec2((guide.p1.x + guide.p2.x) / 2 + offset, (guide.p1.y + guide.p2.y) / 2))
    donor = api.create_physical_sheet_mark(scopes[0], (), tool="line", midpoint=centres[0],
                                          length=12, angle_deg=90, pattern="dashed", dash=2, gap=2)
    ledger_key = api.SCOPED_BASE_PLATE_MARKS
    source[ledger_key] = api.commit_physical_sheet_marking(scopes[0], scopes[0], (donor,)).scoped_store
    path = _raw_write(tmp_path / "two-bay.p6fold", source)
    saved = read_project(path)["snapshot"]
    live = deepcopy(saved)
    target = api.open_physical_sheet_marking("base_plate", snapshot=live, selection=(0, 1))
    inputs = dict(project_path=path, project_sha256=sha256(path.read_bytes()).hexdigest(),
                  saved_snapshot=saved)
    choice, = api.list_saved_scoped_marking_copy_candidates(**inputs, target_owner_id=b)
    assert choice[:3] == (a, 0, 0)
    assert choice[4:] == pytest.approx((centres[0].x, centres[0].y, 12))
    ports = dict(**inputs, live_snapshot=live, source_owner_id=a, source_group_id=choice[3],
                 opened_target=target)
    with pytest.raises(ValueError, match="SAME_PHYSICAL_OWNER"):
        api.verify_saved_scoped_marking_copy(**dict(ports, source_owner_id=b))
    with pytest.raises(ValueError, match="SCOPED_COPY_OWNER_STALE"):
        api.verify_saved_scoped_marking_copy(**dict(ports, live_snapshot=_resize(live, 1)))
    tampered = deepcopy(live)
    tampered[ledger_key][a]["source_sha256"] = "0"*64
    with pytest.raises(ValueError, match="SCOPED_COPY_SAVED_SOURCE_CHANGED"):
        api.verify_saved_scoped_marking_copy(**dict(ports, live_snapshot=tampered))
    with pytest.raises(ValueError, match="SOURCE_SAVED_SOURCE_CHANGED"):
        api.verify_saved_scoped_marking_copy(**dict(ports, project_sha256="0"*64))
    clone = api.place_saved_scoped_marking_copy(**ports, target_features=(), target_position=centres[1])
    assert clone != donor
    assert live == saved and b not in live[ledger_key] and read_project(path)["snapshot"] == saved
    result = api.commit_physical_sheet_marking(target, target, (clone,))
    final = read_project(_raw_write(tmp_path / "copied.p6fold", {**live, ledger_key: result.scoped_store}))["snapshot"]
    assert final[ledger_key][a] == saved[ledger_key][a]
    assert final[ledger_key][b]["features"] == [clone]
    provider, _ = _provider(final)
    outputs = api.export_current_receiving_multibay_dxf(
        final, physical_bay_geometry_provider=provider, flags={"base_plate": True},
        output_dir=tmp_path / "export", pre_commit_guard=lambda: None,
    )
    _assert_two_distinct_marks(outputs, ((donor,), (clone,)))


def test_real_scoped_copy_button_cancel_and_confirm(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
    import gui
    from gui_modules.application.physical_part_hole_editor import open_scoped_receiving_base_plate_editor
    from tests.test_issue3413_primary_group_real_tk import _actual_editor_confirm

    source = _real_source()
    a, b = _ids(source)
    ledger_key = api.SCOPED_BASE_PLATE_MARKS
    receipt = api.open_scoped_base_plate_editor(source, 0, 0)
    guide = next(p for p in receipt.context.render_data.scene.primitives
                 if isinstance(p, LinePrimitive) and p.layer == "BEND")
    centre = Vec2((guide.p1.x + guide.p2.x) / 2, (guide.p1.y + guide.p2.y) / 2)
    donor = api.create_physical_manual_marking("base_plate", receipt.context, (),
                                               midpoint=centre, length=12, angle_deg=90)
    source[ledger_key] = api.commit_scoped_base_plate_marks(source, receipt, (donor,))
    saved = _raw_write(tmp_path / "same-project.p6fold", source)
    initial = saved.read_bytes()
    expected = read_project(saved)["snapshot"][ledger_key]
    final_path = tmp_path / "confirmed.p6fold"
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = gui.Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        errors = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, message, **kw: errors.append(message))
        monkeypatch.setattr(messagebox, "showwarning", lambda title, message, **kw: errors.append(message))
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(saved))
        app.project_file_menu.invoke(0)
        root.update()
        assert str(host.project_controller.project_path) == str(saved), errors
        opening_live_ledger = deepcopy(app._phase6_input_snapshot[ledger_key])
        choices = []
        def choose(title, prompt, **kwargs):
            choices.append(prompt)
            return 1
        monkeypatch.setattr(simpledialog, "askinteger", choose)

        def place_from_bay_one():
            editor = open_scoped_receiving_base_plate_editor(host, 0, 1, expected_owner=b)
            root.update()
            state = _state(editor)
            assert state.manual_mark_copy_button.winfo_ismapped()
            state.manual_mark_copy_button.invoke()
            root.update()
            x, y = state.canvas_view.transform.world_to_canvas(Vec2(centre.x + 35, centre.y))
            state.canvas.event_generate("<ButtonPress-1>", x=round(x), y=round(y))
            state.canvas.event_generate("<ButtonRelease-1>", x=round(x), y=round(y))
            root.update()
            candidate, = state.live_context.feature_list
            assert candidate != donor
            assert app._phase6_input_snapshot[ledger_key] == opening_live_ledger
            return editor, state, candidate

        editor, state, _ = place_from_bay_one()
        state.cancel_all_btn.invoke()
        root.update()
        assert not editor.winfo_exists() and not errors, errors
        assert app._phase6_input_snapshot[ledger_key] == opening_live_ledger and saved.read_bytes() == initial
        editor, _, candidate = place_from_bay_one()
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists() and not errors, errors
        assert len(choices) == 2 and all("\u7b2c1\u9023" in choice for choice in choices)
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(final_path))
        app.project_file_menu.invoke(2)
        root.update()
        ledger = read_project(final_path)["snapshot"][ledger_key]
        assert ledger[a] == expected[a] and ledger[b]["features"] == [candidate]
        assert saved.read_bytes() == initial
    finally:
        root.destroy()

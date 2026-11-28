"""Custom catalog creation owns identity; ordinary output permission is unchanged."""
from copy import deepcopy

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from phase6_designer_workspace import Phase6DesignerWorkspace
import phase6_project_file as project


def _create():
    workspace = Phase6DesignerWorkspace.from_snapshot({"model": "金庫型"})
    key = workspace.add_custom_part(display_name="加強板", fold_axis="X", transverse_length=300)
    return workspace, key


def _snapshot(workspace):
    return {"model": "金庫型", "t": 2, "workspace": workspace.snapshot()}


def _stock(snapshot, key):
    render = api.build_part_render_data(api.custom_part_spec(snapshot, key))
    return render, api.selected_normal_marking_inventory(key, render)


def _receipt(snapshot, key):
    _, geometry = _stock(snapshot, key)
    return api.open_physical_sheet_marking(key, snapshot=snapshot, geometry=geometry)


def _save(tmp_path, name, snapshot):
    return project.read_project(project.write_project(tmp_path / name, {
        "schema": project.PROJECT_SCHEMA, "snapshot": snapshot,
    }))["snapshot"]


def test_identical_independent_custom_stock_has_distinct_owners(tmp_path):
    a, key = _create()
    b, other = _create()
    assert key == other == "custom:1"
    sa, sb = _snapshot(a), _snapshot(b)
    ra, rb = _receipt(sa, key), _receipt(sb, key)
    assert ra.source_sha256 == rb.source_sha256
    assert ra.owner_id != rb.owner_id
    assert ra.output_capability == rb.output_capability == "check_only"
    with pytest.raises(ValueError, match="ROOT_MARKING_OWNER_STALE"):
        api.open_workspace_owner_marking_draft(sb, ra)
    for snap, receipt in ((sa, ra), (sb, rb)):
        assert api.open_workspace_owner_marking_draft(snap, receipt).saved_marks == ()
        _, inventory = _stock(snap, key)
        with pytest.raises(ValueError, match="PHYSICAL_MARKING_NORMAL_OUTPUT_UNSUPPORTED"):
            api.open_selected_ordinary_marking_modal_source(snap, inventory, key)


def test_custom_owner_reopen_save_as_and_retirement(tmp_path):
    workspace, key = _create()
    original = _snapshot(workspace)
    receipt = _receipt(original, key)
    reopened = _save(tmp_path, "original.p6fold", original)
    saved_as = _save(tmp_path, "copy.p6fold", reopened)
    restored = Phase6DesignerWorkspace.from_snapshot(saved_as)
    for snap in (reopened, saved_as, _snapshot(restored)):
        current = _receipt(snap, key)
        assert current.owner_id == receipt.owner_id
        assert current.source_sha256 == receipt.source_sha256
        api.open_workspace_owner_marking_draft(snap, receipt)
    assert restored.remove_part(key)
    new = restored.add_custom_part(display_name="加強板", fold_axis="X", transverse_length=300)
    assert new == "custom:2"
    replaced = _snapshot(restored)
    assert api.resolve_workspace_physical_root_owner(replaced, key) is None
    assert _receipt(replaced, new).owner_id != receipt.owner_id
    with pytest.raises(ValueError, match="ROOT_MARKING_OWNER_STALE"):
        api.open_workspace_owner_marking_draft(replaced, receipt)


def test_legacy_custom_no_owner_migration_or_dxf_change(tmp_path):
    workspace, key = _create()
    current = _snapshot(workspace)
    legacy = deepcopy(current)
    legacy["workspace"]["custom_parts"]["items"][key].pop("physical_owner_id")
    legacy = _save(tmp_path, "legacy.p6fold", legacy)
    restored = Phase6DesignerWorkspace.from_snapshot(legacy)
    assert api.resolve_workspace_physical_root_owner(_snapshot(restored), key) is None
    with pytest.raises(ValueError, match="PHYSICAL_MARKING_DURABLE_OWNER_REQUIRED"):
        _receipt(_snapshot(restored), key)
    before, _ = _stock(legacy, key)
    after, _ = _stock(current, key)
    assert before.material.equals(after.material)
    assert before.fold_guides == after.fold_guides
    assert before.scene.primitives == after.scene.primitives
    for name, stock in (("legacy", before), ("current", after)):
        path = tmp_path / (name + ".dxf")
        api.save_part_render_data_dxf(stock, path, verify_reopen=True)
        doc = ezdxf.readfile(path)
        assert not doc.audit().errors
        assert doc.modelspace().query('*[layer=="CUTTING"]')
        assert doc.modelspace().query('*[layer=="BEND"]')
        assert api.verify_saved_part_render_data_dxf(before, path).ok


def test_custom_bound_check_record_cannot_replace_ordinary_dxf(tmp_path):
    from hashlib import sha256
    from ae_engine.sheetmetal_geometry import Vec2

    workspace, key = _create()
    snap = _snapshot(workspace)
    render, inventory = _stock(snap, key)
    destination = tmp_path / "ordinary.dxf"
    api.save_part_render_data_dxf(render, destination, verify_reopen=True)
    before = sha256(destination.read_bytes()).hexdigest()
    receipt = _receipt(snap, key)
    point = render.material.representative_point()
    mark = receipt.create((), midpoint=Vec2(point.x, point.y), length=8, angle_deg=37)
    draft = api.open_workspace_owner_marking_draft(snap, receipt)
    update = api.prepare_workspace_owner_marking_commit(snap, draft, receipt, (mark,))
    with pytest.raises(ValueError, match="PHYSICAL_MARKING_CUSTOM_SOURCE_REQUIRED"):
        workspace.commit_owner_marking_update(
            update, model=snap["model"], read_current_receipt=lambda: _receipt(_snapshot(workspace), key),
        )
    assert workspace.commit_owner_marking_update(
        update, model=snap["model"], read_current_receipt=lambda: _receipt(_snapshot(workspace), key),
        read_current_source=lambda: _snapshot(workspace),
    )
    live = _snapshot(workspace)
    assert api.open_workspace_owner_marking_draft(live, receipt).saved_marks == (mark,)
    with pytest.raises(ValueError, match="PHYSICAL_MARKING_NORMAL_OUTPUT_UNSUPPORTED"):
        api.save_confirmed_workspace_owner_marking_dxf(
            key, destination, read_current=lambda: (live, inventory), overwrite=True,
        )
    assert sha256(destination.read_bytes()).hexdigest() == before
    assert not ezdxf.readfile(destination).audit().errors


def test_catalog_owner_is_not_caller_assigned_or_duplicate():
    catalog = api.CustomPartCatalog()
    values = dict(display_name="板", fold_axis="X", transverse_length=300)
    key = catalog.add(**values)
    owner = catalog.get(key)["physical_owner_id"]
    with pytest.raises(ValueError, match="CUSTOM_PHYSICAL_OWNER_CREATION_ONLY"):
        catalog.add(**values, physical_owner_id=owner)
    other = catalog.add(**values)
    bad = catalog.snapshot()
    bad["items"][other]["physical_owner_id"] = owner
    with pytest.raises(ValueError, match="CUSTOM_PHYSICAL_OWNER_DUPLICATE"):
        api.CustomPartCatalog(bad)
    assert catalog.update(key, display_name="新名稱")
    assert catalog.get(key)["physical_owner_id"] == owner


def _two_different_custom_sources():
    a, key = _create()
    b, _ = _create()
    a.update_custom_part(key, transverse_length=240)
    return _snapshot(a), _snapshot(b), key


def test_conflicting_catalog_rejected_at_project_write_read_and_api(tmp_path):
    import json
    from hashlib import sha256
    a, b, key = _two_different_custom_sources()
    conflict = deepcopy(b)
    conflict['custom_parts'] = deepcopy(a['workspace']['custom_parts'])
    path = tmp_path / 'existing.p6fold'
    project.write_project(path, {'schema': project.PROJECT_SCHEMA, 'snapshot': a})
    before = sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='CUSTOM_PART_CATALOG_CONFLICT'):
        project.write_project(path, {'schema': project.PROJECT_SCHEMA, 'snapshot': conflict})
    assert sha256(path.read_bytes()).hexdigest() == before
    invalid = tmp_path / 'conflict.p6fold'
    invalid.write_text(json.dumps(project._encode({'schema': project.PROJECT_SCHEMA, 'snapshot': conflict})), encoding='utf-8')
    with pytest.raises(ValueError, match='CUSTOM_PART_CATALOG_CONFLICT'):
        project.read_project(invalid)
    with pytest.raises(ValueError, match='CUSTOM_PART_CATALOG_CONFLICT'):
        api.custom_part_spec(conflict, key)
    with pytest.raises(ValueError, match='CUSTOM_PART_CATALOG_CONFLICT'):
        api.resolve_workspace_physical_root_owner(conflict, key)
    with pytest.raises(ValueError, match='CUSTOM_PART_CATALOG_CONFLICT'):
        Phase6DesignerWorkspace.from_snapshot(conflict)
    matching = deepcopy(a)
    matching['custom_parts'] = deepcopy(a['workspace']['custom_parts'])
    assert _receipt(_save(tmp_path, 'matching.p6fold', matching), key).owner_id == _receipt(a, key).owner_id


def test_custom_receipt_rejects_foreign_canonical_geometry_at_issue_and_accept():
    from dataclasses import replace
    a, b, key = _two_different_custom_sources()
    ra, rb = _receipt(a, key), _receipt(b, key)
    assert ra.source_sha256 != rb.source_sha256
    _, foreign = _stock(b, key)
    with pytest.raises(ValueError, match='PHYSICAL_MARKING_CUSTOM_SOURCE_MISMATCH'):
        api.open_physical_sheet_marking(key, snapshot=a, geometry=foreign)
    # Reproduce an already issued mixed receipt (as in the prior candidate).
    mixed = replace(rb, owner_id=ra.owner_id)
    with pytest.raises(ValueError, match='PHYSICAL_MARKING_CUSTOM_SOURCE_MISMATCH'):
        api.open_workspace_owner_marking_draft(a, mixed)
    assert api.open_workspace_owner_marking_draft(a, ra).saved_marks == ()
    assert api.open_workspace_owner_marking_draft(b, rb).saved_marks == ()


def test_custom_equal_stock_foreign_owner_and_stale_same_owner_stock_rejected(tmp_path):
    from dataclasses import replace
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    a, key = _create()
    b, _ = _create()
    sa, sb = _snapshot(a), _snapshot(b)
    ra, rb = _receipt(sa, key), _receipt(sb, key)
    assert ra.source_sha256 == rb.source_sha256
    with pytest.raises(ValueError, match='PHYSICAL_MARKING_CUSTOM_SOURCE_MISMATCH'):
        api.open_physical_sheet_marking(key, snapshot=sa, geometry=_stock(sb, key)[1])
    with pytest.raises(ValueError, match='PHYSICAL_MARKING_CUSTOM_SOURCE_MISMATCH'):
        api.open_workspace_owner_marking_draft(sa, replace(rb, owner_id=ra.owner_id))
    profiles = api.build_custom_part_profiles(sa, key)
    profiles['X'][1]['len'] += 20
    a.stash_profiles(key, profiles)
    hole = CircleFeature(4, FeatureAnchor.TOP_RIGHT, Vec2(-10,-10))
    a.stash_features(key, (hole,))
    # Match the real project writer: it emits the current workspace and
    # its top-level feature/profile mirrors.
    edited = _save(tmp_path, 'edited.p6fold', {**_snapshot(a), **a.snapshot()})
    restored = Phase6DesignerWorkspace.from_snapshot(edited)
    render = api.build_part_render_data(api.custom_part_spec(
        edited, key, profiles=restored.profiles_for(key), features=restored.features_for(key)))
    new = api.open_physical_sheet_marking(key, snapshot=edited, geometry=api.selected_normal_marking_inventory(key, render))
    assert new.owner_id == ra.owner_id and new.source_sha256 != ra.source_sha256
    assert api.open_workspace_owner_marking_draft(edited, new).saved_marks == ()
    with pytest.raises(ValueError, match='PHYSICAL_MARKING_CUSTOM_SOURCE_MISMATCH'):
        api.open_workspace_owner_marking_draft(edited, ra)
    with pytest.raises(ValueError, match='PHYSICAL_MARKING_CUSTOM_SOURCE_MISMATCH'):
        api.open_workspace_owner_marking_draft({**edited, 't': 3}, new)
    with pytest.raises(ValueError, match='PHYSICAL_MARKING_CUSTOM_SOURCE_MISMATCH'):
        api.prepare_workspace_owner_marking_commit(
            edited, api.open_workspace_owner_marking_draft(edited, new), new, (), proposed_receipt=ra)


def test_custom_owner_survives_receiving_mode_roundtrip(tmp_path):
    dims = {'w': 800, 'h': 1600, 'd': 350}
    source = api.fresh_receiving_mode('set_bay', dims)
    workspace = Phase6DesignerWorkspace.from_snapshot(source)
    key = workspace.add_custom_part(display_name='板', fold_axis='X', transverse_length=240)
    a = {**source, **workspace.snapshot()}
    ra = _receipt(a, key)
    session = api.ReceivingModeSession(a)
    assert session.switch('quantity', dimensions=dims)
    quantity = session.snapshot()
    second = Phase6DesignerWorkspace.from_snapshot(quantity)
    other = second.add_custom_part(display_name='板', fold_axis='X', transverse_length=240)
    assert other == 'custom:2'
    b = {**quantity, **second.snapshot()}
    if 'workspace' in b:
        b['workspace'] = second.snapshot()
    saved = _save(tmp_path, 'quantity.p6fold', b)
    rb = _receipt(saved, other)
    assert ra.owner_id != rb.owner_id
    assert session.switch('set_bay', current_snapshot=saved)
    assert _receipt(session.snapshot(), key).owner_id == ra.owner_id
    assert session.switch('quantity')
    assert _receipt(session.snapshot(), other).owner_id == rb.owner_id

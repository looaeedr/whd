"""Quantity projects without common Door authority use the fresh Family contract."""
from copy import deepcopy

from ae_engine.cabinet_types import policy, receiving
from ae_engine.receiving_quantity_box import project_common_box
from phase6_project_file import PROJECT_SCHEMA_V2, read_project, write_project
from phase6_quantity_model import QuantityModel
from phase6_receiving_modes import fresh_receiving_mode


def legacy_quantity_snapshot():
    snapshot = receiving.apply_family_defaults({'t': 2.0})
    snapshot.update(active_mode='quantity', inner_doors=[],
                    quantity=QuantityModel().snapshot(),
                    receiving_quantity_box={'w': 800, 'h': 1600, 'd': 350,
                                            'inner_door_layers': 1})
    return snapshot


def test_quantity_without_common_door_state_materializes_inner_door_and_survives_reload(tmp_path):
    snapshot = legacy_quantity_snapshot()
    original = deepcopy(snapshot)
    projected = project_common_box(snapshot)
    assert [p.stable_id for p in policy.derive_inner_door_panels(projected)] == ['inner_door:upper:panel']
    assert snapshot == original
    saved = write_project(tmp_path / 'quantity.p6fold',
                          {'schema': PROJECT_SCHEMA_V2, 'snapshot': projected})
    loaded = read_project(saved)['snapshot']
    assert [p.stable_id for p in policy.derive_inner_door_panels(loaded)] == ['inner_door:upper:panel']
    assert loaded['receiving_quantity_box']['door_state']['inner_doors']


def test_explicitly_disabled_common_inner_door_stays_disabled():
    snapshot = fresh_receiving_mode('quantity', {'w': 800, 'h': 1600, 'd': 350})
    snapshot['receiving_quantity_box']['door_state']['inner_doors'] = []
    projected = project_common_box(snapshot)
    assert policy.derive_inner_door_panels(projected) == ()


def test_primary_project_load_refreshes_existing_designer_inner_door_list(tmp_path):
    import json
    import os
    import tkinter as tk
    import pytest
    import gui

    if not os.environ.get('DISPLAY'):
        pytest.skip('requires Tk display')
    saved = write_project(tmp_path / 'legacy-quantity.p6fold',
                          {'schema': PROJECT_SCHEMA_V2,
                           'snapshot': legacy_quantity_snapshot()})
    raw = json.loads(saved.read_text(encoding='utf-8'))
    raw['snapshot']['receiving_quantity_box'].pop('door_state')
    raw['snapshot']['inner_doors'] = []
    saved.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
    root = tk.Tk()
    app = gui.Phase6PrimaryApplication(root)
    try:
        designer = app.load_phase6_project(saved)
        for _ in range(5):
            root.update_idletasks()
            root.update()
        assert 'inner_door:upper:panel' in designer.designer_workspace.available_parts
        assert designer.structure_tree.exists('part:inner_door:upper:panel')
        menu = designer.part_choice_menu
        assert '上層內門門板' in tuple(menu.entrycget(i, 'label')
                                     for i in range(int(menu.index('end')) + 1))
    finally:
        root.destroy()

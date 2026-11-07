"""#2517: Quantity version total and last-delete policy only from public Engine."""
from copy import deepcopy
from inspect import getsource
from types import SimpleNamespace

import ae_engine
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.receiving_quantity_versions import QuantityModel
from gui_modules.application.quantity_version_controls import QuantityVersionControls
from gui_modules.application.quantity_version_ports import quantity_ports


def test_public_root_and_facade_share_exact_projection_owner():
    assert ae_engine.project_operator_quantity_version_controls is (
        api.project_operator_quantity_version_controls
    )
    assert "project_operator_quantity_version_controls" in ae_engine.__all__


def test_one_version_must_not_be_deletable_and_preserves_original_source():
    original = QuantityModel().snapshot()
    before = deepcopy(original)
    result = api.project_operator_quantity_version_controls(original)
    assert original == before
    assert result["versions"] == original["versions"]
    assert result["selected_version_id"] == "quantity-v1"
    assert (result["version_count"], result["total_piece_count"],
            result["selected_piece_count"]) == (1, 1, 1)
    assert result["can_delete_selected"] is False
    result["versions"][0]["piece_count"] = 500
    assert original == before


def test_real_multiple_versions_and_selected_counts_match_quantity_model():
    model = QuantityModel()
    first = model.selected_version_id
    model.set_piece_count(7)
    second = model.add_version()
    model.set_piece_count("3")
    original = model.snapshot()
    summary = api.project_operator_quantity_version_controls(original)
    assert summary["version_count"] == model.version_count == 2
    assert summary["total_piece_count"] == model.total_piece_count == 10
    assert summary["selected_piece_count"] == model.selected_piece_count == 3
    assert summary["selected_version_id"] == second
    assert summary["can_delete_selected"] is True
    model.select(first)
    other = api.project_operator_quantity_version_controls(model.snapshot())
    assert other["total_piece_count"] == 10
    assert other["selected_piece_count"] == 7
    assert original["selected_version_id"] == second


@pytest.mark.parametrize("fault", ("missing", "bad-schema", "zero-count",
                                    "selected", "duplicate", "reused-next"))
def test_invalid_source_fails_without_mutating_input(fault):
    source = QuantityModel().snapshot()
    if fault == "missing":
        source.pop("versions")
    elif fault == "bad-schema":
        source["schema"] = "unknown"
    elif fault == "zero-count":
        source["versions"][0]["piece_count"] = False
    elif fault == "selected":
        source["selected_version_id"] = "quantity-v999"
    elif fault == "duplicate":
        source["versions"].append(deepcopy(source["versions"][0]))
    else:
        source["next_version_number"] = 1
    before = deepcopy(source)
    with pytest.raises(ValueError):
        api.project_operator_quantity_version_controls(source)
    assert source == before


class _Tree:
    def __init__(self):
        self.rows = {}
        self.selected = None

    def get_children(self):
        return tuple(self.rows)

    def delete(self, *items):
        for key in items:
            self.rows.pop(key, None)

    def insert(self, _parent, _position, *, iid, values):
        self.rows[iid] = values

    def selection_set(self, selected):
        self.selected = selected

    def focus(self, selected):
        self.selected = selected


class _Variable:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


def test_controls_do_not_recalculate_piece_total_or_final_version_rule(monkeypatch):
    from tkinter import messagebox
    calls = []
    monkeypatch.setattr(messagebox, "showinfo",
                        lambda *_args, **_kw: calls.append("info"))
    model = QuantityModel()
    payload = api.project_operator_quantity_version_controls(model.snapshot())
    controls = QuantityVersionControls(
        frame=None, versions=_Tree(), count_var=_Variable(),
        totals_var=_Variable(),
        ports={"snapshot": lambda: payload,
               "delete": lambda confirmed: calls.append(("delete", confirmed))},
    )
    body = getsource(QuantityVersionControls)
    assert "sum(row['piece_count'] for row in rows)" not in body
    assert 'len(payload["versions"]) == 1' not in body
    controls.refresh()
    assert controls.totals_var.value == "版本數：1    總件數：1"
    assert controls.count_var.value == "1"
    assert controls.versions.rows["quantity-v1"] == ("孔型版本 1", 1)
    assert controls.delete() is False
    assert calls == ["info"]


def test_real_gui_snapshot_port_delegates_readback_for_both_families():
    source = getsource(quantity_ports)
    assert "manufacturing_api.project_operator_quantity_version_controls(" in source
    for family in ("金庫型", "受電箱"):
        model = QuantityModel()
        app = SimpleNamespace(
            designer_workspace=SimpleNamespace(quantity_model=model),
            baseline_model_var=SimpleNamespace(get=lambda: family),
        )
        ports = quantity_ports(SimpleNamespace(app=app), None)
        assert ports["snapshot"]() == api.project_operator_quantity_version_controls(
            model.snapshot()
        )


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_saved_versions_reloaded_with_identical_engine_totals(tmp_path, family):
    from phase6_project_file import PROJECT_SCHEMA, write_project, read_project
    model = QuantityModel()
    model.set_piece_count(4)
    model.add_version()
    model.set_piece_count(5)
    if family == "受電箱":
        from phase6_receiving_modes import fresh_receiving_mode
        source = fresh_receiving_mode(
            "quantity", {"w": 800, "h": 1600, "d": 350},
            thickness=2,
        )
        source["quantity"] = model.snapshot()
    else:
        source = {
            "model": family, "active_mode": "quantity",
            "w": 800, "h": 1600, "d": 350, "t": 2,
            "quantity": model.snapshot(),
        }
    file = write_project(tmp_path / "quantity-controls.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": source,
    })
    payload = read_project(file)["snapshot"]["quantity"]
    summary = api.project_operator_quantity_version_controls(payload)
    assert (summary["version_count"], summary["total_piece_count"],
            summary["selected_piece_count"]) == (2, 9, 5)

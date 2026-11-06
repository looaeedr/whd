"""#2517 Quantity versions and PAD physical demand use one Engine API owner."""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_cache_signature import manufacturing_state_fingerprint
from ae_engine.manufacturing_contracts import ManufacturingResolveRequest
from ae_engine.receiving_quantity_versions import QuantityModel
from phase6_quantity_manufacturing import build_quantity_manufacturing_requests


def _base(model="金庫型"):
    return ManufacturingResolveRequest(
        cabinet_model=model,
        input_snapshot={
            "model": model, "active_mode": "quantity",
            "w": 800, "h": 1600, "d": 350, "t": 2,
        },
        settings={"w": 800, "h": 1600, "d": 350, "t": 2},
        box_dimensions={"w": 800, "h": 1600, "d": 350},
    )


def test_one_engine_quantity_request_builder_is_old_gui_route():
    snap = {"active_mode": "quantity", "quantity": QuantityModel().snapshot()}
    direct = api.build_operator_quantity_manufacturing_requests(_base(), snap)
    compatible = build_quantity_manufacturing_requests(_base(), snap)
    assert len(direct) == len(compatible) == 1
    assert direct[0][0] == "quantity-v1"
    assert direct[0][1] == 1
    assert direct[0][2].source_fingerprint == compatible[0][2].source_fingerprint
    assert direct[0][2].source_fingerprint


def test_quantity_working_box_settings_fingerprint_obeys_all_registered_receiving_aliases():
    common = dict(input_snapshot={}, working_box={"w": 810}, corner_state={},
                  endcap_fw_state={}, endcap_bottom_wrap_state={}, available_parts=(),
                  part_profiles={}, assembly_intent="", ignore_fixed_corner=False,
                  relief_clearance=0.0)
    for model in ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"):
        a = manufacturing_state_fingerprint(**{**common, "input_snapshot": {"model": model}},
                                            settings_values={"w": 100})
        b = manufacturing_state_fingerprint(**{**common, "input_snapshot": {"model": model}},
                                            settings_values={"w": 200})
        assert a == b
    va = manufacturing_state_fingerprint(**{**common, "input_snapshot": {"model": "金庫型"}},
                                         settings_values={"w": 100})
    vb = manufacturing_state_fingerprint(**{**common, "input_snapshot": {"model": "金庫型"}},
                                         settings_values={"w": 200})
    assert va != vb


def test_engine_quantity_owner_no_gui_phase6_import_or_literal_family_routing():
    root = Path(__file__).resolve().parents[1]
    engine = (root / "ae_engine/operator_quantity_manufacturing.py").read_text(encoding="utf-8")
    gui = (root / "phase6_quantity_manufacturing.py").read_text(encoding="utf-8")
    assert "from phase6_" not in engine
    assert "import phase6_" not in engine
    assert 'in ("受電箱", "RECEIVING")' not in engine + gui
    assert "pad_bom_demands_from_committed_snapshot" in engine
    assert "build_operator_quantity_manufacturing_requests" in gui
    assert "resolved_quantity_physical_demands" not in gui

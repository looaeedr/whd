"""#2517 Engine owns one immutable request/result contract for all callers."""
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as engine
import ae_engine.manufacturing_contracts as owner
import phase6_manufacturing_contracts as legacy


def test_phase6_and_root_publish_the_identical_engine_contract_objects():
    for name in legacy.__all__:
        assert getattr(legacy, name) is getattr(owner, name)
        assert getattr(engine, name) is getattr(owner, name)
        assert getattr(ae_engine, name) is getattr(owner, name)
    source = Path(legacy.__file__).read_text(encoding="utf-8")
    assert "@dataclass" not in source
    assert "def freeze_manufacturing_value(" not in source
    assert "def manufacturing_request_fingerprint(" not in source
    assert "from ae_engine.manufacturing_api import (" in source


def test_immutable_request_fingerprint_preserves_runtime_part_order():
    a = engine.ManufacturingPartInput(part_key="box_body")
    b = engine.ManufacturingPartInput(part_key="head")
    first = engine.ManufacturingResolveRequest(
        canonical_part_keys=("box_body", "head"), parts=(a, b),
        input_snapshot={"set_index": 0, "bay_index": 2, "w": 800},
        settings={"t": 2.0},
    )
    second = legacy.ManufacturingResolveRequest(
        canonical_part_keys=("head", "box_body"), parts=(b, a),
        input_snapshot={"w": 800, "bay_index": 2, "set_index": 0},
        settings={"t": 2.0},
    )
    assert tuple(x.part_key for x in first.parts) == ("box_body", "head")
    assert tuple(x.part_key for x in second.parts) == ("head", "box_body")
    assert engine.manufacturing_request_fingerprint(first) == legacy.manufacturing_request_fingerprint(second)
    assert isinstance(first.input_snapshot["set_index"], int)
    assert isinstance(first.input_snapshot["bay_index"], int)


def test_engine_freeze_thaw_detaches_and_rejects_ui_runtime_objects():
    frozen = engine.freeze_manufacturing_value({"set_index": 0, "quantity": [3]})
    unfrozen = engine.thaw_manufacturing_value(frozen)
    unfrozen["quantity"].append(99)
    assert engine.thaw_manufacturing_value(frozen) == {"set_index": 0, "quantity": [3]}
    assert type(engine.thaw_manufacturing_value(frozen)["set_index"]) is int
    with pytest.raises(TypeError):
        engine.freeze_manufacturing_value(lambda: None)
    class FakeTk:
        __module__ = "tkinter"
    with pytest.raises(TypeError, match="Tk object"):
        engine.freeze_manufacturing_value(FakeTk())


def test_engine_result_contract_cannot_replace_fields():
    result = engine.ManufacturingResolveResult(
        geometry=object(),
        diagnostics=engine.ManufacturingDiagnosticsResult(),
        mutations=engine.ManufacturingMutationResult(),
        effects=engine.ManufacturingEffects(),
        cache=engine.ManufacturingCacheReceipt(),
    )
    with pytest.raises(FrozenInstanceError):
        result.geometry = None
    with pytest.raises(TypeError, match="diagnostics must"):
        engine.ManufacturingResolveResult(
            geometry=object(), diagnostics={}, mutations=result.mutations,
            effects=result.effects, cache=result.cache,
        )

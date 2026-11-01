"""#2517: canonical Receiving NFB tier/CSV sequence belongs to Engine."""
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api, resolve_receiving_nfb_assembly_parts
import ae_engine.receiving_nfb_assembly as owner
import ae_engine.receiving_nfb_layer_physical_parts as layers
import ae_engine.receiving_nfb_committed_final_scene as committed
import phase6_manufacturing_service as service


@pytest.mark.parametrize("model,submitted,should_apply", [
    ("受電箱", True, True),
    ("RECEIVING", True, True),
    ("受電箱", False, False),
    ("受電箱", 1, False),
    ("金庫型", True, False),
    ("", True, False),
])
def test_public_engine_runs_existing_physical_stages_in_exact_order(
    monkeypatch, model, submitted, should_apply,
):
    root = SimpleNamespace(part_key="base_plate")
    expanded = (SimpleNamespace(part_key="base_plate:nfb_layer:0"),)
    final = (SimpleNamespace(part_key="base_plate:nfb_layer:1"),)
    calls = []

    def expand(snapshot, parts):
        calls.append(("expand", tuple(parts)))
        return expanded

    def apply(snapshot, parts):
        calls.append(("apply", tuple(parts)))
        return final

    monkeypatch.setattr(owner, "expand_receiving_nfb_layer_parts", expand)
    monkeypatch.setattr(committed, "apply_committed_csv_v5_to_canonical_parts", apply)
    snapshot = {"model": model, "nfb_config_submitted": submitted}
    actual = resolve_receiving_nfb_assembly_parts(snapshot, (root,))
    assert manufacturing_api.resolve_receiving_nfb_assembly_parts is resolve_receiving_nfb_assembly_parts
    assert calls == ([("expand", (root,)), ("apply", expanded)]
                     if should_apply else [("expand", (root,))])
    assert actual == (final if should_apply else expanded)


def test_committed_csv_errors_reject_without_preparing_fake_scene(monkeypatch):
    first = (SimpleNamespace(part_key="base_plate"),)
    monkeypatch.setattr(
        owner, "expand_receiving_nfb_layer_parts", lambda snapshot, parts: first,
    )
    def fail(snapshot, parts):
        assert parts == first
        raise ValueError("NFB_COMMITTED_CSV_REAL_BASE_PART_MISSING")
    monkeypatch.setattr(committed, "apply_committed_csv_v5_to_canonical_parts", fail)
    with pytest.raises(ValueError, match="NFB_COMMITTED_CSV_REAL_BASE_PART_MISSING"):
        resolve_receiving_nfb_assembly_parts(
            {"model": "受電箱", "nfb_config_submitted": True}, first,
        )


def test_engine_layer_builder_has_no_reverse_gui_type_dependency():
    source = inspect.getsource(layers.expand_receiving_nfb_layer_parts)
    assert "phase6_final_scene_contracts" not in source
    assert "AssemblyScenePart(" not in source
    assert "generated.append(replace(root," in source


def test_phase6_only_consumes_public_engine_manufacturing_sequence():
    source = inspect.getsource(service.resolve)
    assert "resolve_receiving_nfb_assembly_parts(snapshot, parts)" in source
    assert "expand_receiving_nfb_layer_parts(" not in source
    assert "apply_committed_csv_v5_to_canonical_parts(" not in source
    assert "nfb_config_submitted" not in source.split(
        "resolved_joint_graph = resolve_manufacturing_joint_graph(", 1
    )[1].split("if not parts:", 1)[0]

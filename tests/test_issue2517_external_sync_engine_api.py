"""#2517 original Settings external source/revision gate belongs to Engine."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import inspect

import pytest

from ae_engine import manufacturing_api
from phase6_settings_transitions import ExternalSyncPlan, plan_external_sync
from phase6_settings_service import Phase6SettingsTransactionService


def _incoming(*, origin="main_gui", revision=2, settings=None):
    return {
        "origin": origin,
        "revision": revision,
        "transaction_id": "operator:2",
        "delta": {"settings": settings or {"w": 812.5, "h": 1650.0}},
    }


@pytest.mark.parametrize("raw,last,status,accepted,revision", [
    (_incoming(), 1, "OK", True, 2),
    (_incoming(origin="CADSplit"), 1, "WRONG_ORIGIN", False, 1),
    (_incoming(revision="invalid"), 1, "INVALID_REVISION", False, 1),
    (_incoming(revision=1), 1, "STALE_REVISION", False, 1),
    (_incoming(revision=0), 1, "STALE_REVISION", False, 0),
])
def test_external_revision_plan_comes_from_same_public_engine_api(
    raw, last, status, accepted, revision,
):
    source = deepcopy(raw)
    direct = manufacturing_api.plan_operator_external_sync(
        source, last_external_revision=last,
    )
    via_gui = plan_external_sync(raw, last_external_revision=last)
    assert direct == via_gui
    assert type(direct) is manufacturing_api.OperatorExternalSyncPlan
    assert ExternalSyncPlan is manufacturing_api.OperatorExternalSyncPlan
    assert direct.reason == status and direct.accepted is accepted
    assert direct.revision == revision
    assert source == raw


def test_engine_returns_detached_immutable_result_and_no_duplicate_physical_state():
    incoming = _incoming(settings={"w": 803.25, "flag": "false"})
    source = deepcopy(incoming)
    plan = manufacturing_api.plan_operator_external_sync(
        incoming, last_external_revision=1,
    )
    assert plan.settings == {"w": 803.25, "flag": "false"}
    with pytest.raises(FrozenInstanceError):
        plan.revision = 3
    plan.settings["w"] = 900.0
    assert incoming == source


def test_service_stages_only_engine_approved_external_transaction():
    service = Phase6SettingsTransactionService(last_external_revision=1)
    assert service.plan_external_sync(_incoming(origin="other")).reason == "WRONG_ORIGIN"
    assert service.last_external_revision == 1
    good = service.plan_external_sync(_incoming())
    assert good.accepted is True
    assert service.last_external_revision == 2
    assert service.last_external_transaction_id == "operator:2"
    retry = service.plan_external_sync(_incoming())
    assert retry.reason == "STALE_REVISION"
    assert retry.settings == {}
    assert service.last_external_revision == 2


def test_gui_only_delegates_external_sync_and_engine_cannot_depend_on_gui():
    import ae_engine.operator_settings_transactions as owner
    import phase6_settings_transitions as gui
    code = inspect.getsource(gui.plan_external_sync)
    assert "manufacturing_api.plan_operator_external_sync(" in code
    assert "int(raw.get(" not in code and "WRONG_ORIGIN" not in code
    engine_code = inspect.getsource(owner)
    assert "from phase6_" not in engine_code
    assert "import tkinter" not in engine_code

"""#2517 Receiving Head/Tail linked Fold live-source routing stays Engine-owned."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
import fold_designer_bridge as bridge


def test_headless_receiving_alias_uses_current_bay_dimensions_not_stale_settings():
    original = {"model":"receiving", "w":800.0, "h":1600.0,
                "d":350.0, "t":2.0, "fw":29.0, "extra":["kept"]}
    settings = {"w":800.0, "h":1600.0, "d":350.0, "fw":29.0}
    live = {"w":820.5, "h":1700.25, "d":360.75}
    before = deepcopy((original, settings, live))
    output = api.project_operator_linked_endcap_source_snapshot(
        original, settings, live,
    )
    assert (output["w"], output["h"], output["d"]) == (820.5,1700.25,360.75)
    assert output["t"] == 2.0 and output["extra"] == ["kept"]
    output["extra"].append("not source")
    assert (original,settings,live)==before
    assert api.project_operator_linked_endcap_source_snapshot(
        dict(original,model="RECEIVING"), settings, live,
    )["w"] == 820.5


def test_headless_vault_and_custom_ignore_receiving_working_box_overrides():
    for family in ("金庫型","VAULT","自訂"):
        original={"model":family,"w":800.0,"h":1600.0,"d":350.0}
        output=api.project_operator_linked_endcap_source_snapshot(
            original,{"w":810.0,"h":1610.0,"d":355.0},
            {"w":820.0,"h":1700.0,"d":360.0},
        )
        assert tuple(output[k] for k in ("w","h","d"))==(810.0,1610.0,355.0)
        assert output["model"] == family


@pytest.mark.parametrize("bad", (True, False, None, "", 0, -8, float("nan"),float("inf"),[]))
def test_headless_invalid_receiving_live_dimensions_fail_closed_without_source_mutation(bad):
    original={"model":"RECEIVING","w":800,"h":1600,"d":350,"t":2}
    settings={"w":800,"h":1600,"d":350}
    working={"w":bad,"h":1600,"d":350}
    before=deepcopy((original,settings,working))
    with pytest.raises((TypeError,ValueError)):
        api.project_operator_linked_endcap_source_snapshot(
            original,settings,working,
        )
    assert (original,settings,working)==before


def _gui_host(*, model="receiving", width=820.5):
    commits=[]
    workspace=SimpleNamespace(
        available_parts=("box_body","head","tail"),
        active_part="box_body",
        stash_profiles=lambda key,profile:commits.append((key,deepcopy(profile))),
    )
    host=SimpleNamespace(
        state=SimpleNamespace(profiles_vault={"箱身":[]}),
        designer_workspace=workspace,
        _phase6_input_snapshot={"model":model,"w":800.0,"h":1600.0,
                                "d":350.0,"t":2.0,"fw":29.0},
        _settings_values={"w":800.0,"h":1600.0,"d":350.0},
        _phase6_box_whd={"w":width,"h":1700.25,"d":360.75},
        _phase6_corner_state={},
        _phase6_corner_pair_same={},
        _phase6_assembly_type="INSERT_OVERLAY",
        _phase6_endcap_fw_state={},
    )
    return host,commits


def test_bridge_linked_endcap_invokes_public_engine_source_and_preserves_live_bay(monkeypatch):
    host,commits=_gui_host()
    queried=[]
    def captured(snapshot,profile):
        queried.append(deepcopy(snapshot))
        return {
            key:{"X":[{"len":1.0,"core":True}],
                 "Y":[{"len":2.0,"core":True}]}
            for key in ("head","tail")
        }
    monkeypatch.setattr(bridge,"build_linked_endcap_xy_profiles",captured)
    before=deepcopy(host._phase6_input_snapshot)
    projected=bridge._phase6_rebuild_linked_endcaps(host)
    assert (queried[0]["w"],queried[0]["h"],queried[0]["d"]) == (
        820.5,1700.25,360.75)
    assert host._phase6_input_snapshot==before
    assert [key for key,_ in commits] == ["head","tail"]
    assert commits[0][1]==projected["head"]
    source=inspect.getsource(bridge._phase6_rebuild_linked_endcaps)
    assert "manufacturing_api.project_operator_linked_endcap_source_snapshot(" in source
    assert 'in {"受電箱", "RECEIVING"}' not in source


def test_bridge_invalid_live_bay_source_does_not_stash_old_or_partial_head_tail(monkeypatch):
    host,commits=_gui_host(width=True)
    called=[]
    monkeypatch.setattr(bridge,"build_linked_endcap_xy_profiles",
                        lambda *a: called.append(True))
    before=deepcopy(host._phase6_input_snapshot)
    with pytest.raises((TypeError,ValueError)):
        bridge._phase6_rebuild_linked_endcaps(host)
    assert not called and not commits
    assert host._phase6_input_snapshot==before

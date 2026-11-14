"""#2517: live Receiving part-dimension refresh must not overlay stale Settings W/H/D."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest
import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import operator_settings_transactions as owner
import fold_designer_bridge as gui


@pytest.mark.parametrize("family", ("受電箱","RECEIVING","receiving","ReCeIvInG"))
def test_receiving_part_dimension_settings_overlay_preserves_committed_bay(family):
    snapshot={"model":family,"w":820.5,"h":1700.25,"d":360.75,"t":2}
    settings={"w":800,"h":1600,"d":350,"t":2.25,"fw":27}
    before=deepcopy((snapshot,settings))
    projected=api.project_operator_part_dimension_settings_overlay(snapshot,settings)
    assert projected == {"t":2.25,"fw":27}
    assert (snapshot,settings)==before
    projected["fw"]=199
    assert settings["fw"]==27


@pytest.mark.parametrize("family", ("金庫型","VAULT","RO","自訂",""))
def test_other_families_preserve_original_settings_overlays(family):
    snapshot={"model":family,"w":500,"h":600,"d":250}
    settings={"w":510,"h":620,"d":275,"t":2}
    projected=api.project_operator_part_dimension_settings_overlay(snapshot,settings)
    assert projected==settings
    assert projected is not settings


def test_public_engine_facade_and_package_share_single_owner():
    assert (api.project_operator_part_dimension_settings_overlay
            is ae_engine.project_operator_part_dimension_settings_overlay
            is owner.project_operator_part_dimension_settings_overlay)


def test_gui_recalculation_delegates_source_priority_and_does_not_edit_saved_dimensions(monkeypatch):
    snapshot={"model":"receiving","w":820.5,"h":1700.25,"d":360.75,"t":2}
    settings={"w":800,"h":1600,"d":350,"t":2.25}
    raw=deepcopy(settings)
    inspected=[]
    def project(source):
        inspected.append(deepcopy(source))
        return {"box_body":{"w":source["w"],"h":source["h"],"d":source["d"]}}
    monkeypatch.setattr(gui,"project_part_dimensions",project)
    app=SimpleNamespace(_phase6_input_snapshot=deepcopy(snapshot),_settings_values=settings)
    dims=gui._phase6_recalculate_part_dimensions(app)
    assert inspected and tuple(inspected[0][k] for k in ("w","h","d"))==(820.5,1700.25,360.75)
    assert inspected[0]["t"]==2.25
    assert dims["box_body"]["w"]==820.5
    assert tuple(app._phase6_input_snapshot[k] for k in ("w","h","d"))==(820.5,1700.25,360.75)
    assert app._phase6_input_snapshot["part_dimensions"] == dims
    assert settings==raw
    source=inspect.getsource(gui._phase6_recalculate_part_dimensions)
    assert "manufacturing_api.project_operator_part_dimension_settings_overlay(" in source
    assert "operator_canonical_family_name" not in source
    assert 'settings.pop(axis, None)' not in source

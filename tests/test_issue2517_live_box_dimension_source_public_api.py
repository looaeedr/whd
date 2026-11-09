"""#2517 live operator W/H/D must be validated by the public Engine before GUI writes."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest
import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import operator_settings_transactions as owner
import fold_designer_bridge as bridge


class Var:
    def __init__(self, value): self.value=value
    def get(self): return self.value
    def set(self, value): self.value=value


def host(*, key="box_body", w="820.25", h="1600.5", d="360.75"):
    return SimpleNamespace(
        active_part_key=key,
        v_w=Var(w), v_h=Var(h), v_d=Var(d),
        _phase6_box_whd={"w":800,"h":1600,"d":350},
        _phase6_input_snapshot={"model":"受電箱","t":2,"w":800,"h":1600,"d":350},
        _phase6_last_w=800.0, _phase6_last_d=350.0,
        _phase6_sync_ready=False,
        _phase6_part_profiles={},
        state=SimpleNamespace(profiles={"X":[],"Y":[]}),
    )


def test_package_facade_and_original_owner_share_public_function():
    assert (ae_engine.normalize_operator_live_box_dimensions
            is api.normalize_operator_live_box_dimensions
            is owner.normalize_operator_live_box_dimensions)


def test_public_engine_preserves_exact_fractional_live_outside_dimensions_and_source():
    raw={"w":"820.25","h":1600.5,"d":"360.75"}
    before=deepcopy(raw)
    result=api.normalize_operator_live_box_dimensions(raw)
    assert result=={"w":820.25,"h":1600.5,"d":360.75}
    assert raw==before and result is not raw


@pytest.mark.parametrize("field", ("w","h","d"))
@pytest.mark.parametrize("invalid", (True,False,None,"","bad",0,-1,float("nan"),float("inf")))
def test_illegal_live_box_source_fails_closed_without_mutation(field,invalid):
    raw={"w":"820.25","h":1600.5,"d":"360.75"}
    raw[field]=invalid
    before=deepcopy(raw)
    with pytest.raises((ValueError,TypeError)):
        api.normalize_operator_live_box_dimensions(raw)
    assert raw==before


@pytest.mark.parametrize("key", ("box_body","door"))
def test_gui_save_uses_engine_exact_live_box_before_any_legacy_renderer(key,monkeypatch):
    app=host(key=key)
    called=[]
    monkeypatch.setattr(bridge,"_phase6_receiving_layout_applicable",lambda *_:False)
    monkeypatch.setattr(bridge,"_propagate_endcap_derived_cores",lambda *_:None)
    monkeypatch.setattr(bridge,"_FIX10_DO_UPDATE",lambda *_:"BOX_DONE")
    monkeypatch.setattr(bridge,"_phase6_render_with_engine_live_dimensions",lambda *_:"PART_DONE")
    result=bridge._fix11_do_update(app)
    assert app._phase6_box_whd=={"w":820.25,"h":1600.5,"d":360.75}
    assert tuple(app._phase6_input_snapshot[k] for k in ("w","h","d"))==(820.25,1600.5,360.75)
    assert result==("BOX_DONE" if key=="box_body" else "PART_DONE")
    source=inspect.getsource(bridge._fix11_do_update)
    assert "normalize_operator_live_box_dimensions(" in source
    assert "original.get_int(self.v_w.get())" not in source
    assert "original.get_int(self.v_h.get())" not in source
    assert "original.get_int(self.v_d.get())" not in source


def test_gui_invalid_box_source_refuses_before_receiving_bay_commit(monkeypatch):
    app=host(w="nan")
    mutation=[]
    monkeypatch.setattr(bridge,"_phase6_receiving_layout_applicable",lambda *_:True)
    monkeypatch.setattr(bridge,"_phase6_commit_receiving_current_bay_controls",lambda *_:mutation.append(1))
    before=deepcopy((app._phase6_box_whd,app._phase6_input_snapshot))
    with pytest.raises((ValueError,TypeError)):
        bridge._fix11_do_update(app)
    assert mutation==[]
    assert (app._phase6_box_whd,app._phase6_input_snapshot)==before


def test_endcap_edit_preserves_exact_outside_w_h_d_and_calls_existing_engine_reconcile(monkeypatch):
    app=host(key="head")
    calls=[]
    original=api.reconcile_endcap_live_outside_dimensions
    def captured(*args,**kwargs):
        calls.append(deepcopy(kwargs))
        return original(*args,**kwargs)
    monkeypatch.setattr(api,"reconcile_endcap_live_outside_dimensions",captured)
    monkeypatch.setattr(bridge,"_propagate_endcap_derived_cores",lambda *_:None)
    bridge._sync_active_endcap_and_global_whd(app)
    assert calls
    assert calls[0]["top_width"]==820.25
    assert calls[0]["top_depth"]==360.75
    assert app._phase6_box_whd=={"w":820.25,"h":1600.5,"d":360.75}
    assert tuple(app._phase6_input_snapshot[k] for k in ("w","h","d"))==(820.25,1600.5,360.75)


def test_endcap_bad_height_never_mutates_box_or_saved_snapshot(monkeypatch):
    app=host(key="tail",h="bad")
    before=deepcopy((app._phase6_box_whd,app._phase6_input_snapshot))
    called=[]
    monkeypatch.setattr(api,"reconcile_endcap_live_outside_dimensions",lambda *a,**k:called.append(1))
    with pytest.raises((ValueError,TypeError)):
        bridge._sync_active_endcap_and_global_whd(app)
    assert not called
    assert (app._phase6_box_whd,app._phase6_input_snapshot)==before

from types import SimpleNamespace

import fold_designer_bridge as bridge


class Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return str(self.value)


def test_box_body_update_never_changes_editor_active_bend_to_part_label(monkeypatch):
    seen = []
    def fake_fix10(self):
        seen.append(self.state.active_bend)
        return "ok"

    monkeypatch.setattr(bridge, "_FIX10_DO_UPDATE", fake_fix10)
    monkeypatch.setattr(bridge, "_propagate_endcap_derived_cores", lambda *args, **kwargs: None)

    app = SimpleNamespace(
        active_part_key="box_body",
        state=SimpleNamespace(active_bend="X"),
        v_w=Var(400), v_h=Var(600), v_d=Var(250),
        _phase6_input_snapshot={},
    )

    assert bridge._fix11_do_update(app) == "ok"
    assert seen == ["X"]
    assert app.state.active_bend == "X"


def test_profile_key_resolution_falls_back_to_real_profile_key():
    assert bridge._phase6_resolve_profile_key({"X": [1]}, "箱身") == "X"
    assert bridge._phase6_resolve_profile_key({"X": [1], "Y": [2]}, "Y") == "Y"

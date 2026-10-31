"""#2517: legacy EndCap three-row Fold/readback uses Engine, not Phase6 formula."""
import inspect
import pytest
from ae_engine import manufacturing_api, build_endcap_editor_simple_profile, read_endcap_editor_simple_profile
from phase6_fold_profiles import build_endcap_profile, read_endcap_profile


@pytest.mark.parametrize("t,top,d,bottom", [(2.0, 16, 200, 15), (1.5, 24, 350, 18)])
def test_same_three_real_fold_segments_in_engine_and_gui(t, top, d, bottom):
    snapshot = {"model": "受電箱", "t": t, "ytop1": top, "d": d, "ybottom1": bottom}
    rows = build_endcap_editor_simple_profile(snapshot)
    assert build_endcap_editor_simple_profile is manufacturing_api.build_endcap_editor_simple_profile
    assert rows == build_endcap_profile(snapshot)
    assert [r["phase6_key"] for r in rows] == ["ytop1", "endcap_d", "ybottom1"]
    assert [r.get("angle") for r in rows] == [-90, -90, None]
    assert [r.get("ui_len_add") for r in rows] == [t, 2*t, t]
    assert read_endcap_editor_simple_profile is manufacturing_api.read_endcap_editor_simple_profile
    assert read_endcap_editor_simple_profile(rows) == read_endcap_profile(rows) == {
        "ytop1": top, "d": d, "ybottom1": bottom,
    }


def test_endcap_simple_fold_missing_role_refused():
    with pytest.raises(ValueError, match="折彎資料缺少"):
        read_endcap_editor_simple_profile([{"phase6_key": "ytop1", "len": 16}])


def test_phase6_profile_is_only_public_engine_api_caller():
    text = inspect.getsource(build_endcap_profile) + inspect.getsource(read_endcap_profile)
    assert "manufacturing_api.build_endcap_editor_simple_profile(" in text
    assert "manufacturing_api.read_endcap_editor_simple_profile(" in text
    assert "apply_outside_dimension_compensation(" not in text

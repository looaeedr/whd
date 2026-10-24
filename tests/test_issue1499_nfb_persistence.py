# -*- coding: utf-8 -*-
"""#1499 Receiving NFBConfig submission, Bay and quantity versions, v3 no-drop."""
import json
from copy import deepcopy

import pytest

from ae_engine.receiving_layout import (
    new_receiving_layout, normalize_receiving_layout,
    resize_receiving_bays, update_receiving_bay,
    project_receiving_bay_legacy_aliases,
)
from ae_engine.receiving_nfb_persistence import (
    normalize_nfb_config, normalize_nfb_saved_fields,
)
from phase6_quantity_model import (
    SCHEMA, SCHEMA_V2, QuantityModel,
)
from phase6_project_file import (
    PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V2, PROJECT_SCHEMA_V3,
    write_project, read_project,
)


def _config(*, x=0, state="CONFIRMED", filename="400_140X257_107.dxf"):
    return {
        "holes": [{
            "physical_hole_id": "nfb:upper:layer:1:unit:1",
            "model_filename": filename,
            "manual_x_state": state,
            "manual_x_mm": x,
            "datum_revision": "w800t2-rev1",
            "datum_snapshot": {"width": 800, "thickness": 2},
            "rotation_deg": 90,
            "operator_offset_mm": [0, 5],
        }],
        "layer_count": 1, "quantity": 2,
    }


def _layout():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    return resize_receiving_bays(layout, set_index=0, bay_count=2)


def _payload(layout, *, schema=PROJECT_SCHEMA_V1):
    return {"schema": schema, "snapshot": {
        "model": "受電箱", "active_mode": "set_bay",
        "receiving_layout": layout,
    }}


def test_unconfigured_bay_and_quantity_keep_legacy_schema(tmp_path):
    file = write_project(tmp_path / "old.p6fold", _payload(_layout()))
    raw = json.loads(file.read_text(encoding="utf-8"))
    assert raw["schema"] == PROJECT_SCHEMA_V2
    assert all("nfb_config" not in b
               for s in raw["snapshot"]["receiving_layout"]["sets"]
               for b in s["bays"])
    reloaded = read_project(file)
    assert reloaded["schema"] == PROJECT_SCHEMA_V2
    assert SCHEMA == "phase6-quantity-v1"
    assert QuantityModel().snapshot()["schema"] == SCHEMA


def test_submitted_bay_save_reload_v3_retains_exact_zero_and_independent_copy(tmp_path):
    layout = _layout()
    config = _config(x=0)
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=1,
        nfb_config_submitted=True, nfb_config=config,
    )
    copy = resize_receiving_bays(layout, set_index=0, bay_count=3)
    original = copy["sets"][0]["bays"][1]["nfb_config"]
    clone = copy["sets"][0]["bays"][2]["nfb_config"]
    assert clone["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert original["holes"][0]["manual_x_state"] == "CONFIRMED"
    clone["holes"][0]["manual_x_mm"] = 100
    assert original["holes"][0]["manual_x_mm"] == 0
    assert config["holes"][0]["manual_x_mm"] == 0
    file = write_project(tmp_path / "nfb-bay.p6fold", _payload(copy))
    raw = json.loads(file.read_text(encoding="utf-8"))
    assert raw["schema"] == PROJECT_SCHEMA_V3
    rows = raw["snapshot"]["receiving_layout"]["sets"][0]["bays"]
    assert rows[1]["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    assert "nfb_config_submitted" not in rows[0]
    restored = read_project(file)["snapshot"]
    reloaded_rows = restored["receiving_layout"]["sets"][0]["bays"]
    assert reloaded_rows[1]["nfb_config"]["holes"][0]["datum_snapshot"] == {
        "width": 800, "thickness": 2,
    }
    assert reloaded_rows[2]["nfb_config"]["holes"][0]["manual_x_mm"] == 100
    assert project_receiving_bay_legacy_aliases(
        restored, set_index=0, bay_index=0, validate_common=False,
    ).get("nfb_config_submitted") is None


def test_confirmed_x_zero_is_not_missing_and_none_is_not_zero():
    good = normalize_nfb_config(_config(x=0))
    assert good["holes"][0]["manual_x_mm"] == 0
    with pytest.raises(ValueError, match="requires explicit numeric"):
        normalize_nfb_config(_config(x=None))
    n = normalize_nfb_config(_config(x=None, state="NONE"))
    assert n["holes"][0]["manual_x_mm"] is None
    assert normalize_nfb_saved_fields({
        "nfb_config_submitted": False, "nfb_config": _config(),
    }) == {}


def test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate():
    q = QuantityModel()
    q.set_version_nfb_config(q.selected_version_id, submitted=True, config=_config())
    assert q.snapshot()["schema"] == SCHEMA_V2
    v2 = q.add_version()
    assert q.nfb_config_for_version(v2)["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert q.nfb_config_for_version("quantity-v1")["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"
    saved = q.snapshot()
    restored = QuantityModel.from_payload(saved)
    restored.set_version_nfb_config(v2, submitted=True, config=_config(x=200))
    assert restored.nfb_config_for_version("quantity-v1")["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    restored.set_version_nfb_config(v2, submitted=False)
    assert restored.snapshot()["schema"] == SCHEMA_V2
    restored.set_version_nfb_config("quantity-v1", submitted=False)
    assert restored.snapshot()["schema"] == SCHEMA
    assert all("nfb_config" not in row for row in restored.snapshot()["versions"])


def test_quantity_p6fold_root_and_embedded_version_schema_upgrade_together(tmp_path):
    q=QuantityModel()
    q.set_version_nfb_config(q.selected_version_id, submitted=True, config=_config(x=0))
    payload={"schema": PROJECT_SCHEMA_V1, "snapshot": {
        "model":"受電箱", "active_mode":"quantity", "quantity":q.snapshot(),
        "receiving_quantity_box":{
            "w":800, "h":1600, "d":350,
        },
    }}
    output=write_project(tmp_path/"quantity-nfb.p6fold",payload)
    data=json.loads(output.read_text(encoding="utf-8"))
    assert data["schema"] == PROJECT_SCHEMA_V3
    assert data["snapshot"]["quantity"]["schema"] == SCHEMA_V2
    assert "receiving_layout" not in data["snapshot"]
    loaded=read_project(output)
    assert loaded["schema"] == PROJECT_SCHEMA_V3
    assert loaded["snapshot"]["quantity"]["versions"][0]["nfb_config"]["holes"][0]["manual_x_mm"] == 0


def test_old_schema_reader_must_not_silently_strip_new_nfb_scope(tmp_path):
    layout=update_receiving_bay(
        _layout(), set_index=0,bay_index=0,
        nfb_config_submitted=True,nfb_config=_config(),
    )
    output=write_project(tmp_path/"new.p6fold",_payload(layout))
    raw=json.loads(output.read_text(encoding="utf-8"))
    for legacy in (PROJECT_SCHEMA_V1,PROJECT_SCHEMA_V2):
        corrupted=deepcopy(raw)
        corrupted["schema"]=legacy
        file=tmp_path/f"downgraded-{legacy}.p6fold"
        file.write_text(json.dumps(corrupted,ensure_ascii=False),encoding="utf-8")
        with pytest.raises(ValueError,match="old schema"):
            read_project(file)
    with pytest.raises(ValueError,match="孔型版本"):
        QuantityModel.from_payload({
            "schema":"phase6-quantity-v1",
            "versions":[{
                "version_id":"quantity-v1","piece_count":1,
                "head_features":[],"tail_features":[],
                "nfb_config_submitted":True,"nfb_config":_config(),
            }],"selected_version_id":"quantity-v1","next_version_number":2,
        })


def test_derived_flags_not_saved_and_invalid_nfb_fails_without_fallback(tmp_path):
    layout=_layout()
    bad=_config()
    bad["readiness"]="READY"
    with pytest.raises(ValueError,match="derived"):
        update_receiving_bay(
            layout, set_index=0,bay_index=0,
            nfb_config_submitted=True,nfb_config=bad,
        )
    assert normalize_receiving_layout(layout)["sets"][0]["bays"][0].get("nfb_config") is None
    with pytest.raises(ValueError,match="must preserve its actual NFBConfig"):
        update_receiving_bay(
            layout, set_index=0,bay_index=0,nfb_config_submitted=True,
        )
    with pytest.raises(ValueError,match="boolean"):
        update_receiving_bay(
            layout, set_index=0,bay_index=0,
            nfb_config_submitted="true",nfb_config=_config(),
        )


def test_receiving_bay_width_change_requires_nfb_x_reconfirmation_and_preserves_sibling(tmp_path):
    """Changing W invalidates old X datum without deleting model/position."""
    layout = _layout()
    for index in (0, 1):
        layout = update_receiving_bay(
            layout, set_index=0, bay_index=index,
            nfb_config_submitted=True,
            nfb_config=_config(x=0 if index == 0 else 100),
        )
    original = deepcopy(layout)
    same = update_receiving_bay(layout, set_index=0, bay_index=0, width=800)
    assert same["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"

    changed = update_receiving_bay(layout, set_index=0, bay_index=0, width=750)
    left, right = changed["sets"][0]["bays"]
    assert left["width"] == 750
    assert left["nfb_config_submitted"] is True
    moved = left["nfb_config"]["holes"][0]
    assert moved["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert moved["manual_x_mm"] == 0
    assert moved["datum_revision"] == "w800t2-rev1"
    assert moved["datum_snapshot"] == {"width": 800, "thickness": 2}
    assert moved["model_filename"] == _config()["holes"][0]["model_filename"]
    assert right == original["sets"][0]["bays"][1]
    assert layout == original

    # Returning to W800 or issuing a same-width update cannot resurrect the
    # previous operator confirmation, and Save→Reload cannot grant it.
    returned = update_receiving_bay(changed, set_index=0, bay_index=0, width=800)
    returned = update_receiving_bay(returned, set_index=0, bay_index=0, width=800)
    assert returned["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    project = write_project(tmp_path / "changed-bay.p6fold", _payload(returned))
    reopened = read_project(project)["snapshot"]["receiving_layout"]["sets"][0]["bays"]
    assert reopened[0]["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert reopened[0]["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    assert reopened[1] == original["sets"][0]["bays"][1]


def test_receiving_bay_width_and_new_nfb_config_cannot_smuggle_stale_confirmed_x():
    layout = _layout()
    # Same operation changing geometry and installing a legacy W800-confirmed
    # configuration must not escape the invalidation gate.
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=0, width=750,
        nfb_config_submitted=True, nfb_config=_config(x=0),
    )
    hole = layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
    assert hole["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert hole["manual_x_mm"] == 0

    # Even without a simultaneous W edit, a W800 datum may not be
    # imported into an existing W750 Bay as a new "CONFIRMED" source.
    stale = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=_config(x=8),
    )
    assert stale["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    # Explicit operator-confirmed W750 datum is a different, now-current
    # source and should not need a gratuitous second confirmation.
    new_basis = _config(x=8)
    new_basis["holes"][0]["datum_snapshot"]["width"] = 750
    stable = update_receiving_bay(
        stale, set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=new_basis,
    )
    assert stable["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"
    for state in ("NONE", "UNVERIFIED_BASIS", "RECONFIRM_REQUIRED"):
        config = _config(x=0, state=state)
        fresh = update_receiving_bay(
            stable, set_index=0, bay_index=0,
            width=780, nfb_config_submitted=True, nfb_config=config,
        )
        assert fresh["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == state


@pytest.mark.parametrize("basis_key", [
    "width", "w", "box_width_mm", "bay_width_mm", "outer_width_mm",
])
def test_receiving_bay_saved_mismatched_datum_is_invalidated_during_load(
    tmp_path, basis_key,
):
    # A mismatched CONFIRMED state must be corrected at the canonical layout
    # boundary, including old projects that bypassed the new edit callbacks.
    source = update_receiving_bay(
        _layout(), set_index=0, bay_index=0, width=750,
    )
    config = _config(x=0)
    config["holes"][0]["datum_snapshot"] = {basis_key: 800, "thickness": 2}
    injected = deepcopy(source)
    injected["sets"][0]["bays"][0]["nfb_config_submitted"] = True
    injected["sets"][0]["bays"][0]["nfb_config"] = deepcopy(config)
    before = deepcopy(injected)
    canonical = normalize_receiving_layout(injected)
    assert injected == before
    hole = canonical["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
    assert hole["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert hole["manual_x_mm"] == 0
    assert hole["datum_snapshot"][basis_key] == 800
    saved = write_project(tmp_path / f"mismatch-{basis_key}.p6fold", _payload(injected))
    reloaded = read_project(saved)["snapshot"]["receiving_layout"]["sets"][0]["bays"][0]
    assert reloaded["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"


def test_matching_new_width_basis_can_be_explicitly_reconfirmed_without_guesswork():
    layout = update_receiving_bay(
        _layout(), set_index=0, bay_index=0, width=750,
    )
    config = _config(x=0)
    config["holes"][0]["datum_snapshot"] = {"width": 750, "thickness": 2}
    committed = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=config,
    )
    hole = committed["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
    assert hole["manual_x_state"] == "CONFIRMED"
    assert hole["manual_x_mm"] == 0
    assert hole["datum_snapshot"]["width"] == 750


@pytest.mark.parametrize("recorded_datum_width, expected_state", [
    (750, "CONFIRMED"),
    (800, "RECONFIRM_REQUIRED"),
])
def test_old_project_numeric_string_width_respects_current_x_reconfirmation(
    recorded_datum_width, expected_state,
):
    raw = _layout()
    bay = raw["sets"][0]["bays"][0]
    bay["width"] = "750"  # Original Receiving parser accepts numeric text.
    config = _config(x=0)
    config["holes"][0]["datum_snapshot"] = {
        "width": recorded_datum_width, "thickness": 2,
    }
    bay["nfb_config_submitted"] = True
    bay["nfb_config"] = config
    normalized = normalize_receiving_layout(raw)
    checked = normalized["sets"][0]["bays"][0]
    assert checked["width"] == pytest.approx(750)
    assert checked["nfb_config"]["holes"][0]["manual_x_state"] == expected_state


@pytest.mark.parametrize("datum", [
    {"reference": "OLD_ABSOLUTE_X_REFERENCE"},
    {"height": 1600, "inner_door": "upper"},
    {"width": 800, "w": 750},
])
def test_current_csv_v5_missing_world_x_width_basis_cannot_stay_confirmed(
    tmp_path, datum,
):
    """A V5 numerical identity does not establish a manufactured world-X datum.

    Keep exact user X (including zero), model, revision and saved snapshot,
    but require human reconfirmation when the actual Bay width cannot be
    established unambiguously from the submitted per-hole datum.  Saving and
    reopening must never resurrect stale CONFIRMED authority.
    """
    model = "nfbv5:士林:2P400"
    source = _layout()
    user = _config(x=0, filename=model)
    user["holes"][0]["datum_snapshot"] = deepcopy(datum)
    user["holes"][0]["datum_revision"] = "operator-basis-rev1"
    original = deepcopy(user)
    layout = update_receiving_bay(
        source, set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=user,
    )
    assert user == original
    assert source == _layout()
    affected, sibling = layout["sets"][0]["bays"]
    assert affected["nfb_config_submitted"] is True
    hole = affected["nfb_config"]["holes"][0]
    assert hole["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert hole["manual_x_mm"] == 0
    assert hole["datum_snapshot"] == datum
    assert hole["datum_revision"] == "operator-basis-rev1"
    assert hole["model_filename"] == model
    assert sibling == source["sets"][0]["bays"][1]
    path = write_project(tmp_path / "v5-ambiguous-x.p6fold", _payload(layout))
    reopened = read_project(path)["snapshot"]["receiving_layout"]["sets"][0]["bays"][0]
    assert reopened["nfb_config_submitted"] is True
    assert reopened["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert reopened["nfb_config"]["holes"][0]["manual_x_mm"] == 0


def test_current_csv_v5_matching_world_x_width_basis_preserves_explicit_confirmed_zero():
    """Do not invalidate a genuinely width-matched current CSV V5 owner."""
    model = "nfbv5:士林:2P400"
    config = _config(x=0, filename=model)
    config["holes"][0]["datum_snapshot"] = {"w": 800, "inner_door": "upper"}
    layout = update_receiving_bay(
        _layout(), set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=config,
    )
    hole = layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
    assert hole["manual_x_state"] == "CONFIRMED"
    assert hole["manual_x_mm"] == 0
    assert hole["datum_snapshot"]["w"] == 800


def test_quantity_common_width_invalidates_only_stale_version_x_across_save_reload(
    tmp_path,
):
    """#1504 X safety: version-owned NFB X cannot outlive shared cabinet W.

    V1 carries a formerly legitimate W800 datum, V2 explicitly confirms
    W750.  Changing shared physical W to 750 must demote ONLY V1 and never
    mutate the caller, discard models, or change quantity/version identity.
    """
    from phase6_quantity_model import normalize_quantity_snapshot

    model = QuantityModel()
    v1 = model.selected_version_id
    old = _config(x=0, filename="nfbv5:士林:2P400")
    model.set_version_nfb_config(v1, submitted=True, config=old)
    v2 = model.add_version()
    confirmed = _config(x=90, filename="nfbv5:士林:2P400")
    confirmed["holes"][0]["datum_snapshot"]["width"] = 750
    confirmed["holes"][0]["physical_hole_id"] = "nfb:quantity:version2"
    model.set_version_nfb_config(v2, submitted=True, config=confirmed)
    model.set_piece_count(2)
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": model.snapshot(),
        "receiving_quantity_box": {"w": 750, "h": 1600, "d": 350},
    }
    before = deepcopy(snapshot)
    normalized = normalize_quantity_snapshot(snapshot)
    assert snapshot == before
    rows = normalized["quantity"]["versions"]
    assert tuple(row["version_id"] for row in rows) == (v1, v2)
    assert tuple(row["piece_count"] for row in rows) == (1, 2)
    assert rows[0]["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert rows[0]["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    assert rows[0]["nfb_config"]["holes"][0]["datum_snapshot"]["width"] == 800
    assert rows[1]["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"
    assert rows[1]["nfb_config"]["holes"][0]["manual_x_mm"] == 90
    assert rows[1]["nfb_config"]["holes"][0]["datum_snapshot"]["width"] == 750
    assert all(row["nfb_config_submitted"] is True for row in rows)
    assert model.nfb_config_for_version(v1)["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"

    filename = write_project(
        tmp_path / "quantity-width-reconfirm.p6fold",
        {"schema": PROJECT_SCHEMA_V1, "snapshot": snapshot},
    )
    raw = json.loads(filename.read_text(encoding="utf-8"))
    assert raw["schema"] == PROJECT_SCHEMA_V3
    saved_rows = raw["snapshot"]["quantity"]["versions"]
    assert saved_rows[0]["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert saved_rows[1]["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"
    loaded = read_project(filename)["snapshot"]
    restored_rows = loaded["quantity"]["versions"]
    assert restored_rows == saved_rows
    assert loaded["receiving_quantity_box"]["w"] == 750


@pytest.mark.parametrize("basis", [
    {"width": 800},
    {"width": 800, "w": 750},
    {"height": 1600, "inner_door": "upper"},
])
def test_quantity_current_v5_untrusted_or_conflicting_width_cannot_publish_confirmed_x(
    basis,
):
    from phase6_quantity_model import normalize_quantity_snapshot

    model = QuantityModel()
    candidate = _config(x=0, filename="nfbv5:士林:2P400")
    candidate["holes"][0]["datum_snapshot"] = basis
    model.set_version_nfb_config(
        model.selected_version_id, submitted=True, config=candidate,
    )
    state = {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": model.snapshot(),
        "receiving_quantity_box": {"w": 750, "h": 1600, "d": 350},
    }
    reviewed = normalize_quantity_snapshot(state)
    saved = reviewed["quantity"]["versions"][0]["nfb_config"]["holes"][0]
    assert saved["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert saved["manual_x_mm"] == 0
    assert saved["datum_snapshot"] == basis
    assert state["quantity"]["versions"][0]["nfb_config"]["holes"][0][
        "manual_x_state"
    ] == "CONFIRMED"


def test_quantity_live_projection_rechecks_shared_w_against_version_x_before_render():
    """Selected version must not export a stale confirmed X into its live Bay."""
    from ae_engine.receiving_quantity_box import project_common_box

    model = QuantityModel()
    old = _config(x=0, filename="nfbv5:士林:2P400")
    model.set_version_nfb_config(
        model.selected_version_id, submitted=True, config=old,
    )
    snapshot = {
        "model": "受電箱", "active_mode": "quantity", "t": 2,
        "receiving_quantity_box": {"w": 750, "h": 1600, "d": 350},
        "quantity": model.snapshot(),
    }
    untouched = deepcopy(snapshot)
    view = project_common_box(snapshot)
    assert snapshot == untouched
    assert view["w"] == 750
    projected = view["receiving_layout"]["sets"][0]["bays"][0]
    root = view["nfb_config"]["holes"][0]
    version = view["quantity"]["versions"][0]["nfb_config"]["holes"][0]
    assert projected["nfb_config"]["holes"][0] == root == version
    assert root["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert root["manual_x_mm"] == 0
    assert root["datum_snapshot"]["width"] == 800
    assert model.nfb_config_for_version(
        model.selected_version_id
    )["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"

    # Explicitly re-confirming against today's W750 is legal and stable,
    # without a second confirmation or a synthetic global X formula.
    fresh = _config(x=0, filename="nfbv5:士林:2P400")
    fresh["holes"][0]["datum_snapshot"]["width"] = 750
    model.set_version_nfb_config(
        model.selected_version_id, submitted=True, config=fresh,
    )
    new_source = {**snapshot, "quantity": model.snapshot()}
    projected_valid = project_common_box(new_source)
    accepted = projected_valid["receiving_layout"]["sets"][0]["bays"][0][
        "nfb_config"
    ]["holes"][0]
    assert accepted["manual_x_state"] == "CONFIRMED"
    assert accepted["manual_x_mm"] == 0


@pytest.mark.parametrize("invalid_state", [[], {"state": "CONFIRMED"}, ["NONE"]])
def test_r6_manual_116_rejects_unhashable_saved_x_state_at_all_source_owners(invalid_state):
    """Corrupt JSON must raise the same validation error, not leak TypeError."""
    damaged = _config(state=invalid_state)
    original = deepcopy(damaged)
    with pytest.raises(ValueError, match="manual_x_state unsupported"):
        normalize_nfb_config(damaged)
    with pytest.raises(ValueError, match="manual_x_state unsupported"):
        normalize_nfb_saved_fields({
            "nfb_config_submitted": True, "nfb_config": damaged,
            "width": 800,
        })
    with pytest.raises(ValueError, match="manual_x_state unsupported"):
        update_receiving_bay(
            _layout(), set_index=0, bay_index=0,
            nfb_config_submitted=True, nfb_config=damaged,
        )
    quantity = QuantityModel()
    before = quantity.snapshot()
    with pytest.raises(ValueError, match="manual_x_state unsupported"):
        quantity.set_version_nfb_config(
            quantity.selected_version_id, submitted=True, config=damaged,
        )
    assert quantity.snapshot() == before
    assert damaged == original
    # Real legacy manual X confirmations still retain their physical datum.
    accepted = normalize_nfb_config(_config(x=0, state="CONFIRMED"))
    assert accepted["holes"][0]["manual_x_mm"] == 0
    assert accepted["holes"][0]["manual_x_state"] == "CONFIRMED"


def test_r6_manual_116_huge_json_integer_is_a_controlled_invalid_nfb_dimension():
    """Finite manufacture coordinates cannot skip validation via float overflow."""
    damaged = _config(x=10 ** 400, state="CONFIRMED")
    with pytest.raises(ValueError, match="must be finite"):
        normalize_nfb_config(damaged)
    with pytest.raises(ValueError, match="must be finite"):
        normalize_nfb_saved_fields({
            "nfb_config_submitted": True, "nfb_config": damaged,
        })

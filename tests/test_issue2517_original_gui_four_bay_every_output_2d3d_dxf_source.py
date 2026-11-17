"""#2517 original GUI all-selected Receiving output: actual per-sheet DXF parity.

Prior saved multi-Set tests reopened every file and counted physical names;
they did not independently compare every emitted CUTTING/BEND/MARKING DXF to
the exact canonical 2D PartRenderData used for manufacturing, across both
Sets after Save→Reload. This records the original Engine verification inputs
while preserving its actual DXF writer and real independent reopen.
"""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_export import (
    resolved_physical_dxf_filename, resolved_physical_render_parts,
)
from ae_engine import receiving_csv_multibay_manufacturing as owner
from tests.test_issue2517_saved_multiset_original_gui_grouped_dxf import (
    _saved_with_real_inner_door_state,
)
from tests.test_issue2517_saved_nfb_pair_real_inner_door_3d_profiles import (
    _fully_profiled_bay_source,
)
from tests.test_issue2517_saved_two_sets_four_bays_bom_collision_gui_dxf import (
    _original_gui_export, BAY_INDICES,
)
import phase6_project_file as project


def _record_genuine_stage_verification(monkeypatch, *, mutate=None):
    original = owner.verify_saved_part_render_data_dxf
    recorded = {}
    calls = []

    def reopen_original(render, staged_path):
        # Preserve the genuine Engine independent DXF-reopen verification:
        # these are exact 2D source objects it certified, NOT reserialized
        # expectation DXFs or fake 2D material.
        proof = original(render, staged_path)
        assert proof.ok, proof.issues
        name = Path(staged_path).name
        assert name not in recorded, name
        recorded[name] = render
        calls.append(name)
        if mutate is not None:
            mutate(len(calls), name)
        return proof

    monkeypatch.setattr(owner, "verify_saved_part_render_data_dxf",
                        reopen_original)
    return recorded, calls


def _verify_every_emitted_2d_against_original_engine(
    source, output, recorded,
):
    names = {f.name for f in output.glob("*.dxf")}
    assert names == set(recorded), (sorted(names - set(recorded)),
                                    sorted(set(recorded) - names))
    assert len(names) == len(recorded) and len(names) >= 40
    namespaces = {}
    for si, bi in BAY_INDICES:
        bay = source["receiving_layout"]["sets"][si]["bays"][bi]
        ns = api.receiving_manufacturing_instance_namespace(
            set_id=source["receiving_layout"]["sets"][si]["stable_id"],
            bay_id=bay["stable_id"],
        )
        assert ns not in namespaces
        namespaces[ns] = (si, bi)
        assert any(name.startswith(ns + "__") for name in names)
    assert len(namespaces) == 4
    for name, render in recorded.items():
        path = output / name
        doc = ezdxf.readfile(path)
        assert doc.audit().errors == [], name
        actual = api.verify_saved_part_render_data_dxf(render, path)
        assert actual.ok, (name, actual.issues)
        layers = {entity.dxf.layer for entity in doc.modelspace()}
        assert "CUTTING" in layers, name
        assert render.material.area > 0, name
        assert any(name.startswith(ns + "__") for ns in namespaces), name
        # Independent physical sources can have no BEND (flat plates).
        assert ("BEND" in layers) == any(
            getattr(primitive, "layer", None) == "BEND"
            for primitive in render.scene.primitives
        ), name
        assert ("MARKING" in layers) == any(
            getattr(primitive, "layer", None) == "MARKING"
            for primitive in render.scene.primitives
        ), name
    assert sum("left_side" in name for name in names) == 4
    assert sum("right_side" in name for name in names) == 4
    assert sum("inner_door" in name and "panel" in name for name in names) == 4
    assert sum("base_plate" in name and "fixing_plate" not in name
               for name in names) == 4
    assert sum("nfb_pad" in name for name in names) == 4
    assert sum("nfb_ear" in name for name in names) >= 4
    return namespaces


def test_four_bays_all_selected_original_gui_all_published_2d_3d_dxf(
    tmp_path, monkeypatch,
):
    saved, original_bytes, current = _saved_with_real_inner_door_state(tmp_path)
    loaded = project.read_project(saved)["snapshot"]
    exact_snapshot = deepcopy(loaded)
    before_provider, before_calls = _fully_profiled_bay_source(current)
    after_provider, after_calls = _fully_profiled_bay_source(loaded)
    for si in (0, 1):
        old = api.project_receiving_set_cross_bay_collision_display_audit(
            current["receiving_layout"], before_provider,
            set_index=si, thickness_mm=current["t"],
        )
        new = api.project_receiving_set_cross_bay_collision_display_audit(
            loaded["receiving_layout"], after_provider,
            set_index=si, thickness_mm=loaded["t"],
        )
        assert new == old
        assert new.complete and new.require_complete()
        assert all(any(k.endswith("::inner_door:upper:panel") for k in bay)
                   for bay in new.physical_keys_by_bay)
        assert new.evaluated_pair_count == (
            len(new.physical_keys_by_bay[0]) *
            len(new.physical_keys_by_bay[1])
        )
    assert before_calls == after_calls == list(BAY_INDICES)

    witnesses, visits = _record_genuine_stage_verification(monkeypatch)
    output = tmp_path / "original-all-five-checkboxes"
    observed, errors, infos = _original_gui_export(
        monkeypatch, loaded, output,
    )
    assert not errors, errors
    assert len(infos) == 1 and observed == list(BAY_INDICES)
    assert len(visits) == len(witnesses)
    namespaces = _verify_every_emitted_2d_against_original_engine(
        loaded, output, witnesses,
    )
    # The Engine's source-owned physical BOM includes selected CUTTING parts,
    # while source-flat fixing plates may be excluded from manufacturing.
    # Do not claim the full BOM is already welded/approved by this test.
    for si, bi in BAY_INDICES:
        geometry = after_provider(si, bi)
        full = dict(resolved_physical_render_parts(
            geometry, include_unreleased_source_flats=True,
        ))
        released = dict(resolved_physical_render_parts(geometry))
        assert full and released and set(released) <= set(full)
        bay = loaded["receiving_layout"]["sets"][si]["bays"][bi]
        ns = api.receiving_manufacturing_instance_namespace(
            set_id=loaded["receiving_layout"]["sets"][si]["stable_id"],
            bay_id=bay["stable_id"],
        )
        assert namespaces[ns] == (si, bi)
        for key in released:
            filename = resolved_physical_dxf_filename(
                key,
                box_body_physical_piece_roles=frozenset(
                    {"left_side", "back", "right_side", "integral"}
                ),
                instance_namespace=ns,
            )
            assert filename in witnesses, (ns, key, filename)
    assert saved.read_bytes() == original_bytes
    assert loaded == exact_snapshot


def test_four_bay_gui_source_changed_while_staged_reopen_aborts_all_outputs(
    tmp_path, monkeypatch,
):
    saved, original_bytes, loaded = _saved_with_real_inner_door_state(tmp_path)
    original = deepcopy(loaded)

    def change_live_second_set_source(visit, _filename):
        if visit != 2:
            return
        source = loaded["receiving_layout"]["sets"][1]["bays"][1]
        assert source["nfb_config_submitted"] is True
        source["nfb_config"]["holes"][0]["manual_x_mm"] += 12.0

    witnessed, visits = _record_genuine_stage_verification(
        monkeypatch, mutate=change_live_second_set_source,
    )
    output = tmp_path / "invalid-staged-last-Bay-source"
    calls, errors, infos = _original_gui_export(
        monkeypatch, loaded, output,
    )
    assert calls == list(BAY_INDICES)
    assert len(visits) >= 2 and witnessed
    assert errors and not infos, (errors, infos)
    assert list(output.iterdir()) == []
    # The operator's in-memory state changed, but the saved project and every
    # old manufactured DXF remain intact; no 4-Bay partial release.
    assert loaded != original
    assert saved.read_bytes() == original_bytes

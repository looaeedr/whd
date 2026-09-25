from __future__ import annotations

import json
from pathlib import Path

import tools.phase6_bridge_anti_regrowth_guard as guard


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools" / "phase6_bridge_anti_regrowth_guard.py"
BASELINE = ROOT / "docs" / "architecture" / "phase6_bridge_anti_regrowth_baseline.json"
C0 = ROOT / "docs" / "superpowers" / "checkpoints" / "issue532-c0-final-classification.json"
BRIDGE = ROOT / "fold_designer_bridge.py"


def test_c1_permanent_guard_assets_exist():
    assert GUARD.is_file()
    assert BASELINE.is_file()
    assert C0.is_file()


def test_c1_budget_authority_reads_c0_record_not_duplicated_literals():
    authority = guard._load_authority(BASELINE, C0)
    c0 = json.loads(C0.read_text(encoding="utf-8"))
    assert authority["accepted_final_loc"] == c0["quantitative_gate"]["final_bridge_loc"]
    assert authority["accepted_facade_count"] == c0["quantitative_gate"]["facade_count"]
    assert authority["bridge_loc_limit"] == min(
        c0["quantitative_gate"]["final_bridge_loc"] + 25,
        c0["quantitative_gate"]["effective_final_ceiling"],
    )


def test_arg1_and_arg5_current_bridge_fit_c0_budget_and_facade_ratchet():
    authority = guard._load_authority(BASELINE, C0)
    source = BRIDGE.read_text(encoding="utf-8")
    assert source.count("\n") <= authority["bridge_loc_limit"]
    assert guard.facade_binding_count(source) <= authority["accepted_facade_count"]


def test_arg2_large_net_new_top_level_body_requires_review():
    baseline = "def kept():\n    return 1\n"
    body = "\n".join(f"    value_{i} = {i}" for i in range(45))
    current = f"def kept():\n{body}\n    return value_44\n"
    violations = guard.bridge_growth_violations(
        baseline,
        current,
        threshold=40,
        allowlist={},
    )
    assert [row["code"] for row in violations] == [
        "LARGE_TOP_LEVEL_BODY_REVIEW_REQUIRED"
    ]


def test_arg3_reverse_import_detector_rejects_bridge_import():
    assert guard.imports_bridge("import fold_designer_bridge\n")
    assert guard.imports_bridge(
        "from fold_designer_bridge import Phase6FoldDesignerApp\n"
    )
    assert not guard.imports_bridge("import phase6_settings_panel\n")


def test_arg4_second_composition_root_is_detectable():
    sources = {
        "gui_modules/application/fold_designer_adapter.py": (
            "class Phase6FoldDesignerComposition:\n    pass\n"
        ),
        "gui_modules/application/other.py": (
            "class Phase6FoldDesignerComposition:\n    pass\n"
        ),
    }
    assert guard.composition_root_locations(
        sources, "Phase6FoldDesignerComposition"
    ) == (
        "gui_modules/application/fold_designer_adapter.py",
        "gui_modules/application/other.py",
    )


def test_arg6_accepted_direct_alias_cannot_regrow_as_bridge_body():
    baseline = "_phase6_owner_alias = owner.resolve\n"
    current = "def _phase6_owner_alias():\n    return 1\n"
    violations = guard.alias_redefinition_violations(baseline, current)
    assert violations == [
        {
            "code": "EXTRACTED_ALIAS_REDEFINED_IN_BRIDGE",
            "symbol": "_phase6_owner_alias",
        }
    ]


def test_arg7_new_full_app_owner_interface_is_detectable():
    old = "def execute(request):\n    return request\n"
    new = "def execute(request, app):\n    return app\n"
    risky = ("app", "bridge", "full_app")
    assert guard.full_app_interfaces(old, risky) == set()
    assert guard.full_app_interfaces(new, risky) == {"execute(request,app)"}

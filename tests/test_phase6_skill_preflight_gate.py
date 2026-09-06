# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_agents_bootstrap_requires_machine_skill_preflight():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for required in (
        "Skill Preflight",
        ".agents/skills/skill_registry.json",
        ".agents/skills/misc/git-remote-sync-fallback/SKILL.md",
        "python tools/phase6_skill_preflight.py",
        "phase6-corner-3d-model-integrity",
        "phase6-overlay-relief-basis",
        "phase6-release-packaging",
        "截角資料庫",
        "Registry HIT",
    ):
        assert required in text


def test_skill_registry_routes_phase6_keywords_to_required_skills():
    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    assert registry["schema_version"] == 1

    routes = registry["routes"]

    def skills_for(keyword: str) -> set[str]:
        return {
            skill
            for route in routes
            if keyword in route["keywords"]
            for skill in route["required_skills"]
        }

    assert "phase6-corner-3d-model-integrity" in skills_for("corner")
    assert "phase6-corner-3d-model-integrity" in skills_for("3D")
    assert "phase6-overlay-relief-basis" in skills_for("OVERLAY")
    assert "phase6-overlay-relief-basis" in skills_for("flat-X")
    assert "phase6-release-packaging" in skills_for("release")
    assert "phase6-release-packaging" in skills_for("UPDATE")
    assert "diagnosing-bugs" in skills_for("bug")
    assert "tdd" in skills_for("bug")


def test_skill_preflight_cli_reports_missing_and_completed_skills(tmp_path, capsys):
    from tools.phase6_skill_preflight import main

    evidence = tmp_path / "evidence.md"
    evidence.write_text(
        "\n".join(
            [
                "# Evidence",
                "- phase6-corner-3d-model-integrity",
                "- phase6-overlay-relief-basis",
            ]
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "--task",
            "OVERLAY release",
            "--changed-file",
            "ae_engine/certified_relief_registry.py",
            "--evidence",
            str(evidence),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "REQUIRED SKILLS" in out
    assert "✓ phase6-corner-3d-model-integrity" in out
    assert "✓ phase6-overlay-relief-basis" in out
    assert "✗ phase6-release-packaging" in out


def test_skill_preflight_cli_passes_when_all_required_skills_have_evidence(tmp_path, capsys):
    from tools.phase6_skill_preflight import main

    evidence = tmp_path / "evidence.md"
    evidence.write_text(
        "\n".join(
            [
                "phase6-corner-3d-model-integrity",
                "phase6-overlay-relief-basis",
                "phase6-release-packaging",
                "READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
                "READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md",
                "READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json",
                "READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md",
                "READ_REFERENCE: release_required_artifacts.json",
            ]
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "--task",
            "OVERLAY release",
            "--changed-file",
            "基準檔/截角資料庫/certified_relief_rules.json",
            "--evidence",
            str(evidence),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "✓ phase6-release-packaging" in out



def test_agents_bootstrap_requires_pitfall_knowledge_preflight():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for required in (
        "全域踩坑庫",
        "任務領域踩坑庫",
        "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
        "個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md",
        "required_references",
        "Subagent",
    ):
        assert required in text


def test_skill_registry_routes_assembly_work_to_domain_pitfall_reference():
    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    routes = {item["id"]: item for item in registry["routes"]}
    for route_id in ("phase6-corner-relief-3d", "phase6-overlay-basis"):
        assert "個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md" in routes[route_id]["required_references"]


def test_skill_preflight_fails_closed_when_pitfall_reference_evidence_is_missing(tmp_path, capsys):
    from tools.phase6_skill_preflight import main

    evidence = tmp_path / "evidence.md"
    evidence.write_text(
        "\n".join(
            [
                "phase6-corner-3d-model-integrity",
                "diagnosing-bugs",
                "tdd",
            ]
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "--task",
            "組合 bug 修正",
            "--changed-file",
            "fold_designer_bridge.py",
            "--evidence",
            str(evidence),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "REQUIRED REFERENCES" in out
    assert "✗ 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md" in out
    assert "✗ 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md" in out


def test_skill_preflight_passes_only_with_skills_and_required_reference_evidence(tmp_path, capsys):
    from tools.phase6_skill_preflight import main

    evidence = tmp_path / "evidence.md"
    evidence.write_text(
        "\n".join(
            [
                "phase6-corner-3d-model-integrity",
                "diagnosing-bugs",
                "tdd",
                "READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
                "READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md",
                "READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md",
                "READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json",
            ]
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "--task",
            "組合 bug 修正",
            "--changed-file",
            "fold_designer_bridge.py",
            "--evidence",
            str(evidence),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "✓ 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md" in out
    assert "✓ 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md" in out


def test_skill_preflight_always_requires_global_pitfall_reference(tmp_path, capsys):
    from tools.phase6_skill_preflight import main

    evidence = tmp_path / "evidence.md"
    evidence.write_text("# no reference evidence yet\n", encoding="utf-8")
    code = main(["--task", "純文字說明調整", "--evidence", str(evidence)])
    out = capsys.readouterr().out
    assert code == 1
    assert "REQUIRED REFERENCES" in out
    assert "✗ 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md" in out


def test_reference_evidence_requires_explicit_read_reference_marker(tmp_path, capsys):
    from tools.phase6_skill_preflight import main

    evidence = tmp_path / "evidence.md"
    evidence.write_text(
        "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md\n",
        encoding="utf-8",
    )
    code = main(["--task", "純文字說明調整", "--evidence", str(evidence)])
    out = capsys.readouterr().out
    assert code == 1
    assert "✗ 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md" in out

def test_release_policy_requires_skill_preflight_artifacts():
    policy = json.loads((ROOT / "release_required_artifacts.json").read_text(encoding="utf-8"))
    required = set(policy["mandatory_update_files"])
    for rel in (
        ".agents/skills/skill_registry.json",
        "tools/phase6_skill_preflight.py",
        "tests/test_phase6_skill_preflight_gate.py",
        "基準檔/截角資料庫/README_母規則說明.md",
        "基準檔/截角資料庫/certified_relief_rules.schema.json",
        "基準檔/截角資料庫/certified_relief_rules.json",
    ):
        assert rel in required


def test_certified_relief_rules_carry_standard_and_adjustment_metadata():
    payload = json.loads((ROOT / "基準檔/截角資料庫/certified_relief_rules.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert "standard_rules" in payload
    assert "ENDCAP_TOP_STANDARD_V1" in payload["standard_rules"]
    assert "ENDCAP_BOTTOM_STANDARD_V1" in payload["standard_rules"]

    for rule in payload["rules"]:
        for required in (
            "standard_ref",
            "affected_zone",
            "dimension_space",
            "target_semantics",
            "adjustment_type",
            "adjustment_amount",
            "certification_evidence",
        ):
            assert required in rule, rule["rule_id"]
        assert rule["standard_ref"] in payload["standard_rules"]
        assert rule["dimension_space"] in {"MATERIAL", "OUTSIDE", "FORMED_OCCUPATION"}
        assert rule["adjustment_type"] in {"STANDARD", "INSERT", "OVERLAY", "INSERT_OVERLAY", "WRAP"}
        assert rule["certification_evidence"]


def test_git_remote_sync_fallback_skill_is_registry_routed_and_fail_closed(tmp_path, capsys):
    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    routes = {item["id"]: item for item in registry["routes"]}
    route = routes["git-remote-sync-fallback"]

    assert "git-remote-sync-fallback" in route["required_skills"]
    for keyword in ("git push", "GitHub Connector", "DNS", "remote sync"):
        assert keyword in route["keywords"]

    skill = (ROOT / ".agents/skills/misc/git-remote-sync-fallback/SKILL.md").read_text(encoding="utf-8")
    for required in (
        "GitHub Connector 內容同步 ≠ git push",
        "force=false",
        "遠端 HEAD",
        "部分成功",
        "先重新讀取遠端",
        "不得盲目重送",
        "遠端二次驗證",
    ):
        assert required in skill

    from tools.phase6_skill_preflight import main

    evidence = tmp_path / "evidence.md"
    evidence.write_text(
        "READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md\n",
        encoding="utf-8",
    )
    code = main(
        [
            "--task",
            "git push 因 DNS 失敗，改用 GitHub Connector remote sync",
            "--evidence",
            str(evidence),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "✗ git-remote-sync-fallback" in out

    evidence.write_text(
        "git-remote-sync-fallback\n"
        "diagnosing-bugs\n"
        "tdd\n"
        "READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md\n",
        encoding="utf-8",
    )
    code = main(
        [
            "--task",
            "git push 因 DNS 失敗，改用 GitHub Connector remote sync",
            "--evidence",
            str(evidence),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "✓ git-remote-sync-fallback" in out

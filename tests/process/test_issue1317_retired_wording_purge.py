from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_current_skills_do_not_name_retired_shared_zero_receipt_token():
    for path in (
        ".agents/skills/engineering/flow-v2-execution/SKILL.md",
        ".agents/skills/engineering/root-local-first/SKILL.md",
        ".agents/skills/engineering/推推/SKILL.md",
    ):
        assert "CANONICAL_SHARED_0_UPDATED" not in _read(path)


def test_root_local_pitfall_cannot_be_replayed_as_drive_or_latest_zero_workflow():
    text = _read("個人AI檔案庫/踩坑庫/root_local_first_entry_gate_pitfall.md")
    forbidden = (
        "repository-content 任務已指定 `/Google Drive/WHD` 為 canonical root",
        "latest 0 優先於 root",
        "回 root/latest 0 reconcile",
        "回 fresh latest 0 重建 candidate",
        "重新登記成新的 unpushed change",
    )
    for marker in forbidden:
        assert marker not in text
    assert "歷史 Drive/shared-zero authority 被 generic search 重播" in text
    assert "executor-local repo workspace" in text
    assert "tested exact diff → dedicated delivery branch → PR/required checks → trusted merge/readback" in text

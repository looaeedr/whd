from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".agents" / "skills" / "engineering" / "root-local-first" / "SKILL.md"
AI = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "10_WHD_Drive與Git文字搬運防錯.md"


def test_root_local_first_owns_drive_raw_text_transport_contract():
    text = SKILL.read_text(encoding="utf-8")
    assert "DRIVE_RAW_TEXT_TRANSPORT_HARD_GATE_V1" in text
    assert "Buffer.from(base64_string, 'base64').toString('utf-8')" in text
    assert "不得假設 `atob`、`TextDecoder`" in text
    assert "raw `file_uri` / materialize / download / mounted-file path" in text
    assert "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391" in text
    assert "TRANSPORT_DECODE_CORRUPTION" in text
    assert "禁止開 PR／merge" in text


def test_ai_library_is_reference_to_canonical_skill_not_second_authority():
    text = AI.read_text(encoding="utf-8")
    assert "whd_doc_role: REFERENCE" in text
    assert "canonical owner: `.agents/skills/engineering/root-local-first/SKILL.md`" in text
    assert "Buffer.from(base64_string, 'base64').toString('utf-8')" in text
    assert "CURRENT authority 仍是 `root-local-first` Skill" in text

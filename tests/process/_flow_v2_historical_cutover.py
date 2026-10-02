from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests/process/WHD_PROCESS_TEST_CLASSIFICATION_V1.json"
FLOW = ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md"
BRIDGES = (
    ROOT / ".agents/skills/engineering/派工/SKILL.md",
    ROOT / ".agents/skills/engineering/排程模擬/SKILL.md",
    ROOT / ".agents/skills/engineering/工作槽/SKILL.md",
    ROOT / ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
    ROOT / ".agents/skills/engineering/issue-closure-gate/SKILL.md",
    ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md",
    ROOT / ".agents/skills/engineering/remote-execution-guard/SKILL.md",
    ROOT / ".agents/skills/engineering/強制接手/SKILL.md",
    ROOT / ".agents/skills/engineering/執行開發任務/SKILL.md",
    ROOT / ".agents/skills/engineering/寫排程/SKILL.md",
)

def assert_historical_cutover(test_file: str) -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rel = Path(test_file).resolve().relative_to(ROOT).as_posix()
    assert payload["status"] == "CURRENT"
    assert payload["current_execution_authority"] == ".agents/skills/engineering/flow-v2-execution/SKILL.md"
    assert rel in payload["historical_anti_regrowth_tests"], rel
    flow = FLOW.read_text(encoding="utf-8")
    assert "WHD_EXECUTION_RECORD_V2" in flow
    assert "MERGE → FINALIZE → DONE" in flow
    for path in BRIDGES:
        text = path.read_text(encoding="utf-8")
        assert "whd_doc_role: MIRROR" in text, path
        assert "whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md" in text, path
        assert "FLOW_V2_EXECUTION_BRIDGE_V1" in text, path
        assert "不擁有 execution state machine" in text, path

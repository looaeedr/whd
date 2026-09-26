from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DISPATCH = ROOT / ".agents" / "skills" / "engineering" / "派工" / "SKILL.md"
X_SPEC = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "09_X第二主分支與獨立工單鏈治理規格.md"
PITFALL = ROOT / "個人AI檔案庫" / "踩坑庫" / "execution_claim_hard_gate_pitfall.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_issue736_dispatch_requires_batch_first_main_to_x_parity():
    text = _text(DISPATCH)
    required = (
        "MAIN_TO_X_BATCH_FIRST_PARITY_V1",
        "BATCH_FEASIBILITY_AUDIT",
        "SELECTIVE_PROPAGATION_FALLBACK_ONLY",
        "NO_PER_FIX_HELPER_DEFAULT",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: 派工 missing batch-first parity contract: {missing}"


def test_issue736_x_governance_spec_requires_batch_before_selective_sync():
    text = _text(X_SPEC)
    required = (
        "MAIN_TO_X_BATCH_FIRST_PARITY_V1",
        "先做整批可行性審計",
        "不得預設逐顆 cherry-pick",
        "局部 compatible-equivalent 只可作 fallback",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: X governance spec missing batch-first rules: {missing}"


def test_issue736_pitfall_records_helper_fragmentation_failure_mode():
    text = _text(PITFALL)
    required = (
        "MAIN_TO_X_BATCH_FIRST_PARITY_V1",
        "per-fix helper fragmentation",
        "batch-first",
        "fallback only",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: pitfall missing reusable correction: {missing}"


def test_issue736_contract_preserves_active_chain_isolation():
    text = _text(DISPATCH) + "\n" + _text(X_SPEC)
    required = (
        "active chain",
        "FROZEN_X_BASE_SHA",
        "不得把 main→X",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: batch parity must preserve frozen-chain isolation: {missing}"

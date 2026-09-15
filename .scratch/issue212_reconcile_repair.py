from __future__ import annotations

import subprocess
from pathlib import Path

BAD_HEAD = "8462d9be42c8413a10b33934e3eb229244652974"
PRODUCTION_SHA = "0e20662d4e36907d5e529346cccb2a5cafbf4f72"
ACCEPTED_SHA = "246ebc796c474ff1000b936686cf31d2f7e36548"
BRANCH = "repair/issue212-reconcile-safe-v2-20260915"
MARKER = "<!-- QA_PIPELINE_FAIL_CLOSED_V1 -->"

APPROVED_ACCEPTED_PATHS = (
    "docs/superpowers/plans/2026-09-14-gui-layout-presentation-move.md",
    "docs/superpowers/plans/2026-09-14-gui-pure-drawing-move.md",
    "docs/superpowers/plans/2026-09-14-issue212-final-integration.md",
    "docs/superpowers/specs/2026-09-14-issue212-final-integration-design.md",
    "gui.py",
    "gui_modules/__init__.py",
    "gui_modules/drawing.py",
    "gui_modules/layout.py",
    "gui_modules/part_panels.py",
    "gui_modules/project_actions.py",
    "gui_modules/render_2d.py",
    "tests/test_issue111_corner_data_grid_isolation.py",
    "tests/test_issue123_ui_foundation.py",
    "tests/test_issue206_gui_modularization_characterization.py",
    "tests/test_issue209_part_panel_projection.py",
    "tests/test_issue210_project_actions_move_contract.py",
    "tests/test_issue211_renderer_dependency_gate.py",
    "tests/test_phase6_linked_fold_chain_and_parts.py",
)
EXPECTED_PATHS = tuple(sorted((
    "AGENTS.md",
    *APPROVED_ACCEPTED_PATHS,
    "個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md",
)))


def run(*args: str, capture: bool = False) -> str:
    proc = subprocess.run(args, check=True, text=True, capture_output=capture)
    return proc.stdout.strip() if capture else ""


def insert_process_rules() -> None:
    agents = Path("AGENTS.md")
    text = agents.read_text(encoding="utf-8")
    if MARKER in text:
        raise SystemExit("AGENTS.md unexpectedly already contains QA_PIPELINE_FAIL_CLOSED_V1")
    anchor = "### 0.0.3 成品板件驗收硬閘門：Focused GREEN 不能直接合併\n"
    if anchor not in text:
        raise SystemExit("AGENTS.md insertion anchor missing")
    block = """<!-- QA_PIPELINE_FAIL_CLOSED_V1 -->
### 0.0.2A QA Pipeline Fail-Closed 硬閘門

任何會影響 PASS/FAIL 判定的命令，只要透過 pipe（尤其 `tee`）輸出，必須啟用 `set -o pipefail` 或等價保留左側命令 exit status。`pytest ... | tee ...` / `python validator.py | tee ...` 若未 fail-closed，即使 GitHub Actions step/job 顯示 SUCCESS 也不是有效驗收證據。

正式接受前同時必須確認：

1. test / validator 的完整 terminal summary 或等價終態，而不是只看 workflow conclusion；
2. exact tested `head_sha`；
3. characterization / Move-Only baseline 使用 immutable accepted commit SHA，禁止 movable branch ref；
4. symbol owner/class 來自 AST/dependency inventory 或 exact source reread，不得由 public inheritance surface 猜測。

若歷史 run 違反任一條，狀態只能標記為 evidence invalid / rerun required；禁止拿假綠結果關單、合併或 release。

"""
    agents.write_text(text.replace(anchor, block + anchor, 1), encoding="utf-8")

    pitfall = Path("個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md")
    text = pitfall.read_text(encoding="utf-8")
    if MARKER in text:
        raise SystemExit("long-log pitfall unexpectedly already contains QA_PIPELINE_FAIL_CLOSED_V1")
    block = """

<!-- QA_PIPELINE_FAIL_CLOSED_V1 -->
## QA pipeline 假綠 / movable baseline 踩坑（2026-09-14）

### 事故模式

T5 GUI modularization 曾出現 `pytest ... | tee` 與 `python validator.py | tee` 左側已 FAIL，但 GitHub step/job 因 `tee` exit 0 顯示 SUCCESS。另一個 Move-Only validator 同時使用 movable branch ref、並把可繼承呼叫 symbol 的 public subclass 誤認成真正 owner，造成驗證結果不可信。

### 根因

- shell pipeline 未啟用 `pipefail`，wrapper 的成功遮蔽真正 validator/test failure。
- 把 CI 綠燈顏色當 acceptance authority，沒有反讀 pytest/validator terminal summary。
- baseline 用 branch name 而非 immutable accepted SHA，驗證基準可在執行途中漂移。
- 由 public API surface 猜 class owner，沒有用 AST/原始碼確認實際定義位置。

### 永久規則

- fail-significant command 只要經過 pipe/`tee`，必須 `set -o pipefail`（或等價取得左側 exit status）；沒有這條的舊 GREEN evidence 一律不得沿用。
- Acceptance 同時要求：workflow terminal + 實際 test/validator terminal summary + exact tested `head_sha`。
- Characterization / Move-Only 比較基準固定寫 immutable accepted commit SHA；禁止 movable branch ref。
- owner/class 由 AST dependency inventory 或 exact source reread 確認；繼承可見性不等於 ownership。
- 發現假綠後要回溯原 log 重新分類，不能為了維持 GREEN 去改 production 配合 stale test。
"""
    pitfall.write_text(text.rstrip() + block + "\n", encoding="utf-8")


def main() -> None:
    parent = run("git", "rev-parse", "HEAD^", capture=True)
    if parent != BAD_HEAD:
        raise SystemExit(f"unexpected bootstrap parent: {parent}")
    run("git", "cat-file", "-e", f"{PRODUCTION_SHA}^{{commit}}")
    run("git", "cat-file", "-e", f"{ACCEPTED_SHA}^{{commit}}")
    run("git", "merge-base", "--is-ancestor", PRODUCTION_SHA, BAD_HEAD)
    run("git", "merge-base", "--is-ancestor", ACCEPTED_SHA, BAD_HEAD)

    # Start the repaired tree from exact current production, not from the broken merge tree.
    run("git", "read-tree", f"{PRODUCTION_SHA}^{{tree}}")
    run("git", "checkout-index", "-a", "-f")
    run("git", "clean", "-fdx")

    for path in APPROVED_ACCEPTED_PATHS:
        run("git", "checkout", ACCEPTED_SHA, "--", path)

    insert_process_rules()
    run("git", "add", "AGENTS.md", "個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md")

    actual = tuple(sorted(filter(None, run(
        "git", "diff", "--cached", "--name-only", PRODUCTION_SHA, capture=True
    ).splitlines())))
    if actual != EXPECTED_PATHS:
        raise SystemExit(f"approved diff mismatch\nexpected={EXPECTED_PATHS!r}\nactual={actual!r}")

    run("git", "diff", "--cached", "--check", PRODUCTION_SHA)
    for temporary in (
        ".github/workflows/issue212-reconcile-repair-v2.yml",
        ".scratch/issue212_reconcile_repair.py",
    ):
        if Path(temporary).exists():
            raise SystemExit(f"temporary bootstrap residue remains: {temporary}")

    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "commit", "-m", "fix(issue212): rebuild reconcile candidate from current production")
    repaired = run("git", "rev-parse", "HEAD", capture=True)
    print(f"REPAIRED_HEAD={repaired}")
    run("git", "push", "origin", f"HEAD:{BRANCH}")


if __name__ == "__main__":
    main()

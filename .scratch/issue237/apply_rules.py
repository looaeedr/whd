from pathlib import Path

MARKER = '<!-- QA_PIPELINE_FAIL_CLOSED_V1 -->'

monitoring = Path('.agents/skills/engineering/monitoring-remote-qa/SKILL.md')
pitfall = Path('個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md')
agents = Path('AGENTS.md')

monitoring_block = '''\n\n<!-- QA_PIPELINE_FAIL_CLOSED_V1 -->\n## QA Pipeline Fail-Closed Gate\n\nRemote QA 的 workflow/job 顯示 GREEN 不足以單獨成為 acceptance evidence。只要 fail-significant command 透過 pipe（特別是 `tee`）輸出，shell 必須啟用 `set -o pipefail` 或等價機制，並保留左側 validator/test command 的真實 exit status。\n\n- `pytest ... | tee ...`、`python validator.py | tee ...` 沒有 pipefail 時，左側 exit != 0 可能被 `tee` 的 0 覆蓋；此類 run 即使 GitHub step/job 顯示 SUCCESS 也視為**證據無效**，必須重跑 fail-closed gate。\n- Acceptance 必須反讀 terminal test/validator summary（PASS/FAIL/SKIP/ERROR 或等價終態）與 tested `head_sha`；不能只看 workflow conclusion。\n- Characterization / Move-Only validator 的 baseline 必須鎖 immutable accepted commit SHA；禁止用會移動的 branch ref 當比較真值。\n- Symbol owner/class 必須由 AST/dependency inventory 或 exact source reread 決定；不得因 public subclass 能呼叫該 symbol 就假定它是實際 owner。\n- 以上規則也適用於 remote QA replacement run；修 gate 後必須在新的 exact head 上重新取得 terminal evidence。\n'''

pitfall_block = '''\n\n<!-- QA_PIPELINE_FAIL_CLOSED_V1 -->\n## QA pipeline 假綠 / movable baseline 踩坑（2026-09-14）\n\n### 事故模式\n\nT5 GUI modularization 曾出現 `pytest ... | tee` 與 `python validator.py | tee` 左側已 FAIL，但 GitHub step/job 因 `tee` exit 0 顯示 SUCCESS。另一個 Move-Only validator 同時使用 movable branch ref、並把可繼承呼叫 symbol 的 public subclass 誤認成真正 owner，造成驗證結果不可信。\n\n### 根因\n\n- shell pipeline 未啟用 `pipefail`，wrapper 的成功遮蔽真正 validator/test failure。\n- 把 CI 綠燈顏色當 acceptance authority，沒有反讀 pytest/validator terminal summary。\n- baseline 用 branch name 而非 immutable accepted SHA，驗證基準可在執行途中漂移。\n- 由 public API surface 猜 class owner，沒有用 AST/原始碼確認實際定義位置。\n\n### 永久規則\n\n- fail-significant command 只要經過 pipe/`tee`，必須 `set -o pipefail`（或等價取得左側 exit status）；沒有這條的舊 GREEN evidence 一律不得沿用。\n- Acceptance 同時要求：workflow terminal + 實際 test/validator terminal summary + exact tested `head_sha`。\n- Characterization / Move-Only 比較基準固定寫 immutable accepted commit SHA；禁止 movable branch ref。\n- owner/class 由 AST dependency inventory 或 exact source reread 確認；繼承可見性不等於 ownership。\n- 發現假綠後要回溯原 log 重新分類，不能為了維持 GREEN 去改 production 配合 stale test。\n'''

agents_block = '''\n\n<!-- QA_PIPELINE_FAIL_CLOSED_V1 -->\n### 0.0.2A QA Pipeline Fail-Closed 硬閘門\n\n任何會影響 PASS/FAIL 判定的命令，只要透過 pipe（尤其 `tee`）輸出，必須啟用 `set -o pipefail` 或等價保留左側命令 exit status。`pytest ... | tee ...` / `python validator.py | tee ...` 若未 fail-closed，即使 GitHub Actions step/job 顯示 SUCCESS 也不是有效驗收證據。\n\n正式接受前同時必須確認：\n\n1. test / validator 的完整 terminal summary 或等價終態，而不是只看 workflow conclusion；\n2. exact tested `head_sha`；\n3. characterization / Move-Only baseline 使用 immutable accepted commit SHA，禁止 movable branch ref；\n4. symbol owner/class 來自 AST/dependency inventory 或 exact source reread，不得由 public inheritance surface 猜測。\n\n若歷史 run 違反任一條，狀態只能標記為 evidence invalid / rerun required；禁止拿假綠結果關單、合併或 release。\n'''

for path, block in ((monitoring, monitoring_block), (pitfall, pitfall_block)):
    text = path.read_text(encoding='utf-8')
    if MARKER not in text:
        path.write_text(text.rstrip() + block + '\n', encoding='utf-8')

text = agents.read_text(encoding='utf-8')
if MARKER not in text:
    anchor = '<!-- WHD_SECTION_ROLE role=HISTORICAL contract=legacy-v5-architecture-roadmap -->'
    if anchor not in text:
        raise SystemExit('AGENTS historical anchor missing')
    text = text.replace(anchor, agents_block + '\n' + anchor, 1)
    agents.write_text(text, encoding='utf-8')

for path in (monitoring, pitfall, agents):
    text = path.read_text(encoding='utf-8')
    if text.count(MARKER) != 1:
        raise SystemExit(f'{path}: marker count {text.count(MARKER)} != 1')
    print(f'{path}=GREEN')

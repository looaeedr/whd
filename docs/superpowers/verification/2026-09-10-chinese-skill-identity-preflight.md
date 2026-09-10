# 2026-09-10 中文 Skill Identity / Content Audit Evidence

Task: 掃描 `.agents/skills/**` 全樹；所有中文資料夾 Skill 的 frontmatter `name` 必須等於資料夾 basename，並檢查/修復內容中的 stale identity、斷掉路由、不存在工具或背景 Subagent 假設，以及已 superseded 的 WHD authority。

Baseline branch/head: `chore/repair-dispatching-skill-20260910 @ ae5bf1dfd7bd1909323e411716fdb3e6ff47e21a`
Work branch: `chore/normalize-chinese-skill-names-20260910`

## Skills read / applied

- 寫技能
- tdd
- diagnosing-bugs
- phase6-release-packaging
- 掃描深模組
- 驗證板件與DXF
- monitoring-remote-qa

## Required references read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/07_WHD技能發現與掃描深模組規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
READ_REFERENCE: release_required_artifacts.json

## Audited Chinese Skill folders

Engineering:
- 執行開發任務 — baseline name `implement`
- 寫成規格書 — baseline name `to-spec`
- 寫技能 — baseline name `寫技能`
- 拆解任務工單 — baseline name `to-tickets`
- 拷問邊建立文件 — baseline name `grill-with-docs`
- 掃描深模組 — baseline name `improve-codebase-architecture`
- 派工 — baseline name `派工`
- 程式碼庫設計 — baseline name `codebase-design`
- 領域建模 — baseline name `domain-modeling`
- 驗證板件與DXF — baseline name `驗證板件與DXF`

Productivity:
- 深度質詢 — baseline name `grilling`

Total: 11 Chinese Skill folders; 8 baseline identity mismatches.

## Content findings before modification

1. `拷問邊建立文件/SKILL.md`只有一句 `Call the Skill tool twice...`，綁死不存在的 Skill-tool 假設，也沒有 durable docs workflow。
2. `深度質詢/SKILL.md` 無條件要求 dispatch sub-agent 並等待 background exploration，缺少無 Subagent runtime fallback。
3. `程式碼庫設計/DESIGN-IT-TWICE.md` 無條件要求 parallel 3+ sub-agents，缺少 inline/sequential fallback。
4. `掃描深模組/SKILL.md` 仍把 `codebase-design/grilling/domain-modeling` 當主要 identity；需要遷移至中文 canonical paths。
5. `engineering/README.md` 與 `productivity/README.md` 有多個不存在的舊英文路徑；`ask-matt` router 也仍以舊英文 slash identity 導航。
6. `驗證板件與DXF` 的 Receiving Divider 段仍容易把 collision/backprojection 看成 relief authority；現行 rule 應是 `CROSS（十字截角）＋參數` / Certified Registry + reference DXF authority，collision/backprojection 僅 shadow verification。
7. `執行開發任務` 仍把 `/tdd`、`/code-review` 當硬命令形式；應改為使用實際可用 Skill/工具，不假設 slash-command runtime。

## Requirement RED

Contract: `tests/test_chinese_skill_identity_contract.py`

RED is valid only when pytest reaches the contract assertions. Preflight/setup/import/tooling failures are harness failures and do not count as requirement RED.

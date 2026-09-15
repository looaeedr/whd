# 2026-09-11 第二批 Skill 納入 Preflight / Verification Evidence

## 任務

依使用者核准設計處理第二批外部 Skill：

1. 不建立重複的 `make-skill-template` 專案 Skill；只把其仍有價值、且不違反 WHD 治理的 frontmatter / compatibility / metadata / allowed-tools / templates 資源邊界補進既有中文 canonical Skill `寫技能`。
2. 以 `github/awesome-copilot` 的 `mcp-cli` 為輸入來源，建立 WHD 中文 canonical Skill `MCP工具操作`；保留 discover → inspect schema → execute 的核心能力，但改成 capability-adaptive：有 CLI/connector/native tool 就用，沒有就 fail closed，不得假裝工具存在。
3. 新 Skill 必須遵守 WHD branch-first、Preflight、中文 identity、RED→GREEN contract、Registry / AI Library / release policy durable writeback。

## Branch / baseline

- authoritative target: `cleanup/2d-3d-sync`
- target HEAD at branch creation: `a37de3ad697ef225b711f6ea0eee86bf2b7712d4`
- work branch: `feat/second-batch-skills-20260911`
- work branch initial HEAD re-read: `a37de3ad697ef225b711f6ea0eee86bf2b7712d4`
- existing `寫技能` blob baseline: `6715aaf20d784e37a053b9ed89e0ce1bbf57675d`
- existing `skill_registry.json` blob baseline: `6bfec2d5299496caf7040b1ed25883bf9cac50bd`
- existing AI rule blob baseline: `c1d1353e4159b5adefd6215bf8c4fcb6ef26d5d0`
- existing release manifest blob baseline: `80dac236539f6f684c2b613b301fe34fe55a89f5`

## External source provenance

- source repository: `github/awesome-copilot`
- pinned main HEAD: `7568a482ce2df38f8965ab5336a3220db796a4ba`
- `mcp-cli`: `skills/mcp-cli/SKILL.md` at pinned main HEAD above.
- `make-skill-template`: historical source read at commit `86f78ee41d41c6c20081080b519a35d1a68c6673`; it is used only as comparison/input, not copied as a second WHD Skill.

## Required Skills read

READ_SKILL: 寫技能
READ_SKILL: phase6-release-packaging
READ_SKILL: monitoring-remote-qa
READ_SKILL: MCP工具操作

Supplementary relevant project Skill read:

READ_SKILL: 找技能

> `MCP工具操作` 是本工單新建 Skill；candidate 內容由上述 pinned upstream 與已核准 WHD adaptation contract 寫成，並在 final acceptance 前完成 remote re-read。此 marker 讓新增 route 後的 candidate Preflight 可在同一 commit 驗證新 canonical Skill。

## Required References read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## Changed files

- `.agents/skills/engineering/寫技能/SKILL.md`
- `.agents/skills/productivity/MCP工具操作/SKILL.md`
- `.agents/skills/productivity/README.md`
- `.agents/skills/skill_registry.json`
- `tests/test_second_batch_skills_contract.py`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `release_required_artifacts.json`
- `docs/superpowers/verification/2026-09-11-second-batch-skills.md`
- `.github/workflows/second-batch-skills-qa-20260911.yml`（temporary QA only；final cleanup 已刪除）

## Authority / adaptation decisions

- 使用者明確要求第二批名稱同樣中文化；`MCP工具操作` 為 canonical folder/frontmatter/H1 identity。
- WHD 中文 Skill identity 規則優先於外部來源的 lowercase-hyphen naming convention。
- `make-skill-template` 與現有 `寫技能` 高度重疊，因此不建立第二套 authoring authority。
- 外部 `mcp-cli` 的 CLI 名稱與命令只是可用 capability，不是 WHD 的普遍必備 runtime；Skill 必須先偵測實際可用介面。
- Connector / native tool 已存在時，不應為了照範例強迫繞去 CLI；CLI 存在時才可使用 CLI 命令。
- 所有 tool/server/schema/result 的「已發現／已呼叫／已成功」敘述必須有實際 tool result；unknown 保持 unknown。
- 外部 tool result 只提供外部資料/動作結果，不自動升格成 WHD domain / manufacturing Source of Truth。

## RED evidence

- bootstrap run: `34596573648 @ 4d3b1b1d2d64615ba47c5ba26c8733248fa681de` → SUCCESS；Knowledge Preflight、config invariant、clean tree 都 PASS。這輪只驗施工環境，不算功能 GREEN。
- RED commit: `aa178e9c804dd58ec856de2adf0b1f7beefac135`。
- RED run: `34596846034` → FAILURE at `Second batch contracts and project guards`；setup/dependencies、config snapshot、Knowledge Preflight 全部先 PASS。
- RED summary: **7 failed / 59 passed**。7 個 failure 都對應已核准缺口：`MCP工具操作` 不存在、Registry route 缺失、`寫技能` 尚未吸收 metadata/templates contract、README/AI/release 尚未 durable 納入。這是 requirement RED，不是 import/setup/harness failure。
- RED workflow 同 commit 已移除 evidence-only path trigger；後續只更新 verification evidence 不再重跑 QA，避免 durable evidence commit 造成 accidental rerun。

## GREEN / final acceptance evidence

- implementation commit / tested head: `616f92f6d8f8b64c41ce3719fe74850b51a202c2`。
- final acceptance run: `34597299001` → **SUCCESS**。
- Knowledge Preflight：`寫技能`、`MCP工具操作`、`phase6-release-packaging`、`monitoring-remote-qa` 全部 PASS；required references 全部 PASS。
- focused + project guards：**66 passed / 0 failed / 0.48s**。
- `config.ini` before / after SHA256 均為 `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`。
- `git diff --exit-code` PASS。
- remote re-read 已確認 `.agents/skills/productivity/MCP工具操作/SKILL.md` 的 canonical `name: MCP工具操作`、capability-adaptive contract、schema-before-execute、exit-code semantics 與 WHD authority boundary；`寫技能` 也已反讀確認吸收 frontmatter/templates 邊界；Registry route 已反讀確認 `mcp-tool-operation → MCP工具操作`。

## Temporary QA cleanup

- temporary workflow cleanup commit: `18b1d103da14b3607f2e39495b72485ec85a1a4f`。
- cleanup 後 Actions branch listing 仍只有原本 3 次 run；沒有因 cleanup 產生第 4 次 accidental rerun。
- `.github/workflows/second-batch-skills-qa-20260911.yml` 在 cleanup HEAD 遠端 re-read → **404 Not Found**。
- final evidence update 位於 workflow cleanup 之後，因此 evidence-only update 不會觸發 QA。

## Final drift policy

- tested head：`616f92f6d8f8b64c41ce3719fe74850b51a202c2`。
- cleaned head 應只比 tested head 多：temporary workflow removal + 本 evidence 的 terminal/cleanup 記錄。
- 不允許 Skill / Registry / tests / AI Library / release policy 在 GREEN 後再發生未驗證 drift。

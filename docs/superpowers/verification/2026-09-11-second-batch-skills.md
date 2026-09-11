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

Supplementary relevant project Skill read:

READ_SKILL: 找技能

## Required References read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## Planned changed files

- `.agents/skills/engineering/寫技能/SKILL.md`
- `.agents/skills/productivity/MCP工具操作/SKILL.md`
- `.agents/skills/productivity/README.md`
- `.agents/skills/skill_registry.json`
- `tests/test_second_batch_skills_contract.py`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `release_required_artifacts.json`
- `docs/superpowers/verification/2026-09-11-second-batch-skills.md`
- `.github/workflows/second-batch-skills-qa-20260911.yml` (temporary QA only; must be deleted after terminal GREEN)

## Authority / adaptation decisions

- 使用者明確要求第二批名稱同樣中文化；`MCP工具操作` 為 canonical folder/frontmatter/H1 identity。
- WHD 中文 Skill identity 規則優先於外部來源的 lowercase-hyphen naming convention。
- `make-skill-template` 與現有 `寫技能` 高度重疊，因此不建立第二套 authoring authority。
- 外部 `mcp-cli` 的 CLI 名稱與命令只是可用 capability，不是 WHD 的普遍必備 runtime；Skill 必須先偵測實際可用介面。
- Connector / native tool 已存在時，不應為了照範例強迫繞去 CLI；CLI 存在時才可使用 CLI 命令。
- 所有 tool/server/schema/result 的「已發現／已呼叫／已成功」敘述必須有實際 tool result；unknown 保持 unknown。
- 外部 tool result 只提供外部資料/動作結果，不自動升格成 WHD domain / manufacturing Source of Truth。

## RED → GREEN plan

1. 先加入 `tests/test_second_batch_skills_contract.py`，鎖住 `MCP工具操作` 中文 identity、capability detection、schema-before-execute、no-fake-tool、failure semantics、Registry route、release inclusion，以及 `寫技能` 對 compatibility / metadata / allowed-tools / templates 的吸收規則。
2. 在新 Skill / authoring 補強尚未存在時執行 RED，確認 failure 原因是缺少第二批 contract，而不是 harness/import 問題。
3. 最小實作到 targeted GREEN。
4. 跑中文 identity、writing skill、find skill、Preflight、release policy / integrity guards。
5. `config.ini` 前後 SHA 必須相同，`git diff --exit-code` 必須乾淨。
6. Remote QA 依 `monitoring-remote-qa` 鎖定 `run_id + head_sha` 追到 terminal；GREEN 後刪除 temporary workflow、遠端反讀 404，再做 tested-head → cleaned-head drift audit。

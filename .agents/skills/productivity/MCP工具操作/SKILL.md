---
name: MCP工具操作
description: 透過目前實際可用的 Model Context Protocol（MCP）介面發現 server/tool、檢查 schema 並安全執行外部工具。當使用者提到 MCP、Model Context Protocol、MCP server、MCP tool、mcp-cli，或要求透過 MCP 連接外部系統時使用。優先使用 runtime 已提供的原生 connector/tool 介面；只有真的存在 mcp-cli 時才走 CLI，沒有可用 MCP 能力就 fail closed，不得假裝已列出、已呼叫或已成功。
---

# MCP工具操作

把 MCP 當成「可發現、可檢查 schema、可執行的外部工具介面」，不是固定綁死某一支 CLI。這個 Skill 以 `github/awesome-copilot` 的 `mcp-cli` workflow 為輸入來源，保留 Discover → Explore → Inspect → Execute 核心，但依 WHD 規則改成 capability-adaptive。

## 1. Authority 與邊界

執行順序的 authority：

1. 使用者本輪明確要求與授權範圍。
2. 本回合 runtime 真正暴露的 connector / MCP client / tool schema 與實際 tool result。
3. 對應外部服務自己的 API / MCP schema。
4. 本 Skill 的通用流程與 CLI 範例。

外部範例不能凌駕目前 runtime。尤其 `mcp-cli` 只是其中一條可用路徑，不是所有環境都必須安裝的前提。

MCP 回傳的資料或動作結果也**不自動升格**成 WHD domain / manufacturing **Source of Truth**。若外部資料要影響產品規格、幾何、Registry 或 canonical state，仍需經該領域自己的 authority 規則確認。

## 2. 能力偵測

開始前先確認本回合到底能用什麼：

- 是否已有**原生 connector**、plugin、typed tool 或其他 runtime-native 外部工具介面；
- 是否真的能列出 MCP server / tool；
- 是否能取得 tool input schema；
- 是否真的有可執行的 `mcp-cli`；
- 是否有需要的 authentication / permission；
- 目前介面是 read-only 還是允許 mutation。

規則是：**有就用，沒有就退化，但不得假裝。**

優先順序：

1. runtime 已提供原生 connector / typed tool 時，優先使用它，因為 schema、認證與錯誤通常已由 host 提供；不要只為模仿範例而繞去 shell。
2. 沒有原生介面、但 `mcp-cli` 確實存在且可執行時，才走 CLI 路徑。
3. 若另有明確可用的 MCP client，可依其真實 schema 使用。
4. **沒有可用的 MCP** 介面時 fail closed：清楚說明 capability gap，不得聲稱已搜尋 server、已看到 tool、已呼叫或已成功。

## 3. 標準流程

### 3.1 發現（Discover）

先取得 runtime 真正可見的 MCP servers / connectors / tools 清單。

- 原生介面：使用 host 提供的 discovery / tool listing 能力。
- CLI 路徑：只有確認 `mcp-cli` 存在時才執行 `mcp-cli`。
- 已知具體 server/tool 時仍要先確認它在目前 runtime 可用，不從記憶猜 availability。

發現結果必須來自本回合**實際結果**。無結果時保持 unknown。

### 3.2 探索（Explore）

對候選 server / connector 看它真正暴露哪些 tools、每個 tool 的用途與基本參數。

CLI 路徑可用：

```bash
mcp-cli <server>
mcp-cli <server> -d
mcp-cli grep "<glob>"
```

`-d` 只在來源 CLI 支援時代表顯示 description；其他 client 不得假定相同 flag。

### 3.3 檢查 Schema（Inspect）

**先讀 schema，再組參數。** 不得猜 server、tool、欄位名稱、required arguments、enum、file/url 型別或 mutation contract。

CLI 路徑：

```bash
mcp-cli <server>/<tool>
```

原生 connector / typed tool 路徑直接使用 host 提供的 function schema。若 schema 取不到，而且參數契約會影響正確性或安全性，停止執行並報告缺口；不要靠相似 API 腦補。

### 3.4 執行（Execute）

只有在 server/tool 可用、schema 已確認、參數符合 schema 且使用者授權範圍允許後才執行。

CLI 路徑：

```bash
mcp-cli <server>/<tool> '<json>'
mcp-cli <server>/<tool> '<json>' --json
```

複雜 JSON 可使用 stdin / heredoc，避免 shell quoting 破壞 payload：

```bash
mcp-cli server/tool <<'EOF'
{"key": "value"}
EOF
```

原生 connector 路徑則直接依 typed schema 呼叫；不要先轉成 CLI 字串再繞回去。

## 4. `mcp-cli` 條件式速查

以下只在本環境**真的有 `mcp-cli`** 時成立：

| Command | 用途 |
| --- | --- |
| `mcp-cli` | 列出 servers / tools |
| `mcp-cli <server>` | 查看 server tools 與參數 |
| `mcp-cli <server>/<tool>` | 取得 tool JSON schema |
| `mcp-cli <server>/<tool> '<json>'` | 呼叫 tool |
| `mcp-cli grep "<glob>"` | 依名稱搜尋 tools |
| `-j, --json` | JSON output，適合 scripting |
| `-r, --raw` | raw text output |
| `-d` | 顯示 descriptions |

不要因為本表存在就宣稱 CLI 已安裝，也不要把這些 flags 套到其他 MCP client。

## 5. Result / error contract

所有「已發現」「已呼叫」「已寫入」「已成功」都必須有本回合的**實際結果**支撐。

CLI 路徑保留來源 `mcp-cli` 的 exit code 語意：

- `0`：success。
- `1`：client-side error，例如 bad args / missing config。
- `2`：server/tool error。
- `3`：network error。

若實際 CLI 版本回傳不同 contract，以該版本真實 help/schema/result 為準並明確說明；不能為了符合本文件竄改結果。

原生 connector / typed tool 不強行映射到上述 exit code。直接依它實際回傳的 structured success/error/state 分類，保留原始錯誤語意。

失敗時：

1. 先判斷是 capability、schema/input、auth/permission、server、network 還是 domain error。
2. 只有證據足夠才修參數或重試。
3. 不把 permission denied 當成 tool 不存在，也不把 timeout 當成功。
4. 不用另一個未驗證工具偷偷替代後宣稱原工具成功。

## 6. Mutation 與敏感資料

MCP 可能連到 GitHub、filesystem、database、SaaS 或內部服務。對會改外部狀態的操作：

- 先確認目前 tool 真有 write capability；
- 尊重使用者已授權的目標與範圍；
- schema 要求 file/url/id 時使用真實可接受型別，不自行轉造；
- 不把 token、password、auth header 寫進 command example、log、Skill 或 durable evidence；
- mutation 完成後依可用介面重新 read-back / fetch，不能只相信「request sent」。

若任務本身另有專案級 branch-first、PR、approval、release 或 destructive-action gate，這些 gate 仍然有效；MCP 只是 transport，不是繞過治理的捷徑。

## 7. WHD 專案邊界

- `MCP工具操作` 是外部工具操作 Skill，不是 WHD 機械 domain resolver。
- MCP tool 回傳的尺寸、fixture、測試結果、probe、collision、AI 建議，不會因為透過 MCP 取得就自動成為 product authority。
- 外部 Skill / server / connector 被發現，也不得自動寫進 WHD Registry 或 Skill tree；若要納入專案，仍走 `找技能` → 使用者明確同意 → `寫技能` 的治理流程。
- MCP 呼叫若碰到 GitHub-backed WHD repository，仍遵守 `AGENTS.md`、Preflight、branch-first、remote QA、non-force integration 等既有規則。

## 8. 自我檢查

執行前後確認：

- [ ] `name: MCP工具操作` 與中文資料夾 basename 一致。
- [ ] 已做能力偵測，沒有把 `mcp-cli` 當成普遍存在。
- [ ] 能用原生 connector / typed tool 時沒有無理由降級成 shell wrapper。
- [ ] 已完成發現 → 探索 → schema inspect → execute；沒有跳過 schema 猜參數。
- [ ] 任何 success / write / discovery claim 都有實際結果。
- [ ] CLI 路徑有保留真實 exit code；原生工具沒有被硬套 CLI exit code。
- [ ] secret 未寫進輸出或 durable evidence。
- [ ] mutation 後有 read-back（若介面支援）。
- [ ] 外部結果沒有自動升格成 WHD domain Source of Truth。

## 9. 來源與適配

輸入來源：`github/awesome-copilot` 的 `skills/mcp-cli/SKILL.md`。WHD 版保留其 discovery / schema inspection / execution 與 CLI quick reference，但由專案規則補上 capability detection、native connector 優先、no-fake-tool、schema fail-closed、mutation read-back，以及 WHD authority boundary。

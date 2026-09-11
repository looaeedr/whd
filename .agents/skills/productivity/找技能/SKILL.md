---
name: 找技能
description: 當使用者問「怎麼做 X」「有沒有技能可以做 X」「幫我找技能」「能不能擴充這個能力」，或想搜尋、比較、安裝可重用 Agent Skill 時使用。先理解需求，再搜尋候選、驗證品質、呈現選項；只有使用者明確同意後才安裝，外部 Skill 也不得自動納入 WHD 專案技能樹。
---

# 找技能

這個 Skill 用來從可用的 Agent Skill 生態中**發現、評估、推薦與在取得同意後安裝技能**。核心流程沿用來源檔：理解需求 → 看 leaderboard / 搜尋 → 品質驗證 → 呈現候選 → 使用者決定是否安裝。

它不是「看到一個 Skill 就自動裝」的流程，也不是「找到外部 Skill 就自動把它變成 WHD 專案 Skill」。

## 何時使用

當使用者：

- 問「怎麼做 X」，而 X 很可能已有可重用 Skill；
- 說「幫我找 X 的技能」「有沒有技能可以…」；
- 問「你能不能做 X」，且 X 是專門領域能力，可能需要額外 Skill；
- 想擴充 Agent 能力；
- 想找工具、模板或既有 workflow；
- 表示某個設計、測試、部署、文件或其他領域希望有專門協助。

若使用者已明確要求直接完成一個一般能力足以處理的任務，不要硬把所有問題都改成找 Skill。

## 能力偵測

開始搜尋前先確認本回合**實際可用**的能力：

- 是否能上網或搜尋公開來源；
- 是否可存取 `skills.sh`；
- 是否有 Node/npm 與 `npx skills` CLI；
- 是否有其他可信任的 Skill catalog / package manager；
- 是否真的具備安裝權限；
- 是否能讀取候選 Skill 的來源 repository / `SKILL.md`；
- 若在 repository 內，是否有該專案自己的 Skill governance。

原則：**有就用，沒有就退化，但不得假裝。**

- 沒有 `npx skills` 時，不得聲稱已執行 `npx skills find`。
- 無法開 `skills.sh` 時，不得聲稱看過 leaderboard。
- 沒有安裝能力時，只能提供候選與可驗證資訊，不能聲稱安裝完成。
- 任何「已搜尋／已驗證／已安裝」都必須有本回合**實際結果**支撐。

## Skills CLI

來源檔把 Skills CLI（`npx skills`）視為 open agent skills ecosystem 的 package manager，主要命令為：

```bash
npx skills find [query] [--owner <owner>]
npx skills add <package>
npx skills update
```

需要全域安裝且使用者已明確同意時，來源檔提供：

```bash
npx skills add <owner/repo@skill> -g -y
```

其中 `-g` 表示 user-level/global 安裝，`-y` 跳過互動確認。**只有環境真的有這個 CLI 且具備執行權限時才使用。**

來源檔另提供 `https://skills.sh/` 作為瀏覽入口；可存取時才用它做 leaderboard / candidate discovery。

## Step 1：理解需求

先把使用者需求縮成三件事：

1. **領域**：例如 React、testing、design、deployment。
2. **具體工作**：例如寫 tests、做 animation、review PR、產 changelog。
3. **是否值得找現成 Skill**：若是常見、可重用流程，通常值得搜尋；極專案化的一次性問題可能直接處理更快。

不要只拿使用者一句話原封不動丟搜尋。先萃取 1–3 組具體關鍵字，必要時加入替代詞。

## Step 2：先看 Leaderboard

若 `skills.sh` 可用，先檢查 leaderboard，看看該領域是否已有高使用量、較成熟的 Skill。

這一步是候選發現，不是品質背書。排行榜高不代表自動可信，也不代表適合目前專案。

若 leaderboard 不可用，記錄 capability gap，直接進 Step 3 的其他可用搜尋方式，不得卡住整個流程。

## Step 3：搜尋 Skill

若 `npx skills` 可用，可使用：

```bash
npx skills find <query>
npx skills find <query> --owner <owner>
```

來源檔的搜尋例子：

- React 效能 → `npx skills find react performance`
- PR review → `npx skills find pr review`
- changelog → `npx skills find changelog`

若 CLI 不可用，使用本回合真的可用且可驗證的搜尋／catalog 能力；仍須保留來源、名稱與候選 provenance。

## Step 4：品質驗證

**不得只看搜尋結果就推薦。** 至少檢查：

1. **安裝數量**：來源檔建議優先考慮 1K+ installs；低於 100 installs 要提高警覺。這是 heuristic，不是絕對 PASS/FAIL。
2. **來源信譽**：官方／已知來源通常比未知作者風險低；來源檔舉例包含 `vercel-labs`、`anthropics`、`microsoft`。
3. **GitHub stars / repository evidence**：來源檔建議 repository 少於 100 stars 時提高懷疑程度；同樣屬 heuristic，不是絕對門檻。
4. **實際內容**：能讀 `SKILL.md` 就檢查 trigger、workflow、需要的工具、寫入範圍、安裝腳本與是否含不必要權限。
5. **維護狀態與相容性**：若能取得，檢查近期維護、必要 runtime、是否和目前環境／專案規則衝突。

數字不可取得時就標記 unknown，不得虛構 installs/stars。

## Step 5：呈現候選

**呈現候選**時至少給：

- Skill 名稱；
- 它解決什麼問題；
- 來源 owner/repository；
- 能驗證到的安裝數量／GitHub stars／維護資訊；
- 需要的工具或 runtime；
- 可用時提供安裝命令；
- 可用時提供 `skills.sh` 或來源 repository 的進一步資訊；
- 風險或與目前專案不相容處。

沒有查到的欄位直接寫 unknown / 未驗證，不自行補值。

## Step 6：使用者決定後才安裝

安裝屬於會改變使用者環境的動作：

- **不得自動安裝**。
- 必須先讓使用者看到候選與來源。
- 只有**使用者明確同意**某個 Skill 後，才使用當前環境實際具備的安裝機制。
- 安裝後要以真實命令／工具結果確認成功，不能只因命令已送出就說完成。

若環境沒有安裝工具，提供可執行命令即可，不能假裝已代為安裝。

## WHD 專案納入邊界

「外部 Skill 被找到／甚至已安裝」與「成為 WHD repo 內的 canonical Skill」是兩回事。

- **不得自動納入 WHD** `.agents/skills/**`、Registry、README、Preflight 或 release policy。
- 使用者若只是想在個人環境使用 Skill，到安裝層即可停止。
- 使用者若明確要求「把這個 Skill 加進 WHD」，才轉交 `.agents/skills/engineering/寫技能/SKILL.md`。
- 納入 WHD 必須重新遵守 `AGENTS.md`、Phase6 **Preflight**、branch-first、中文 identity、contract test、AI Library/Registry/release durable writeback。
- 外部 Skill 的內容是輸入來源，不自動凌駕 WHD 專案規則。

例如：外部 `修改DXF` Skill 即使可被找到，也不代表它因此是 WHD Skill；除非使用者另外明確要求納入並通過專案治理。

## 常見 Skill 類別

來源檔建議搜尋時可從這些方向想關鍵字：

- Web Development：react / nextjs / typescript / css / tailwind
- Testing：testing / jest / playwright / e2e
- DevOps：deploy / docker / kubernetes / ci-cd
- Documentation：docs / readme / changelog / api-docs
- Code Quality：review / lint / refactor / best-practices
- Design：ui / ux / design-system / accessibility
- Productivity：workflow / automation / git

## 搜尋技巧

- 具體關鍵字比單一大詞好，例如 `react testing` 優於只有 `testing`。
- 找不到時換同義詞，例如 `deploy` → `deployment` / `ci-cd`。
- 有可信來源時可用 owner scope 收斂結果。
- 不因某個來源「熱門」就跳過 Step 4 品質驗證。

## 找不到 Skill 時

若沒有相關候選：

1. 明確說目前沒有找到符合條件的 Skill；
2. 若一般能力足夠，直接協助使用者完成工作；
3. 若這件事會重複發生，可建議建立自有 Skill；
4. 若 `npx skills init` 在目前環境可用，可提供它作為建立入口；不可用時轉交 `寫技能` 流程。

## 自我檢查

- [ ] `name: 找技能` 與中文資料夾 basename 一致。
- [ ] 已先理解需求，不是看到「技能」兩字就亂搜。
- [ ] leaderboard / CLI / web / install 都先做能力偵測。
- [ ] 沒有把不可用工具寫成已執行。
- [ ] 推薦前做過品質驗證，unknown 欄位沒有腦補。
- [ ] 呈現候選包含來源、用途、可驗證品質資訊與風險。
- [ ] 安裝前取得使用者明確同意。
- [ ] 沒有把外部 Skill 自動納入 WHD。
- [ ] 若要求納入 WHD，已轉 `寫技能` + Preflight + branch-first + durable writeback。

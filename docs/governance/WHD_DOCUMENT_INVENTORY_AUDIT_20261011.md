---
whd_doc_role: REFERENCE
whd_contract: docs-inventory-audit-20261011
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 文檔全樹盤點與權威衝突清查（2026-10-11）

> **REFERENCE／一次性清查證據，不是新的執行入口、權威來源或持續 CI gate。** 現行執行權限依正式 X 的 `AGENTS.md`、`.agents/skills/skill_registry.json`、可信 `tools/change_lane_gate.py`；產品尺寸及製造事實仍依各 CURRENT owner、原始工程圖、實際程式和產品驗收。不得將本表當成覆寫產品資料的授權。

## 已盤點的來源、範圍與界線

- 倉庫：`looaeedr/whd`，正式 X：`cleanup/2d-3d-sync`，本次快照 SHA：`d7a0d4392058be168d9e1fbd13332905af575e47`。
- 透過 GitHub root Contents 與各個頂層樹的 `git/trees/<sha>?recursive=1` 逐一列舉；**2,341 個檔案，其中 888 個以 `.md`／`.rst`／`.txt` 結尾**，各子樹均未標記 `truncated`。
- `AGENTS.md`、現行治理索引、根目錄導覽、AI Library 核心／SOP、59 份 `SKILL.md` 及高優先設計／驗收規則已做內容或 metadata 層級核對；**888 個文件的路徑全數納入清單，但尚不能宣稱每份正文都完成逐行語意驗收**。
- `main` 為不管理的歷史分支，不清理、不同步；不使用 Google Drive／DC／RC 代替 GitHub 此次盤點。

| 正式 X 位置 | .md / .rst / .txt | 分類與處置界線 |
| --- | ---: | --- |
| `docs/` | 450 | 其中 `docs/superpowers/` 436；設計、驗收與歷史證據混合，**不能依日期整批降級** |
| `logs/` | 185 | 日誌與驗收證據，保留原件 |
| `.agents/` | 88 | Skill 及附屬導覽，59 份 `SKILL.md` 已核對 metadata／舊流程關鍵字 |
| `.scratch/` | 54 | 歷史研究、暫存及工單追溯，未證明可丟棄不得刪除 |
| `個人AI檔案庫/` | 38 | SOP、權威導覽及事故庫，按 CURRENT／REFERENCE 分流 |
| `修改日誌/` | 23 | 時序證據，不是目前產品現況 |
| 根目錄 | 24 | `AGENTS.md` CURRENT；交接／說明多已標 REFERENCE／HISTORICAL |
| `BACKUP/` | 13 | 歷史備份，不能誤當 CURRENT |
| `基準檔/` | 7 | 產品／基準檔範圍，不得透過純治理 PR 擅改 |
| `handoff/` | 6 | 歷史快照或 MIRROR 指標 |
| **合計** | **888** | 其餘頂層目录沒有上述副檔名的檔案 |

## 正式權威與舊流程清查

1. `個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md` 的 `WHD_AUTHORITY` 標記共 **36 筆**：29 CURRENT、4 MIRROR、2 REFERENCE、1 HISTORICAL；已列出的 contract **沒有重複 CURRENT**。四筆 MIRROR 的 `path=...` 後面另有 `canonical=...` 註記，解析時不可把兩者串接成一個不存在的檔名。
2. `README.md`、`AI_HANDOFF.md`、`CONTEXT.md`、`DELIVERY_README.md`、`目前主要任務.md`、`handoff/00_AI_HANDOFF_README.md` 等已將歷史或 MIRROR 屬性寫明；本文不再以過時操作段落推翻 `AGENTS.md`。
3. 59 份 Skill 的關鍵字命中須區分「禁止恢復 Flow v2／Phase6 Preflight／lease」與真正的強制入口；不得只憑含字串就刪改原文。工作入口以 `/派工` 雲端施工、exact CI 後有限 `LOCALX_INTEGRATION`，與當次明確 `/接手` RC 施工區分。
4. `docs/superpowers/README.md` 是 REFERENCE 歷史索引，**但** `docs/superpowers/specs/2026-09-21-joint-placement-marking-design.md` 與 `2026-09-16-ci-test-sharding-parallelization-design.md` 等契約仍具 CURRENT 身份；不可把整個 `superpowers` 目錄一刀切當作失效文檔。
5. `docs/specs/WHD_Spec_v1_5.md` 的定稿日狀態屬歷史文字，`docs/specs/WHD_Spec_v1_5_status_readback_20261011.md` 已明確釐清；原規格受 SHA 驗收矩陣保護，不能為修措辭而改寫原文。

## 確認的待處置風險與本輪修正

### A. 治理文字誤導（可經可信白名單直送 X）

- `.agents/skills/engineering/推推/SKILL.md` 在「純治理直送」原本要求建立 `governance/*`、`docs/*`、`skills/*`「**本地分支**」。這可能使代理錯將治理任務改走使用者本機，與 `AGENTS.md` 的 cloud-first／DC 預設禁止牴觸。
- 本次同一治理 PR 只修成「從最新正式 X **以 GitHub／雲端建立治理分支**」，不擴充 DC／RC 權限、不改產品發版路徑、不新增 preflight gate。是否正式上線，以本 PR 的 GitHub 合併與檢查紀錄為準。

### B. 製造基準檔重複且落後（**不可治理直送覆寫**）

- `基準檔/標準基準檔格式.md` 仍保留舊加工層表，沒有 `WHD_DOC_META_V1` metadata，且沒有現行 `加工層分類與定義.md` 的底板／中板 CUTTING Color **30／150**、MARKING Color **212／213** 的新子類規則。
- 現行加工層 CURRENT owner 為根目錄 `加工層分類與定義.md`；`標準基準檔格式.md` 根目錄只是 MIRROR pointer，**與 `基準檔/標準基準檔格式.md` 不是同一個檔案**。
- 不臆斷 `基準檔/` 檔案是否被程式讀取或有加工端相依；先核對呼叫點、規格和回歸，再依 `PRODUCT_LOCALX_ONLY` 更新、降級為非權威參考或維持必要相容性。嚴禁在本次治理 PR 直接刪除或覆蓋該檔。

### C. 分支文檔差異不可偷渡發布

- 本次回讀顯示 GitHub `localX` 較正式 X **超前 52 commits，X 並未超前**；檔案 diff 中四份文檔有差異：新增 `docs/manufacturing/receiving-large-weld-ear.md`，修訂 AI Library 的 `03_常用Prompt指令庫.md`、`05_CAD批次拆圖與特徵萃取規範.md`、`07_WHD技能發現與掃描深模組規則.md`。
- 這些內容已進入 `localX`，**不代表已發布 X**；尤其焊接耳朵製造政策為產品域，正式 X 仍需使用者當次 `/推推`。不可利用本次治理通道搬運上述產品差異。

## 清查判定

- **已執行**：全樹文件清單、權威索引角色統計、重要 CURRENT／REFERENCE／MIRROR 的優先核對、59 份 Skill metadata 與退役流程關鍵字查核、確認一處治理文字錯誤並提出修正。
- **不得宣稱**：已逐行驗收 888 份正文、所有歷史設計已失效、所有 DXF/製造參數已驗收、對本地/正式 X 完成產品發布。
- **下一類實質工作**：產品通道驗證 `基準檔/標準基準檔格式.md` 的權責、實際讀取者與新版加工層顏色相容性；對其餘日期化驗收文件僅保留追溯，不建新流程、不清空歷史。

本檔不新增 GitHub ruleset、定時排程、強制前置關卡或獨立 CURRENT owner。

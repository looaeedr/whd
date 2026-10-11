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
- 透過 GitHub root Contents 與各個頂層樹的 `git/trees/<sha>?recursive=1` 逐一列舉；**原快照 2,341 個檔案，其中 888 個以 `.md`／`.rst`／`.txt` 結尾**，各子樹均未標記 `truncated`。**此數是建檔前的快照，不是永遠固定的當前 X 檔案數**；清查報告經 #1623 建立、#1624 更新後，正式 X 同類文件為 **889**（新增的正是本份治理清查報告）。不得混用快照計數與更新後的 live tree 計數。
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
4. `docs/superpowers/README.md` 是 REFERENCE 歷史索引。已逐份核對 `docs/superpowers/specs/` **74 份** `.md` 的 metadata：**65 HISTORICAL、6 REFERENCE、3 CURRENT**；其中 CURRENT 是 `2026-09-21-joint-placement-marking-design.md`、`2026-09-16-ci-test-sharding-parallelization-design.md`、`2026-09-16-ci-test-sharding-parallelization-revision-notes.md`。因此不可把整個 `superpowers` 目錄一刀切當作失效文檔。
5. `docs/specs/WHD_Spec_v1_5.md` 的定稿日狀態屬歷史文字，`docs/specs/WHD_Spec_v1_5_status_readback_20261011.md` 已明確釐清；原規格受 SHA 驗收矩陣保護，不能為修措辭而改寫原文。

## 確認的待處置風險與本輪修正

### A. 治理文字誤導（可經可信白名單直送 X）

- `.agents/skills/engineering/推推/SKILL.md` 在「純治理直送」原本要求建立 `governance/*`、`docs/*`、`skills/*`「**本地分支**」。這可能使代理錯將治理任務改走使用者本機，與 `AGENTS.md` 的 cloud-first／DC 預設禁止牴觸。
- 本次同一治理 PR 只修成「從最新正式 X **以 GitHub／雲端建立治理分支**」，不擴充 DC／RC 權限、不改產品發版路徑、不新增 preflight gate。是否正式上線，以本 PR 的 GitHub 合併與檢查紀錄為準。

### B. 製造基準檔重複且落後（**不可治理直送覆寫**）

- `基準檔/` 實際有 **四份** `標準基準檔格式.md` 舊表，全部缺少 `WHD_DOC_META_V1` metadata，且沒有現行 `加工層分類與定義.md` 的底板／中板 CUTTING Color **30／150**、MARKING Color **212／213** 的新子類規則。四份不能因名稱相同就當作可以直接刪除的無用重複：
  - exact Git Blob `eee31499f5034ecbcf136588d3564e6a77da6b85`：`基準檔/標準基準檔格式.md`、`基準檔/開孔/標準基準檔格式.md`。
  - exact Git Blob `ebd2c810cc96bb3a995c563ea6aec49b9aa26e2d`：`基準檔/指示燈/標準基準檔格式.md`、`基準檔/金庫型/標準基準檔格式.md`。
- `基準檔/CONTEXT.md` 與 `基準檔/截角資料庫/README_母規則說明.md` 同樣缺少角色 metadata；在核對實際製造、截角計算與程序讀取者前，不能機械補 CURRENT 或將它們替換成單純 pointer。
- 現行加工層 CURRENT owner 為根目錄 `加工層分類與定義.md`；`標準基準檔格式.md` 根目錄只是 MIRROR pointer，**與 `基準檔/標準基準檔格式.md` 不是同一個檔案**。
- 不臆斷 `基準檔/` 檔案是否被程式讀取或有加工端相依；先核對呼叫點、規格和回歸，再依 `PRODUCT_LOCALX_ONLY` 更新、降級為非權威參考或維持必要相容性。嚴禁在本次治理 PR 直接刪除或覆蓋該檔。

### C. 分支文檔差異不可偷渡發布

- 本次回讀顯示 GitHub `localX` 較正式 X **超前 52 commits，X 並未超前**；檔案 diff 中四份文檔有差異：新增 `docs/manufacturing/receiving-large-weld-ear.md`，修訂 AI Library 的 `03_常用Prompt指令庫.md`、`05_CAD批次拆圖與特徵萃取規範.md`、`07_WHD技能發現與掃描深模組規則.md`。
- 這些內容已進入 `localX`，**不代表已發布 X**；尤其焊接耳朵製造政策為產品域，正式 X 仍需使用者當次 `/推推`。不可利用本次治理通道搬運上述產品差異。

## 第二輪深入清查：歷史計畫、驗收、checkpoint、logs（2026-10-11）

> 本節以正式 X 讀取的 Git 樹與個別檔案 frontmatter、GitHub Issue 結案回讀為依據；**是角色與歷史證據風險稽核，不表示這些檔案的製造語意已獲產品驗收。** 舊計畫的保留理由是追溯用，不重啟退役派工／Preflight。

| 目錄 | 路徑數 | HISTORICAL | REFERENCE | CURRENT | 未標角色 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `docs/superpowers/plans/` | 96 | 82 | 10 | 4 | 0 |
| `docs/superpowers/verification/` | 91 | 81 | 3 | 3 | 4 份原始 `.txt` |
| `docs/superpowers/checkpoints/` | 172 | 44 | 22 | 0 | **73 份 `.md`、33 份原始 `.txt`** |
| `logs/` | 185 | 未完成全檔角色統計 | 未完成 | 未完成 | 62 份 `.md`、123 份 `.txt`，抽檢的歷史紀錄無 metadata |
| `.scratch/` | 54 | 未完成全檔角色統計 | 未完成 | 未完成 | 54 份 `.md`，抽檢的 checkpoint／journal 無 metadata |

前三個 `docs/superpowers` 子目錄已**逐件取原文前言／角色資訊**；`logs`／`.scratch` 本節只完成路徑盤點及跨頭尾的抽樣內容檢查，不能把抽樣結果冒充全篇驗收。

### 已結案但仍標 CURRENT 的七份計畫／驗收證據

- `docs/superpowers/plans/2026-09-15-issue280-permanent-test-reconciliation-and-move.md`（Issue [#280](https://github.com/looaeedr/whd/issues/280) 已於 2026-09-15 結案）。
- `docs/superpowers/plans/2026-09-16-issue304-t0-baseline.md`、`2026-09-16-issue305-t1-shard-manifest.md`、`2026-09-16-issue306-t2-non-gui-sharding.md`（Issue [#304](https://github.com/looaeedr/whd/issues/304)／[#305](https://github.com/looaeedr/whd/issues/305)／[#306](https://github.com/looaeedr/whd/issues/306) 均已於 2026-09-16 結案；母票 [#303](https://github.com/looaeedr/whd/issues/303) 於 2026-09-17 結案）。
- `docs/superpowers/verification/2026-09-16-issue304-t0-baseline.md`、`2026-09-16-issue305-t1-shard-manifest.md`、`2026-09-16-issue306-t2-non-xvfb-sharding.md`。

這七份檔案的 CURRENT metadata 與「日期化歷史實作指令／一次性驗收數據」同時存在，形成**角色語意待確認**問題：舊分支起點、RUN、原收集節點數（如 T0 的 2153）不是今天的授權或目前測試數。**不能僅因工單已關閉就斷言其整份領域契約失效**，CI 分片權威仍須跟現在的 `tools/test_shard_execution.py`、現行 workflow 和已核准 CURRENT design 核對；調整原文件需走產品通道 `localX`／必要 CI，不能以本治理報告或治理白名單修改。

### Checkpoint 歷史保留與未標記文件

- `docs/superpowers/checkpoints/` 的 **73 份無角色 Markdown**，包括 `issue334-t1-green-candidate.md`、`issue531-b6-controller-aggregate.md`、`phase4-t0-deep-owner-census.md` 等，保留當時綠燈、批次審核與固定 SHA。**不能根據檔名、日期、單一 GREEN 就視為當前可執行工作**；查閱時先交叉核對現行 Issue／PR／最新 source。
- 另 **33 份原始 `.txt`** 沒有 metadata；原始測試／Preflight 證據不可機械插入 YAML 或改寫內容，應由索引／清查報告說明歷史用途。
- `docs/superpowers/verification/issue678-poweroff-red/approved/` 有四份無 metadata 的原始 `.txt`，同樣保留位元內容與測試追溯，不自行修改。
- `logs/` 有 62 個 `.md`、123 個 `.txt`；`.scratch/` 有 54 份 `.md`。抽檢 `logs/box_body_single_source/T*.state.md`、`logs/preflight/*`、`.scratch/dm*/checkpoint.md`、`.scratch/*/phase6_preflight_evidence.md` 均是日期化執行證據，**沒有理由把其中 READ_SKILL／Preflight 憑證重新升格成 CURRENT 前置**。
- 本節不對過去合法驗收的結果重新判決、不自動刪除，也不創建新的必經 Gate；真正需要刪改原件時，先查引用者與 path classifier，避免破壞追溯或產品守衛。

## 第三輪深入清查：日誌、備份、技能附屬文件（2026-10-11）

以下**僅將 GitHub 正式 X 的角色／用途逐件核對結果記錄到治理報告**，不重寫保留日期與 SHA 的原始材料。先前「logs／scratch 抽樣」的紀錄為第一輪狀態，已由本節的新一輪完整 metadata 查核取代。

| 位置 | 完整清單數量 | 此輪逐檔角色核對 | 正確判讀 |
| --- | ---: | --- | --- |
| `logs/` | **62 Markdown + 123 TXT = 185** | 62/62 Markdown 均沒有 `whd_doc_role` metadata；123 TXT 保留原始證據，不宣稱逐行審完 | 歷史 preflight、QA、回歸與工作紀錄，沒有 CURRENT 權威 |
| `.scratch/` | **54 Markdown** | 54/54 未標角色 | 研究／工單／測試 checkpoint／歷史草稿，不能因 `Status: GREEN` 便重新啟動舊流程 |
| `BACKUP/` | **13 Markdown** | 13/13 未標角色 | 原始備份不可與同名正式文件混用；不刪改 |
| `修改日誌/` | **23 Markdown** | 23/23 未標角色 | 按日期的修改紀錄不是今天的 runtime／交付權威 |
| 根目錄 | **24 Markdown／TXT 類** | 22 份有 `CURRENT`／`REFERENCE`／`MIRROR`／`HISTORICAL` metadata；`bug.txt`、`requirements.txt` 無（非角色文件） | 真 CURRENT 是 `AGENTS.md`、`加工層分類與定義.md`，其餘遵原本宣告的角色 |
| `.agents/skills/**` 附屬 Markdown（排除 59 份 `SKILL.md`） | **29** | 28 REFERENCE、1 HISTORICAL；無未標角色或 CURRENT 附屬副本 | SKILL 附屬說明不能覆蓋 canonical Skill 的規則 |
| `個人AI檔案庫/踩坑庫/` | **15 Markdown** | 15 REFERENCE；無 CURRENT | 事故／防錯參考，不是新執行授權 |

### 舊備份的確定衝突：退役 Preflight 被當成強制入口

- `BACKUP/20260903-210301-AGENTS.md`、`BACKUP/20260903-210816-DEEP-AGENTS.md` 保存歷史標題「啟動硬閘門：先完成 Phase6 Knowledge Preflight，才准做事」；此要求與現在正式 X `AGENTS.md` 的**已退役**規則不同。歷史 backup 只當原文證據，不得被任一 Agent 當正式 startup instructions。
- `BACKUP/20260903-205244-DELIVERY_README.md` 等保留「[CURRENT] 2026-09-02」**當時**的聲明；即使原文沒有改成 `HISTORICAL`，其所在 `BACKUP/` 也不能作當前 CURRENT owner。
- 已核對目前正式 X 的 `tools/knowledge_governance.py`：`SKIP_PARTS` 包含 `.scratch`、`BACKUP`；`is_governed_markdown()` 不把 `logs/`、`修改日誌/` 當作受管制的 CURRENT Markdown 權威路徑。因此**已存在權威邊界**，本次不新增另一套 gate、不改老備份或生硬補 YAML。
- 必須區分兩種掃描：`_iter_reference_texts()` 可以讀取未排除的普通文字供分析，**「被索引到」不等於具有正式權威**。不能因搜尋命中舊文字而執行已退役工單交易／Preflight。
- 上述路徑的數量統計只是 metadata／開頭身分核對，**不代表全部 239 份 logs／scratch 正文逐行語意審核完成**。真正現行行為仍需核對產品 code、CURRENT spec 與驗證證據。

## 第四輪正文引用審查（2026-10-11）

- 以正式 X Git tree `5d95ae2173d82bdc8ac03ecae381e355a0ca185a` 的實際 Blob 路徑核對 12 份主要 CURRENT 規格／AGENTS、**59 份** `SKILL.md` 與 **17 份** AI 專案 SOP 內 backtick 標示的 repo-root 檔案引用。主要 CURRENT 規格與 active Skill 的**既存型態 repo-root 引用**未發現確定的失效路徑；此掃描不是對未加 backtick、Markdown 相對連結或所有語意的完整證明。
- `.agents/skills/engineering/setup-matt-pocock-skills/SKILL.md` 所述 `docs/agents/issue-tracker.md` 等是該 Setup Skill **預計建立**的輸出，當前不存在是設計情境，不是壞掉的現行依賴，故**不亂補空檔**。
- `個人AI檔案庫/第二層_專案與SOP/07_WHD技能發現與掃描深模組規則.md` 的 `tests/test_check_zh_tw_report.py`／`tests/test_skill_sources_zh_tw.py` 指向同目錄支援，真實來源在 `.agents/skills/engineering/掃描深模組/tests/`，不是 root `tests/`；`tests/knowledge/test_skill_catalog_classification_contract.py` 則在正式 X Git 樹不存在，後續須在產品通道核對替代測試身分，**不可用相近檔名冒名替代**。
- `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md` 仍保存多項已退役 claim／scheduler helper 與失效程式路徑，屬日期化歷史事故。不可憑 REFERENCE 文件提到 `tools/stale_claim_takeover.py` 就重建 Flow v2；歷史可追溯性需要保留。
- **已實修**：同在治理白名單的 `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`，原先把已不存在的 `tests/knowledge/test_knowledge_authority_contract.py`、`tests/knowledge/test_active_skill_runtime_contract.py` 宣稱為實際 machine guard。本輪保留歷史檔名供查核、明確標不存在；正確核對目前存在的 `tests/knowledge/test_current_history_authority_contract.py`、`tests/knowledge/test_knowledge_authority_classification.py`、`tests/knowledge/test_skill_registry_coverage_contract.py` 和 `tests/knowledge/test_skill_registry_domain_reference_contract.py`；**不把 Registry coverage 冒稱 runtime fallback 全覆蓋**。修改走同一治理 PR #1627，適用 X trusted Change Lane Gate。
- **產品文檔正文最小修正**：另由 `localX` 基準開立 [PR #1629](https://github.com/looaeedr/whd/pull/1629)，對前述七份結案計畫／驗收文檔保留 CURRENT 元資料與所有原始 run/SHA，僅加時效說明；新增既有產品回歸測試以觸發真正的 exact-HEAD Product Regression。**2026-10-11 最新狀態回讀**：此 PR latest HEAD `aab737a83fa8d72ccde07a2f7e9d56f6683a1ac2` 的 Product Regression [#38139520828](https://github.com/looaeedr/whd/actions/runs/38139520828) 已 `completed/success`，但 GitHub PR 仍 OPEN，尚未合法整合至本機／GitHub `localX`，因此**未進正式 X**；未獲當次 `/推推` 不能發布。

## 第五輪正文指令殘留修正追蹤（2026-10-11）

- **已合併正式 X [PR #1634](https://github.com/looaeedr/whd/pull/1634)**，merge SHA `993bd292908bbc1d7ecd0cac3aca2f8f5f9618c8`：`個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md`、`issue_closure_completion_pitfalls.md`、`root_local_first_entry_gate_pitfall.md` 已將舊 continuity／finalization／root-local-first machine ownership 直接在原文正名為歷史，並有 `tests/knowledge/test_current_history_authority_contract.py` regression 保護；保留事故原件與 PR／CI provenance。
- **已合併正式 X [PR #1638](https://github.com/looaeedr/whd/pull/1638)**，merge SHA `c71cb1595614e2693b563945e821b30d4e8b6b36`：`deterministic_repo_migration_pitfalls.md` 的舊 `WORKSPACE_DEFAULT` 命令歸入歷史；`preflight_keyword_boundary_pitfall.md` 區分仍有用途的 matcher 相容性與退役的強制 Preflight receipt。兩項治理 CI 均全綠並有 X readback。
- **本輪治理候選**：`issue_closure_completion_pitfalls.md` 內殘留 `Canonical Skill`／`Machine guards`／`Registry route` 小標題，以及 `continuous_execution_pitfalls.md` 三處 `永久規則：`，雖位於 HISTORICAL 段仍易被檢索摘要誤判為現行。擬以最小文字修正標明「當時」並新增防回歸測試；實際發布須以新 PR 的可信 CI／合併回讀確認，**此報告本身不是已交付宣告**。
- **產品域仍待整合**：#1629 的 7 份歷史 CI 計畫／驗收、`06_踩坑記錄與防錯經驗庫.md`／`07_WHD技能發現與掃描深模組規則.md` 已做原位修正，latest HEAD exact CI GREEN 但 PR OPEN。其分類為產品通道而非本治理白名單，不能偷渡正式 X，也不能把 GitHub OPEN/CI GREEN 說成已同步本機。
- 未變更產品 DXF、加工層顏色、CUTTING／MARKING owner、`main` 或本機。保留跨域產品判斷給 `localX` 的真實回歸與工程來源。

## 第六輪：OPEN PR 分支保護與誤導性關單測試引用（2026-10-11）

- `個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md` 為 **REFERENCE**。再次抽查發現其「OPEN PR head/base refs 不可刪」這項仍有效的安全原則有真實實作：`tools/branch_cleanup_ref_guard.py` 仍存在，內含 `protected_open_pr_refs`、`assert_delete_candidates_safe`，對缺失或錯誤的 ref evidence fail closed。**不能把此安全工具與已退役的 finalization/claim 工具混為一談，也不應移除有效安全規則。**
- 但該文件聲稱存在的 `tests/process/test_branch_cleanup_ref_guard.py` 在本次正式 X Git tree 不存在。這次把測試收斂在已被 Knowledge Governance Bootstrap 現行 workflow 呼叫的 `tests/governance/test_default_branch_explicit_x_contract.py`，新增 `test_open_pr_head_and_base_refs_fail_closed` 實際覆蓋 head/base refs、`refs/heads/` 格式及 malformed evidence。**沒有新增工作流啟動步驟或多一條排程硬閘門。**
- 同一份 REFERENCE 的 `authorize-finalization`／`verify-finalization-proof` 仍有「必須」用語，現已原位改標 `HISTORICAL`，避免使用者從搜尋片段誤認為現行 closing gate；有效的 GitHub Issue／PR readback 與禁止假證據原則不變。
- 本輪僅為候選治理 PR 的已施工內容；**通過 exact-head 可信治理 CI、合併 X 並回讀**之前，不宣稱本節已正式上線。
- 另有第一層 `04_全域AI協作規則.md` 的「每票先建 Issue」段落，屬 `REFERENCE` 且含舊轉派欄位。當前已有雲端直送治理分流；該檔不在治理直送白名單，不能因本次發現就越權修改，應先核對其適用對象及變更通道。

## 第七輪補充：產品工作 PR 與正式 X 發布 PR 的規則適用範圍（2026-10-11）

- 現行 `docs/governance/WHD_DIRECT_GOVERNANCE_PUBLISH_POLICY.md` 原「Product/mixed PR 只能以 `localX` 為 head，且要使用者 exact `/推推`」易被脫離上下文引用，錯誤地套用到日常 **base=`localX` 的產品工作 PR**，造成每張單被要求額外 `/推推`。實際受信任 `tools/change_lane_gate.py` 僅對 **base=`cleanup/2d-3d-sync` 的正式 X PR** 驗證產品 head=`localX` 及 owner exact `/推推`。
- 這次對 CURRENT governance policy 做**適用範圍文字澄清**：`X ← localX` 正式產品發布仍嚴格要求當次 `/推推`；`work branch → localX` 則依 `AGENTS.md`／既有工單授權完成 exact CI 與合法的本機優先整合，不需每張工作 PR 另下 `/推推`。**不修改 trusted gate 程式、不放寬任何 X 發布驗收**。
- 在既有會由 Knowledge Governance Bootstrap 呼叫的 `tests/process/test_change_lane_gate.py` 補文字／實際 `evaluate_pr` 雙重回歸，防止這兩種 PR 角色再次混為一談。本節是本次候選的施工證據，正式上線與否仍以新 PR CI、merge／readback 為準。

## 第八輪：Markdown 連結與 repo 引用回讀（2026-10-11）

> 此節只陳述本次已逐檔取得的 GitHub 正式 X 原文與相應 live repo path 比對，**不是所有文件／所有未加 backtick 文字的全域無錯保證**。歷史範例、相對於 AI Library root 的簡寫及未在 Git 的使用者本機路徑，不能單憑 repo-root path regex 就認作壞連結。

### 相對 Markdown links

- 已核對 `docs/governance/` **8** 份及 `個人AI檔案庫/踩坑庫/` **15** 份 Markdown 之顯式 `[label](target)` 非 URL 相對目標：**共 23 份，未出現此型態的相對連結**，故本次未發現可修的失效 Markdown 相對超連結。未聲稱所有 backtick 檔案名稱、純文字提及或外部 URL 都有效。
- 又核對 `docs/` 非 `superpowers`、非 `governance` 的 **7** 份計畫／產品規格／readback，亦未發現此型態相對 Markdown 連結。
- 根目錄 `README.md`、`AI_HANDOFF.md`、`CONTEXT.md`、`DELIVERY_README.md` 與 `handoff/` 四份代表性說明已查內文 repo-root 反引號引用；`handoff/00_AI_HANDOFF_README.md` 的 `../AGENTS.md` 等為**真正存在的相對路徑**，不能誤報成找不到 root `../AGENTS.md`。
- `個人AI檔案庫/第一層_核心檔案/05_反饋學習與自我演化機制.md` 中 `第一層_核心檔案/...`、`第二層_專案與SOP/...` 使用的是**AI Library 根目錄相對慣例**，其檔案實際存在；不應擅自替換成不存在的 Git root 路徑。第一層 `03` 的舊 `Z:/改DXF/AGENTS.md` 屬歷史本機路徑，不能當成 Git 缺檔要求下載或啟動 DC。

### 真正過時的參考來源：已在 localX 有修正，不可重複施工

- 正式 X `個人AI檔案庫/第二層_專案與SOP/05_CAD批次拆圖與特徵萃取規範.md` Blob `7cc78f8cba17c8024ce2b570427f1d86beafe616` 仍稱 `Z:\\Ollama-整合whd\\` 為最新一體化專案，並稱透過 repo 已不存在的 `modules/ae_adapter.py` 對接製造。
- GitHub `localX` **已有原位修正**：Blob `0224e682f0e0f57daec8becc28175b37d26b8b55` 將它正名為 `REFERENCE／歷史拆圖方案`，不假稱舊 Windows 路徑與 Adapter 是現行入口；同份 Blob 亦已存在於 #1629 的工作分支。這是**已在 localX 的產品文件修正，不代表正式 X 已發布**。正式製造 public boundary 的實際原始碼為 `ae_engine/manufacturing_api.py`；`gui_modules/application/manufacturing_adapter.py` 是既有 UI state → AE contract 的 adapter，**不可據此推論原始 CAD 批次萃取入口已經實作或驗收完成**。
- 同時核對 #1629 的其他三個代表性檔案 Blob：`06_踩坑記錄與防錯經驗庫.md` 在 GitHub `localX` 與 X 相同、尚不等於 #1629 版本；`07_WHD技能發現與掃描深模組規則.md` 的 localX 與 #1629 各有不同 Blob；`docs/superpowers/plans/2026-09-16-issue304-t0-baseline.md` 在 localX 與 X 相同、尚未含 #1629 註記。**不能把 #1629 全部分支當作已整合，也不能用較舊分支覆寫 localX 的較新內容。**
- #1629 的實際 GitHub PR 仍 OPEN；後續須以新 `localX` HEAD fresh compare、actual product diff、exact CI 與已授權的安全整合處理，正式 X 仍僅由當次 `/推推` 發布。這不是提出任何新的製造規格、CLI 強制門檻或 DC／RC 授權。

## 第八輪：引用關係及回歸實際執行鏈（2026-10-11）

- 逐檔檢查 `docs/governance/` 8 份與 `個人AI檔案庫/踩坑庫/` 15 份 Markdown 形式的相對連結，**沒有發現失效的相對 Markdown URL**。範圍僅此 23 份的 `[文字](相對路徑)`；這一結論不擴大到全部文件，也不代表行內反引號引用已驗證。
- 用最新正式 X Git tree 比對 **17 份 AI 專案 SOP**、**39 份工程 `SKILL.md`**、根目錄、交接與主要規格的反引號 repo-root 檔案路徑。Skill 唯一以 `docs/agents/*.md` 形式出現的缺檔，屬 setup Skill **預定生成的輸出**，不應建立假檔；真正殘留的失效路徑集中於 `06_踩坑記錄與防錯經驗庫.md` 與 `07_WHD技能發現與掃描深模組規則.md`，已在產品 PR #1629 提交修訂但**尚不代表合併／發布**。另 `WHD_20261010_retired_process_provenance.md` 中失效程式路徑為刻意保留的 HISTORICAL 原文，不能誤當 CURRENT。
- **發現驗收接線缺口**：先前治理 PR #1634／#1638／#1639 的反退役規則案例寫入 `tests/knowledge/test_current_history_authority_contract.py`，但正式 X 的 `Knowledge Governance Bootstrap` 只運行列舉的 `unittest` 檔及 Markdown inventory，沒有實際執行上述 pytest 函式。故不能以那些 PR 的 CI GREEN 推論「新寫的每項反退役案例都跑過」。
- **本輪最小實修**：在既有 `.github/workflows/knowledge-governance-bootstrap.yml` 加入該 suite 的 `python -m pytest` 及必要 pytest 安裝，並讓僅修改該測試檔也能觸發原有 workflow；在已被 CI 執行的 `tests/governance/test_default_branch_explicit_x_contract.py` 補接線回歸。**沒有另建 workflow／排程或第二道硬閘門**。此為治理白名單候選，是否全綠及實際合併，以本次 PR 的 exact HEAD run、X readback 為準。
- 未動使用者本機、`main`、製造圖面與產品 `localX`；不能把治理 CI 的執行結果當作產品回歸通過。

## 清查判定

- **已執行**：全樹文件清單、權威索引角色統計、重要 CURRENT／REFERENCE／MIRROR 的優先核對、59 份 Skill metadata 與退役流程關鍵字查核、確認一處治理文字錯誤並提出修正。
- **不得宣稱**：已逐行驗收 888 份正文、所有歷史設計已失效、所有 DXF/製造參數已驗收、對本地/正式 X 完成產品發布。
- **下一類實質工作**：產品通道驗證 `基準檔/標準基準檔格式.md` 的權責、實際讀取者與新版加工層顏色相容性；對其餘日期化驗收文件僅保留追溯，不建新流程、不清空歷史。

本檔不新增 GitHub ruleset、定時排程、強制前置關卡或獨立 CURRENT owner。

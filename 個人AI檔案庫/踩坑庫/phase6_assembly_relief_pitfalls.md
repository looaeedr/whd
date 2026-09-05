
## 2026-08-29：已知公式不能被 3D discovery 覆蓋
- 錯誤模式：已知正確 INSERT 公式應為 38×27，但 3D skin intersection 可能求出 38.98、39 或回退 40。
- 正確做法：CERTIFIED registry 命中後，3D 只能 shadow validate，不得改答案。
- 注意：registry 存公式與 precondition，不存單一 dead dimension。沒有 precondition 的 38 會傷到其他拓撲。

## 2026-08-29：資料庫化不能只做 solver 前的 metadata lookup
- 錯誤模式：只在 3D solver 前新增 registry，但 Door/Base/Indicator/known-model GUI 仍自己硬建 C01~C04，形成兩份 Source of Truth。
- 正確做法：固定板件 adapter、known-model state、assembly relief lookup 都消費同一 family-aware registry；legacy constants 僅保留舊資料/API compatibility。

## 2026-08-29：Head semantic TOP 不等於 canonical `top_*` 角名
- Head manufacturing scene 最後會 Y mirror；semantic TOP joint 在 Head canonical material 是 physical bottom，Tail 才是 physical top。
- Registry formula 若把 Head/Tail 都直接切 `top_left/top_right`，尺寸看似合理也可能切錯實體角。

## 2026-08-29：fallback 開關不能關掉 Certified Registry
- 「未知組合允許3D求截角」只能控制 registry MISS 後的 discovery。
- CERTIFIED lookup 必須永遠執行；否則操作員關掉 3D fallback 反而會失去最可信的已知公式。

## 2026-08-29：3D promotion 不得一鍵寫正式資料庫
- GUI 只能建立 `PROMOTION_CANDIDATE` manifest。
- 必須經多參數、Head/Tail、2D/3D/assembly、Save/Reload、拓撲穩定回歸與人工核准後，才可升為 `CERTIFIED_FROM_3D`。


### 2026-08-29：把 3D 候選 16×23 + 14×4 誤升格為 linked-FW C04 公式
- 症狀：linked-FW INSERT_OVERLAY 被錯寫為 primary_u=side+0.5T、secondary_u=side-0.5T，T=2/side=15/FW=25 得到 16×23 + 14×4。
- 根因：把 3D backprojection 的候選 band 當成已知 C04 製造公式，且沒有先回查 2026-08-21 已認證契約。
- 正確：C04 primary_u=side_fold+FW；secondary_u=side_fold+0.5T；linked-FW 無 ytop1 時 primary_v=FW-1T；因此 fixture = 40×23 + 16×4。
- 防線：INSERT/OVERLAY topology_levels=1；INSERT_OVERLAY=2；registry lookup 必須驗證 evaluator 實際 stage count。任何不符直接拒絕。

## 2026-08-29：正式組合圖不可變成 Joint Registry Debug Console

- 症狀：加入 Assembly Joint / WRAP / Registry 診斷後，正式組合圖長出 Joint 選擇、Registry/preserve/relief/pre-post 狀態字串、彩色 penetration segment 或方向箭頭；修正時又可能因「把診斷 UI 全刪」而誤傷正常 operator 功能。
- 根因：把 `ResolvedManufacturingGeometry.diagnostics` 的「內部診斷資料」和 operator assembly render bundle 的「正式 drawing layer」混成同一層。
- 正式規則：diagnostics 可以留在 solver/registry Source of Truth，但正式組合圖預設只顯示製造必要內容。Joint/Registry 詳細診斷只從專用診斷入口查詢。
- 修法邊界：修在 query/render adapter 邊界，不可為了隱藏畫面而改 canonical material，不可順手改 Door / Base Plate / 單板 FinalScene / Save-Reload 等無關資料鏈。
- 回歸要求：修改前後必做 operator UI inventory + scene geometry 摘要比對；除明確要移除的診斷污染外，任何控制項、板件、尺寸、碰撞顯示或幾何減少都算回歸。
- 對應 Skill：`.agents/skills/engineering/phase6-assembly-view-boundaries/SKILL.md`。
## [HISTORICAL/SUPERSEDED — 不可作 runtime oracle] 2026-08-29 — OVERLAY flat-X：名義 FW 與箱身成型 FW 混淆
- 症狀：`金庫型貼外.p6fold` 曾被算成上方 40/320，之後又錯改成 25/350；兩者都沒有以組裝後實體占位作最後驗證。
- 根因：把「EndCap 沒有 X BEND」錯解成「上方 X relief 只需 EndCap nominal FW」。實際插入/避讓對象是箱身折好後的 FW 占位。
- 正解：EndCap nominal FW 保持 25；Box Body `fw_left/fw_right` 由 Fold Profile + T 求 formed occupation。此 fixture T=2 時 formed FW=29，因此上方每側 29、中央 342，任一側 `29+371=400`；Y 仍依 EndCap FW25 算 39。下方 1.5T 仍每側 3、中央 394。
- [HISTORICAL/SUPERSEDED — 不可作 runtime oracle] 當時 Registry `ENDCAP_TOP_OVERLAY_STANDARD_V1@2` 使用 `BOX_BODY_FORMED_FW` / `mating_width`。此條只保留踩坑演進證據。
- Persistence：舊 `.p6fold` committed relief 是 cache。contract version / formed-FW fingerprint / registry revision 不合就失效 fresh solve，禁止重播舊 40。
- 防線：3D `shadow_validation` 與 `ResolvedManufacturingGeometry.relief_rules` 都保存 geometry evidence；2D/單板3D/組合圖/Save-Reload 共用 canonical material。
- 對應 Skill：`.agents/skills/engineering/phase6-overlay-relief-basis/SKILL.md`。


### [CURRENT] 2026-09-02 — OVERLAY v3 修正
- Active rule 是 `ENDCAP_TOP_OVERLAY_STANDARD_V1@3`。正式 CUTTING 回到 STANDARD + semantic delta：`primary_u=side_fold+FW`、`primary_v=ytop1+FW-T`、`secondary_u=side_fold`、`secondary_depth=T`。
- fixture `T=2/side_fold=15/FW=25/ytop1=16` = `40×39 + 15×2`。
- formed FW 僅作 3D shadow / collision evidence，**不得作 runtime oracle**。
- `40×23 + 16×4` 仍是 linked-FW INSERT_OVERLAY fixture，不得移植到標準 OVERLAY。

## 2026-08-30 — WRAP 不可塞進高階組合方式，也不可每次重跑 3D

- 受電箱的側背分離是箱身結構；封頭／封尾仍是 INSERT / OVERLAY / INSERT_OVERLAY。
- 外側包覆 WRAP 只屬封頭／封尾下方的局部 Joint 條件，不應放進高階「組合方式」選單。
- 已認證 WRAP 截角必須直接由 Registry 公式產生；3D 用於未知 geometry discovery 或 shadow/regression，不得每次重新求已知答案。
- WRAP 的展開料算法不能直接沿用其他組合方式；但 Head/Tail 通常連動的是設定，不是 final material Polygon。
- 受電箱 core-origin placement 不能全域套到金庫型／自訂；Family scope 必須同時進 Viewer 與 Collision Solver。
- 改任何截角或 3D 圖時，必須執行 `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`。

## 2026-09-04 — targeted gate 已跑完，但 Tk/Xvfb teardown 不退出，不等於 production failure

- **事件**：Multi-Door / Assembly targeted gate 的測試本體已完成；兩顆 Assembly probe 串在同一 pytest process 時，stdout 只留下局部進度，程序未正常退出。拆成單 nodeid、使用自管 Xvfb 與獨立 process group 後，兩顆都 PASS；完整 targeted gate 最終為 **82/82 PASS**。
- **錯誤模式**：看到外層 timeout、pytest process 未退出、或只看到 `.`/局部百分比，就直接宣告 production fail；或者反過來只看到點號就把它當 PASS。
- **根因**：Tk / Matplotlib / Xvfb / interpreter teardown 與 production assertion 是不同層。GUI 測試可能已完成 assertion，但 event loop、child process 或 wrapper 還活著；也可能其實只跑到中途，因此必須以 pytest 最終 summary + process 狀態分類。
- **正確判定**：
  1. 有完整 `N passed`/`N skipped` summary、failed=0、errors=0，但程序不退：標記 `complete_teardown_timeout`，kill 整個 process group，該 nodeid 不重跑。
  2. 只有點號、局部百分比或沒有完整 summary：標記 `incomplete_timeout`；不是 PASS，也不是 production FAIL。縮到單 nodeid / prefix isolation 找 order-dependent teardown 或真 failure。
  3. 只有 pytest 自己明確 `FAILED` / `ERROR` / collection failure 才算真正 RED。
- **防線**：每批獨立 process group；runner 自管 Xvfb；timeout 後先讀 log/journal，再 killpg；已完成 nodeid 從 pending 移除；teardown 問題另開 harness 工單，禁止修改幾何公式來掩蓋。
- **對應 Skill**：`.agents/skills/engineering/派工/SKILL.md`、`.agents/skills/engineering/phase6-release-packaging/SKILL.md`。

## 2026-09-04 — fresh-extract / restore 造成 execution tree 混合狀態，不能靠聊天記憶續工

- **事件**：T04 執行中發現工作目錄部分檔案回到 fresh-extract 原始版、部分仍保有 T01–T03 修改。若直接續工，測試結果會混合兩個 source tree，無法證明任何 checkpoint。最後以 **T03 已驗收 checkpoint ZIP** 為唯一可信基準完整恢復，再重放 T04 未驗收變更。
- **錯誤模式**：fresh extract、工具回合重建、手動複製檔案或 checkpoint restore 後，只看 mtime、某幾個檔案內容、pytest collection SHA，或依聊天記憶判斷「應該接得上」就繼續修改。
- **根因**：collection SHA 只證明測試 nodeid 集合，不證明 production source tree identity；部分舊檔 + 部分新檔的 execution tree 仍可能收集出完全相同的測試集合。
- **正確恢復**：
  1. 每個已驗收 checkpoint 保存來源 archive/checkpoint SHA、所有已修改 production/test/skill 檔 SHA256，以及可重算的 execution-tree fingerprint。
  2. 任何 fresh extract / restore / 手動複製後，**先重算 fingerprint 再 resume**。
  3. fingerprint 不符即視為混合狀態：隔離或丟棄該目錄，從最近已驗收 checkpoint 在乾淨目錄**完整還原**，驗 fingerprint 一致後才重放尚未驗收工單。
  4. 禁止「挑幾個看起來舊的檔案補拷貝」後繼續；那仍然沒有可證明的 tree identity。
- **防線**：journal collection SHA + execution-tree provenance 必須同時一致；其中任一不一致都不能 resume。
- **對應 Skill**：`.agents/skills/engineering/派工/SKILL.md`、`.agents/skills/engineering/執行開發任務/SKILL.md`、`.agents/skills/engineering/phase6-release-packaging/SKILL.md`。


## 2026-09-04 — 長任務沒有固定進度回報，使用者會無法判斷是否真的仍在執行

- **症狀**：派工／長回歸實際仍在跑，但對話長時間沒有狀態更新；使用者只能反覆追問「還在跑嗎／怎麼停了」。
- **根因**：把「不能因回報而停工」錯解成「可以長時間完全不回報」，缺少固定 cadence 與最小回報欄位。
- **正式規則**：Phase6 派工任務未完成期間，**每 30 秒至少回報一次目前進度**。每次至少包含：目前工單、正在做的事項、最新測試或進度數字、是否有阻塞。
- **不中斷原則**：進度回報是觀測點，不是 checkpoint gate；不得因回報而暫停、等待、結束或重啟正在執行的任務。若單一不可中斷工具呼叫超過 30 秒，返回控制權後立即補報；不得為了湊 30 秒頻率殺掉正常測試或 process group。
- **防線**：`.agents/skills/engineering/派工/SKILL.md` 與 `.agents/skills/engineering/執行開發任務/SKILL.md` 都必須保留此條；技能自檢需驗證「30 秒」「目前工單」「最新測試/進度」「不得中斷」四個語意存在。

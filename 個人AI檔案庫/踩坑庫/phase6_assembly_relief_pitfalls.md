
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


## 2026-09-06 — Receiving 底板：安裝關係、datum、orientation 是三個不同層
- **事故**：使用者已確認「底板基準就是箱體底面，問題是幾何至少一半跑出箱體」，分析卻曾因「後方內側安裝、折邊落在後面板」而推論應換 placement 面／整片方向。
- **正確分層**：
  1. Assembly datum：使用者/產品已確認的基準。
  2. Installed relation：成形後哪些折邊貼到哪個表面。
  3. Local→world orientation / per-cell offset：真正可能造成越界、鏡像、半片出箱的變數。
- **防線**：RED 同時 assert datum 不變 + world bounds 合法 + per-door ownership。只驗中心點或視覺位置不足。
- **一門一底板**：Receiving 多門時 Base Plate topology 必須跟 Door cell stable id 1:1；先修 physical topology，再修 placement。

## 2026-09-06 — Dynamic Door/Box Body GUI 必須分 fresh-open 與 live family-switch 兩條 lifecycle seam
- **事故**：fresh-open Receiving dynamic Door 可切換，因此一度誤判 selector 已 GREEN；exact 操作 `金庫型 → 3D 已開 → baseline_model_var=受電箱` 下，workspace 已有 dynamic Door，visible menu 卻沒 refresh。
- **遠端證據**：run `34040520812`：Door live-switch RED；同一 run 的 Receiving 三片 Box Body child sections live-switch probe PASS。
- **防線**：family topology GUI regression 至少分 fresh-open 與 designer-open live-switch 兩條；兩者都驗 physical parts、selector entries、callback activation、settings-page rebuild。
- **避免假修**：不得只在 designer init 建 selector；topology transaction 後必須由 authoritative available-parts state 驅動 refresh。

## 2026-09-06 — GitHub branch 是 execution tree 時，不得拿 ZIP checkpoint 做 3D regression A/B
- **事故**：曾以 ZIP extract 跑 3D/Base Plate 修改與 test，再拿 ZIP 原版單測作 A/B，與真正 `cleanup/2d-3d-sync@cf217e3` 無法建立 commit provenance。
- **防線**：3D/placement regression A/B 兩端都要是可定位 Git ref / commit / checkpoint fingerprint。ZIP 只有使用者明確指定為 baseline 才可成為端點。
- **處理**：execution tree 錯時，所有幾何 PASS/FAIL、world bounds、checkpoint ZIP 都標 REVOKED，從最近可信 Git HEAD 重新 RED。

## 2026-09-07 — Divider 截角不得從 DXF 外框偷答案

- **CURRENT**：Receiving Divider 包外四段為 `18 / FW / 106 / 17`；`T=2, FW=29` 材料為 `16 / 25 / 102 / 15`。舊 Receiving 五段資料只保留歷史證據，不得作 runtime oracle。
- `中隔.dxf` 的 CUTTING 外框不是現場截角 Source of Truth；正式 runtime 只消費固定孔/基準特徵。若拿 DXF 外框直接當 Final Material，會讓測試假綠，也無法應付 W/T/FW/箱身結構變動。
- Divider relief 必須由真實 `box_body:left_side/right_side` 世界幾何碰撞求 candidate，再 backproject 回 pre-core relief domain 並 refold 驗證；沒有 side-piece geometry 就 fail closed。
- `box_body` aggregate 與 physical pieces 不可混為一談。GUI/2D 若只看到 aggregate，會同時造成「多件式看起來只有一件」與 collision source 缺失等假象。
- Dynamic physical IDs 不得被 legacy label whitelist 過濾；`PART_LABELS` 不是 topology/physical identity authority。



## 2026-09-08 — Divider relief verified 前必須先有 FW placement certificate

- **事件**：Receiving Divider 在舊 placement 下，即使 FW 成形面沒有與 BoxBody FW 成形面面齊，3D collision solver 仍可算出 cut polygon 並回傳 `verified=True`。這代表 collision replay 自洽不等於 assembly placement 正確。
- **已驗證防線**：任何 Receiving Divider relief promotion 前，先建立 `DIVIDER_FW_FACE_FLUSH_V1` placement certificate：
  1. BoxBody `left_side` / `right_side` 的實際 FW physical skins 必須互相一致；
  2. Divider semantic FW segment 的實際 physical skins 必須與上述 BoxBody FW skins 共面；
  3. Divider placement 必須保證 FW → core 的方向朝 family `inward_vector`。
- 上述任一失敗時，solver 必須 fail closed，回 `INVALID_DIVIDER_FW_PLACEMENT`，不得建立 `divider_assembly_relief.verified=True`。
- **重要**：T48-1 正確 placement 後，某一 fixture 的動態 collision output 約為左右 26 mm；這只是該 fixture 的 runtime evidence，**不是固定截角規格，也不得寫入 Registry 當 oracle**。
- 舊測試若硬鎖 `1 mm`、`47/26` 或其他單次 probe 數值，應改成驗幾何 invariant：實際干涉存在、動態 cut > 0、對稱 fixture 結果符合對稱、post-solve illegal penetration 歸零、合法 mating contact 保留。
- T48-2 remote acceptance：run `34168152160`，`13 passed / 0 failed`，`config.ini` SHA256 前後一致。


## 2026-09-08 — Combined Acceptance 的舊 numeric oracle / stale fixture 不得反壓 production

- **事件**：T48 第一輪 Combined 已有 167 PASS，但剩 10 FAIL。逐顆分類後，1 顆 Issue40 仍鎖舊 `rigid_delta` 數值、8 顆 collision fixture 沒帶 production 已要求的 canonical BoxBody Fold Profile、1 顆 multi-piece blank fixture 沒帶現行 `canonical_strip_render_data`。
- **判定規則**：production 已有 fail-closed contract 時，舊 fixture 缺必要 authority 不是理由去放寬 production；probe-derived numeric delta 也不是產品 oracle。
- **正確修法**：
  1. semantic datum 測試驗證 `anchor_after - anchor_before == rigid_delta` 以及 post-relief center + mother datum 的幾何關係，不鎖某次 world/probe 數字；
  2. collision fixture 必須供應 canonical BoxBody Fold Profile，不能靠缺省舊路徑；
  3. multi-piece fixture 必須完整符合目前 render-data contract，不得用舊 constructor 形狀假裝 production regression。
- **驗證證據**：只重跑第一輪 10 個失敗 node，run `34168772770` 得到 **10 PASS / 0 FAIL**，且 `config.ini` SHA256 前後一致。
- **永久防線**：Combined failure 先分類 requirement regression / production regression / stale test oracle / stale fixture；只有前兩類才修改 production。不得為了讓歷史測試回綠而撤掉 canonical geometry 的 fail-closed 要求。

## 2026-09-08 — Divider Physical Geometry Contract：sink 不得重新解 Fold/FW/relief

- **Divider Physical Geometry Contract** 收斂 family Fold Chain、core physical segment、FW physical face、placement datum、canonical relief 與 final material；下游只看 resolved result。
- `frame_width_segment_index` 可作 Divider module 內的 implementation detail，但 2D / 3D / Assembly / DXF 不得把它當領域 oracle，也不得以 `FW=29`、固定 segment index、world Z、bbox center 或單次 probe 值猜物理關係。
- FW 的正式 placement authority 是 physical face face-flush；relief promotion 必須先有合法 placement certificate，再做 collision/backprojection/refold verification。
- `中隔.dxf` 只供固定孔／既有特徵；外框不是 final relief contour Source of Truth。
- resolved geometry sinks 共用同一 final material。Renderer / exporter 若為了「畫對」而另算 CUTTING 或截角，就是第二 geometry path。
- Save 只存 authoritative state；Reload 重新 canonical solve。derived `final_geometry`、probe geometry 或 render cache 不得持久化成第二份真值。


## 2026-09-09 — Validation Authority Boundary：驗證不是製造計算來源

- **全域硬規則**：驗證只回答「production 結果對不對」；不得回答「production 應該怎麼算」。任何 test expected、fixture output、probe/measurement delta、tolerance、PASS/FAIL evidence 都不得被 production 當成公式、offset、補償或 branch condition。
- Divider / EndCap / BoxBody 類幾何 mismatch 必須回到 authoritative state、physical geometry、`T`、FW face、AssemblyJoint/Registry、collision/backprojection、canonical resolver 查根因；禁止用 `expected - actual` 反推切多少、移多少、補多少。
- tolerance/epsilon/boolean fringe 只屬驗證判定邊界；若它出現在 manufacturing formula，視為 authority leakage。
- 某數值只有在**另有獨立 authoritative provenance（產品／機械 authority）**並正式固化於 spec/registry/canonical state 時才能成為 production input；QA 恰好量到相同數字不構成 authority。
- Review/source scan 發現 production 依賴 `tests/**`、fixture expected、單次 probe magic number，直接 fail closed，不得以「測試都過」接受。

## 2026-09-09 — Issue63：驗證結果不得反向成為 Divider production 幾何公式

- **硬規則：驗證不是計算來源。** Receiving Divider 的 production relief / hole transform 只能由 authoritative state、真實 physical geometry、collision/backprojection、canonical resolve 與 authoritative `T` 推導；pytest expected、驗收量測值、單次 fixture output 都只能驗證結果，不得回灌製造計算。
- 真板厚補償的 authority 是 `T` 本身。當 mid-surface / skin 幾何要轉成 physical solid 時，使用由 authoritative `T` 推得的 `T/2` skin→solid sweep；這是物理板厚模型，不是由封頭尾／中隔最後量到的中間段差值反推補償。
- Issue63 的 `T=2.0 → solid_half_thickness=1.0` 是上述規則的直接結果。驗收中 resolved 封頭／尾中間段約 `742.0`、Divider 中間段約 `741.999` 的 `0.001` 差，只來自 solver/boolean fringe（`0.0005 × 2`）的數值容差；**只能作 test tolerance，不得成為 manufacturing compensation。**
- 孔位 parity 量到的「Ø6.4 到截角邊 10.0 mm」與曾觀察到整組固定孔偏移約 `100 mm` 都是 validation evidence，不是公式。正式孔位修正必須由 `中隔.dxf` authoritative fixed-hole / physical-edge datum 與正式 rigid orientation transform 推導；禁止直接寫 `-100` 或任何由單次差值反推的 magic offset。
- 同理，任何 `47/26`、`1 mm`、某次 middle-segment 長度、world bbox、renderer origin、probe delta 都不得作 runtime oracle。測試應鎖幾何 invariant：FW physical face-flush、pre-solve collision、backprojection ownership、post-refold illegal penetration=0、fixed-hole datum rigid parity、2D/3D/DXF resolved sink 同源。
- **完成條件**：若為了讓 test GREEN 必須把 expected / tolerance / fixture delta 寫進 production，直接判定為架構違規；先修 authority/data-flow 或 stale oracle，不得用驗證資料餵製造公式。



## 2026-09-09 — Divider：3D triangulation 輪廓不得升格為 STANDARD CUTTING

- **症狀**：Receiving Divider 已通過 FW face-flush、collision replay、`illegal penetration=0`，甚至中間有效直線段 parity 也可通過，但 final material 仍出現不屬於標準截角的斜邊。
- **實際根因**：Divider 專用 relief solver 把 backprojection endpoints 直接做 `MultiPoint(...).convex_hull`，再把該 hull 當正式 CUTTING。三角網格交線的數值頂點因此被錯誤升格成製造 topology；#63 的舊 shape test 又用同一 convex-hull 假設建立 expected，形成 circular oracle。
- **有效 RED**：run `34346306940`。左右兩端都在「存在 triangulation-generated non-axis CUTTING edge」精確紅燈；同一測試中的 core boundary、physical skin depth、`T/2` solid depth都由各自 authority 動態推導，不含 dead dimension。
- **被撤銷假設**：第一輪猜測「disconnected collision components 被 global hull 橋接」；run `34345831526` 的 reproducer 找不到該 disconnected gap，所以該假設已撤銷。禁止日後把已撤銷假設當歷史事實。
- **正確 authority 分工**：
  - Fold/material contract → STANDARD manufacturing topology / pre-core boundary；
  - real `left_side/right_side` collision/backprojection → touched span end + required physical skin depth；
  - authoritative `T` → `T/2` skin→solid sweep；
  - refold replay → 只判定剩餘非法穿透是否為 0；
  - validation → 只判定以上結果對不對，不回灌 production。
- **正確實作**：先將 physical crossing linework fit 回既有 stable orthogonal corner topology，再做 `T/2` inward sweep；union 必須保留 STANDARD topology，禁止再用 convex hull 重新產生斜邊／新 stage。
- **防線**：只驗 `illegal penetration=0` 不夠。任何 collision-derived relief 必須另驗 manufacturing topology invariant；STANDARD one-level corner若出現非 X/Y 軸 CUTTING edge，直接 fail closed。
- **GREEN 證據**：run `34346627948`：Issue71 exact seam **2 PASS**；Divider broader guards（#63/#39/DM3/DM4）**23 PASS / 0 FAIL**；`config.ini` SHA256 前後一致。

## 2026-09-09 — BoxBody child identity 不可直接升格成 operator part

- `box_body:<role>` 是 physical geometry identity，不是 UI hierarchy 的 Source of Truth。
- 頂層板件只保留 logical `box_body`；physical children 的操作資訊巢狀放在箱身內。
- 每片 visibility 必須獨立，但 visibility mask 只作用於 drawing sink；完整 child meshes 仍留在 assembly datum / collision source。
- 若取消顯示某 child 後 Head/Tail 位置、collision 或 relief 改變，表示 renderer visibility 又污染了 mechanical authority，直接判定回歸。

## 2026-09-09 — Issue74：core_start 不是 Divider 穿透界線；兩張 source skin 不可再補 T/2

- **症狀**：Divider verifier 曾回 `verified=true`，但 true-thickness world-space 檢查仍發現左側板 `zl1/zl2` 與右側板 `zr2` 穿過 Divider；相鄰 FW/D 只是一張 skin 接觸。
- **根因 1 — legality boundary 錯置**：舊 solver 用 Divider `core_start` 當硬界線，把 `core_start` 後的交線全部當 retained contact。實際上 collision legality 必須看 source physical Fold band 是否跨過**兩張** skin，不能看 target UV 是否超過某條折線。
- **根因 2 — 板厚重複補償**：第一輪 true-thickness 修正把 source 兩張 skins 已經界定好的 physical footprint 又加一次 `T/2`，造成多切。兩張 source skins 已包含 source 板厚，不可再做相同方向的 source skin→solid 補償。
- **根因 3 — 只挖 footprint 會做成內部槽**：把碰撞 footprint 小矩形直接 difference 雖可讓 positive overlap 歸零，但不等於正確 corner relief。Manufacturing topology 必須由 Fold semantics 建出「外緣 primary + 必要 secondary arm」。
- **正式 production authority**：
  - source semantic Fold band + both-skin crossing：只判定 penetrating band；
  - Fold material lengths + Divider `core_start` + authoritative `T`：算 nominal CUTTING；
  - physical footprint：只做 coverage/replay validation；若 nominal 不覆蓋就 fail closed，禁止把 measured miss/delta 加回公式；
  - post-solve：驗 retained material 與 pre-solve true-solid footprint 的 positive-area overlap=0，邊界 intersection line 不算正體積穿透。
- **Receiving nominal 公式**：
  - 左 primary：`U=core_start+zl2`，`V=fw_left+T/2`；
  - 左 secondary：center U 同上、寬 `T`，V=`fw_left .. fw_left+zl1`；
  - 右 primary：`U=core_start+zr2`，`V=fw_right+T/2`。
- **目前 fixture evidence（非 runtime oracle）**：`core_start=41, zl1=22, zl2=20, FW料=25, zr2=16, T=2` → 左 primary `61×26`；左 secondary `X60..62, V25..47`（比 primary 再深 21）；右 primary `57×26`。這些數字只能用來驗當次輸出，production 必須每次從 Fold+T 重算。
- **數值毛邊**：`0.0005` boolean fringe 只為浮點 polygon robustness；不得當 clearance / 多切量 / manufacturing compensation。
- **驗收**：Issue74 exact + Divider guards 必須同時 GREEN，並保留 `config.ini` SHA invariant；舊「左右深度必須相同」與「只截到 core_start」測試 oracle 已廢止。


## 2026-09-09 — Issue74 CORRECTION：source both-skin != source+target 全實體

- **撤銷錯誤結論**：先前「source Fold band 已跨兩張 skins，所以再加 T/2 一定是重複補償」只說對一半。兩張 source skins 的確已含 **source 板厚**，但 backprojection 仍落在 **Divider target skin**；target 中隔自己的板厚尚未成為 solid。
- **真正根因**：Issue74 第一版 verifier 把 source-solid footprint 當成完整 source+target solid collision，漏做 target sheet 的 `T/2` inward sweep，因此 current fixture primary 只切到約26，造成 Divider middle 約744，與 resolved Head/Tail 742 parity FAIL（run `34352892221`）。
- **正確 production chain**：
  1. real left/right side Fold band crosses both source skins → source true-solid penetration；
  2. crossing backproject 到 Divider target-skin UV；
  3. authoritative Divider `T` → target `T/2` inward sweep，形成真正 source-solid × target-solid collision footprint；
  4. 用 stable orthogonal manufacturing topology 從 touched material edge 連到該 physical solid footprint；
  5. refold 後 positive-area illegal overlap=0 才可 promotion。
- **禁止事項**：不得用 `W/FW` 閉合、Head/Tail 742、expected 27、probe miss/delta 反推 production。這些都只能驗證。
- **final physical evidence**：run `34353654567` 自碰撞得到 left zl2 約26 skin +1 target half-thickness ≈27 solid、right zr2 約26+1≈27、left zl1 約47+1≈48；Xvfb 中隔 middle 約741.999 與 Head/Tail 742.0 parity PASS。數值只屬該 fixture evidence，不可硬編。
- **永久防線**：任何「已經有兩張 skins」的說法都必須標明是 source 還是 target；只有 source/target 兩邊的 true-thickness 都被建模後，才可宣稱完整實體 collision。

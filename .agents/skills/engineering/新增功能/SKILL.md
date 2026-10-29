---
name: 新增功能
description: WHD /功能 專用新功能與擴充流程；先查來源與完整影響鏈，依既有測試、GitHub localX 及 /推推 發布規則執行。
whd_doc_role: CURRENT
whd_contract: feature-development-flow
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 新增功能 — /功能

## 不得停止程序 `INTERACTIVE_COMMAND_NO_STOP_HARD_GATE_V1`

使用者同時下達 `/功能 /DEBUG /派工` 時，本 Skill 只負責新功能與驗收需求，診斷交給 diagnosing-bugs，直接施工與 `localX` 交付沿用派工；只走一條 Issue／PR 工作鏈。**不得預先設定停止程序**；查到可行動作就直接動手，回報不構成暫停，沒有新授權需求就不重問。來源不足時先查來源，不能猜測製造規格；單一工具被拒就續做其他合法工作。


本 Skill 只協調「新增功能完整性」，不創建第二套派工、lease、CI、Git 交付或發布流程。權威為 GitHub `localX` 的 `AGENTS.md`、CURRENT domain 規格／原始資料，以及既有 `派工`、`執行開發任務`、`UI設計與去AI味`、`寫成規格書`、`tdd`、`驗證板件與DXF`、`tools/change_test_profile.py`；`/debug` 仍專責既有 BUG，不由本 Skill 取代。

## 命令語意

- **/功能 設計 <需求>**：只讀追查原始碼、提出設計與驗收案例；**不得修改程式**、開 PR 或自行啟動施工。
- **/功能 新增 <需求>**：使用者明確授權新增／擴充；同範圍一次完成查核→施工→CI→遠端 localX 整合與回讀，不逐 PR 重問。
- **/功能 繼續 #Issue**：核對原 Issue、PR、branch、HEAD 與真實結果後續作，不重複開 Issue／PR。
- 僅要求「設計」「看看」「規劃」視為只讀；「照設計處理」代表相同範圍的施工授權。未定的實際產品語意不可擅自決定。
- 本命令不授權 CoreELEC／RC／DC／本機 shell，不等於 `/接手` 或 `/推推`；工具能力／權限仍按 `AGENTS.md`。

## 第一關 — 需求與真實來源

確認入口、操作、預設值、切換、版本／數量／套／連／Bay、套用／取消、保存與完成判準；已回答的使用者決定不重問。辨別 **CONFIRMED PRODUCT RULE、CURRENT IMPLEMENTATION、CURRENT TEST ORACLE、UNRESOLVED**；測試／畫面／既有錯誤不能替代使用者確認的機械規則。

嚴守 `SOURCE_READ_BEFORE_MUTATION_V1`：先 fresh-read GitHub `localX` exact HEAD 的 `AGENTS.md`、CURRENT 規格、CSV／JSON／DXF／基準檔，實際讀取相關完整函式，追 **入口 → 呼叫鏈 → 狀態／座標轉換 → Save → Reload → 2D／3D／碰撞／製造**。只查本功能必要依賴，不全面無限掃倉。任何程式或測試修改前交代 **SOURCE_READ_EVIDENCE**（repo/ref/HEAD、已讀程式與函式、正確資料權威、驗收或 RED-capable 案例、最小修改範圍）。

無法證實來源、座標基準、折向、孔位或製造判準時 `SOURCE_READ_PRECONDITION_FAILED`，繼續只讀查證，**不得猜測**、不得編造預期值後直接施工。

## 第二關 — FEATURE GATE（影響鏈完整性）

依真實影響逐項列適用與驗證判準，不適用可寫 **N/A + 原因**，不是強迫所有功能修改所有模組：

1. 操作入口／GUI：欄位、可見性、捲動、焦點、高亮、主副視窗與切換。
2. 資料模型：來源、尺寸語意、版本、數量與 Bay／套／連權責。
3. 保存／重新開啟：Save → Reload、舊資料相容、預設值回復。
4. 2D：實際座標、文字、孔位、標籤與截角。
5. 3D：**真實幾何**、折邊、名牌孔、正反面、Z 基準及碰撞。
6. 製造：受影響的 CUTTING／BEND／DXF、製造圖、實體板件。
7. 回歸：其他入口、資料、性能及使用者已核准的舊功能。

GUI 上畫出一條孔邊不能冒充 3D 實體真的有孔，預覽不能替代製造輸出；驗收要走真實功能鏈。小規模擴充採**精簡模式**：在現有 Issue／PR 寫需求、影響鏈及測試；跨模組、幾何或新資料契約採**完整模式**：沿用既有規格與工單拆解技能，不建第二套治理。兩種模式品質門檻完全一樣。

## 第三關 — TEST GATE（實作、測試、回修）

小功能先依當次真實影響鏈選出一個可判斷需求的 pytest node；用 `tools/change_test_profile.py --feedback-test <真實 node-id>` 取得 `fast_feedback.command`，在合法雲端執行器做最小 FEATURE_ACCEPTANCE RED→GREEN，必要時加受影響子系統測試。`NEEDS_EXPLICIT_TEST` 代表來源不足、須找真測試，不得猜測。此回饋只加速開發，**不是**免完整 `PRODUCT_FULL_REGRESSION` 或 Windows 人工驗收。無合法執行器就回報尚未執行，不冒稱 GREEN。

一般 `/功能 新增` 採既有 `/派工` 位置規則：GitHub localX 分支、GitHub／SCHEDULER／REMOTE_ACTION 施工；不可偷用本機。必要時新增 **FEATURE_ACCEPTANCE、UNIT_OR_COMPONENT、AFFECTED_SUBSYSTEM、INTEGRATION** 案例，驗證使用者真實操作結果，不以「沒當機」充數。

依 `WHD_CHANGE_TEST_PROFILE_V1`／`tools/change_test_profile.py` 的 `FEATURE` 類型與實際 diff，補適用的 **UI／GEOMETRY** overlay，包括 Tk/Xvfb、Save→Reload、DXF、2D/3D 真正 seam，最後完成必要的 **PRODUCT_FULL_REGRESSION** 和 PR exact SHA CI。CI 失敗沿同一 Issue／PR 修復與新 SHA 重測，不在 queued/in_progress 或 PR 建立時宣告完成。

**沒有真正的 GUI runtime → VISUAL_ACCEPTANCE_PENDING**；不可聲稱做過畫面驗收，也不能把 headless 測試冒充 Windows GUI UAT。

## 第四關 — localX 與正式發布

CI 及 scope、base drift、mergeability 驗證後，依原本 `GITHUB_LOCALX_FIRST`、`expected_head_sha` 將 PR 安全合併 GitHub 遠端 `localX` 並回讀 SHA；未驗 Windows 狀態必須是 **GITHUB_LOCALX_MERGED + WINDOWS_LOCALX_SYNC_PENDING、WINDOWS_UAT_PENDING**。Windows `Z:\localX` 由使用者以既有 Fast-forward 腳本更新、實際操作 GUI／3D／製造路徑。

發現缺漏依原 Issue 補修再重測整合；完整 Issue 收尾沿用原 `派工`，不增第二套工作槽或背景輪詢。**正式 X=cleanup/2d-3d-sync 只在使用者實際驗收及當次 /推推 後發布**；治理／技能也先合 localX，**不得治理直送 X**。

每 2–3 個實質操作回報證據，分別報告功能與測試、PR／run ID／HEAD、Windows 同步與 UAT、正式 X；遇單一步驟被拒時，不繞過安全授權，直接改做其他合法可執行動作；記錄錯誤不構成停止程序。


---
whd_doc_role: CURRENT
whd_contract: receiving-same-tier-mixed-depth-pad-auto-resolution
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 受電箱：同一實體層不同深度 NFB 自動產生墊高片（2026-10-28）

## 問題與重現

已提交的 CSV V5 NFB 在同一物理層含不同深度（例：士林 3P400SN 107 mm、100HN-s 68 mm）時，舊 `.p6fold` 可能把**LEFT 實體尺寸**配上 `receiving_base_plate.pattern=CENTER_DOUBLE_SIDE_FOLD`。原 `receiving_base_plate_values` 優先沿用該錯標型式，`committed_nfb_pad_draft_parts` 與 `build_committed_pad_assembly_display` 因非 LEFT/RIGHT flat 回傳空集合，2D、3D、板件清單漏掉必要 PAD。**真正 CENTER 實體（尺寸吻合目前已認證來源）是獨立的有效板型，不屬此失效情境**。

## 來源與裝配規則

1. 僅使用目前已提交、來源身份一致的 CSV V5 型號及其深度；不自定 NFB 尺寸、厚度、X/Y 或 PAD 型式。
2. 每個實體層獨立求最深 NFB；該層每顆較淺 NFB 需要一片來源推導 PAD，所有同深度 NFB 不需要；不可跨層共用基準或件數。
3. 當至少一層存在實際深度差，舊存檔若標成 CENTER，但它完整保存的板件幾何尺寸與**目前來源認證的 CENTER 真實型式不一致**（例如保存的是 LEFT 的 H340 尺寸），才切回來源驗證通過的 LEFT flat + 真實 PAD。實體底板、四定位方孔、PAD CUTTING/BEND、3D、BOM 和 CHECK/Q 必須同源。**合法 CENTER 是另一張經認證的實體板件**，不得因 NFB 深度差逕自取消其已有製造資格，更不可在 CENTER 上疊畫假 PAD。
4. 若目前來源不能認證 flat 或 PAD，明確阻擋該路徑而不是悄悄退回 CENTER 讓 PAD 消失。缺少世界 X／原 Hole Editor 已提交特徵仍要按原契約阻擋，不能編造製造孔位。
5. 只修同層深度差決策，不更動 PAD 幾何公式、折線、板件厚度、輸出格式、全箱 MFG/NC 或焊接放行。

## 驗收矩陣

- 單層：107/68 mm，預設來源與**錯貼 CENTER 標籤但完整板件尺寸仍屬 LEFT** 的舊檔解析成同一個 LEFT+PAD；較淺者 PAD 39 mm。合法來源 CENTER 與其原 PART_ONLY 輸出維持可用。
- 雙層：有差異的層各自帶 PAD，父板身份 `base_plate:nfb_layer:<tier>` 不混用；另一層同深度不生成。
- 真實已提交 Hole Editor：2D PAD 物理身份／4 螺孔／2 折線、真 Base 四定位方孔、3D 貼合與內門對位、Save/Reload、BOM 分版本驗收。
- 未提交／CSV 來源錯誤／未確認 X：維持 fail-closed、不得出假的 PAD/NC。
- Windows 2D/3D 像素驗收與 exact HEAD CI 須獨立留收據；pytest 結果不可冒充人工畫面驗收。

## 交付邊界

修復分支隔離；通過驗證後才可合入 GitHub `localX` 做人工驗收。沒有使用者 `/推推` 不動正式 X。保存原 Windows `Z:\localX` 未提交設定與日誌。

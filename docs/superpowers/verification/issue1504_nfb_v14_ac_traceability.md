---
whd_doc_role: REFERENCE
whd_contract: issue1504-nfb-v14-ac-traceability
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #1504 NFB v1.4 — 88 項 AC 追溯矩陣（未驗收完畢）

> **請勿把 88 項已找到候選測試誤讀為 88 項通過。** 此表每一項 `accepted=false`；測試檔存在不代表已核對其 assertion。

原規格與 SHA256：
- `WHD_受電箱_NFB_UI與開孔編輯整合規格_20261010_v1.4.md` — `2fcf48521b913435b01639b9fa1b3ef7789ec93724033e332cedd4c85e1d0eef`
- `WHD_受電箱_開關層數_耳朵打標與內門開孔_規格書_20261010_v1.4.md` — `f4441937f43bf70de1224cf74926b8cfe031dc6eef6f18f165bd6bf6a8a2e5e1`

基準：NFB-AC-01～56 和 SWT-AC-01～32 全數 88 項。每個 AC 包含原文、期別、owner 工單、候選 test path、以及尚缺驗收。真相來源仍是兩份已核准 v1.4；本矩陣不是第二規格。

**2026-10-18 最新施工口徑（#1502／#1503，已合入 localX 的 PR #1909）：** 受電箱每個 NFB 層各有一片真實底板；底板與左右底板固定片的 X 永遠以**箱體中心 X=0** 為基準，**不可因 NFB 向左／向右移動而移動**。W800／T2 的折後底板對耳朵固定孔 X=−335／+335（孔距 **670 mm**），側板內皮 X=−398／+398；原始展開數據 732 mm 不得當成折後裝配孔距。每顆 NFB 的原始 DXF 已驗證螺絲孔可各自按 world X 移動，固定孔／固定片仍不動。各層底板 Y 隨各層開孔中心，H1600 且由箱頂 330／830 時世界 Y=470／−30；外門的下層分區不產生本項底板。**固定片折彎、真實焊接 Z 接觸、側板 MARKING、正式 MFG-2 DXF 與 Windows UAT 仍待驗收**，不能憑 #1909 CI 綠燈把相關 AC 改為已通過。原始 v1.4 AC 文字及 SHA 保持不變，本段只記錄現行規則覆蓋舊解讀。

本期未完成：[#1500](https://github.com/looaeedr/whd/issues/1500) 真正 Windows GUI／原DXF提交複製 Undo 存讀操作；[#1502](https://github.com/looaeedr/whd/issues/1502) NFB→耳朵→實體底板及 CHECK/Q 正式裝配製造；[#1503](https://github.com/looaeedr/whd/issues/1503) PAD/EAR 暫緩且不偽造核准。#1504 和主單 #1490 不得提前結案。

狀態：`EVIDENCE_CANDIDATE_ONLY`=檔案存在但 assertion 未逐條驗證；`BLOCKED_1500_REAL_GUI`=缺實機 GUI；`BLOCKED_1502_PHYSICAL_MFG`=缺實際裝配與製造；`DEFERRED_PRODUCT_EVIDENCE`=產品設計／實測證據延期。所有狀態都不是 PASS。

機器資料：`docs/superpowers/verification/issue1504_nfb_v14_ac_traceability.json`。

| AC | Owner | 尚缺驗收 | 階段 | 核准原文 |
|---|---|---|---|---|
| NFB-AC-01 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 受電箱才看見 NFB UI；其他箱型既有 Hole Editor 不變。 |
| NFB-AC-02 | #1491、#1500 | BLOCKED_1500_REAL_GUI | UI-1A／UI-1B（提交下限） | 未提交可零槽；正式提交後層數 1／2、至少一槽，刪除最後槽不得隱式退回未配置；1→2、2→1 遵守 Q12／Q17／Q18。 |
| NFB-AC-03 | #1492 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 真實廠牌 DXF 列表、右側預覽、縮放／平移／重設；選檔不污染正式狀態。 |
| NFB-AC-04 | #1493 | EVIDENCE_CANDIDATE_ONLY | UI-1A（編輯）／MFG-1（幾何違法回滾） | 配置卡重排序與 2D 位移明確分離；mm 欄位精確；Q5／Q6／Q7 清除受影響層全部位移；Q16 保留位移、名義孔距不動，重新驗證非法回滾。 |
| NFB-AC-05 | #1493、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1A（設定）／MFG-1（真實旋轉） | 整層預設與單顆角度覆寫互不混淆；0/90/180/270 正確、禁止鏡像；更換型號保留設定。 |
| NFB-AC-06 | #1493 | EVIDENCE_CANDIDATE_ONLY | UI-1A（取消 Undo）／MFG-1（幾何違法） | 離開／取消／Undo 不漏出暫存變更；範圍／碰撞非法時保留上次合法配置。 |
| NFB-AC-07 | #1500 | BLOCKED_1500_REAL_GUI | UI-1B | Bay 複製需覆寫確認、整組深複製；來源及目標之後獨立。 |
| NFB-AC-08 | #1499 | EVIDENCE_CANDIDATE_ONLY | UI-1B | 數量模式不同 `version_id` 可保存不同 NFB；版本增刪／切換／深複製／重讀均保持身份。 |
| NFB-AC-09 | #1498、#1499 | EVIDENCE_CANDIDATE_ONLY | UI-1B（重載）／MFG-1（板件守衛） | 已經合法提交但後續因板件未完成或來源失效而未驗證的草稿可 Save→Reload；只阻斷真正依賴 NFB 缺項的物理板件，列明 Set／Bay／版本／層／顆與原因；不連坐同 Bay 無關板件。 |
| NFB-AC-10 | #1494、#1495 | EVIDENCE_CANDIDATE_ONLY | UI-1A（名義顯示）／MFG-1（物理投影） | 1100 高 Y=550 或 290/790；表列已證實的 X 孔距正確；其他高度／寬度不能推測。 |
| NFB-AC-11 | #1496、#1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-1（主孔）／MFG-2（其餘來源組） | 真實來源 ARC、CIRCLE、多 layer／entity color、上下資料組皆完整識別；主開孔 pivot 正確。 |
| NFB-AC-12 | #1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-2 | 同顆跨板件孔／打標有穩定關聯，所有合法製造圖元位於正確實體板件，不被當成一張板。 |
| NFB-AC-13 | #1503 | DEFERRED_PRODUCT_EVIDENCE | UI-1A（不可移底板）／PAD（後續實作） | 底板不因 NFB 深度變更而位移；墊高未施工時禁止產出其假 DXF。 |
| NFB-AC-14 | #1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-2（完整跨板件） | 2D／3D／DXF／Save→Reload 使用同一已解析製造資料；相同加工片合併，不同 NFB 加工不得誤合併。 |
| NFB-AC-15 | #1492 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 僅選取與高亮不重建整箱 3D、不反覆重讀全部 DXF；UI 互動不卡頓。 |
| NFB-AC-16 | #1499、#1500 | BLOCKED_1500_REAL_GUI | UI-1A（取消）／UI-1B（重載）／MFG-1（舊孔出圖不變） | 新舊未配置案開啟面板再取消仍未配置；Save→Reload 與升級前逐片實際製造幾何／圖層／件數與輸出範圍一致，無虛構 NFB；來源未配置 Bay 複製禁用；提交後 Save→Reload 不丟失提交事實；金庫型及既有 Hole Editor 回歸。 |
| NFB-AC-17 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A（繼承）／UI-1B（正式保存） | 「本套／本配置→層→單顆」品牌繼承只更新跟隨者，覆寫者保持；跨廠牌型號不偷替換，缺有效來源標待重選。 |
| NFB-AC-18 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 層數只有 NFB 配置一處可編輯；本套開關旁只保留廠牌＋入口；單顆 X／整排 X 基準未知、非 1100 Y 未知，均顯示未定且禁止偽製造定位。 |
| NFB-AC-19 | #1493、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1A（清位移）／MFG-1（違法回滾） | Q5／Q6／Q7 只清受影響層全部手動位移，對應狀態改 NONE 並清舊快照；Q16 保留位移／名義孔距，重驗整層非法原子回滾；操作 Undo／Cancel 可完整還原。 |
| NFB-AC-20 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 改本套／本配置／層預設品牌前正確預告將待重選顆數；取消狀態完全不變，確認才套用；同值明確覆寫仍維持覆寫身份。 |
| NFB-AC-21 | #1491、#1499 | EVIDENCE_CANDIDATE_ONLY | UI-1A（預設）／UI-1B（版本保存） | 數量模式每個版本的本配置預設廠牌與三級繼承獨立；深複製後修改甲不影響乙；套／連本套品牌僅既有控件可寫。 |
| NFB-AC-22 | #1499 | EVIDENCE_CANDIDATE_ONLY | UI-1B | X datum 未定仍可輸入含明確 0 的位移，Save→Reload 保存 UNVERIFIED_BASIS、箱寬／層／顆 ID 順序／名義規則版本；沒有位移用 NONE；不保存衍生製造通過狀態。 |
| NFB-AC-23 | #1499、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1B（重新確認）／MFG-1（製造阻斷） | 新 X 基準確立後，舊位移不能自動生效，須比較條件並經使用者重新確認；受影響顆未確認前維持草稿與製造阻斷。 |
| NFB-AC-24 | #1498 | EVIDENCE_CANDIDATE_ONLY | UI-1B（狀態）／MFG-1（板件守衛） | 逐顆「已驗證／未驗證」及原因正確；已提交配置由當前來源推導 DRAFT／CONFIGURED；DRAFT 只阻斷 NFB 依賴未完成的物理板件，不阻斷無關片／Bay／版本，列受阻身份。 |
| NFB-AC-25 | #1493 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 「型號待重選」仍可依已核准名義表顯示相對中心距；實際 X 定位、碰撞、越界各自未驗證，沒有憑空置中。 |
| NFB-AC-26 | #1493、#1499 | EVIDENCE_CANDIDATE_ONLY | UI-1A（角度）／UI-1B（重載） | 儲存單顆 90° 等旋轉設定並重載；主開孔中心未驗證時不產生假旋轉放置／已驗證顯示。 |
| NFB-AC-27 | #1493、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1A（設定）／MFG-1（幾何回滾） | Q16 型號變更／待重選恢復不改已知名義中心距，保留位移並重驗整層實際幾何；具完整資料且非法時全筆原子回滾。 |
| NFB-AC-28 | #1499、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1B（重新確認）／MFG-1（逐顆驗證） | 未驗證位移至少可按 Bay／配置批次重新確認，先提示條件差異與受影響清單；逐顆非法者不能批次放行。 |
| NFB-AC-29 | #1499、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1B（重載）／MFG-1（重新解析） | Save→Reload／來源 DXF 變動後重新推導主孔中心、位置、越界及草稿結論，不信任專案舊衍生驗證旗標。 |
| NFB-AC-30 | #1494 | EVIDENCE_CANDIDATE_ONLY | UI-1A（中心距）／MFG-1（防假孔） | 已知名義中心距不依賴已選型號外形；缺型號不抹掉中心距，但未驗證的實際製造孔不得輸出。 |
| NFB-AC-31 | #1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-2 | 量產版本不同 NFB 導出不同實際加工幾何時，不得錯誤合併 DXF；同加工者仍依既有 CHECK `Q{加工片數}` 正確分組。 |
| NFB-AC-32 | #1493 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 清除位移後可觀測是哪層、幾顆受影響；Undo 恢復位移／基準條件快照，沒有殘留過期暫存。 |
| NFB-AC-33 | #1499 | EVIDENCE_CANDIDATE_ONLY | UI-1A（未提交）／UI-1B（儲存）／MFG-1（舊式 DXF） | 新專案／新增 Bay／版本初始 UNCONFIGURED；未提交不需槽位，舊式 DXF 產出不變。 |
| NFB-AC-34 | #1500 | BLOCKED_1500_REAL_GUI | UI-1A（停用）／UI-1B（首次提交／重載） | UI-1A 守衛未驗收時「確認套用」及可造成提交的 Bay 複製停用；UI-1B 首次提交（含複製到 UNCONFIGURED 目標）須逐件提醒及確認，取消全不變；提交後未完成製造驗證者 DRAFT 並可 Save→Reload。 |
| NFB-AC-35 | #1500 | BLOCKED_1500_REAL_GUI | UI-1B | 「還原為未配置」獨立確認、Undo；`submitted=false` 且丟棄當前 NFBConfig 層／顆／位移等，不保存休眠配置；不刪原本套品牌或 legacy Features，回復舊式出圖；禁靠刪最後槽返回。 |
| NFB-AC-36 | #1500 | BLOCKED_1500_REAL_GUI | UI-1A（禁止提交複製）／UI-1B（正式深複製） | 來源 UNCONFIGURED 禁止 NFB 複製；已配置來源複製到未配置目標是首次提交，需守衛與提醒；數量版本深複製提交事實，未配置來源不產生 NFBConfig 休眠資料，各版本獨立。 |
| NFB-AC-37 | #1497 | EVIDENCE_CANDIDATE_ONLY | MFG-1 | 同位置既有 Hole Editor Feature 與 NFB 來源先識別後關聯／排他，來源不明 fail-closed；沒有重複孔，還原後舊特徵完整恢復。 |
| NFB-AC-38 | #1498、#1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-1（守衛）／UI-1B（提交）／MFG-2（加工分流） | 已提交配置對應內門必相依；可信 DXF 依 Color 30／150 判定底板／中板；型號未選或無法解析時阻斷實際存在的底板／中板，可信證明無相依則恢復匯出；EAR 延期不單獨阻斷側板，不連坐其他件／Bay。 |
| NFB-AC-39 | #1501、#1502 | BLOCKED_1502_PHYSICAL_MFG | UI-1B（部分清單）／MFG-2（最終加工判等） | 明示部分匯出產生實際可出／受阻清單與原因、版本、件數差異；不留混淆的完整批次舊 DXF，CHECK `Q{加工片數}` 只算實際合法匯出且幾何相同片。 |
| NFB-AC-40 | #1499、#1500 | BLOCKED_1500_REAL_GUI | UI-1B | 基準首次核准及版本變更正確觸發 RECONFIRM_REQUIRED；只有有來源宣告相容者例外；重新手動輸入/批次確認綁定版本；位移 0 不等於 NONE；Save→Reload 不錯認。 |
| NFB-AC-41 | #1503 | DEFERRED_PRODUCT_EVIDENCE | UI-1B（納管驗證）／PAD（延期聲明） | `CONFIGURED` 只能在本期所有納管板件合法後成立；PAD／EAR 延期要列在整套交付報告中，不能誤宣告全部裝配完成。 |
| NFB-AC-42 | #1491、#1500 | BLOCKED_1500_REAL_GUI | UI-1A（停用）／UI-1B（啟用） | UI-1A 可做完整配置預覽、取消與 Undo，但 guard flag 未 READY 時正式套用／覆寫按鈕停用、不得提交或污染既有 DXF；守衛通過驗收後才開放 UI-1B。 |
| NFB-AC-43 | #1500 | BLOCKED_1500_REAL_GUI | UI-1B | 已配置來源複製到未配置目標，顯示同首次提交的實際受阻候選板件與確認；取消時目標依舊 UNCONFIGURED、來源不變，無守衛時拒絕複製套用。 |
| NFB-AC-44 | #1498、#1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-1（守衛）／UI-1B（提交）／MFG-2（底／中板） | 已提交但空槽／待重選／來源解析失敗時，對應內門與實際存在的底板／中板均不可出完整製造 DXF；來源可信且確認未使用 Color 30／150 時，底板／中板不因 NFB 被阻斷；左右側板不因尚未批准的 EAR 需求被阻斷。 |
| NFB-AC-45 | #1500 | BLOCKED_1500_REAL_GUI | UI-1B | 還原為未配置後不殘留可複製或重啟的 NFBConfig 休眠內容；同一 transaction Undo 可完整恢復先前提交設定及守衛結果，legacy 製造與本套品牌 owner 不變。 |
| NFB-AC-46 | #1499、#1500 | BLOCKED_1500_REAL_GUI | UI-1B（已提交檔守衛）／MFG-1（內門阻斷） | 守衛功能旗標關閉但載入已提交 NFBConfig 的檔案，不得當作 UNCONFIGURED 照舊匯出缺 NFB 孔的完整 DXF；阻止受影響完整匯出並明確警示。 |
| NFB-AC-47 | #1493 | EVIDENCE_CANDIDATE_ONLY | UI-1A | UI-1A 關閉有未提交變更的 NFB 面板須確認；取消關閉時保留編輯會話，確認捨棄不寫權威配置且舊式 DXF 不變。 |
| NFB-AC-48 | #1494、#1495、#1496 | EVIDENCE_CANDIDATE_ONLY | MFG-1（進場） | MFG-1 缺 X 單顆／整排、Y 局部投影或主孔中心任一證據時，不得讓未知配置成為「可製造」；四組已知名義中心距不自動等於已驗收可製造。 |
| NFB-AC-49 | #1494 | EVIDENCE_CANDIDATE_ONLY | MFG-1（X 進場） | W800×3 的 723/361.5 個案須核對來源 DXF 左輪廓、真正下料 CUTTING 左緣及下料→門面→箱體 X 映射；未證實前不得以此個案推導其它組合。 |
| NFB-AC-50 | #1495 | EVIDENCE_CANDIDATE_ONLY | UI-1A（未定顯示）／MFG-1（Y 進場） | 1100 名義 550／290／790 從箱體外頂投影到內門成品與展開 Y 具可重現雙向測試；非 1100 標「Y 基準未定」，不猜。 |
| NFB-AC-51 | #1496、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1A（提示）／MFG-1（解析與能力） | DXF 主 CUTTING 中心、ARC/CIRCLE、來源顏色及旋轉 pivot 經真圖認證；選型列表逐組正確顯示「可製造（內門）」／「僅預覽」，不可因型號孤立合格便全範圍放行。 |
| NFB-AC-52 | #1497 | EVIDENCE_CANDIDATE_ONLY | MFG-1（製造）／UI-1B（閘門） | MFG-1 輸出合法內門真實 CUTTING、消除與 legacy 相同物理孔的重複加工來源；缺必要幾何 fail-closed，MFG-1 未通過時 UI-1B 不准提交。 |
| NFB-AC-53 | #1498、#1500 | BLOCKED_1500_REAL_GUI | MFG-1（能力）／UI-1B（提交） | 機器可驗證的版本化 MFG-1 能力註冊驅動提交可用性，不靠 GUI 手動旗標；能力不可用禁止新提交／提交型複製，但既有已提交專案不降級成未配置。 |
| NFB-AC-54 | #1499 | EVIDENCE_CANDIDATE_ONLY | UI-1B（Save／Reload／降級回歸） | 有已提交 scope 時升根 `.p6fold` 與 quantity payload schema；舊版依凍結支援 schema 清單拒載新版本，不吞未知欄位後產出完整 DXF；全部未提交工程仍保留本功能無關的舊 schema 相容。 |
| NFB-AC-55 | #1496、#1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-1（盤點／守衛）／UI-1B（告知）／MFG-2（正式加工） | 逐型號盤點真實 NFB DXF 的 Color 30／150／212 與來源可解析狀態，交付有／無／未知數量（未取得原 DXF 前不得填 0）；MFG-2 未完成時 Color 30／150 受影響底／中板保持阻斷並列於提交提醒與部分匯出清單。 |
| NFB-AC-56 | #1500 | BLOCKED_1500_REAL_GUI | UI-1B | UI-1B 不提供「忽略草稿強制舊式內門出圖」覆寫；可以撤銷提交、還原未配置並 Undo。 |
| SWT-AC-01 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 單一可寫 NFB 安裝層數入口，與既有本套品牌 UI 一致；金庫型不出現 NFB 專屬規則。 |
| SWT-AC-02 | #1495 | EVIDENCE_CANDIDATE_ONLY | UI-1A（名義）／MFG-1（投影） | 上層 1100：一層每顆共用名義 Y=550、兩層上 Y=290／下 Y=790；非 1100 顯示未定，不偷用公式。 |
| SWT-AC-03 | #1493 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 每層多顆有獨立身份與型號、順序、X 位移及旋轉設定；既有中心距只於有效規格組合使用。 |
| SWT-AC-04 | #1491、#1499 | EVIDENCE_CANDIDATE_ONLY | UI-1A（繼承）／UI-1B（保存） | 品牌繼承 A：只更新跟隨者，保留覆寫；當生效廠牌與舊檔不合，顯示待重選，不能默默替換。 |
| SWT-AC-05 | #1492、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1A（來源預覽）／MFG-1（主孔） | 每顆來源 DXF 原圖預覽、確認／取消、主開孔中心未驗證標示清楚；不冒充可製造定位。 |
| SWT-AC-06 | #1493、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1A（設定）／MFG-1（非法回滾） | UI 的 Q5／Q6／Q7／Q16 行為只驗收 NFB-AC-04／19／27；本件查核名義中心距不受型號改變、非法實際幾何不得放行，Undo／取消保留既有加工。 |
| SWT-AC-07 | #1499、#1500 | BLOCKED_1500_REAL_GUI | UI-1B | UI-1B 提交守衛啟用後，Bay 深複製及數量版本深複製獨立，`.p6fold` Save→Reload 保留已提交配置及使用者設定；UI-1A 僅編輯預覽不可聲稱已保存配置。 |
| SWT-AC-08 | #1498、#1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-1（內門）／MFG-2（其他板件） | 沒有可信來源、主孔中心或合法世界定位時，按實體物理件相依阻斷完整 NFB DXF，逐件列出來源／缺項；不阻斷可證明無依賴片。 |
| SWT-AC-09 | #1503 | DEFERRED_PRODUCT_EVIDENCE | UI-1A（禁偽墊高）／PAD（延期） | 來源上方開孔、下方墊高不混淆；**本期不輸出墊高或自動改底板位置**。 |
| SWT-AC-10 | #1497、#1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-1（內門）／MFG-2（EAR 依正式核准） | 真實內門開孔與 NFB 個別中心一致，不以銘牌孔／假矩形替代；左／右耳朵真焊接接觸與打標同源。 |
| SWT-AC-11 | #1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-2 | 2D／3D／DXF／Save 從同一解算來源一致；受電箱 NFB 衍生切孔不同的料件不能錯誤合併。 |
| SWT-AC-12 | #1504 | EVIDENCE_CANDIDATE_ONLY | UI-1A／MFG-1／UI-1B／MFG-2／PAD（各階段回歸） | 不破壞內門框末段 22 mm、46＋2T、門縫、底板原幾何、背孔／中隔與金庫型回歸。 |
| SWT-AC-13 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 變更上游品牌前顯示待重選顆數，確認後更新跟隨者，取消時品牌／型號／位移／旋轉／覆寫狀態完全不動。 |
| SWT-AC-14 | #1491、#1499 | EVIDENCE_CANDIDATE_ONLY | UI-1A（獨立）／UI-1B（保存） | 套／連本套預設只能由既有本套品牌控件寫入；數量模式各版本 NFBConfig 自有預設品牌，新增版本深複製且修改互不污染。 |
| SWT-AC-15 | #1499 | EVIDENCE_CANDIDATE_ONLY | UI-1B | 按 NFB UI v1.4 §2.3.1 的單一 `manual_x_state`、快照、基準版本保存未知基準位移；Save→Reload 不自動升格製造偏移（UI-1B 才可持久化）。 |
| SWT-AC-16 | #1499、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1B（批次確認）／MFG-1（真實驗證） | 新 X 基準定案，既有未知基準位移必須逐顆或按 Bay／配置批次重新確認；確認後仍逐顆驗證，不能批次跳過干涉檢查。 |
| SWT-AC-17 | #1492、#1499 | EVIDENCE_CANDIDATE_ONLY | UI-1A（預覽）／UI-1B（重載） | 型號待重選時已知名義中心距仍可顯示，實際幾何／碰撞保持未驗證；旋轉角度可存但主孔中心缺乏時不產生假放置。 |
| SWT-AC-18 | #1498、#1500 | BLOCKED_1500_REAL_GUI | MFG-1（守衛）／UI-1B（狀態） | 未提交配置維持既有加工；已提交草稿逐顆顯示原因，依真實受影響板件阻斷，不波及可證明無依賴實體件；詳 NFB-AC-24／38／39。 |
| SWT-AC-19 | #1499、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1B（重載）／MFG-1（幾何推導） | 重載／來源更新重新推導實際位置、主孔中心、碰撞與草稿，不把過期驗證狀態當存檔真值。 |
| SWT-AC-20 | #1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-2 | 數量模式 NFB 衍生孔型不同時不誤合併加工料件；相同實際加工幾何依既有 CHECK `Q{加工片數}` 規則合併。 |
| SWT-AC-21 | #1498、#1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-1（依賴守衛）／MFG-2（實際板件） | 已提交配置內門必相依；空槽／待重選或來源解析失敗保守阻斷實際底板／中板，可信來源依 Color 30／150 的正式類別分流且已證明無相依者可正常匯出。 |
| SWT-AC-22 | #1503 | DEFERRED_PRODUCT_EVIDENCE | MFG-1（側板非 EAR 阻斷）／PAD（延期） | 耳朵與 PAD 延期未核准不得憑空生成側板焊接標記，亦不能僅憑 EAR 未完成阻斷原有側板；具其他已批准加工依賴者正常驗證。 |
| SWT-AC-23 | #1497 | EVIDENCE_CANDIDATE_ONLY | MFG-1 | 一個舊式 Feature 與 NFB 孔應相同物理位置時完成來源關聯／排他且不重複；未驗證阻斷該片正式加工；還原未配置不失原特徵。 |
| SWT-AC-24 | #1500、#1501、#1502 | BLOCKED_1502_PHYSICAL_MFG | UI-1A（不提交）／MFG-1（守衛）／UI-1B（保存）／MFG-2（分組） | UI-1A 未提交保留 legacy 出圖；UI-1B 完成守衛才可提交。還原未配置丟棄 NFBConfig 且可 Undo；複製至未配置目標視為首次提交，受阻件有 manifest、其餘合法件可部分出圖，CHECK 件數正確。 |
| SWT-AC-25 | #1498 | EVIDENCE_CANDIDATE_ONLY | MFG-1（依賴）／UI-1B（提交） | 未選型與缺來源不導致既有 UNCONFIGURED 箱體任何新增阻斷；已提交之內門及真實存在的底板／中板依保守基線阻斷，側板不憑 EAR 延期受阻。 |
| SWT-AC-26 | #1500 | BLOCKED_1500_REAL_GUI | UI-1A（提交鎖定）／UI-1B（READY 後啟用） | 真實板件依賴守衛未驗收前，UI 確認與會提交到未配置 Bay 的複製操作均不可用；不影響舊式內門／底板／中板出圖。 |
| SWT-AC-27 | #1494 | EVIDENCE_CANDIDATE_ONLY | MFG-1（X 進場） | 單顆 X／整排 X 的內門／箱體 datum 與來源 DXF 有正式核准測例，沒有的組合不得冒稱可製造，W800×3 不能替其他箱寬解除 `OPEN-X-ROW`。 |
| SWT-AC-28 | #1495 | EVIDENCE_CANDIDATE_ONLY | UI-1A（提示）／MFG-1（Y 進場） | 1100 上層的外頂 Y=550／290／790 正確投影到形成內門及展開局部 Y，非 1100 不猜座標。 |
| SWT-AC-29 | #1497 | EVIDENCE_CANDIDATE_ONLY | MFG-1（NFB-DXF 進場／內門切孔） | 每顆 NFB 的主 CUTTING 開孔中心、輪廓與旋轉有真實 DXF／Feature 測例；與既有中間孔加工來源排他、不重複、不刪 legacy Feature。 |
| SWT-AC-30 | #1498 | EVIDENCE_CANDIDATE_ONLY | UI-1A（標示）／MFG-1（能力註冊） | 已知四組相鄰名義孔距不是可製造清單；只對逐組核准的 W×N×Y×型號×內門 datum 顯示可製造（內門），範圍外僅預覽。 |
| SWT-AC-31 | #1499 | EVIDENCE_CANDIDATE_ONLY | UI-1B（Save／Reload／降級回歸） | 未提交保持既有 schema 與 DXF；已有提交 scope 須根專案與 Quantity schema 升版，凍結舊版 schema 清單的舊 reader 拒載；不能對不認識新 schema 的舊版 silent export。 |
| SWT-AC-32 | #1496、#1502 | BLOCKED_1502_PHYSICAL_MFG | MFG-1（盤點／依賴）／UI-1B（告知）／MFG-2（出圖） | 真 DXF Color 30／150 盤點件數與解析狀態逐檔可追溯；未取得源檔前不得假報 0。MFG-2 未完成的相依底／中板阻斷、其他無相依板件照常出圖，manifest／CHECK 計數不受污染。 |

## 88 項確切測試函式（部分自動化證據，不代表整條 AC 驗收）

**88/88 條已找到確切的 Python 測試函式；0/88 條通過完整 AC 驗收。** 這只確認函式名稱、候選檔案與原 owner 一致，並經 AST 檢查它真的存在。尚未逐條證明所有操作、UI、加工、裝配與現場斷言均完整覆蓋。

如單條需求含多種操作，以下只代表其中一部分證據。例如 #1500 的真實 UI 操作與 #1502 的實體製造仍必須單獨驗收，不得因測試函式存在而放行。

| AC | 測試函式識別（僅部分證據） | 未完成狀態 |
|---|---|---|
| NFB-AC-01 | `tests/test_issue1491_nfb_ui1a.py::test_no_unapproved_geometry_or_persistence_fields` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-02 | `tests/test_issue1491_nfb_ui1a.py::test_empty_slot_keeps_physical_order_and_requires_no_fake_hole` | BLOCKED_1500_REAL_GUI |
| NFB-AC-03 | `tests/test_issue1492_nfb_real_dxf_preview.py::test_pan_zoom_reset_never_reopens_source_or_changes_manufacturing` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-04 | `tests/test_issue1493_nfb_draft_transactions.py::test_insert_delete_reorder_reset_only_touched_layer_x` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-05 | `tests/test_issue1493_nfb_draft_transactions.py::test_angle_inherit_explicit_same_override_no_mirror` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-06 | `tests/test_issue1493_nfb_draft_transactions.py::test_cancel_escape_undo_restore_stable_unit_ids_brand_x_and_conditions` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-07 | `tests/test_issue1500_nfb_transactions.py::test_copy_submitted_source_into_independently_verified_target_unit_id` | BLOCKED_1500_REAL_GUI |
| NFB-AC-08 | `tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-09 | `tests/test_issue1498_nfb_part_readiness.py::test_each_set_bay_version_independent_and_no_cross_scope_ready_cache` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-10 | `tests/test_issue1494_nfb_x_shadow_projection.py::test_w800_three_canonical_x_comes_from_actual_whd_cutting_and_assembly` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-11 | `tests/test_issue1496_nfb_dxf_source.py::test_color_sources_preserve_entity_layer_and_block_inheritance` | BLOCKED_1502_PHYSICAL_MFG |
| NFB-AC-12 | `tests/test_issue1502_nfb_base_source_projection.py::test_one_door_nfb_owner_projects_corresponding_base_cutting_and_marks` | BLOCKED_1502_PHYSICAL_MFG |
| NFB-AC-13 | `tests/test_issue1503_deferred_pad_ear_manufacturing.py::test_unapproved_brand_pad_depth_does_not_move_or_cut_base` | DEFERRED_PRODUCT_EVIDENCE |
| NFB-AC-14 | `tests/test_issue1502_nfb_ear_base_assembly_contract.py::test_ear_mounting_does_not_invent_base_or_change_verified_inner_NFB` | BLOCKED_1502_PHYSICAL_MFG |
| NFB-AC-15 | `tests/test_issue1492_nfb_real_dxf_preview.py::test_cache_changes_with_real_source_identity_and_bounded_memory` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-16 | `tests/test_issue1499_nfb_persistence.py::test_unconfigured_bay_and_quantity_keep_legacy_schema` | BLOCKED_1500_REAL_GUI |
| NFB-AC-17 | `tests/test_issue1491_nfb_ui1a.py::test_brand_change_does_not_silently_swap_csv_filename_even_if_other_brand_same_name` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-18 | `tests/test_issue1491_nfb_ui1a.py::test_nominal_pitch_exact_but_never_absolute_x` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-19 | `tests/test_issue1493_nfb_draft_transactions.py::test_q16_replace_model_preserves_x_and_identity_but_unverifies_geometry` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-20 | `tests/test_issue1491_nfb_ui1a.py::test_single_set_brand_owner_and_explicit_same_value_overrides` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-21 | `tests/test_issue1491_nfb_ui1a.py::test_single_set_brand_owner_and_explicit_same_value_overrides` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-22 | `tests/test_issue1499_nfb_persistence.py::test_confirmed_x_zero_is_not_missing_and_none_is_not_zero` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-23 | `tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-24 | `tests/test_issue1498_nfb_part_readiness.py::test_each_set_bay_version_independent_and_no_cross_scope_ready_cache` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-25 | `tests/test_issue1493_nfb_draft_transactions.py::test_q16_replace_model_preserves_x_and_identity_but_unverifies_geometry` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-26 | `tests/test_issue1493_nfb_draft_transactions.py::test_angle_inherit_explicit_same_override_no_mirror` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-27 | `tests/test_issue1497_nfb_cutting_preflight.py::test_q16_invalid_model_change_blocks_whole_batch_without_moving_other_hole` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-28 | `tests/test_issue1497_nfb_cutting_preflight.py::test_two_independent_upper_units_require_unique_physical_claims_and_no_overlap` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-29 | `tests/test_issue1499_nfb_persistence.py::test_derived_flags_not_saved_and_invalid_nfb_fails_without_fallback` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-30 | `tests/test_issue1494_nfb_x_shadow_projection.py::test_no_unapproved_size_or_single_unit_center_defaults` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-31 | `tests/test_issue1502_nfb_base_batch_export_gate.py::test_one_unreleased_base_rejects_entire_multi_bay_export_before_io` | BLOCKED_1502_PHYSICAL_MFG |
| NFB-AC-32 | `tests/test_issue1493_nfb_draft_transactions.py::test_cancel_escape_undo_restore_stable_unit_ids_brand_x_and_conditions` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-33 | `tests/test_issue1499_nfb_persistence.py::test_unconfigured_bay_and_quantity_keep_legacy_schema` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-34 | `tests/test_issue1500_nfb_transactions.py::test_first_submission_includes_held_plates_in_warning_but_commits_inner_config` | BLOCKED_1500_REAL_GUI |
| NFB-AC-35 | `tests/test_issue1500_nfb_transactions.py::test_restore_clears_only_nfb_and_undo_restores_without_deleting_legacy` | BLOCKED_1500_REAL_GUI |
| NFB-AC-36 | `tests/test_issue1500_nfb_transactions.py::test_unconfigured_source_copy_forbidden_and_overwrite_needs_confirmation` | BLOCKED_1500_REAL_GUI |
| NFB-AC-37 | `tests/test_issue1497_w800_three_canonical_cutting.py::test_legacy_same_location_or_same_physical_owner_blocks_atomic_export` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-38 | `tests/test_issue1498_nfb_part_readiness.py::test_real_base_color30_and_marking212_have_specific_base_dependency` | BLOCKED_1502_PHYSICAL_MFG |
| NFB-AC-39 | `tests/test_issue1501_nfb_export_manifest.py::test_shihlin_color150_partial_only_counts_real_pieces` | BLOCKED_1502_PHYSICAL_MFG |
| NFB-AC-40 | `tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate` | BLOCKED_1500_REAL_GUI |
| NFB-AC-41 | `tests/test_issue1503_deferred_pad_ear_manufacturing.py::test_forged_approved_flag_cannot_override_deferred_role_in_atomic_batch` | DEFERRED_PRODUCT_EVIDENCE |
| NFB-AC-42 | `tests/test_issue1500_nfb_ui1b_bridge.py::test_live_submit_rechecks_bay_source_and_snapshot_before_adapter_write` | BLOCKED_1500_REAL_GUI |
| NFB-AC-43 | `tests/test_issue1500_nfb_transactions.py::test_unconfigured_source_copy_forbidden_and_overwrite_needs_confirmation` | BLOCKED_1500_REAL_GUI |
| NFB-AC-44 | `tests/test_issue1498_nfb_part_readiness.py::test_missing_real_plate_id_is_scope_blocker_not_an_invented_part` | BLOCKED_1502_PHYSICAL_MFG |
| NFB-AC-45 | `tests/test_issue1500_nfb_transactions.py::test_restore_clears_only_nfb_and_undo_restores_without_deleting_legacy` | BLOCKED_1500_REAL_GUI |
| NFB-AC-46 | `tests/test_issue1499_nfb_persistence.py::test_old_schema_reader_must_not_silently_strip_new_nfb_scope` | BLOCKED_1500_REAL_GUI |
| NFB-AC-47 | `tests/test_issue1493_nfb_draft_transactions.py::test_cancel_escape_undo_restore_stable_unit_ids_brand_x_and_conditions` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-48 | `tests/test_issue1494_nfb_x_shadow_projection.py::test_no_unapproved_size_or_single_unit_center_defaults` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-49 | `tests/test_issue1494_nfb_x_shadow_projection.py::test_w800_three_canonical_x_comes_from_actual_whd_cutting_and_assembly` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-50 | `tests/test_issue1495_receiving_nfb_y_projection.py::test_approved_nominal_box_top_y_maps_to_real_1075_blank` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-51 | `tests/test_issue1496_nfb_dxf_source.py::test_unsupported_not_silently_treated_as_certified` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-52 | `tests/test_issue1497_w800_three_canonical_cutting.py::test_w800x3_uses_whd_723_blank_x_for_three_real_holes` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-53 | `tests/test_issue1498_nfb_part_readiness.py::test_ready_requires_actual_per_hole_x_y_and_rotation_proof` | BLOCKED_1500_REAL_GUI |
| NFB-AC-54 | `tests/test_issue1499_nfb_persistence.py::test_old_schema_reader_must_not_silently_strip_new_nfb_scope` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-55 | `tests/test_issue1496_nfb_source_inventory_report.py::test_complete_per_brand_audit_has_exact_links_and_null_unknown` | BLOCKED_1502_PHYSICAL_MFG |
| NFB-AC-56 | `tests/test_issue1500_nfb_transactions.py::test_restore_clears_only_nfb_and_undo_restores_without_deleting_legacy` | BLOCKED_1500_REAL_GUI |
| SWT-AC-01 | `tests/test_issue1491_nfb_ui1a.py::test_no_unapproved_geometry_or_persistence_fields` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-02 | `tests/test_issue1495_receiving_nfb_y_projection.py::test_approved_nominal_box_top_y_maps_to_real_1075_blank` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-03 | `tests/test_issue1493_nfb_draft_transactions.py::test_insert_delete_reorder_reset_only_touched_layer_x` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-04 | `tests/test_issue1491_nfb_ui1a.py::test_brand_change_does_not_silently_swap_csv_filename_even_if_other_brand_same_name` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-05 | `tests/test_issue1492_nfb_real_dxf_preview.py::test_native_arc_circle_bulge_and_aci_preserved_in_real_source_strokes` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-06 | `tests/test_issue1493_nfb_draft_transactions.py::test_q16_replace_model_preserves_x_and_identity_but_unverifies_geometry` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-07 | `tests/test_issue1499_nfb_persistence.py::test_submitted_bay_save_reload_v3_retains_exact_zero_and_independent_copy` | BLOCKED_1500_REAL_GUI |
| SWT-AC-08 | `tests/test_issue1498_nfb_part_readiness.py::test_unknown_missing_and_ambiguous_sources_are_unknown_not_zero` | BLOCKED_1502_PHYSICAL_MFG |
| SWT-AC-09 | `tests/test_issue1503_deferred_pad_ear_manufacturing.py::test_unapproved_nfb_pad_and_ear_must_not_generate_even_part_only_dxf` | DEFERRED_PRODUCT_EVIDENCE |
| SWT-AC-10 | `tests/test_issue1497_w800_three_canonical_cutting.py::test_w800x3_uses_whd_723_blank_x_for_three_real_holes` | BLOCKED_1502_PHYSICAL_MFG |
| SWT-AC-11 | `tests/test_issue1502_nfb_base_source_projection.py::test_one_door_nfb_owner_projects_corresponding_base_cutting_and_marks` | BLOCKED_1502_PHYSICAL_MFG |
| SWT-AC-12 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-13 | `tests/test_issue1491_nfb_ui1a.py::test_brand_change_does_not_silently_swap_csv_filename_even_if_other_brand_same_name` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-14 | `tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-15 | `tests/test_issue1499_nfb_persistence.py::test_confirmed_x_zero_is_not_missing_and_none_is_not_zero` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-16 | `tests/test_issue1499_nfb_persistence.py::test_confirmed_x_zero_is_not_missing_and_none_is_not_zero` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-17 | `tests/test_issue1492_nfb_real_dxf_preview.py::test_missing_and_unindexed_dxf_cannot_show_fake_contour` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-18 | `tests/test_issue1498_nfb_part_readiness.py::test_each_set_bay_version_independent_and_no_cross_scope_ready_cache` | BLOCKED_1500_REAL_GUI |
| SWT-AC-19 | `tests/test_issue1499_nfb_persistence.py::test_derived_flags_not_saved_and_invalid_nfb_fails_without_fallback` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-20 | `tests/test_issue1502_existing_base_nfb_assembly.py::test_two_real_NFB_heights_cannot_share_one_assumed_ear_group` | BLOCKED_1502_PHYSICAL_MFG |
| SWT-AC-21 | `tests/test_issue1498_nfb_part_readiness.py::test_unknown_missing_and_ambiguous_sources_are_unknown_not_zero` | BLOCKED_1502_PHYSICAL_MFG |
| SWT-AC-22 | `tests/test_issue1503_deferred_pad_ear_manufacturing.py::test_existing_base_ear_slots_are_not_confused_with_unapproved_ear_parts` | DEFERRED_PRODUCT_EVIDENCE |
| SWT-AC-23 | `tests/test_issue1497_w800_three_canonical_cutting.py::test_existing_legacy_circle_is_preserved_exactly_once_in_real_nfb_dxf` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-24 | `tests/test_issue1500_nfb_transactions.py::test_restore_clears_only_nfb_and_undo_restores_without_deleting_legacy` | BLOCKED_1502_PHYSICAL_MFG |
| SWT-AC-25 | `tests/test_issue1498_nfb_part_readiness.py::test_unconfigured_preserves_legacy_even_when_nfb_source_absent` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-26 | `tests/test_issue1500_nfb_transactions.py::test_first_submission_includes_held_plates_in_warning_but_commits_inner_config` | BLOCKED_1500_REAL_GUI |
| SWT-AC-27 | `tests/test_issue1494_nfb_x_shadow_projection.py::test_w800_three_canonical_x_comes_from_actual_whd_cutting_and_assembly` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-28 | `tests/test_issue1495_receiving_nfb_y_projection.py::test_non_1100_upper_y_is_unapproved_not_silently_scaled` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-29 | `tests/test_issue1497_configured_nfb_manufacturing_release.py::test_legacy_same_physical_hole_fails_no_duplicate_cutting` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-30 | `tests/test_issue1498_nfb_part_readiness.py::test_wrong_approved_inner_source_or_wrong_part_is_not_a_manufacturing_capability` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-31 | `tests/test_issue1499_nfb_persistence.py::test_old_schema_reader_must_not_silently_strip_new_nfb_scope` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-32 | `tests/test_issue1496_index_color_evidence.py::test_unique_model_links_keep_missing_unknown_distinct_from_real_zero` | BLOCKED_1502_PHYSICAL_MFG |


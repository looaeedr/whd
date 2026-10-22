---
whd_doc_role: REFERENCE
whd_contract: issue1504-nfb-v14-ac-traceability
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #1504 NFB v1.4 — 88 項 AC CURRENT 追溯（2026-10-23，逐條實證簽核）

## CURRENT｜2026-10-23 #1504 AC-05 現行 CSV V5 真 CUTTING／DXF 旋轉驗收（exact CI 後生效）

- 本批候選由 **22／88 → 23／88**，尚餘 **65**；NFB-AC-05 原要求與來源 SHA 保留，現行 `nfbv5:士林:2P400` 經提交 `NFBConfig` → 原內門 FinalScene → 原操作入口 `export_current_csv_nfb_door_base_pair` → 實際存檔 DXF 回讀。四種角度 0／90／180／270 分別以 CSV 真矩形頂點、實體門折邊 UV datum、固定 pivot 獨立比對 CUTTING；負例非法角度禁止寫任何 DXF。
- 搭配原 #2050 的層預設／單顆覆寫／換型保留角度／禁止鏡射及 #2057 的已提交 V5 rotation Save→Reload，以正負多個函式佐證，強制入 Product CI。0／180 對中心對稱矩形會有同一實體 CUTTING，角度保存及右手軸定義另行檢驗，不能虛報 180 變出不同切孔。
- 只簽當期 **來源已知 W800 上層真內門 PART-ONLY** 範圍，不擴充其它箱寬的 WORLD-X、整櫃 MFG-2／NC、焊接與 Windows 兩舊案全 GUI。正式 X 仍僅 `/推推`；**沒有 exact PR HEAD 五階段 SUCCESS 及 GitHub localX 回讀不得計入 23**。

## CURRENT｜2026-10-23 #1504 AC-04／AC-19 來源交易核銷（需 exact CI + localX readback）

- **2026-10-23 前一批由 20／88 → 22／88（當時尚餘 66 條）**；原 88 項 AC 文字與來源 SHA 完全不改。新增 `tests/test_issue1504_ac04_ac19_source_transactions.py` 供正式 Product CI 逐項驗證：Q5／Q6／Q7 操作只清受影響層的位移與 datum，另一層及穩定單顆 ID 保留；0／12.5／−0.125 mm 不失精度，非法 NaN、Inf、bool 等輸入原子拒絕；Q16 更換當期 V5 CSV 型號只保留 X／名義中心距、不核准 WORLD-X，來源或幾何非法時整筆不修改；Undo／Cancel 還原。
- 已保留 #1493 的混合 legacy ID／allocator 舊版、#1497 Q16 物理切孔批次拒絕與正反證據，防止只看測試檔名冒簽。新批次完成 **exact PR HEAD Product Regression 五階段 SUCCESS、GitHub localX 合併 SHA fresh readback** 才能生效。
- **17 條 #1500 真雙舊案 GUI、14 條 #1502 已交付待全 AC、4 條全箱歷史延期均不改為 PASS**；NFB-AC-05 現行 CSV 物理旋轉及 NFB-AC-54／SWT-AC-31 舊 reader 仍未簽。無 Windows 最新版本實測；正式 X 不動，需另外 `/推推`。

## CURRENT｜#1503 已結案後的阻擋狀態回讀（2026-10-22 台灣時間）

- **#1503 CLOSED/completed**：EAR／SIDE 打標與單雙層 PAD＋Base **PART-ONLY** 2D、3D、BOM、正式 CHECK/Q DXF 已有 GitHub CI 與 R5-2600 Windows 原生 GUI／片件收據，不能繼續把 #1503 當 *OPEN* 依賴，或宣稱 PAD 只有預覽。
- 本次機器矩陣 `open_gates` 改為 **#1500、#1504**；四條歷史 `DEFERRED_PRODUCT_EVIDENCE`（NFB-AC-13/41、SWT-AC-09/22）不再綁定已結案的 #1503。**它們仍是未簽 AC**：其中原文字有被後續實體 Z／PAD 交付覆蓋的歷史範圍，整箱 MFG-2／NC、焊接工藝／全域碰撞仍須獨立物理證據。不得把 PART-ONLY 收據升格成全箱工廠放行。
- **截至本段 2026-10-22 回讀，簽核數量為 20／88**，只修正過期阻擋指向；既有 17 條雙原始舊案 GUI 與 14 條 #1502 已交付但未滿原 AC 仍各自維持原狀。本頁後續提及「#1503 尚 OPEN／僅 PAD 延期」屬歷史記錄，不能覆蓋此 CURRENT readback；正式 X 未授權發布。


> **本表原文逐字保留，另列 CURRENT 覆蓋規則。** 原核准的 56 NFB AC + 32 SWT AC 共有 88 項；目前 `88/88` test-function 路徑可定位，但不能因此宣告 `88/88` 已通過。目前 **23/88 個當期來源範圍的完整自動化 AC 斷言（以本批 exact CI＋localX readback 生效為前提）**（原 13 項＋本批 `NFB-AC-06`、`NFB-AC-08`、`NFB-AC-26`、`NFB-AC-33`、`NFB-AC-37`、`SWT-AC-17`、`SWT-AC-25`，再加本批 `NFB-AC-04`、`NFB-AC-19`）；其他 65 項尚未簽核。本批必須以 exact PR HEAD 全套 Product CI SUCCESS ＋ GitHub localX readback 才生效；不可用測試檔存在或 CI 綠燈概括 88 項。

## 2026-10-22 CURRENT｜七項來源鏈集中核銷（需 #2057 exact HEAD CI 與 localX readback）

- **NFB-AC-06**：UI-1A 真草稿 Cancel／Escape／Undo、非法變更無來源洩漏，Native Hole Editor NFB 預覽非法索引不污染一般孔位／舊孔，主頁籤確定前不寫 Bay。
- **NFB-AC-08**：Quantity 版本 add/select/delete/deep-copy，每版真不同 NFB 型號、X／rotation／件數，以 `.p6fold` Save→Reload 精確保存，未核准 X 不在複製時偷轉 APPROVED。
- **NFB-AC-26**：現行 CSV V5 逐顆 90°／180° 儲存重載，顆覆寫與層繼承正確；實體主孔 X 未驗證時保持 `UNVERIFIED_BASIS`、不憑角度生假 WORLD-X 或製造允許。
- **NFB-AC-33**：未提交新 Bay／版本與專案使用舊 schema，無強制 NFB 槽位及新製造阻擋；Legacy source 的製造權限保留。這不表示曾逐位元組比對所有舊 DXF。
- **NFB-AC-37**：舊原生 Hole Editor CUTTING 與 W800×3 NFB 同實體位置／ID 排他，發現衝突即阻斷寫檔；未衝突的原 `CIRCLE` 在真輸出只出現一次，舊 FinalScene source 不受修改。
- **SWT-AC-17**：跨廠牌待重選仍保存名義孔距、不偷產真輪廓或 WORLD-X；現行 V5 角度可存檔但主孔 X 未經來源核准仍不顯示為可製造。
- **SWT-AC-25**：UNCONFIGURED 保持 Legacy，已提交但來源缺失／含糊時阻斷真內門與實際有相依的底／中板；側板不被尚未核准的 EAR 規則連坐。當期受電箱沒有憑空新增一片中板。
- 本批每項均保存 exact test function（主斷言＋至少兩個獨立正／反向證據），且 `tests/test_issue1504_seven_ac_source_signoff_batch.py` 在 canonical Product CI 強制檢查。**17 條 GUI 真兩舊案、14 條 #1502 交付但原 AC 尚未滿足的項目、4 條延後全箱工藝仍不簽**；不改原 88 項要求、正式 X 僅 `/推推`。

原規格與來源 SHA256 不變：
- `WHD_受電箱_NFB_UI與開孔編輯整合規格_20261010_v1.4.md` — `2fcf48521b913435b01639b9fa1b3ef7789ec93724033e332cedd4c85e1d0eef`
- `WHD_受電箱_開關層數_耳朵打標與內門開孔_規格書_20261010_v1.4.md` — `f4441937f43bf70de1224cf74926b8cfe031dc6eef6f18f165bd6bf6a8a2e5e1`

## 2026-10-22 CURRENT｜NFB-AC-22 + SWT-AC-15 直接保存證據（待本 PR exact SHA CI）

- 同一現行 `nfbv5:士林:2P400` 型號，使用真 UI-1A 編輯 `set_nfb_manual_x` 驗證 **明確 X=0 為 UNVERIFIED_BASIS**，清除位移改為 `NONE` 而非偷偷置中；草稿無製造核准狀態。
- 真 `write_project` → 原始 `.p6fold` JSON → `read_project` → 再儲存重開：確認 Bay 的單一來源品牌、層／顆順序、箱寬、基準快照與名義規則版本不失，且零位移與 NONE 有別；root schema 僅在提交時升 v3。
- Quantity 各版本以現行 `phase6-quantity-v2` 保存相同未知 X，重讀仍不變；嘗試寫入 `manufacturing_ready/approved` 或非法 X 會被拒，未提交工程仍保留舊 schema。
- **範圍是 NFB X 編輯／持久化的自動化 AC，不是 Windows 雙案完整 GUI UAT、X 物理座標核准、整櫃 DXF/焊接/MFG-2 放行。** 機器矩陣只提升上述兩項，不動 17 項 #1500 GUI 阻擋或 4 項 #1503 全局延期。

## 2026-10-22 CURRENT｜SWT-AC-03 直接 UI 身份驗證；NFB-AC-05 仍待真實製造旋轉

- 使用現行兩款士林 `nfbv5:` CSV 型號，以真正 `editable_nfb_draft`、位移/角度修改、調換、插入、刪除來源證明：兩層三顆身份不重複，每顆型號、手動 X、旋轉獨立；重排只清受影響層的失效 X，另一層保持；源頭名義孔距只允許既有規格組合，且永不自動得出絕對 X 或製造核准。
- `NFB-AC-05` 的單層／單顆繼承、0/90/180/270、覆寫與 Q16 旋轉保留、不鏡射都新增測試，但原 AC 還有 **MFG-1 真 CUTTING/pivot** 範圍。既有四角實際出圖測試採歷史 DXF 來源，不可當作當前 CSV V5 的直接物理證據；所以 NFB-AC-05 **仍 EVIDENCE_CANDIDATE_ONLY**，沒有擅簽。
- 只提升 SWT-AC-03 的自動化 UI 編輯 AC（須 exact SHA CI），不解除 17 項舊 GUI 雙案、4 項 MFG 延期、X 未核准定位及正式 X `/推推` 閘門。

## 2026-10-22｜剩餘 79 項一次盤點及四項來源核銷（來源範圍，待 exact CI）

- 原 88 AC 已有 9 項核銷，剩餘 **79 項全部找到主測試函式，集中於 23 個已被 canonical Product Regression 選入的檔案**。逐條追溯與未覆蓋邊界見 [`issue1504_79_pending_ac_batch_source_audit.json`](issue1504_79_pending_ac_batch_source_audit.json)。CI 選入主檔不等於跨入口 GUI／製造全條 AC 已驗證；不得再把這 79 項當作未跑測試重跑。
- 本批直接核銷 `NFB-AC-48`：缺單顆／整排 X、Y 或主孔實體中心即保守拒絕；**名義中心距不核准實體 X 或製造**。實際負例由 `test_issue1497_nfb_cutting_preflight.py`、`test_issue1494_nfb_x_shadow_projection.py`、`test_issue1504_current_nfb_y_ac10_swt02.py` 的既有函式共同驗證。
- `NFB-AC-49`：真 WHD W800×3 DXF 源輪廓、723 展開 CUTTING 基準、內門面到箱體座標的正反向 X 測試；**僅此個案，沒有替其他 W×N 或正式製造 X 解除限制**。
- `NFB-AC-50` 與 `SWT-AC-28`：舊 1100 高 550／290／790 名義 Y 與內門成形／展開可逆投影；非 1100 不猜。現行操作高度 330／830 的新規格另由相同真板件投影測試驗證，不倒退成舊預設；若無完整來源仍非正式 CUTTING 核准。
- 79 項基準盤點分類是 44 主要證據候選、17 #1500 GUI 真雙案、14 #1502 已交付但全 AC 尚需比對、4 #1503 PAD/EAR 整箱不同範圍。四項來源簽核後預期為 **13 已簽、40 候選、17 GUI、14 #1502、4 #1503，共 88**。不可把 PAD＋Base PART-ONLY、已驗 EAR 打標重新列作從未施工，也不得恢復已被現行 CSV／Z 規則覆蓋的舊限制。
- **不在本批冒簽的完整驗收**：NFB-AC-05 現行 CSV V5 四角物理 CUTTING/pivot 尚須直接 DXF 証據；NFB-AC-54／SWT-AC-31 舊 reader 和 DXF 向下相容；17 條雙舊案真 GUI；完整整櫃 MFG-2／焊接與跨板件全域接觸。正式 X 仍必須另外 `/推推`。

## 現行權威（覆蓋舊例，非第二份 AC 規格）

1. **來源已從舊廠牌 DXF 選型改為現行 CSV V5**：已提交之 `NFBConfig` + `基準檔/開孔/NFB/數值規格/<品牌>/NFB數值規格.csv` 決定每顆主開孔、螺絲孔、旋轉與深度；舊 DXF 類比與 Color 30／150／212 盤點僅限舊來源/既有類別，不得讓它重新成為現行 CSV 型號的必要前置，更不能虛構受電箱獨立「中板」。
2. **裝配基準已修正**：底板中心 **箱體中心 X=0**；NFB 單顆 X 僅改自己的 NFB 螺絲孔；每一實體層一片底板，底板 Y 依該層開孔高度（W800/H1600，330／830 對應 Y=470／−30），並非舊例的每層尺寸。W800、側板 T2 折後固定孔 X=−335／+335，**孔距 670 mm**；側板內皮 X=−398／+398，展開原例 732 mm 不是折後孔距。
3. **底板不是 Z 不動**：根據當前 NFB 深度與內門內側實體 skin，**底板及左右固定片一起移動 Z，內門不動**；底板背皮與固定片貼合皮面為同一面。原 `NFB-AC-13`／`SWT-AC-09` 禁移底板的 2026-10-10 原文已被後來核准的組裝規則覆蓋，原句僅供追溯。
4. **EAR 已不是全部未驗**：依新版真 `固定片.dxf` **T2/BEND23、大片孔心84、折後對側板內皮63**，已驗原 3D 實際折向、側板接觸/UV MARKING、單雙層固定片與左右 SIDE per-part CUTTING+BEND+MARKING DXF 及回讀；有 Windows 真 Tk 接觸/打標驗收紀錄。**獨立 PAD 設計、焊接工藝、未證實型號、整箱無條件製造放行仍不核准。**
5. **#1502 已於 2026-10-21 CLOSED**：PR [#2037](https://github.com/looaeedr/whd/pull/2037)、[完整 Product CI #39561179927](https://github.com/looaeedr/whd/actions/runs/39561179927) Preflight／Shard0/1/2／Canonical 全 SUCCESS、GitHub `localX@e33c9c9b509c55fd72ea7a83923ae8d27a8e5d34` 合併/readback。它是 **source-scoped 產品交付的證據，不等於所有 15 條原 AC 已完全簽核**。
6. **仍開的前置**：[#1500](https://github.com/looaeedr/whd/issues/1500)（真 GUI 交易/操作驗收）、[#1503](https://github.com/looaeedr/whd/issues/1503)（**僅 PAD** 延期與獨立焊接工藝），本張 #1504 為 AC 最終 owner，主單 [#1490](https://github.com/looaeedr/whd/issues/1490) 由完成 #1504 後關閉；**正式 X 僅使用者 `/推推`，Windows 最新 localX 不得由 GitHub CI 冒稱已同步**。


### 2026-10-22｜品牌繼承與來源防偽的新增簽核

- **NFB-AC-17**：`test_nfb_ac17_three_tier_followers_overrides_provenance_and_preview` 直接驗證本套品牌、層覆寫、顆覆寫、明確同值覆寫／取消覆寫與舊來源待重選；預覽沒有製造 WORLD-X。
- **SWT-AC-04**：`test_swt_ac04_spoofed_catalog_and_stale_csv_never_relabel_v5_source` 和 `test_swt_ac04_selected_brand_and_override_are_persisted_without_second_set_owner` 驗證 CSV V5 帶廠牌身分不可被偽清單換廠、來源消失必待重選、保存覆寫模式不新增第二套權威。
- **生效條件**：上述三條回歸必須加入 canonical Product Regression 並隨 #1504 PR exact SHA 五階段全 SUCCESS，合入 GitHub `localX` 回讀後才可視為當期自動化簽核成立。這不是 #1500 真 Windows GUI UAT 或整箱 MFG/NC 放行。


- **NFB-AC-10／SWT-AC-02（2026-10-22）**：增補 `tests/test_issue1504_current_nfb_y_ac10_swt02.py`，區分「舊工程沒有人工高度→1100 名義 550／290／790」與「CURRENT 來源已設定→330／830」，同一真內門 part／folded UV 可逆投影；非 1100 不借用名義公式、未核准 W×N 不猜 X 或製造 WORLD-X。只有 exact HEAD canonical CI 五階段全綠、localX merge/readback 後才是當期範圍簽核，**不復原舊 UI 預設**。

## 88 條狀態（最新由上方 23/88 及機器矩陣決定；下方早期回顧僅為歷史）

- `BLOCKED_1500_REAL_GUI`：17 條 — #1500 正式提交／跨連複製／還原與 Undo GUI 整合尚待完整確認
- `DEFERRED_PRODUCT_EVIDENCE`：4 條 — #1503 僅 PAD 產品製造／獨立工藝證據延期，已核准 EAR 不重做
- `EVIDENCE_CANDIDATE_ONLY`：47 條 — 已有候選測試，尚未逐項核斷言
- `ACCEPTED_AUTOMATED_CURRENT_SCOPE`：6 條 — `NFB-AC-30` 已驗名義孔距／無來源不造假孔；`NFB-AC-17`、`SWT-AC-04` 以同一 CURRENT CSV 型號來源核對本套→層→顆的品牌繼承、明確覆寫、跨廠牌待重選、偽清單/來源消失不得顯示 MODEL_SELECTED，以及已提交 NFBConfig 保存覆寫身分。須本 PR exact SHA CI 全綠且合回 localX 方生效；不代表真 Windows GUI / 全櫃製造放行。
- `SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC`：14 條 — #1502 已合入 localX 且現有實體來源範圍 CI 綠燈；完整 AC 尚待逐條驗收

`source-scoped #1502` 的 14 項仍標 `accepted=false`，以及 `SWT-AC-24` 轉歸 #1500 交易 GUI 前置；沒有任何 AC 再寫「#1502 尚未結案」。來源 `json`：`docs/superpowers/verification/issue1504_nfb_v14_ac_traceability.json`。

### 逐條原文與 CURRENT 解讀差異

| AC | CURRENT 覆蓋／待驗真相 |
|---|---|
| NFB-AC-03 | CURRENT 2026-10-21: NFB brand/model geometry is the user's per-brand numeric NFB數值規格.csv and committed NFBConfig, NOT a mandatory legacy manufacturer DXF file. Original DXF preview acceptance wording is historical compatibility scope, not a current CSV selection prerequisite. |
| NFB-AC-10 | CURRENT 2026-10-21: receiving-tab layer-height editor displays defaults 330/830 directly; old 550 and 290/790 in the 2026-10-10 §7 AC are not the current 2-tier default. The actual saved operator Y and tier-owned source determine mounting Y. |
| NFB-AC-11 | CURRENT 2026-10-21: legacy DXF ARC/CIRCLE/Color are still traced when referenced, but current model aperture and screw offsets come from brand numeric CSV; source identity is stored per switch, not deduced from old original drawing layers. |
| NFB-AC-13 | CURRENT correction: a submitted NFB depth NEVER moves the inner door; it DOES move the real BasePlate and its left/right EARs together in world Z to keep their true contact skins. Base X remains centered; Y follows the tier NFB aperture height, and per-switch X only moves NFB screws. Unapproved independent PAD blank is still blocked. |
| NFB-AC-14 | #1502 current localX source-scoped actual 2D/3D, current CSV committed FinalScene, original operator DXF saved/reopened, CHECK Q and multi-tier proof exist. Full original AC acceptance is still separately audited. |
| NFB-AC-38 | CURRENT Receiving has no separate middle plate. Color150 can remain an original/source classification elsewhere but MUST NOT fabricate a Receiving 中板. Current committed brand numeric CSV and actual material/real plate dependents own CUTTING/guard, not mandatory old model DXF Color30/150. |
| NFB-AC-39 | Current partial export manifest is read-only about actual allowed/held per physical Set/Bay and real part count; current CSV inner-door + one/two source BasePlate DXFs reopen and CHECK Q from the actual operator path. Not permission for unconditional full cabinet. |
| NFB-AC-44 | CURRENT source guard uses actual submitted current numeric CSV and real NFB-dependent plates, not a fictitious Receiving middle plate. Unsupported sources stay held per physical part, without preventing independent side-source production. |
| NFB-AC-55 | Original DXF color inventory remains a *historical* diagnostic with missing != zero; current CSV V5 brand/model numeric catalogue is now the primary model source. Do not make Color30/150/212 mandatory for every current CSV model. |
| SWT-AC-09 | CURRENT correction: changing selected NFB depth moves the real BasePlate and paired EARs together in Z; it does NOT implicitly create a PAD. The upper aperture/lower original screw-group provenance cannot be treated as a PAD blank. |
| SWT-AC-11 | #1502 current localX real FinalScene/2D, saved/reopened original DXF and CHECK Q now supply source-scoped physical evidence; full original AC sign-off remains independent. |
| SWT-AC-21 | CURRENT numeric NFB CSV supplies model geometry; Receiving has actual BasePlate(s), no imaginary middle plate inferred from legacy Color150. |
| SWT-AC-22 | CURRENT EAR is no longer unverified: original 固定片.dxf T2/BEND23 formed-geometry signed +90, real side skin physical contact and original side UV MARKING per-part DXF were verified, including Windows-native Tk 2D/3D. PAD/welding workmanship and unconditional whole-cabinet NC remain unapproved. |
| SWT-AC-24 | Current #1502 part-scoped output complete; first submit, cross-Bay copy, restore and Undo share #1500 live transaction guard and are still pending complete operator acceptance, NOT blocked by a closed #1502 issue. |
| SWT-AC-32 | Color30/150 inventory is valid for legacy sources but does not manufacture an absent Receiving 中板. Actual current NFB CSV and source material role + real CHECK Q/manifest are the current owner. |

## 原始 AC 項目與 test function 追溯

| AC | Owner | 尚缺驗收 | 階段 | 核准原文 |
|---|---|---|---|---|
| NFB-AC-01 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 受電箱才看見 NFB UI；其他箱型既有 Hole Editor 不變。 |
| NFB-AC-02 | #1491、#1500 | BLOCKED_1500_REAL_GUI | UI-1A／UI-1B（提交下限） | 未提交可零槽；正式提交後層數 1／2、至少一槽，刪除最後槽不得隱式退回未配置；1→2、2→1 遵守 Q12／Q17／Q18。 |
| NFB-AC-03 | #1492 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 真實廠牌 DXF 列表、右側預覽、縮放／平移／重設；選檔不污染正式狀態。 |
| NFB-AC-04 | #1493 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（編輯）／MFG-1（幾何違法回滾） | 配置卡重排序與 2D 位移明確分離；mm 欄位精確；Q5／Q6／Q7 清除受影響層全部位移；Q16 保留位移、名義孔距不動，重新驗證非法回滾。 |
| NFB-AC-05 | #1493、#1497 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（設定）／MFG-1（真實旋轉） | 整層預設與單顆角度覆寫互不混淆；0/90/180/270 正確、禁止鏡像；更換型號保留設定。 |
| NFB-AC-06 | #1493 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（取消 Undo）／MFG-1（幾何違法） | 離開／取消／Undo 不漏出暫存變更；範圍／碰撞非法時保留上次合法配置。 |
| NFB-AC-07 | #1500 | BLOCKED_1500_REAL_GUI | UI-1B | Bay 複製需覆寫確認、整組深複製；來源及目標之後獨立。 |
| NFB-AC-08 | #1499 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1B | 數量模式不同 `version_id` 可保存不同 NFB；版本增刪／切換／深複製／重讀均保持身份。 |
| NFB-AC-09 | #1498、#1499 | EVIDENCE_CANDIDATE_ONLY | UI-1B（重載）／MFG-1（板件守衛） | 已經合法提交但後續因板件未完成或來源失效而未驗證的草稿可 Save→Reload；只阻斷真正依賴 NFB 缺項的物理板件，列明 Set／Bay／版本／層／顆與原因；不連坐同 Bay 無關板件。 |
| NFB-AC-10 | #1494、#1495 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（名義顯示）／MFG-1（物理投影） | 1100 高 Y=550 或 290/790；表列已證實的 X 孔距正確；其他高度／寬度不能推測。 |
| NFB-AC-11 | #1496、#1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-1（主孔）／MFG-2（其餘來源組） | 真實來源 ARC、CIRCLE、多 layer／entity color、上下資料組皆完整識別；主開孔 pivot 正確。 |
| NFB-AC-12 | #1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-2 | 同顆跨板件孔／打標有穩定關聯，所有合法製造圖元位於正確實體板件，不被當成一張板。 |
| NFB-AC-13 | #1503 | DEFERRED_PRODUCT_EVIDENCE | UI-1A（不可移底板）／PAD（後續實作） | 底板不因 NFB 深度變更而位移；墊高未施工時禁止產出其假 DXF。 |
| NFB-AC-14 | #1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-2（完整跨板件） | 2D／3D／DXF／Save→Reload 使用同一已解析製造資料；相同加工片合併，不同 NFB 加工不得誤合併。 |
| NFB-AC-15 | #1492 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 僅選取與高亮不重建整箱 3D、不反覆重讀全部 DXF；UI 互動不卡頓。 |
| NFB-AC-16 | #1499、#1500 | BLOCKED_1500_REAL_GUI | UI-1A（取消）／UI-1B（重載）／MFG-1（舊孔出圖不變） | 新舊未配置案開啟面板再取消仍未配置；Save→Reload 與升級前逐片實際製造幾何／圖層／件數與輸出範圍一致，無虛構 NFB；來源未配置 Bay 複製禁用；提交後 Save→Reload 不丟失提交事實；金庫型及既有 Hole Editor 回歸。 |
| NFB-AC-17 | #1491 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（繼承）／UI-1B（正式保存） | 「本套／本配置→層→單顆」品牌繼承只更新跟隨者，覆寫者保持；跨廠牌型號不偷替換，缺有效來源標待重選。 |
| NFB-AC-18 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 層數只有 NFB 配置一處可編輯；本套開關旁只保留廠牌＋入口；單顆 X／整排 X 基準未知、非 1100 Y 未知，均顯示未定且禁止偽製造定位。 |
| NFB-AC-19 | #1493、#1497 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（清位移）／MFG-1（違法回滾） | Q5／Q6／Q7 只清受影響層全部手動位移，對應狀態改 NONE 並清舊快照；Q16 保留位移／名義孔距，重驗整層非法原子回滾；操作 Undo／Cancel 可完整還原。 |
| NFB-AC-20 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 改本套／本配置／層預設品牌前正確預告將待重選顆數；取消狀態完全不變，確認才套用；同值明確覆寫仍維持覆寫身份。 |
| NFB-AC-21 | #1491、#1499 | EVIDENCE_CANDIDATE_ONLY | UI-1A（預設）／UI-1B（版本保存） | 數量模式每個版本的本配置預設廠牌與三級繼承獨立；深複製後修改甲不影響乙；套／連本套品牌僅既有控件可寫。 |
| NFB-AC-22 | #1499 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1B | X datum 未定仍可輸入含明確 0 的位移，Save→Reload 保存 UNVERIFIED_BASIS、箱寬／層／顆 ID 順序／名義規則版本；沒有位移用 NONE；不保存衍生製造通過狀態。 |
| NFB-AC-23 | #1499、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1B（重新確認）／MFG-1（製造阻斷） | 新 X 基準確立後，舊位移不能自動生效，須比較條件並經使用者重新確認；受影響顆未確認前維持草稿與製造阻斷。 |
| NFB-AC-24 | #1498 | EVIDENCE_CANDIDATE_ONLY | UI-1B（狀態）／MFG-1（板件守衛） | 逐顆「已驗證／未驗證」及原因正確；已提交配置由當前來源推導 DRAFT／CONFIGURED；DRAFT 只阻斷 NFB 依賴未完成的物理板件，不阻斷無關片／Bay／版本，列受阻身份。 |
| NFB-AC-25 | #1493 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A | 「型號待重選」仍可依已核准名義表顯示相對中心距；實際 X 定位、碰撞、越界各自未驗證，沒有憑空置中。 |
| NFB-AC-26 | #1493、#1499 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（角度）／UI-1B（重載） | 儲存單顆 90° 等旋轉設定並重載；主開孔中心未驗證時不產生假旋轉放置／已驗證顯示。 |
| NFB-AC-27 | #1493、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1A（設定）／MFG-1（幾何回滾） | Q16 型號變更／待重選恢復不改已知名義中心距，保留位移並重驗整層實際幾何；具完整資料且非法時全筆原子回滾。 |
| NFB-AC-28 | #1499、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1B（重新確認）／MFG-1（逐顆驗證） | 未驗證位移至少可按 Bay／配置批次重新確認，先提示條件差異與受影響清單；逐顆非法者不能批次放行。 |
| NFB-AC-29 | #1499、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1B（重載）／MFG-1（重新解析） | Save→Reload／來源 DXF 變動後重新推導主孔中心、位置、越界及草稿結論，不信任專案舊衍生驗證旗標。 |
| NFB-AC-30 | #1494 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（中心距）／MFG-1（防假孔） | 已知名義中心距不依賴已選型號外形；缺型號不抹掉中心距，但未驗證的實際製造孔不得輸出。 |
| NFB-AC-31 | #1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-2 | 量產版本不同 NFB 導出不同實際加工幾何時，不得錯誤合併 DXF；同加工者仍依既有 CHECK `Q{加工片數}` 正確分組。 |
| NFB-AC-32 | #1493 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 清除位移後可觀測是哪層、幾顆受影響；Undo 恢復位移／基準條件快照，沒有殘留過期暫存。 |
| NFB-AC-33 | #1499 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（未提交）／UI-1B（儲存）／MFG-1（舊式 DXF） | 新專案／新增 Bay／版本初始 UNCONFIGURED；未提交不需槽位，舊式 DXF 產出不變。 |
| NFB-AC-34 | #1500 | BLOCKED_1500_REAL_GUI | UI-1A（停用）／UI-1B（首次提交／重載） | UI-1A 守衛未驗收時「確認套用」及可造成提交的 Bay 複製停用；UI-1B 首次提交（含複製到 UNCONFIGURED 目標）須逐件提醒及確認，取消全不變；提交後未完成製造驗證者 DRAFT 並可 Save→Reload。 |
| NFB-AC-35 | #1500 | BLOCKED_1500_REAL_GUI | UI-1B | 「還原為未配置」獨立確認、Undo；`submitted=false` 且丟棄當前 NFBConfig 層／顆／位移等，不保存休眠配置；不刪原本套品牌或 legacy Features，回復舊式出圖；禁靠刪最後槽返回。 |
| NFB-AC-36 | #1500 | BLOCKED_1500_REAL_GUI | UI-1A（禁止提交複製）／UI-1B（正式深複製） | 來源 UNCONFIGURED 禁止 NFB 複製；已配置來源複製到未配置目標是首次提交，需守衛與提醒；數量版本深複製提交事實，未配置來源不產生 NFBConfig 休眠資料，各版本獨立。 |
| NFB-AC-37 | #1497 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | MFG-1 | 同位置既有 Hole Editor Feature 與 NFB 來源先識別後關聯／排他，來源不明 fail-closed；沒有重複孔，還原後舊特徵完整恢復。 |
| NFB-AC-38 | #1498、#1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-1（守衛）／UI-1B（提交）／MFG-2（加工分流） | 已提交配置對應內門必相依；可信 DXF 依 Color 30／150 判定底板／中板；型號未選或無法解析時阻斷實際存在的底板／中板，可信證明無相依則恢復匯出；EAR 延期不單獨阻斷側板，不連坐其他件／Bay。 |
| NFB-AC-39 | #1501、#1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | UI-1B（部分清單）／MFG-2（最終加工判等） | 明示部分匯出產生實際可出／受阻清單與原因、版本、件數差異；不留混淆的完整批次舊 DXF，CHECK `Q{加工片數}` 只算實際合法匯出且幾何相同片。 |
| NFB-AC-40 | #1499、#1500 | BLOCKED_1500_REAL_GUI | UI-1B | 基準首次核准及版本變更正確觸發 RECONFIRM_REQUIRED；只有有來源宣告相容者例外；重新手動輸入/批次確認綁定版本；位移 0 不等於 NONE；Save→Reload 不錯認。 |
| NFB-AC-41 | #1503 | DEFERRED_PRODUCT_EVIDENCE | UI-1B（納管驗證）／PAD（延期聲明） | `CONFIGURED` 只能在本期所有納管板件合法後成立；PAD／EAR 延期要列在整套交付報告中，不能誤宣告全部裝配完成。 |
| NFB-AC-42 | #1491、#1500 | BLOCKED_1500_REAL_GUI | UI-1A（停用）／UI-1B（啟用） | UI-1A 可做完整配置預覽、取消與 Undo，但 guard flag 未 READY 時正式套用／覆寫按鈕停用、不得提交或污染既有 DXF；守衛通過驗收後才開放 UI-1B。 |
| NFB-AC-43 | #1500 | BLOCKED_1500_REAL_GUI | UI-1B | 已配置來源複製到未配置目標，顯示同首次提交的實際受阻候選板件與確認；取消時目標依舊 UNCONFIGURED、來源不變，無守衛時拒絕複製套用。 |
| NFB-AC-44 | #1498、#1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-1（守衛）／UI-1B（提交）／MFG-2（底／中板） | 已提交但空槽／待重選／來源解析失敗時，對應內門與實際存在的底板／中板均不可出完整製造 DXF；來源可信且確認未使用 Color 30／150 時，底板／中板不因 NFB 被阻斷；左右側板不因尚未批准的 EAR 需求被阻斷。 |
| NFB-AC-45 | #1500 | BLOCKED_1500_REAL_GUI | UI-1B | 還原為未配置後不殘留可複製或重啟的 NFBConfig 休眠內容；同一 transaction Undo 可完整恢復先前提交設定及守衛結果，legacy 製造與本套品牌 owner 不變。 |
| NFB-AC-46 | #1499、#1500 | BLOCKED_1500_REAL_GUI | UI-1B（已提交檔守衛）／MFG-1（內門阻斷） | 守衛功能旗標關閉但載入已提交 NFBConfig 的檔案，不得當作 UNCONFIGURED 照舊匯出缺 NFB 孔的完整 DXF；阻止受影響完整匯出並明確警示。 |
| NFB-AC-47 | #1493 | EVIDENCE_CANDIDATE_ONLY | UI-1A | UI-1A 關閉有未提交變更的 NFB 面板須確認；取消關閉時保留編輯會話，確認捨棄不寫權威配置且舊式 DXF 不變。 |
| NFB-AC-48 | #1494、#1495、#1496 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | MFG-1（進場） | MFG-1 缺 X 單顆／整排、Y 局部投影或主孔中心任一證據時，不得讓未知配置成為「可製造」；四組已知名義中心距不自動等於已驗收可製造。 |
| NFB-AC-49 | #1494 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | MFG-1（X 進場） | W800×3 的 723/361.5 個案須核對來源 DXF 左輪廓、真正下料 CUTTING 左緣及下料→門面→箱體 X 映射；未證實前不得以此個案推導其它組合。 |
| NFB-AC-50 | #1495 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（未定顯示）／MFG-1（Y 進場） | 1100 名義 550／290／790 從箱體外頂投影到內門成品與展開 Y 具可重現雙向測試；非 1100 標「Y 基準未定」，不猜。 |
| NFB-AC-51 | #1496、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1A（提示）／MFG-1（解析與能力） | DXF 主 CUTTING 中心、ARC/CIRCLE、來源顏色及旋轉 pivot 經真圖認證；選型列表逐組正確顯示「可製造（內門）」／「僅預覽」，不可因型號孤立合格便全範圍放行。 |
| NFB-AC-52 | #1497 | EVIDENCE_CANDIDATE_ONLY | MFG-1（製造）／UI-1B（閘門） | MFG-1 輸出合法內門真實 CUTTING、消除與 legacy 相同物理孔的重複加工來源；缺必要幾何 fail-closed，MFG-1 未通過時 UI-1B 不准提交。 |
| NFB-AC-53 | #1498、#1500 | BLOCKED_1500_REAL_GUI | MFG-1（能力）／UI-1B（提交） | 機器可驗證的版本化 MFG-1 能力註冊驅動提交可用性，不靠 GUI 手動旗標；能力不可用禁止新提交／提交型複製，但既有已提交專案不降級成未配置。 |
| NFB-AC-54 | #1499 | EVIDENCE_CANDIDATE_ONLY | UI-1B（Save／Reload／降級回歸） | 有已提交 scope 時升根 `.p6fold` 與 quantity payload schema；舊版依凍結支援 schema 清單拒載新版本，不吞未知欄位後產出完整 DXF；全部未提交工程仍保留本功能無關的舊 schema 相容。 |
| NFB-AC-55 | #1496、#1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-1（盤點／守衛）／UI-1B（告知）／MFG-2（正式加工） | 逐型號盤點真實 NFB DXF 的 Color 30／150／212 與來源可解析狀態，交付有／無／未知數量（未取得原 DXF 前不得填 0）；MFG-2 未完成時 Color 30／150 受影響底／中板保持阻斷並列於提交提醒與部分匯出清單。 |
| NFB-AC-56 | #1500 | BLOCKED_1500_REAL_GUI | UI-1B | UI-1B 不提供「忽略草稿強制舊式內門出圖」覆寫；可以撤銷提交、還原未配置並 Undo。 |
| SWT-AC-01 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 單一可寫 NFB 安裝層數入口，與既有本套品牌 UI 一致；金庫型不出現 NFB 專屬規則。 |
| SWT-AC-02 | #1495 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（名義）／MFG-1（投影） | 上層 1100：一層每顆共用名義 Y=550、兩層上 Y=290／下 Y=790；非 1100 顯示未定，不偷用公式。 |
| SWT-AC-03 | #1493 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A | 每層多顆有獨立身份與型號、順序、X 位移及旋轉設定；既有中心距只於有效規格組合使用。 |
| SWT-AC-04 | #1491、#1499 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（繼承）／UI-1B（保存） | 品牌繼承 A：只更新跟隨者，保留覆寫；當生效廠牌與舊檔不合，顯示待重選，不能默默替換。 |
| SWT-AC-05 | #1492、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1A（來源預覽）／MFG-1（主孔） | 每顆來源 DXF 原圖預覽、確認／取消、主開孔中心未驗證標示清楚；不冒充可製造定位。 |
| SWT-AC-06 | #1493、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1A（設定）／MFG-1（非法回滾） | UI 的 Q5／Q6／Q7／Q16 行為只驗收 NFB-AC-04／19／27；本件查核名義中心距不受型號改變、非法實際幾何不得放行，Undo／取消保留既有加工。 |
| SWT-AC-07 | #1499、#1500 | BLOCKED_1500_REAL_GUI | UI-1B | UI-1B 提交守衛啟用後，Bay 深複製及數量版本深複製獨立，`.p6fold` Save→Reload 保留已提交配置及使用者設定；UI-1A 僅編輯預覽不可聲稱已保存配置。 |
| SWT-AC-08 | #1498、#1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-1（內門）／MFG-2（其他板件） | 沒有可信來源、主孔中心或合法世界定位時，按實體物理件相依阻斷完整 NFB DXF，逐件列出來源／缺項；不阻斷可證明無依賴片。 |
| SWT-AC-09 | #1503 | DEFERRED_PRODUCT_EVIDENCE | UI-1A（禁偽墊高）／PAD（延期） | 來源上方開孔、下方墊高不混淆；**本期不輸出墊高或自動改底板位置**。 |
| SWT-AC-10 | #1497、#1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-1（內門）／MFG-2（EAR 依正式核准） | 真實內門開孔與 NFB 個別中心一致，不以銘牌孔／假矩形替代；左／右耳朵真焊接接觸與打標同源。 |
| SWT-AC-11 | #1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-2 | 2D／3D／DXF／Save 從同一解算來源一致；受電箱 NFB 衍生切孔不同的料件不能錯誤合併。 |
| SWT-AC-12 | #1504 | EVIDENCE_CANDIDATE_ONLY | UI-1A／MFG-1／UI-1B／MFG-2／PAD（各階段回歸） | 不破壞內門框末段 22 mm、46＋2T、門縫、底板原幾何、背孔／中隔與金庫型回歸。 |
| SWT-AC-13 | #1491 | EVIDENCE_CANDIDATE_ONLY | UI-1A | 變更上游品牌前顯示待重選顆數，確認後更新跟隨者，取消時品牌／型號／位移／旋轉／覆寫狀態完全不動。 |
| SWT-AC-14 | #1491、#1499 | EVIDENCE_CANDIDATE_ONLY | UI-1A（獨立）／UI-1B（保存） | 套／連本套預設只能由既有本套品牌控件寫入；數量模式各版本 NFBConfig 自有預設品牌，新增版本深複製且修改互不污染。 |
| SWT-AC-15 | #1499 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1B | 按 NFB UI v1.4 §2.3.1 的單一 `manual_x_state`、快照、基準版本保存未知基準位移；Save→Reload 不自動升格製造偏移（UI-1B 才可持久化）。 |
| SWT-AC-16 | #1499、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1B（批次確認）／MFG-1（真實驗證） | 新 X 基準定案，既有未知基準位移必須逐顆或按 Bay／配置批次重新確認；確認後仍逐顆驗證，不能批次跳過干涉檢查。 |
| SWT-AC-17 | #1492、#1499 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（預覽）／UI-1B（重載） | 型號待重選時已知名義中心距仍可顯示，實際幾何／碰撞保持未驗證；旋轉角度可存但主孔中心缺乏時不產生假放置。 |
| SWT-AC-18 | #1498、#1500 | BLOCKED_1500_REAL_GUI | MFG-1（守衛）／UI-1B（狀態） | 未提交配置維持既有加工；已提交草稿逐顆顯示原因，依真實受影響板件阻斷，不波及可證明無依賴實體件；詳 NFB-AC-24／38／39。 |
| SWT-AC-19 | #1499、#1497 | EVIDENCE_CANDIDATE_ONLY | UI-1B（重載）／MFG-1（幾何推導） | 重載／來源更新重新推導實際位置、主孔中心、碰撞與草稿，不把過期驗證狀態當存檔真值。 |
| SWT-AC-20 | #1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-2 | 數量模式 NFB 衍生孔型不同時不誤合併加工料件；相同實際加工幾何依既有 CHECK `Q{加工片數}` 規則合併。 |
| SWT-AC-21 | #1498、#1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-1（依賴守衛）／MFG-2（實際板件） | 已提交配置內門必相依；空槽／待重選或來源解析失敗保守阻斷實際底板／中板，可信來源依 Color 30／150 的正式類別分流且已證明無相依者可正常匯出。 |
| SWT-AC-22 | #1503 | DEFERRED_PRODUCT_EVIDENCE | MFG-1（側板非 EAR 阻斷）／PAD（延期） | 耳朵與 PAD 延期未核准不得憑空生成側板焊接標記，亦不能僅憑 EAR 未完成阻斷原有側板；具其他已批准加工依賴者正常驗證。 |
| SWT-AC-23 | #1497 | EVIDENCE_CANDIDATE_ONLY | MFG-1 | 一個舊式 Feature 與 NFB 孔應相同物理位置時完成來源關聯／排他且不重複；未驗證阻斷該片正式加工；還原未配置不失原特徵。 |
| SWT-AC-24 | #1500、#1501、#1502 | BLOCKED_1500_REAL_GUI | UI-1A（不提交）／MFG-1（守衛）／UI-1B（保存）／MFG-2（分組） | UI-1A 未提交保留 legacy 出圖；UI-1B 完成守衛才可提交。還原未配置丟棄 NFBConfig 且可 Undo；複製至未配置目標視為首次提交，受阻件有 manifest、其餘合法件可部分出圖，CHECK 件數正確。 |
| SWT-AC-25 | #1498 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | MFG-1（依賴）／UI-1B（提交） | 未選型與缺來源不導致既有 UNCONFIGURED 箱體任何新增阻斷；已提交之內門及真實存在的底板／中板依保守基線阻斷，側板不憑 EAR 延期受阻。 |
| SWT-AC-26 | #1500 | BLOCKED_1500_REAL_GUI | UI-1A（提交鎖定）／UI-1B（READY 後啟用） | 真實板件依賴守衛未驗收前，UI 確認與會提交到未配置 Bay 的複製操作均不可用；不影響舊式內門／底板／中板出圖。 |
| SWT-AC-27 | #1494 | EVIDENCE_CANDIDATE_ONLY | MFG-1（X 進場） | 單顆 X／整排 X 的內門／箱體 datum 與來源 DXF 有正式核准測例，沒有的組合不得冒稱可製造，W800×3 不能替其他箱寬解除 `OPEN-X-ROW`。 |
| SWT-AC-28 | #1495 | ACCEPTED_AUTOMATED_CURRENT_SCOPE | UI-1A（提示）／MFG-1（Y 進場） | 1100 上層的外頂 Y=550／290／790 正確投影到形成內門及展開局部 Y，非 1100 不猜座標。 |
| SWT-AC-29 | #1497 | EVIDENCE_CANDIDATE_ONLY | MFG-1（NFB-DXF 進場／內門切孔） | 每顆 NFB 的主 CUTTING 開孔中心、輪廓與旋轉有真實 DXF／Feature 測例；與既有中間孔加工來源排他、不重複、不刪 legacy Feature。 |
| SWT-AC-30 | #1498 | EVIDENCE_CANDIDATE_ONLY | UI-1A（標示）／MFG-1（能力註冊） | 已知四組相鄰名義孔距不是可製造清單；只對逐組核准的 W×N×Y×型號×內門 datum 顯示可製造（內門），範圍外僅預覽。 |
| SWT-AC-31 | #1499 | EVIDENCE_CANDIDATE_ONLY | UI-1B（Save／Reload／降級回歸） | 未提交保持既有 schema 與 DXF；已有提交 scope 須根專案與 Quantity schema 升版，凍結舊版 schema 清單的舊 reader 拒載；不能對不認識新 schema 的舊版 silent export。 |
| SWT-AC-32 | #1496、#1502 | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC | MFG-1（盤點／依賴）／UI-1B（告知）／MFG-2（出圖） | 真 DXF Color 30／150 盤點件數與解析狀態逐檔可追溯；未取得源檔前不得假報 0。MFG-2 未完成的相依底／中板阻斷、其他無相依板件照常出圖，manifest／CHECK 計數不受污染。 |

## 88 項確切測試函式（部分自動化證據，不代表整條 AC 驗收）

**88/88 條已找到確切的 Python 測試函式；13/88 條有當期範圍的完整 AC 自動化斷言，仍需本 PR exact HEAD CI 全綠後生效。** 這只確認函式名稱、候選檔案與原 owner 一致，並經 AST 檢查它真的存在。尚未逐條證明所有操作、UI、加工、裝配與現場斷言均完整覆蓋。

如單條需求含多種操作，以下只代表其中一部分證據。例如 #1500 的真實 UI 操作與 #1502 的實體製造仍必須單獨驗收，不得因測試函式存在而放行。

| AC | 測試函式識別（僅部分證據） | 未完成狀態 |
|---|---|---|
| NFB-AC-01 | `tests/test_issue1491_nfb_ui1a.py::test_no_unapproved_geometry_or_persistence_fields` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-02 | `tests/test_issue1491_nfb_ui1a.py::test_empty_slot_keeps_physical_order_and_requires_no_fake_hole` | BLOCKED_1500_REAL_GUI |
| NFB-AC-03 | `tests/test_issue1492_nfb_real_dxf_preview.py::test_pan_zoom_reset_never_reopens_source_or_changes_manufacturing` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-04 | `tests/test_issue1493_nfb_draft_transactions.py::test_insert_delete_reorder_reset_only_touched_layer_x` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-05 | `tests/test_issue1504_swt03_nfb05_current_unit_rotation.py::test_nfb_ac05_layer_inheritance_override_model_reselection_and_all_quarter_turns` | ACCEPTED_AUTOMATED_CURRENT_SCOPE（現行 V5 製造 CUTTING 旋轉證據未全） |
| NFB-AC-06 | `tests/test_issue1493_nfb_draft_transactions.py::test_cancel_escape_undo_restore_stable_unit_ids_brand_x_and_conditions` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-07 | `tests/test_issue1500_nfb_transactions.py::test_copy_submitted_source_into_independently_verified_target_unit_id` | BLOCKED_1500_REAL_GUI |
| NFB-AC-08 | `tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-09 | `tests/test_issue1498_nfb_part_readiness.py::test_each_set_bay_version_independent_and_no_cross_scope_ready_cache` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-10 | `tests/test_issue1504_current_nfb_y_ac10_swt02.py::test_nfb_ac10_current_330_830_operator_y_roundtrips_real_panel` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-11 | `tests/test_issue1496_nfb_dxf_source.py::test_color_sources_preserve_entity_layer_and_block_inheritance` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| NFB-AC-12 | `tests/test_issue1502_nfb_base_source_projection.py::test_one_door_nfb_owner_projects_corresponding_base_cutting_and_marks` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| NFB-AC-13 | `tests/test_issue1503_deferred_pad_ear_manufacturing.py::test_unapproved_brand_pad_depth_does_not_move_or_cut_base` | DEFERRED_PRODUCT_EVIDENCE |
| NFB-AC-14 | `tests/test_issue1502_nfb_ear_base_assembly_contract.py::test_ear_mounting_does_not_invent_base_or_change_verified_inner_NFB` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| NFB-AC-15 | `tests/test_issue1492_nfb_real_dxf_preview.py::test_cache_changes_with_real_source_identity_and_bounded_memory` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-16 | `tests/test_issue1499_nfb_persistence.py::test_unconfigured_bay_and_quantity_keep_legacy_schema` | BLOCKED_1500_REAL_GUI |
| NFB-AC-17 | `tests/test_issue1504_brand_inheritance_current_csv.py::test_nfb_ac17_three_tier_followers_overrides_provenance_and_preview` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-18 | `tests/test_issue1491_nfb_ui1a.py::test_nominal_pitch_exact_but_never_absolute_x` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-19 | `tests/test_issue1493_nfb_draft_transactions.py::test_q16_replace_model_preserves_x_and_identity_but_unverifies_geometry` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-20 | `tests/test_issue1491_nfb_ui1a.py::test_single_set_brand_owner_and_explicit_same_value_overrides` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-21 | `tests/test_issue1491_nfb_ui1a.py::test_single_set_brand_owner_and_explicit_same_value_overrides` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-22 | `tests/test_issue1504_ac22_swt15_current_x_persistence.py::test_nfb_ac22_v5_bay_x_zero_none_datum_order_save_reopen_never_auto_approves` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-23 | `tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-24 | `tests/test_issue1498_nfb_part_readiness.py::test_each_set_bay_version_independent_and_no_cross_scope_ready_cache` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-25 | `tests/test_issue1504_ac25_reselection_nominal_x.py::test_nfb_ac25_reselection_preserves_approved_relative_pitch_no_fake_x_checks` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-26 | `tests/test_issue1493_nfb_draft_transactions.py::test_angle_inherit_explicit_same_override_no_mirror` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-27 | `tests/test_issue1497_nfb_cutting_preflight.py::test_q16_invalid_model_change_blocks_whole_batch_without_moving_other_hole` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-28 | `tests/test_issue1497_nfb_cutting_preflight.py::test_two_independent_upper_units_require_unique_physical_claims_and_no_overlap` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-29 | `tests/test_issue1499_nfb_persistence.py::test_derived_flags_not_saved_and_invalid_nfb_fails_without_fallback` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-30 | `tests/test_issue1504_ac30_current_nominal_no_fake_cutting.py::test_nfb_ac30_nominal_spacing_survives_missing_model_without_fake_cutting`（另含同檔 CSV 無來源不產生 CUTTING + #1497 X 未認證拒絕） | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-31 | `tests/test_issue1502_nfb_base_batch_export_gate.py::test_one_unreleased_base_rejects_entire_multi_bay_export_before_io` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| NFB-AC-32 | `tests/test_issue1493_nfb_draft_transactions.py::test_cancel_escape_undo_restore_stable_unit_ids_brand_x_and_conditions` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-33 | `tests/test_issue1499_nfb_persistence.py::test_unconfigured_bay_and_quantity_keep_legacy_schema` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-34 | `tests/test_issue1500_nfb_transactions.py::test_first_submission_includes_held_plates_in_warning_but_commits_inner_config` | BLOCKED_1500_REAL_GUI |
| NFB-AC-35 | `tests/test_issue1500_nfb_transactions.py::test_restore_clears_only_nfb_and_undo_restores_without_deleting_legacy` | BLOCKED_1500_REAL_GUI |
| NFB-AC-36 | `tests/test_issue1500_nfb_transactions.py::test_unconfigured_source_copy_forbidden_and_overwrite_needs_confirmation` | BLOCKED_1500_REAL_GUI |
| NFB-AC-37 | `tests/test_issue1497_w800_three_canonical_cutting.py::test_legacy_same_location_or_same_physical_owner_blocks_atomic_export` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-38 | `tests/test_issue1498_nfb_part_readiness.py::test_real_base_color30_and_marking212_have_specific_base_dependency` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| NFB-AC-39 | `tests/test_issue1501_nfb_export_manifest.py::test_shihlin_color150_partial_only_counts_real_pieces` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| NFB-AC-40 | `tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate` | BLOCKED_1500_REAL_GUI |
| NFB-AC-41 | `tests/test_issue1503_deferred_pad_ear_manufacturing.py::test_forged_approved_flag_cannot_override_deferred_role_in_atomic_batch` | DEFERRED_PRODUCT_EVIDENCE |
| NFB-AC-42 | `tests/test_issue1500_nfb_ui1b_bridge.py::test_live_submit_rechecks_bay_source_and_snapshot_before_adapter_write` | BLOCKED_1500_REAL_GUI |
| NFB-AC-43 | `tests/test_issue1500_nfb_transactions.py::test_unconfigured_source_copy_forbidden_and_overwrite_needs_confirmation` | BLOCKED_1500_REAL_GUI |
| NFB-AC-44 | `tests/test_issue1498_nfb_part_readiness.py::test_missing_real_plate_id_is_scope_blocker_not_an_invented_part` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| NFB-AC-45 | `tests/test_issue1500_nfb_transactions.py::test_restore_clears_only_nfb_and_undo_restores_without_deleting_legacy` | BLOCKED_1500_REAL_GUI |
| NFB-AC-46 | `tests/test_issue1499_nfb_persistence.py::test_old_schema_reader_must_not_silently_strip_new_nfb_scope` | BLOCKED_1500_REAL_GUI |
| NFB-AC-47 | `tests/test_issue1493_nfb_draft_transactions.py::test_cancel_escape_undo_restore_stable_unit_ids_brand_x_and_conditions` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-48 | `tests/test_issue1494_nfb_x_shadow_projection.py::test_no_unapproved_size_or_single_unit_center_defaults` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-49 | `tests/test_issue1494_nfb_x_shadow_projection.py::test_w800_three_canonical_x_comes_from_actual_whd_cutting_and_assembly` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-50 | `tests/test_issue1495_receiving_nfb_y_projection.py::test_approved_nominal_box_top_y_maps_to_real_1075_blank` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| NFB-AC-51 | `tests/test_issue1496_nfb_dxf_source.py::test_unsupported_not_silently_treated_as_certified` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-52 | `tests/test_issue1497_w800_three_canonical_cutting.py::test_w800x3_uses_whd_723_blank_x_for_three_real_holes` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-53 | `tests/test_issue1498_nfb_part_readiness.py::test_ready_requires_actual_per_hole_x_y_and_rotation_proof` | BLOCKED_1500_REAL_GUI |
| NFB-AC-54 | `tests/test_issue1499_nfb_persistence.py::test_old_schema_reader_must_not_silently_strip_new_nfb_scope` | EVIDENCE_CANDIDATE_ONLY |
| NFB-AC-55 | `tests/test_issue1496_nfb_source_inventory_report.py::test_complete_per_brand_audit_has_exact_links_and_null_unknown` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| NFB-AC-56 | `tests/test_issue1500_nfb_transactions.py::test_restore_clears_only_nfb_and_undo_restores_without_deleting_legacy` | BLOCKED_1500_REAL_GUI |
| SWT-AC-01 | `tests/test_issue1491_nfb_ui1a.py::test_no_unapproved_geometry_or_persistence_fields` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-02 | `tests/test_issue1504_current_nfb_y_ac10_swt02.py::test_swt_ac02_legacy_nominal_and_unknown_non1100_y_never_guess` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| SWT-AC-03 | `tests/test_issue1504_swt03_nfb05_current_unit_rotation.py::test_swt_ac03_current_csv_units_keep_independent_identity_model_x_and_rotation` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| SWT-AC-04 | `tests/test_issue1504_brand_inheritance_current_csv.py::test_swt_ac04_spoofed_catalog_and_stale_csv_never_relabel_v5_source` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| SWT-AC-05 | `tests/test_issue1492_nfb_real_dxf_preview.py::test_native_arc_circle_bulge_and_aci_preserved_in_real_source_strokes` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-06 | `tests/test_issue1493_nfb_draft_transactions.py::test_q16_replace_model_preserves_x_and_identity_but_unverifies_geometry` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-07 | `tests/test_issue1499_nfb_persistence.py::test_submitted_bay_save_reload_v3_retains_exact_zero_and_independent_copy` | BLOCKED_1500_REAL_GUI |
| SWT-AC-08 | `tests/test_issue1498_nfb_part_readiness.py::test_unknown_missing_and_ambiguous_sources_are_unknown_not_zero` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| SWT-AC-09 | `tests/test_issue1503_deferred_pad_ear_manufacturing.py::test_unapproved_nfb_pad_and_ear_must_not_generate_even_part_only_dxf` | DEFERRED_PRODUCT_EVIDENCE |
| SWT-AC-10 | `tests/test_issue1497_w800_three_canonical_cutting.py::test_w800x3_uses_whd_723_blank_x_for_three_real_holes` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| SWT-AC-11 | `tests/test_issue1502_nfb_base_source_projection.py::test_one_door_nfb_owner_projects_corresponding_base_cutting_and_marks` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| SWT-AC-12 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-13 | `tests/test_issue1491_nfb_ui1a.py::test_brand_change_does_not_silently_swap_csv_filename_even_if_other_brand_same_name` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-14 | `tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-15 | `tests/test_issue1504_ac22_swt15_current_x_persistence.py::test_swt_ac15_quantity_v5_x_zero_none_version_isolation_and_reopen` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| SWT-AC-16 | `tests/test_issue1499_nfb_persistence.py::test_confirmed_x_zero_is_not_missing_and_none_is_not_zero` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-17 | `tests/test_issue1492_nfb_real_dxf_preview.py::test_missing_and_unindexed_dxf_cannot_show_fake_contour` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| SWT-AC-18 | `tests/test_issue1498_nfb_part_readiness.py::test_each_set_bay_version_independent_and_no_cross_scope_ready_cache` | BLOCKED_1500_REAL_GUI |
| SWT-AC-19 | `tests/test_issue1499_nfb_persistence.py::test_derived_flags_not_saved_and_invalid_nfb_fails_without_fallback` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-20 | `tests/test_issue1502_existing_base_nfb_assembly.py::test_two_real_NFB_heights_cannot_share_one_assumed_ear_group` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| SWT-AC-21 | `tests/test_issue1498_nfb_part_readiness.py::test_unknown_missing_and_ambiguous_sources_are_unknown_not_zero` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |
| SWT-AC-22 | `tests/test_issue1503_deferred_pad_ear_manufacturing.py::test_existing_base_ear_slots_are_not_confused_with_unapproved_ear_parts` | DEFERRED_PRODUCT_EVIDENCE |
| SWT-AC-23 | `tests/test_issue1497_w800_three_canonical_cutting.py::test_existing_legacy_circle_is_preserved_exactly_once_in_real_nfb_dxf` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-24 | `tests/test_issue1500_nfb_transactions.py::test_restore_clears_only_nfb_and_undo_restores_without_deleting_legacy` | BLOCKED_1500_REAL_GUI |
| SWT-AC-25 | `tests/test_issue1498_nfb_part_readiness.py::test_unconfigured_preserves_legacy_even_when_nfb_source_absent` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| SWT-AC-26 | `tests/test_issue1500_nfb_transactions.py::test_first_submission_includes_held_plates_in_warning_but_commits_inner_config` | BLOCKED_1500_REAL_GUI |
| SWT-AC-27 | `tests/test_issue1494_nfb_x_shadow_projection.py::test_w800_three_canonical_x_comes_from_actual_whd_cutting_and_assembly` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-28 | `tests/test_issue1495_receiving_nfb_y_projection.py::test_non_1100_upper_y_is_unapproved_not_silently_scaled` | ACCEPTED_AUTOMATED_CURRENT_SCOPE |
| SWT-AC-29 | `tests/test_issue1497_configured_nfb_manufacturing_release.py::test_legacy_same_physical_hole_fails_no_duplicate_cutting` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-30 | `tests/test_issue1498_nfb_part_readiness.py::test_wrong_approved_inner_source_or_wrong_part_is_not_a_manufacturing_capability` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-31 | `tests/test_issue1499_nfb_persistence.py::test_old_schema_reader_must_not_silently_strip_new_nfb_scope` | EVIDENCE_CANDIDATE_ONLY |
| SWT-AC-32 | `tests/test_issue1496_index_color_evidence.py::test_unique_model_links_keep_missing_unknown_distinct_from_real_zero` | SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC |


- **NFB-AC-25（2026-10-22）**：以原批准 W600／750／800 名義相對孔距驗證不同廠牌型號 `NEEDS_RESELECTION` 仍保留 pitch；新增 `preview.layers[].slots[].verification`，絕對 X、collision、bounds 各別 `UNVERIFIED`，不以缺值代替通過。Q16 保留手動 0 並棄過期 datum；未知 W×N 不置中；常規 NFB MFG-1 未獲放行。專項測試 `tests/test_issue1504_ac25_reselection_nominal_x.py` 列入產品 CI；此項當期自動化簽核僅在 exact SHA 全綠合入 GitHub `localX` 後成立，不等於人工 GUI 或正式製造放行。

---
whd_doc_role: CURRENT
whd_contract: receiving-fixed-ear-brand-maximum-z-20261026
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 受電箱固定片 Z：由廠牌 NFB 最大深度一次定位（2026-10-26）

> **使用者最新規則**：固定片以該廠牌最深 NFB 為主，Z 位置算出後，不管幾層、哪一種 NFB 都不變。本文件取代 #1502／#1503 文件中「固定片跟著各層或選用型號深度移動」的敘述。

## 唯一深度來源與身分

- 讀取**目前 Set／Bay 所使用廠牌**的整份 `基準檔/開孔/NFB/數值規格/<廠牌>/NFB數值規格.csv`，取所有**已填有效 NFB深_mm**數值的最大值 `D_brand_max`；**不得**用已選型號最大值、每層最大值、開關索引尾碼或另一廠牌深度取代。
- 既有 CSV 有缺漏深度時，其缺漏不得當 0／猜測；整表無有效深度就拒絕生成固定片定位。所謂最大值僅涵蓋已填的資料，缺漏規格未完成不得宣稱全面驗證。
- 單一固定片定位群不可混用不同廠牌的 Z 權威；品牌混用時停止固定片 Z 的製造驗證，待使用者確認跨品牌共同基準策略。
- 士林目前已填數值最大 **107 mm**（2P400／3P400SN 等）；士林 2P125SN=68、3P125SN=72，但即使只選這兩種，固定片深度仍使用 **107 mm**。

## 物理面與世界座標（+Z 朝外、往箱內為負）

```text
inner_skin_z   = 真實內門朝箱內折後實體皮面 Z
base_t         = 該底板來源 T
ear_t          = 該固定片來源 T（目前新版固定片 T2）
brand_max      = max(所屬廠牌全部已知的 NFB深_mm)
ear_contact_z  = inner_skin_z - brand_max - base_t
ear_back_z     = ear_contact_z - ear_t
```

世界 Z 要由真正內門／底板實體 skin 對齊，不能誤用折後包絡中心、外門偏移 80 或板中線。固定片接觸面和底板背面**必須零間隙**，而零間隙是另外必須檢驗的事實，非算式宣告即通過。

## 絕對不變量

1. **同一 Set／Bay、同一廠牌、內門實體 Z／板厚／箱體基準不變：** 不論 1 層、2 層、每層多顆，所有左右固定片的**接觸 Z 相等**。
2. 同廠牌選用 NFB 從 68 換 72、107，或調整單顆 X／Y、旋轉及同層數量，**不可改固定片 Z**。各層 Y 可不同；固定片 X 仍沿實際左／右側板內面。
3. 若**廠牌或內門真實 Z／板厚／箱體實體基準**變更，須重新計算該新條件的唯一 Z，不可偷用舊廠牌快取。CAD/GUI 的畫面變更不等於物理基準改變。
4. 底板實體仍可因使用者選的型號、來源折彎方案與 PAD 產生不同 Z／工作面，但**不得以移動固定片補償型號深差**。
5. 若某層實體底板背面仍落在該層所選型號深度，而與共同固定片 Z 不相等，將此接觸標為 **未驗證／未可製造**。後續須確認符合來源規格的 PAD／折板方案及真實 2D／3D 零間隙，不得假設浮動底板能直接焊接或出製造圖。

## 固定片 X/Y 與當前來源幾何

- 一層一片底板、左右各一片固定片；雙層各有獨立左／右固定片，**共用相同 Z**。
- 底板 X=0；每層的 Y 取內門該層實際 NFB 群世界 Y，NFB 自己的 X 只移螺絲孔。
- 當前 `固定片.dxf` 大片來源為 **T2、256×105、孔心距底邊84、BEND23**；非歷史 T3／86。
- `pitchX = W - 2*(sideT + 63)`；W800／側板 T2 時橫向孔距 670 mm、X±335。左右平底板長向孔距 210；中間雙折 140。固定片 Z 規則**不能**用來擅自決定左／中／右板型。
- 焊接與側板 `MARKING` 應依共同固定片接觸 Z，於側板真實 skin 投影 2D；未通過折向／接觸／DXF round-trip 的圖不可放行。

## 驗收

- 士林單層雙 2P125SN：`D_brand_max=107`，固定片接觸 Z 不得以選取深度 68 計算。
- 士林雙層 2P125SN 與 3P125SN：**四片固定片接觸 Z 相同**；各層可有不同 Y。
- 士林單層或雙層改用 2P400 深 107：固定片 Z 與只選 125SN 時**一致**。
- 混廠牌、缺原始深度／內門實體基準、零間隙未驗證：禁止聲稱製造合格；舊圖只可預覽。
- 必須核對當前 `localX` 3D 裝配、左右側板 MARKING、孔對、原圖再開、回歸測試；本文件本身**不是製造放行**。

## 程式與沿用文件

- `ae_engine/receiving_nfb_numeric_catalog.py::brand_max_depth_mm`
- `ae_engine/receiving_tier_ear_z_targets.py::committed_receiving_ear_brand_max_depth_mm`
- `ae_engine/receiving_tier_ear_z_targets.py::resolve_receiving_tier_ear_contact_targets`
- `docs/manufacturing/receiving-fixed-plate-source-20261018.md`
- `docs/manufacturing/receiving-nfb-depth-physical-faces.md`（過時固定片 Z 計算已標記由本規則取代）
- `docs/manufacturing/receiving-large-weld-ear.md`（歷史 T3，不得恢復為 CURRENT）

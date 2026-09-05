# 03 — Part Topology Map

- Door → FourSideFlange + rectangular corner policy (`side fold - T`)
- Indicator Box → FourSideFlange；與 Door 同類 thickness-dependent corner rule
- Base Plate → FourSideFlange；full bend-depth corner policy
- End Cap/Tail → FourSideFlange family + top two-fold chain + Vault assembly insertion relief
- Box Body → StripFoldChain + no corner relief
- Stretched Door → 與 Door 共用 structural builder；baseline 只提供 secondary features
- Stretched Box Body → 與 Box Body 共用 StripFoldChain/bend anchors
- Stretched End Cap → 與 End Cap 共用 authoritative structure，baseline mapper 直接產 DrawingScene

新零件先判斷 topology，再判斷既有 policy 是否可用。新名稱/尺寸不是新增 rule 的理由。

## 2026-08-17 Unknown / CornerType

`未知類型` 不是新的硬編碼零件 topology。它重用現有可用 topology，但 Corner relief 由手動 `CornerType` policy 提供；不載入任何既有 baseline DXF 作為製造規則。

既有金庫型零件仍固定使用自己的 CornerType mapping，不接受未知類型的手動選擇狀態。

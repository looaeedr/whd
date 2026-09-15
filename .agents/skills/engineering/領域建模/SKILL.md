---
name: 領域建模
description: 建立並持續磨利專案 domain model。當需要定義/修正 codebase terminology、寫或更新 CONTEXT.md、釐清共享詞義，或記錄真正值得留下的 ADR 時使用；純讀 glossary 不等於啟動本 Skill。
---

# 領域建模

設計過程中主動建立並修正專案的 domain model：挑戰模糊詞、用 edge-case scenario 壓測定義，並在概念真正確認時立即落到 glossary / ADR。

純粹為了使用既有詞彙而讀 `CONTEXT.md` 不算領域建模；只有正在**改變模型**時才啟動本 Skill。

## File structure

單一 context 常見結構：

```text
/
├── CONTEXT.md
├── docs/
│   └── adr/
└── src/
```

若 root 有 `CONTEXT-MAP.md`，代表 repository 有多個 contexts；依 map 找各 context 的 `CONTEXT.md` 與 context-specific ADR，system-wide decision 才放共用 `docs/adr/`。

檔案 lazy-create：沒有內容就不先建空檔。第一個 canonical term settle 時才建立 `CONTEXT.md`；第一個符合 ADR gate 的 decision 出現時才建立 `docs/adr/`。

## During the session

### Challenge against the glossary

使用者的詞若與 existing `CONTEXT.md` 衝突，立即指出兩個定義，不可悄悄選一個。例如 glossary 的 cancellation 是 X，但本輪似乎用成 Y，就要把衝突交給使用者決定。

### Sharpen fuzzy language

遇到 overloaded/fuzzy term，提出精確 canonical term，並說明不同概念為何不能共用同一名稱。

### Discuss concrete scenarios

用具體 scenario 與 edge case 壓測 domain relationship，逼出 boundary/invariant。scenario 是用來驗定義，不是自行新增產品規則。

### Cross-reference with code

使用者描述的 domain behavior 與 current code 衝突時，指出衝突並區分：

- user-confirmed domain rule；
- current implementation；
- current test behavior。

current code/test 不能因為存在就自動成為 domain authority。

### Update CONTEXT.md inline

term 一旦 settle，立即依 [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md) 更新 `CONTEXT.md`，不要等 session 結束後憑記憶 batch 補寫。

`CONTEXT.md` 只放 domain glossary：不得塞 implementation detail、spec、temporary probe、run id、測試紀錄或工作清單。

### Offer ADRs sparingly

只有以下三項都成立才建立/建議 ADR：

1. **Hard to reverse**：日後改變的成本明顯。
2. **Surprising without context**：未來讀者沒有背景會問「為什麼這樣做？」
3. **Real trade-off**：確實有可行 alternatives，並因具體理由選了其中之一。

任一不成立就跳過。需要 ADR 時依 [ADR-FORMAT.md](./ADR-FORMAT.md)。

## Authority / durable correction

- 最新使用者已確認 domain definition 高於 stale glossary/ADR；若它推翻舊規則，舊內容要同步標 superseded/replaced，而不是留下兩套 current truth。
- implementation detail 不得進 glossary；implementation decision 若真符合 ADR gate 才進 ADR。
- unresolved term 保持 OPEN，不用暫時猜測填滿文件。
- repository write 後 re-read，確認 durable doc 真的落盤。

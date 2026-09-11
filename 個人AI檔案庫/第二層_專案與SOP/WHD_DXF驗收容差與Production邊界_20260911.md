# WHD DXF 驗收容差與 Production 邊界（2026-09-11）

## 事件
Issue #104 的 Receiving Door DXF reopen 原本固定回報 `CUTTING_MISMATCH`，但 forensic 證明 scene 與重新開啟 DXF 的 CUTTING LWPOLYLINE / LINE 座標逐點一致，serializer 沒有改變幾何。差異來自 verifier 與 canonical Final Material 對微小浮點端點 gap 的重建語意不同。

## 永久規則
1. Validation 只能判定對錯，不得把 symmetric-difference 面積、probe 數字、測試 epsilon 或其他驗證結果反灌 production 幾何。
2. DXF acceptance 必須真的把 `.dxf` 寫到磁碟，再用 `ezdxf.readfile()` 從 bytes 重開；不能拿 scene 或 serializer 回傳值冒充 reopen。
3. Production canonical geometry 的製造容差與 DXF verifier 的數值等價容差是不同 authority。Verifier 不得直接拿 production 的 0.05–0.25 mm broad snap 來治癒 DXF gap。
4. Verifier 只能在自己的 `coordinate_tolerance` 內重接 LINE/LWPOLYLINE endpoints。微小浮點 gap（例如遠小於 `1e-6`）可視為序列化等價；超過 verifier tolerance 的真實 gap 必須 FAIL，即使 production helper 的製造容差會把它接起來。
5. 修 verifier 假紅燈時，production `cutting_material.py`、Door 幾何、DXF serializer 不得因 validation 數字而改動。
6. Regression 必須同時包含正例與反例：微小 gap PASS；大於 verifier tolerance 的 gap FAIL；並保留真實 Receiving 上門/下門 DXF roundtrip。
7. 合併前仍要跑完整 headless、Xvfb、`config.ini` invariant、tracked-file drift audit；temporary QA workflow 用完必須刪除。

## Issue #104 authority
- 問題分類：DXF acceptance reconstruction false negative。
- 兩片 Receiving Door 的 serializer 座標 parity 已證明完全一致。
- `2220.64823 mm²` 只可作 forensic evidence，不是 production 計算來源。
- 正確修正位置：`ae_engine/dxf_acceptance.py` 的 verifier-local reconstruction/tolerance seam。

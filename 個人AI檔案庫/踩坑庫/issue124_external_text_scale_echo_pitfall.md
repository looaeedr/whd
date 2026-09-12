# Issue124 external text-scale anti-echo

## 症狀

Main GUI 明確以 `persist=False` 把文字倍率同步到已開啟的 Fold Designer；Designer runtime 的文字倍率確實更新，但 `config.ini` 仍被改寫。這不是 persistence caller 自己直接忽略 `persist=False`，而是 child Tk trace 把同步結果 echo 回 host，host callback 再走正常持久化路徑。

## 真正資料流

`Main persist=False` → `designer.apply_external_settings()` → `_phase6_external_apply_guard=True` → Designer text-scale trace → `_phase6_apply_ui_text_size()` → `_ui_text_size_change_callback` echo 回 Main → Main callback 以正常持久化語意寫入 `config.ini`。

問題點是 text-scale callback seam 漏看既有 `_phase6_external_apply_guard`；external apply guard 本來就代表「外部同步期間 child 不得反向 publish／persist」。

## 正確修法

在 **callback boundary** 套用既有 `_phase6_external_apply_guard`：

- Designer runtime sync 仍必須完成；
- Tk/UI state 仍照新文字倍率更新；
- 只抑制 external apply 期間的 echo callback；
- 不新增第二個 persistence authority；
- 不停掉 trace、不跳過 runtime update、不把驗證結果回灌 production。

## 不變量

`persist=False` 必須同時滿足：

1. child/Designer runtime 狀態已同步；
2. `config.ini` byte-for-byte 不變；
3. canonical geometry / topology / manufacturing / DXF authority 不受影響。

## 防錯規則

任何 host → child 的 external batch apply，只要已設 `_phase6_external_apply_guard`，新增的 trace/callback 路徑都必須檢查是否會繞過 guard 反向回 host。不能只看「外層 caller 傳了 persist=False」就認定不會寫檔；必須驗整條 callback chain 與 persisted bytes。

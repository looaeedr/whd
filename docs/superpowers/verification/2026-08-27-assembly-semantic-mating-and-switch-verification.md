# 2026-08-27 組合體語意接合與板件切換驗證

## 目的
驗證組合體不再以視覺旋轉猜接合，而是沿用既有 `組合方式 -> CornerType -> resolved Fold Profile` 語意；同時驗證第一次進組合體後可正常切回箱身單件編輯。

## Source of Truth
- `phase6_fold_profiles.py`：由 `組合方式` 解析 EndCap X/Y Fold Profile topology。
- `ae_engine/assembly_geometry.py::place_endcap_against_box_body()`：唯一 assembly world mating transform。
- `fold_designer_bridge.py::_fix11_activate_part()`：組合體與實際板件導航切換。

## 機械語意
- EndCap local `z=0`：**板厚中心面**；2026-08-28 起實體接觸面改由 T 厚 inner skin 擁有，詳見 `2026-08-28-endcap-physical-sheet-assembly-verification.md`。
- EndCap local `+z`：已解析 Fold Profile 的實際折邊方向。
- Head：`+z` 映射向下、折邊進箱；2026-08-28 起 mid-surface `z=0` 向箱外偏移 T/2，使 physical-sheet inner skin 貼 box-body world max-Y。
- Tail：保持 authoritative native X/Y orientation（不得二次鏡射 local Y）；`+z` 映射向上、折邊進箱。實體 inner skin 貼 box-body world min-Y。
- `INSERT / INSERT_OVERLAY`：X folded (`yl1/endcap_w_core/yr1`)。
- `OVERLAY`：X flat (`endcap_w_flat`)，不得虛構左右 X 折邊。

## TDD RED 證據
1. Tail 舊 transform 使 local `+z=12` 從 box bottom `-40` 跑到 `-52`（箱外），新需求預期 `-28`（箱內）；同時 X 被左右反轉。
2. 真 Tk 模擬 Menu radiobutton 先 `part_var.set("箱身")` 後呼叫 `activate_part("box_body")`，舊程式 mode 雖改 `single`，但 `fold_editor_host.winfo_manager()==""`，證明 early-return 漏掉實際切換。

## GREEN 驗證
- Tail 合成非對稱 mesh：X 保持、local Y 保持 native orientation、local +Z 往箱內；assembly 不得二次上下鏡射。
- Head/Tail 的 physical-sheet **inner skin** 精確貼箱身上/下 mating plane；mid-surface `z=0` 向箱外偏移 T/2；positive-Z folds 皆在箱身內。
- 真 `build_endcap_xy_profiles()`：對 `INSERT / OVERLAY / INSERT_OVERLAY` 三種組合方式逐一折成 mesh；Head world-Y 最大值等於 body max-Y，Tail world-Y 最小值等於 body min-Y，且其餘折邊不超出箱身高度。
- 真 Tk `組合體 -> 箱身`：mode=`single`、`part_var=箱身`、Fold Editor 重新顯示。

## 禁止事項
- 禁止在 viewer 另做 Tail 視覺鏡射而 collision 沿用舊 transform。
- 禁止 assembly transform 再複製 `INSERT/OVERLAY/INSERT_OVERLAY` 的 topology 判斷；它必須消費 resolver 已產生的 Fold Profile。
- 禁止用 EndCap 整體 bbox 中心取代 local `z=0` mid-surface datum；實體 mating datum 是由該中心面 + T/2 推導出的 inner skin。

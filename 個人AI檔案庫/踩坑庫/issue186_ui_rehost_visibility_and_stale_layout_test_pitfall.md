---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #186 UI rehost：critical control 可見性與 stale layout test 踩坑

<!-- ISSUE186_UI_REHOST_VISIBILITY_PITFALL -->

## 症狀

UI layout/rehost 完成後，structural test 可能仍顯示 widget/container 都存在，但 operator 實際看不到或捲動後失去 critical control。#186 的案例是 #163 將整個 left workspace 放入單一 scroll owner 後，Structure Tree 會跟 lower inputs 一起被捲走；一般 1400×900 初始畫面正常，但 760×420 + 1.4 text scale 捲到底時曾只剩約 37px 可見。

## 根因分類

1. `widget exists` / parent 正確 / container 正確，不代表 real-GUI mapped/reachable。
2. UI rehost 後必須驗 resize、scroll、text scale、mapped/viewable 與 interaction。
3. 若新 layout 已正式接受，舊 regression test 仍要求舊 parent/row ownership，該 FAIL 是 stale/superseded test authority，不是 production regression。

## 正確處理

- Critical selector / Structure Tree / primary action 必須用 real Tk/Xvfb 驗：`winfo_ismapped()` / `winfo_viewable()`、viewport overlap/reachability、實際 selection/action。
- 至少涵蓋 text scale 1.0 / 1.2 / 1.4，並驗 constrained window + scroll-to-bottom。
- 保留 single authoritative navigation surface，不新增 duplicate selector 掩蓋根因。
- 若 current accepted contract 與舊 test 衝突：先找最新 authority，更新 stale test；不要把 production 搬回舊 layout 只為 GREEN。
- QA FAIL 要分成 production regression / stale test / harness false failure。validation 只判 correctness，不得反向成為 production calculation 或 UI authority。

## #186 實例 authority

#163 current layout contract：top 只留 File + Corner Data；visual controls / fullscreen / transaction / global controls 在 right control region。任何仍硬鎖它們必須在 `top_command_row` 的舊測試都已被 #163 supersede。

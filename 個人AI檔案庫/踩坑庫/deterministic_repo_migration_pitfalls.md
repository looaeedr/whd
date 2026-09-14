# Deterministic repo migration 踩坑庫

## Validator 不是 authority

Migration 的 desired state 必須來自已釘住 SHA 的 authoritative matrix/registry。Validator 只能判定結果是否符合 authority；不得把 validator 的 expected value、錯誤訊息、snapshot 或測試資料反向灌回 migration，否則 validation 會偷變成第二套 authority。

固定防錯：先讀 authority、列完整 governed scope、再產生 mapping；遇到 duplicate mapping、missing mapping、unknown role、nonexistent target 一律 fail closed，不靠猜測補值。

## Idempotence 不能只看「第二次也 PASS」

相同 repository state、**same authority input** 下做 **second execution**，必須得到 **zero diff**。若第二次還會重排、重寫 metadata、加入時間戳、改換行或改內容，即使 validator PASS 也不是 deterministic migration。

需要保留原資料時，依契約做 byte-for-byte 驗證；不要用「看起來一樣」代替。

## Scope inventory 先於 mutation

如果邊掃邊改，就無法證明 governed inventory 完整，也容易漏掉 role/path。先固定 inventory count 與 mapping，再一次套用；任何 changed-file set 超出計畫都由 drift audit 擋下。

## 不跨越 domain authority

這個流程不能拿來修 production geometry、DXF 或 manufacturing truth。若 migration 發現 domain truth 有問題，停止並交給該 domain 的 authority/Skill；不要藉 migration 順手改製造資料。

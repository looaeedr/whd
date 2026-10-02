---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #188 Dark Theme Runtime Pitfall

<!-- ISSUE188_DARK_THEME_RUNTIME_PITFALL -->

## 事故

#188 把 3D Primary Workspace 改成 WHD dark engineering theme 時，source-level 顏色替換並不足以保證 runtime 可讀。實際風險集中在 shared theme ownership、classic Tk、Matplotlib clear/re-render、drawing-surface exception 與 text-scale persistence 邊界。

## 永久規則

- `shared theme` 只能有一個 canonical token/style owner；2D、3D、settings 與 Matplotlib consumer 不得各複製一套 palette truth。
- `ttk.Style` 不會自動套到 classic `tk.Menu`；Menu 的 normal/active/disabled foreground/background 必須明確處理。
- Matplotlib 的 `ax.clear()` 會清掉 axes presentation state；theme 必須在每次 render refresh 後重新套用，不能只在 Figure/axes constructor 套一次。
- generic 3D canvas 可使用 shared dark canvas token，但已驗收的 `Corner Data` / unfold drawing viewport 仍固定 `#000000`；禁止全域 canvas replace 破壞這個例外。
- 暗色化不等於全部灰化。尺寸、目前 selection、warning/error 與主要操作文字必須維持足夠 contrast 與 semantic role。
- `text scale 1.0 / 1.2 / 1.4` 都是正式 acceptance surface；要驗 clipping、reachability、Treeview/menu/Entry state 與 scroll，而不是只驗 source constant。
- visual acceptance 優先使用 `real Tk/Xvfb` effective widget state；有 screenshot/pixel capture 才宣告 pixel evidence，沒有就不得假裝看過畫面。
- theme/text-scale callback 必須保留外部同步 `persist=False` 邊界；驗收前後 `config.ini` 應 byte/hash invariant，避免 presentation refresh trace-echo 成 persistence mutation。
- 這整套規則是 `presentation-only`；**不得成為 manufacturing / geometry / DXF authority**，也不得藉 theme apply/re-render 改 Save→Reload、PartRenderData、physical-part identity 或 workspace state。

## Machine guard

- `.agents/skills/engineering/UI設計與去AI味/SKILL.md` → `ISSUE188_SHARED_DARK_THEME_RUNTIME`
- `tests/process/test_issue188_durable_theme_contract.py`
- #188 real Tk/Xvfb runtime visual QA 與 inherited matrix

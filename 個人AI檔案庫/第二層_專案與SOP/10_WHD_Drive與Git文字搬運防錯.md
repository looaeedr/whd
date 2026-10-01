# WHD Drive 與 Git 文字搬運防錯

- whd_doc_role: REFERENCE
- canonical owner: `.agents/skills/engineering/root-local-first/SKILL.md`
- contract: `DRIVE_RAW_TEXT_TRANSPORT_HARD_GATE_V1`

## 問題

Drive / connector 讀 plain-text raw file 時，一般 `content` 欄位可能為空，但 raw payload / raw size 實際非空。若把空的 text projection直接寫進 Git，會把正常來源誤寫成空檔。

## CURRENT 防錯

- Node.js runtime 的 base64 解碼固定使用：
  ```js
  Buffer.from(base64_string, 'base64').toString('utf-8')
  ```
- 不假設 `atob` 或 `TextDecoder` 一定存在。
- 非 Node / 無 `Buffer` 時，改走 raw `file_uri`、materialize、download 或 mounted file；不自行發明 decoder。
- source raw size 非零時，decoded/materialized result 不得為空。
- Git write 後必須對 frozen root source做 exact-content / SHA-256 readback。
- 非空 source 若變成 Git empty blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`，判定 transport corruption，禁止 PR／merge。
- 恢復必須由 verified frozen root/raw bytes重灌 exact file，不能在 branch 上猜內容。

本文件只記 transport pitfall；CURRENT authority 仍是 `root-local-first` Skill。

# WHD Drive 與 Git 文字搬運防錯

- whd_doc_role: REFERENCE
- canonical owner: `.agents/skills/engineering/root-local-first/SKILL.md`
- contract: `DRIVE_RAW_TEXT_TRANSPORT_HARD_GATE_V1`

Drive raw/plain-text 若提供 base64，Node.js runtime 固定用：

```js
Buffer.from(base64_string, 'base64').toString('utf-8')
```

不得假設 `atob` / `TextDecoder` 存在；非空 raw source 解碼後不得為空。若 Git work branch 被誤寫成 empty blob，必須從 verified raw/root source 覆蓋回原分支後再繼續。

本文件只記 transport pitfall；CURRENT authority 仍是 `root-local-first` Skill。

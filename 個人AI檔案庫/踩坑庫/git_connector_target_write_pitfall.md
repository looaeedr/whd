---
whd_doc_role: REFERENCE
whd_contract: git-connector-target-write-pitfall
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# GitHub Connector 誤寫 production target 踩坑


## 單次 mutation rejection 的分類規則

- 單次 connector/runtime mutation rejection 先標 `RETRYABLE_UNCLASSIFIED`，不得直接寫成 permanent `CAPABILITY_BLOCKED`。
- 升級 blocker 前必須 fresh-read：authenticated repo permission、base/target existence、branch existence、matching ruleset/branch protection、exact connector action contract。
- 建新 branch 用 `create_branch(base_sha)`；`update_ref(force=false)` 只移動既有 branch。
- 只有所有合法 transport 都有 fresh durable evidence 證明 unavailable/forbidden，才可宣告 permanent capability blocker。
- recovery 不得把一次被拒的 mutation 當停止點；必須 fresh retry 或切換另一條仍合法的 executable leaf。

# Design It Twice

當使用者要比較一個 deepening candidate 的多種 interface 設計時，不要停在第一個合理答案。用至少 3 個**刻意不同的設計約束**產生方案，再以 depth、locality、seam placement 比較。

本文件使用 [SKILL.md](SKILL.md) 的正式詞彙：**module、interface、seam、adapter、leverage、locality**。

## 能力邊界

先判斷目前是否真的有獨立 Subagent Runtime：

- **有真正 Subagent**：可平行產生 3+ 個方案，每個 agent 使用不同 constraint，並保留各自獨立輸出。
- **沒有真正 Subagent**：由同一執行者 **依序 / inline** 產生 3+ 個方案；每個方案開始前重新套用不同 constraint，不讀取/修飾上一案作為起點，盡量降低 anchoring。
- inline 方案不等於 independent-agent sample；呈現時明確說明是同一執行者的多方案探索。
- **不得假裝**已 spawn sub-agents、不得等待不存在的 agent 回報，也不得因沒有 Subagent 就跳過 Design It Twice。

## Process

### 1. Frame the problem space

先整理 chosen candidate 的共同限制：

- 新 interface 必須滿足的 constraints；
- dependencies 與其類別（見 [DEEPENING.md](DEEPENING.md)）；
- current caller/use cases；
- 哪些 implementation 應收進 seam 後方；
- 一個只用來具體化限制、**不是 proposal** 的 rough code sketch。

如果目前有真的平行 agent，可以在它們工作時讓使用者閱讀 problem framing；沒有則直接進入下一步，不製造假的背景等待。

### 2. 產生 3+ 個刻意不同方案

至少使用以下三種 constraint：

1. **最小 interface**：1–3 個 entry points，最大化 leverage / entry point。
2. **最大彈性**：支援較多 use cases / extension，但必須說明增加的 interface cost。
3. **最常見 caller 優先**：讓 default path 最簡單，其他情境退到較深 implementation。
4. 若有 cross-seam dependency，再加 **ports & adapters** 方案。

每個方案都要用 `CONTEXT.md` 的 domain vocabulary 與本 Skill 的 architecture vocabulary，並輸出：

1. Interface：types/methods/params + invariants/order/error modes。
2. Usage example。
3. Implementation hides behind the seam。
4. Dependency strategy / adapters。
5. Trade-offs：leverage 高在哪、薄在哪、locality 如何改變。

若使用 Subagent，每個 agent 收到獨立 technical brief；若 inline，依序用相同 technical brief + 不同 constraint，避免只是同一設計換名字。

### 3. Present and compare

逐案呈現，接著以 prose 比較：

- **Depth**：interface 每增加一單位知識，caller 得到多少 capability。
- **Locality**：未來 change/bug/knowledge 是否集中。
- **Seam placement**：變動點是否真的被隔離。
- **Adapter reality**：是否有至少兩個真變體支持該 seam，而不是 speculative abstraction。

最後給明確 recommendation；若 hybrid 更好，說清楚取哪幾個元素與原因。不要只丟 menu 給使用者自己猜。

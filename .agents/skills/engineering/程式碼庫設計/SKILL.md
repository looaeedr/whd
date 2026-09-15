---
name: 程式碼庫設計
description: 深模組設計的共用 vocabulary 與 interface/seam 原則。當要改善 module interface、找 deepening opportunity、決定 seam、提升 testability/AI navigability，或其他 Skill 需要 module/interface/depth/seam/adapter/leverage/locality 詞彙時使用。
---

# 程式碼庫設計

設計 **deep modules**：以小 interface 隱藏大量 implementation，放在乾淨 seam 上，並能透過同一 interface 測試。目標是 caller 的 **leverage**、maintainer 的 **locality** 與穩定的 test surface。

## Glossary

下列術語是本 Skill 的 canonical architecture vocabulary；不要隨意用近義詞取代而改變含義。

**Module**：任何同時有 interface + implementation 的東西；可以是 function、class、package 或跨 tier slice。

**Interface**：caller 正確使用 module 必須知道的全部資訊：type signature、invariants、ordering constraints、error modes、required config、performance characteristics。不是只指語言的 `interface` keyword 或 method signature。

**Implementation**：module interface 背後的 code。與 **Adapter** 不同：implementation 描述內部內容；adapter 描述它在 seam 上扮演的角色。

**Depth**：interface 的 leverage。caller 每學一單位 interface 能得到多少 capability。大量行為藏在小 interface 後方 = deep；interface 幾乎和 implementation 一樣複雜 = shallow。

**Seam**（Michael Feathers）：可以不在該位置修改程式就替換 behavior 的位置；module interface 所在之處。seam placement 與 interface shape 是兩個不同 design decisions。

**Adapter**：在 seam 上滿足 interface 的 concrete participant，描述 role 而非 substance。

**Leverage**：caller 從 depth 得到的回報；一份 interface knowledge 可驅動多個 capabilities/call sites/tests。

**Locality**：maintainer 的回報；change、bug、knowledge、verification 集中在少數地方，而非散落到 callers。

## Deep vs shallow

```text
Deep module
┌─────────────────────┐
│   Small Interface   │
├─────────────────────┤
│                     │
│ Deep Implementation │
│                     │
└─────────────────────┘
```

```text
Shallow module
┌─────────────────────────────────┐
│        Large Interface          │
├─────────────────────────────────┤
│       Thin Implementation       │
└─────────────────────────────────┘
```

設計 interface 時問：

- methods 能不能更少？
- params 能不能更簡單？
- caller 不需要知道的 complexity 能不能藏進 module？

## Principles

- **Depth 是 interface 的性質，不是 implementation line count。** deep module 內部仍可由小而可替換的 parts 組成，但它們不一定要暴露成 external interface。
- **Deletion test。** 想像刪掉 module：complexity 若消失，它可能只是 pass-through；complexity 若散回 N 個 callers，表示 module 正在集中 complexity。
- **Interface 是 test surface。** caller 與 tests 應穿過同一 seam。若測試總想鑽過 interface 檢查內部，module shape 可能不對。
- **One adapter = hypothetical seam; two adapters = real seam。** 不為 speculative variability 先造抽象層。
- **Internal seam 與 external seam 分開。** implementation 內可有 private testing seams，不等於 caller 必須學會它們。

## Designing for testability

1. **Accept dependencies, don't create them.** 需要替換的 dependency 由 interface 接收，不在 function 深處硬 new concrete provider。
2. **Return results where possible.** 能回傳 result 就不要只靠不可觀察 side effect。
3. **Small surface area.** methods/params 越少，caller setup 與 test matrix 越小。
4. **Test behavior, not implementation wiring.** test 應能在 refactor 後仍描述同一 capability。

## Relationships

- Module 有一個對 caller 呈現的 Interface。
- Depth 是 Module 相對 Interface 的 leverage。
- Seam 是 Interface 存在的位置。
- Adapter 在 Seam 上滿足 Interface。
- Depth 產生 caller 的 Leverage 與 maintainer 的 Locality。

## Rejected framings

- 用 implementation-lines / interface-lines 比例定義 depth：會鼓勵灌水 implementation。
- 把 Interface 只理解成 TypeScript `interface` 或 public methods：太窄。
- 用泛稱 `boundary` 代替 seam：容易與 DDD bounded context 混淆。

## Going deeper

- 深化 cluster / dependency categories / seam discipline：讀 [DEEPENING.md](DEEPENING.md)。
- 比較多種 interface 設計：讀 [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md)。該流程必須先偵測是否有真正 Subagent；沒有時使用 inline/sequential 多方案 fallback，不得假裝平行 agent。

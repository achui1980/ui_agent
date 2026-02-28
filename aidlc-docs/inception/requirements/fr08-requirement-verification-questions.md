# FR-08 需求验证问题 — 动态测试数据生成

> **说明**: 请在每个问题的 `[Answer]:` 标签后填写你的回答。对于选择题，填写选项字母即可。

---

## 意图分析摘要

- **请求类型**: 新功能
- **范围**: 多组件（新增 Agent、修改 Flow 逻辑、新增 CLI 命令）
- **复杂度**: 中等偏高
- **背景**: 当前系统要求用户在访问页面前准备好测试数据（JSON/YAML/CSV 文件），在未知表单的场景下不可行。需要 agent 在看到页面后自动生成合理的测试数据。

---

## 问题 1: 架构方案

**背景**: 我们已在对话中讨论了两种方案：A) 新增第 5 个 Data Generator Agent，在 Page Analyzer 和 Field Mapper 之间；B) 扩展 Field Mapper 承担数据生成职责。你已选择方案 A。

**问题**: 确认你的选择：在 Page Analyzer 和 Field Mapper 之间新增一个独立的 Data Generator Agent？

- A) 是，新增独立的 Data Generator Agent（已确认）
- B) 改为扩展 Field Mapper
- C) 其他

[Answer]:A

---

## 问题 2: CLI 入口设计

**背景**: 动态生成模式不需要测试数据文件，只需要 URL。我们讨论了两种 CLI 方案。

**问题**: 确认 CLI 设计：新增独立的 `ui-agent generate <url>` 子命令？

- A) 是，新增 `ui-agent generate <url>` 子命令（已确认）
- B) 改为在 `ui-agent run` 上加 `--generate` 标志
- C) 两种都支持
- D) 其他

[Answer]:A

---

## 问题 3: Persona（人物画像）配置

**背景**: 多步表单需要跨页面数据一致性（如第 1 页填的姓名在第 3 页也要一致）。Persona 机制用于维护这种一致性。

**问题**: 确认 Persona 策略：全自动生成，无需用户提供任何配置？

- A) 是，全自动生成，零配置（已确认）
- B) 改为支持可选的 persona 提示文件
- C) 其他

[Answer]:A

---

## 问题 4: 数据生成的领域适配

**背景**: Data Generator Agent 需要理解表单的业务领域才能生成合理数据。例如 Medicare 表单需要生成符合 Medicare 资格的年龄（≥65 岁）、有效的 Medicare ID 格式等。

**问题**: Data Generator 应该如何处理领域特定的数据生成？

- A) 依靠 LLM 的通用知识自动推断领域和约束（如看到 "Medicare" 字样就知道要生成 65+ 的年龄）
- B) 支持用户通过命令行参数传入领域提示（如 `--domain "Medicare enrollment"`）
- C) 在 Agent 的 backstory 中预设多个常见领域的知识（保险、医疗、金融等）
- D) 其他

[Answer]:A

---

## 问题 5: 与现有 static 模式的兼容

**背景**: 现有的 `ui-agent run` 命令使用预先准备的测试数据文件。新增 dynamic 模式不应破坏这个路径。

**问题**: 对于 `page_crew.py` 中的 Crew 构建，你希望怎么处理两种模式？

- A) 条件分支：`generation_mode == "dynamic"` 时构建 5-agent crew，否则保持 4-agent crew
- B) 始终构建 5-agent crew，但 Data Generator 在 static 模式下是 pass-through（直接传递已有数据）
- C) 其他

[Answer]:A

---

## 问题 6: 生成数据的格式约束

**背景**: 不同的表单字段有不同的格式要求，如日期（MM/DD/YYYY vs YYYY-MM-DD）、电话号码（带不带区号）、邮编（5 位 vs 9 位）。

**问题**: Data Generator 应该如何确定生成数据的格式？

- A) 从页面分析结果中推断（placeholder、validation pattern、label 提示）
- B) 生成通用格式，由 Field Mapper 负责格式转换
- C) 两者结合：Data Generator 尽量匹配页面格式，Field Mapper 做最终适配
- D) 其他

[Answer]:C

---

## 问题 7: 安全基线影响

**背景**: 项目已启用部分安全基线（API key 保护 + PII 脱敏）。动态生成的数据虽然是假数据，但可能看起来像真实 PII。

**问题**: 动态生成的测试数据是否需要在日志中做 PII 脱敏处理？

- A) 是，与真实数据一视同仁，INFO+ 级别日志中脱敏
- B) 否，动态生成的数据是假数据，不需要脱敏
- C) 可配置：默认脱敏，提供选项关闭
- D) 其他

[Answer]:A

---

## 问题 8: 测试策略

**背景**: 动态生成功能涉及 LLM 调用（Data Generator Agent 依赖 LLM 生成数据），单元测试中需要考虑如何 mock。

**问题**: 对于这个新功能，你期望的测试覆盖范围？

- A) 单元测试（mock LLM）+ 现有 E2E 测试中新增 dynamic 模式场景
- B) 仅单元测试（mock LLM），E2E 测试稍后再加
- C) 单元测试 + 独立的 dynamic 模式 E2E 测试
- D) 其他

[Answer]:A

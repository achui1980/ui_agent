# 需求验证问题

> **说明**: 请在每个问题的 `[Answer]:` 标签后填写你的回答。对于选择题，填写选项字母即可。

---

## 意图分析摘要

- **请求类型**: 功能增强 + Bug 修复
- **范围**: 多组件（Flow 逻辑、Agent Prompt、报告系统、测试）
- **复杂度**: 中等
- **背景**: 通过 E2E 测试（2026-02-28）发现了 7 个残留问题，表单虽然成功提交但报告状态不准确

---

## 问题 1: 总体状态逻辑

**背景**: 当前 `overall_status` 的计算逻辑是：只要有任何页面 `verification_passed=false`，就报告为 PARTIAL。但实际上表单在重试后成功提交了。E2E 测试中，Step 2 第一次尝试失败，重试后成功推进到 Step 3，最终成功提交，但报告仍为 PARTIAL。

**问题**: 你期望 `overall_status` 如何反映重试成功的场景？

- A) 只要最终成功提交就报告 PASS，中间的重试失败不算
- B) 保持当前逻辑（有失败就 PARTIAL），但增加一个 `final_outcome` 字段区分"最终成功"
- C) 引入三级状态：PASS（无重试一次成功）、PASS_WITH_RETRIES（重试后成功）、PARTIAL（部分页面失败）、FAIL（完全失败）
- D) 其他（请在下方描述）

[Answer]:C

---

## 问题 2: fields_filled 与 LLM 输出

**背景**: 我们已修复代码来解析 crew 输出中的 `field_results` 到 `FieldActionResult`，但真实运行中 LLM agent 的输出不包含 `field_results` 键。这是因为 form_filler agent 的 `expected_output` prompt 没有要求输出字段级别的结果。

**问题**: 你希望如何解决 `fields_filled` 始终为空的问题？

- A) 修改 form_filler agent 的 prompt，要求 LLM 在输出中包含每个字段的操作结果（field_id, selector, value, status）
- B) 不依赖 LLM 输出，改为在 Tool 层（FillInputTool 等）收集字段操作结果，通过共享状态传递
- C) 两种都做：Tool 层收集实际结果（更可靠），同时 LLM 也输出供对比验证
- D) 其他（请在下方描述）

[Answer]:C

---

## 问题 3: page_index 递增逻辑

**背景**: E2E 测试中 `page_index` 始终为 0（前 3 次处理），只有最后确认页才变成 1。原因是重试时不递增，但成功提交后进入新页面时也没正确递增。

**问题**: 你期望 `page_index` 如何工作？

- A) 每次验证成功并进入新页面时递增（重试不递增），准确反映表单步骤
- B) 每次 `process_page` 调用都递增（包括重试），反映总处理次数
- C) 使用 agent 报告的 `new_page_id` 来判断是否进入了新页面，有新 page_id 才递增
- D) 其他（请在下方描述）

[Answer]:B

---

## 问题 4: 错误恢复

**背景**: 当前如果浏览器崩溃或 LLM API 超时，Flow 会直接抛出异常终止，不会生成任何报告。

**问题**: 你希望在异常情况下如何处理？

- A) 捕获异常，保存已有的部分结果到报告（状态为 ERROR），确保不丢失数据
- B) 当前行为可以接受（直接报错退出），暂不需要优化
- C) 加入重试机制：浏览器崩溃时重新启动浏览器，从当前页面继续；API 超时时重试当前 crew 执行
- D) 其他（请在下方描述）

[Answer]:A

---

## 问题 5: 自动化 E2E 测试

**背景**: 目前没有自动化的端到端测试。每次验证都需要手动启动 Flask server + 执行 CLI 命令。

**问题**: 你是否需要一个可重复运行的自动化 E2E 测试？

- A) 是，写一个 pytest E2E 测试（标记为 `@pytest.mark.e2e`），自动启动 Flask server + 调用 FormTestFlow + 验证报告结果。使用真实 LLM。
- B) 是，但使用 mock LLM 来避免 API 消耗，重点测试浏览器操作和报告生成
- C) 暂不需要自动化 E2E 测试
- D) 其他（请在下方描述）

[Answer]:A

---

## 问题 6: 安全基线

**背景**: AI-DLC 框架提供了一个安全基线扩展（15 条 OWASP 安全规则）。对于你的项目，主要关注点是 API key 保护、日志中的 PII、输入验证等。

**问题**: 是否需要启用安全基线扩展？

- A) 是，启用安全基线，在后续开发中作为强制约束
- B) 否，这是一个测试工具/PoC，安全不是当前优先级
- C) 部分启用 — 只关注 API key 保护和日志安全
- D) 其他（请在下方描述）

[Answer]:C

---

## 问题 7: 优先级排序

**问题**: 以下改进项，你的优先级排序是？（从高到低排列，用逗号分隔字母）

- A) 修复 `overall_status` 逻辑（PARTIAL → 正确状态）
- B) 修复 `fields_filled` 为空
- C) 修复 `page_index` 递增
- D) 添加错误恢复
- E) 添加自动化 E2E 测试
- F) `screenshot_path` 始终为空
- G) 修复 `PageResult.validation_errors` 类型不一致（list[dict] vs list[str]）

[Answer]:E,D,A,F,C,B,G

---

# 需求文档

## 意图分析

- **用户请求**: 完善 UI Agent 项目，修复 E2E 测试暴露的残留问题，提升系统可靠性和可观测性
- **请求类型**: 功能增强 + Bug 修复
- **范围**: 多组件（Flow 逻辑、Agent Prompt、Tool 层、报告系统、测试框架）
- **复杂度**: 中等

---

## 功能需求

### FR-01: 自动化端到端测试（优先级 1）

**描述**: 创建可重复运行的 pytest E2E 测试，自动启动 Flask test server，使用真实 LLM API 执行完整的 3 步保险表单流程，验证报告结果。

**验收标准**:
- 测试标记为 `@pytest.mark.e2e`，不会在默认 `pytest` 运行中执行
- 自动启动/关闭 Flask test server（fixture 管理生命周期）
- 使用 `test_data/multi_step_form.json` 作为测试数据
- 调用 `FormTestFlow.kickoff()` 执行完整流程
- 验证报告生成（JSON + HTML 文件存在）
- 验证确认页到达（`verification_passed=true`）
- 超时保护：单次测试不超过 5 分钟
- 测试完成后清理生成的报告文件

**涉及文件**:
- 新建: `tests/test_e2e/test_e2e_flow.py`
- 新建: `tests/test_e2e/__init__.py`
- 修改: `pyproject.toml`（添加 pytest marker 配置）

---

### FR-02: 错误恢复与部分结果保存（优先级 2）

**描述**: 当浏览器崩溃或 LLM API 超时等异常发生时，捕获异常并保存已有的部分结果到报告，状态为 ERROR。确保不丢失已完成页面的数据。

**验收标准**:
- Flow 的 `process_page` 和 `_run_page_loop` 中捕获异常
- 异常发生时调用 `generate_report()`，`overall_status` 设为 `ERROR`
- 已处理完的页面结果保留在报告中
- 异常信息记录在报告的 `error_message` 字段中
- 浏览器异常后确保 `browser_manager.close()` 被调用（资源清理）
- 日志中记录完整的异常堆栈

**涉及文件**:
- 修改: `src/flow/form_test_flow.py`（`_run_page_loop`, `process_page`, `generate_report`）
- 修改: `src/models/report.py`（添加 `error_message` 字段）
- 新增测试: `tests/test_flow/test_flow.py`

---

### FR-03: 四级 overall_status 状态逻辑（优先级 3）

**描述**: 引入四级状态系统替代当前的二级逻辑，准确反映测试执行结果。

**状态定义**:
| 状态 | 条件 |
|------|------|
| `PASS` | 所有页面一次验证通过，最终页面 `is_final_page=true` |
| `PASS_WITH_RETRIES` | 最终页面成功（`is_final_page=true`），但过程中有重试 |
| `PARTIAL` | 部分页面成功但未到达最终页面（如超过 max_retries 跳过） |
| `FAIL` | 没有任何页面验证通过，或第一个页面就失败 |

**验收标准**:
- `generate_report()` 中实现新的状态计算逻辑
- 报告 JSON 中 `overall_status` 使用新的四级值
- HTML 报告模板支持新状态的显示（颜色/图标区分）
- 向后兼容：旧报告的 PASS/PARTIAL/FAIL 仍可被识别

**涉及文件**:
- 修改: `src/flow/form_test_flow.py`（`generate_report`）
- 修改: `templates/report.html`
- 修改测试: `tests/test_flow/test_flow.py`

---

### FR-04: screenshot_path 填充（优先级 4）

**描述**: 当前报告中 `screenshot_path` 始终为空。需要将 crew 执行过程中截取的截图路径正确传递到报告中。

**验收标准**:
- `_update_state_from_crew_result()` 解析 crew 输出中的 `screenshot_path`
- 如果 crew 未返回 `screenshot_path`，使用 `screenshots` 列表中的最新截图
- 每个 `PageResult` 的 `screenshot_path` 有值（如果该页有截图）
- HTML 报告中可以展示页面截图

**涉及文件**:
- 修改: `src/flow/form_test_flow.py`
- 修改测试: `tests/test_flow/test_flow.py`

---

### FR-05: page_index 递增修复（优先级 5）

**描述**: `page_index` 应在每次 `process_page` 调用时递增（包括重试），反映总处理次数。

**验收标准**:
- 每次调用 `process_page` 时 `page_index` 递增
- 报告中的 `pages` 列表按 `page_index` 排序
- 重试的页面与首次尝试有不同的 `page_index`
- `total_pages` 反映总处理次数

**涉及文件**:
- 修改: `src/flow/form_test_flow.py`（`_run_page_loop`, `_update_state_from_crew_result`）
- 修改测试: `tests/test_flow/test_flow.py`

---

### FR-06: fields_filled 双层收集（优先级 6）

**描述**: 通过 Tool 层收集字段操作结果（主要来源），同时修改 LLM prompt 要求输出 `field_results`（对比验证）。

**验收标准**:
- FillInputTool、SelectOptionTool、CheckboxTool、DatePickerTool 执行后将结果写入共享状态
- 共享状态（如 tool 级别的结果收集器）在 crew 执行前初始化，执行后收集
- form_filler agent 的 `expected_output` prompt 要求包含 `field_results`
- `_update_state_from_crew_result()` 优先使用 Tool 层收集的结果，LLM 输出作为补充
- 报告中 `fields_filled` 有实际数据

**涉及文件**:
- 修改: `src/tools/fill_input_tool.py`、`select_option_tool.py`、`checkbox_tool.py`、`date_picker_tool.py`
- 修改: `src/agents/form_filler.py`（prompt 调整）
- 修改: `src/flow/page_crew.py`（结果收集器初始化）
- 修改: `src/flow/form_test_flow.py`（结果提取）
- 新增/修改测试

---

### FR-07: validation_errors 类型统一（优先级 7）

**描述**: `PageResult.validation_errors` 类型声明为 `list[dict]` 但实际存储 `list[str]`。统一为 `list[str]`。

**验收标准**:
- `PageResult.validation_errors` 类型改为 `list[str]`
- 所有写入该字段的代码保持一致
- 现有测试通过

**涉及文件**:
- 修改: `src/models/page_result.py`
- 修改测试（如有需要）

---

## 非功能需求

### NFR-01: 安全 — API Key 保护

**描述**: 确保 API key 不会泄露到 git 历史、日志或报告中。

**验收标准**:
- `.env` 在 `.gitignore` 中（已满足）
- 日志中不输出完整的 API key（如有输出需脱敏）
- 报告中不包含 API key
- `.env.example` 使用占位符（已满足）

---

### NFR-02: 安全 — 日志中的 PII 保护

**描述**: 测试数据中可能包含个人信息（姓名、邮箱、地址等），日志中应避免直接记录完整的测试数据。

**验收标准**:
- DEBUG 级别日志可以包含测试数据（开发调试用）
- INFO 级别日志只记录字段 key，不记录 value
- 报告中保留完整数据（报告本身是测试产物）

---

## 扩展配置

| 扩展 | 启用状态 | 决定时间 | 说明 |
|------|---------|---------|------|
| 安全基线 | 部分启用 | 需求分析 | 仅启用 API key 保护（SECURITY-01/09）和日志安全（SECURITY-03）|

---

## 实施优先级

| 优先级 | 需求 | 预估复杂度 |
|--------|------|-----------|
| 1 | FR-01: 自动化 E2E 测试 | 中 |
| 2 | FR-02: 错误恢复 | 中 |
| 3 | FR-03: 四级状态逻辑 | 低 |
| 4 | FR-04: screenshot_path | 低 |
| 5 | FR-05: page_index 递增 | 低 |
| 6 | FR-06: fields_filled 双层收集 | 高 |
| 7 | FR-07: validation_errors 类型 | 低 |

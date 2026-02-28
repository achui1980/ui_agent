# 代码质量评估

**AI-DLC 阶段：** 启动 / 逆向工程
**日期：** 2026-02-28
**项目：** UI Agent - 基于 AI 的 Web 表单测试系统

---

## 测试覆盖率

### 概述

项目拥有一个 pytest 测试套件，约 72 个测试用例，组织在 `tests/` 目录下，与 `src/` 结构镜像对应。

| 测试模块 | 位置 | 覆盖范围 |
|---------|------|---------|
| `test_parsers/test_parsers.py` | 解析器 | JSON（结构化 + 扁平）、YAML、CSV、Excel 解析 |
| `test_tools/test_tools.py` | 工具 | 全部 10 个工具类，使用模拟的 Playwright Page |
| `test_flow/test_flow.py` | 流程 | FormTestFlow 状态机、状态转换、报告生成 |
| `test_config.py` | 配置 | Settings 默认值、环境变量加载 |
| `test_cli.py` | CLI | Click 命令调用 |
| `test_reporting/test_reporting.py` | 报告器 | JSON 和 HTML 报告生成 |
| `conftest.py` | Fixtures | 共享 fixtures：`settings`、`sample_test_data`、`test_data_dir` |

### 测试方法

- **仅有单元测试** -- 所有测试均使用模拟对象。浏览器工具通过 `unittest.mock.MagicMock` 模拟 Playwright `Page`。不调用真实浏览器或 LLM。
- **无端到端测试** -- 没有针对真实浏览器/LLM 或内置 Flask 测试服务器（`test_server/app.py`）运行的集成测试。
- **无 NL 解析器测试** -- 自然语言解析器（`nl_parser.py`）未包含在测试套件中（需要 LLM 模拟或真实 API 调用）。
- **测试组织** -- 测试按类分组（如 `class TestFillInputTool:`），方法命名如 `test_fill_success`、`test_fill_healed`、`test_fill_failed`。
- **断言方式** -- 检查状态关键字字符串：`assert "SUCCESS" in result`、`assert "HEALED" in result`。
- **Fixtures** -- `conftest.py` 中的共享 fixtures 提供测试用 `Settings` 实例和示例数据。文件相关测试使用 pytest 内置的 `tmp_path`。

### 覆盖率缺口

1. **无集成/端到端测试** -- 完整的智能体流水线（4 个智能体协作处理真实表单）未经测试
2. **无 NL 解析器覆盖** -- `parse_natural_language()` 未经测试
3. **无 VLM 工具覆盖** -- `ScreenshotAnalysisTool` 的 VLM 调用路径未经测试
4. **无多页面流程测试** -- 流程测试未验证含真实 Crew 输出的多页面遍历
5. **无错误恢复测试** -- 浏览器崩溃/断开连接场景未经测试

---

## 近期修复的问题（2026-02-28）

以下问题已在当前代码库中识别并解决：

### 1. `fields_filled` 硬编码为空

**原先：** `generate_report()` 始终以 `fields_filled=[]` 创建 `PageResult`，忽略 Crew 输出。
**修复：** 现在在 `_update_state_from_crew_result()` 中解析 Crew 输出的 `field_results`，并传递到 `generate_report()` 中构建 `FieldActionResult` 对象。

### 2. 仅执行第一个测试用例

**原先：** `form_test_flow.py` 始终运行 `test_cases[0]`，忽略其余用例。
**修复：** `main.py:run()` 现在遍历所有测试用例，为每个用例创建新的 `FormTestFlow`。`_load_test_case()` 方法将测试用例加载提取为可复用方法，供 Flow 解析步骤和 CLI 循环调用。

### 3. 配置字段与状态断开

**原先：** `Settings` 中的 `awa_max_steps` 和 `awa_screenshot_dir` 未与任何运行时行为关联。
**修复：** `FormTestFlow.__init__()` 现在将 `settings.awa_max_steps` 映射到 `state.max_pages`，将 `settings.awa_max_healing_attempts` 映射到 `state.max_retries`。`awa_screenshot_dir` 由智能体工厂传递给 `ScreenshotTool` 和 `ScreenshotAnalysisTool`。

### 4. SelectOptionTool 中的死代码

**原先：** 包含不可达的代码路径。
**修复：** 移除死代码，清理策略流程。

### 5. 缺少 `__future__` annotations

**原先：** 部分模块缺少 `from __future__ import annotations`。
**修复：** 已在所有源码模块中添加，确保 PEP 604 联合类型语法的一致性。

### 6. 未使用的导入

**原先：** 多个模块存在未使用的导入语句。
**修复：** 已在整个代码库中清理。

### 7. ScreenshotAnalysisTool 未导出

**原先：** `src/tools/__init__.py` 未重导出 `ScreenshotAnalysisTool`。
**修复：** 已添加到 `src/tools/__init__.py` 的导入和 `__all__` 中。

---

## 遗留问题

### 功能问题

#### 1. `overall_status` 在成功重试后报告为 PARTIAL

**严重程度：** 中
**位置：** `src/flow/form_test_flow.py:373-380`
**描述：** 总体状态逻辑检查 `all(p.get("verification_passed") for p in self.state.page_results)`。当某页首次尝试失败但重试成功时，失败和成功的 `page_results` 条目都会被存储。这意味着中间的失败结果会导致 `overall_status` 为 `PARTIAL`，即使表单最终成功提交。重试成功与真正的部分完成无法区分。

#### 2. `fields_filled` 在实际运行中仍为空

**严重程度：** 中
**位置：** `src/flow/form_test_flow.py:314`
**描述：** `field_results` 的提取依赖于 LLM 智能体在其 JSON 输出中包含 `field_results` 键。实际运行中，CrewAI 智能体的 fill 任务输出通常不会以预期格式包含该键，导致 `field_results` 为空列表。这是提示工程问题（fill 任务的 `expected_output` 描述了格式，但 LLM 不能可靠地遵循），而非代码逻辑问题。

#### 3. `page_index` 在重试间未正确递增

**严重程度：** 低
**位置：** `src/flow/form_test_flow.py:328`
**描述：** 页面结果中的 `page_index` 反映 `self.state.current_page_index`，重试时不递增（设计如此——重试保持同一页面）。但当同一页面记录多个 page_results（失败 + 重试）时，两个条目的 `page_index` 相同，无法区分哪个结果对应哪次尝试。

#### 4. `screenshot_path` 在报告中始终为空

**严重程度：** 低
**位置：** `src/models/page_result.py:21`、`src/flow/form_test_flow.py:328`
**描述：** 报告中 `PageResult.screenshot_path` 始终为 `""`，因为 `_update_state_from_crew_result()` 将截图存入 `self.state.screenshots`（扁平列表），但从未填充页面结果字典中的每页 `screenshot_path` 字段。

#### 5. 浏览器中途崩溃时无错误恢复

**严重程度：** 中
**位置：** `src/flow/form_test_flow.py`
**描述：** 如果 Playwright 浏览器进程在 `process_page()` 执行期间崩溃或断开连接，Flow 会抛出未处理的异常。页面循环周围没有 try/except，没有浏览器重启逻辑，`generate_report()` 不会被调用，因此部分结果会丢失。

#### 6. `PageResult.validation_errors` 类型不一致

**严重程度：** 低
**位置：** `src/models/page_result.py:19`
**描述：** 模型中 `validation_errors` 的类型为 `list[str]`，这是正确的。但 AGENTS.md 将其记录为 `list[dict]`。Flow 代码在 `_update_state_from_crew_result()`（第 297-300 行）中将验证错误规范化为字符串，正确处理了 dict 和 string 两种输入。问题在于文档不一致，而非运行时 bug。

#### 7. TestCase 类触发 PytestCollectionWarning

**严重程度：** 低
**位置：** `src/models/test_case.py`
**描述：** `TestCase` 类名匹配 pytest 的收集模式（`Test*`），导致 `PytestCollectionWarning: cannot collect test class 'TestCase' because it has a __init__ constructor`。这是装饰性问题，不影响测试执行，但会在测试输出中增加噪声。

---

## 代码风格评估

### 优势

- **格式一致** -- 全代码库 4 空格缩进、双引号、兼容 Black 的约 88 字符行宽
- **类型注解** -- 所有函数签名都有返回类型注解；使用 Python 3.11+ 小写泛型（`dict[str, str]`、`list[TestCase]`）
- **PEP 604 联合类型** -- 每个模块都有 `from __future__ import annotations`，启用 `X | None` 语法
- **导入排序** -- 标准库、第三方、本地模块各组之间空行分隔
- **命名规范** -- 一致的 `snake_case` 文件名、`PascalCase` 类名、`snake_case` 函数名、`_` 前缀私有成员
- **全面使用 Pydantic** -- 所有数据模型和配置使用 Pydantic，使用 `model_dump()`（非已弃用的 `.dict()`）
- **自愈工具模式** -- 一致的 try/except/try/except 结构，配合 SUCCESS/HEALED/FAILED 状态字符串

### 次要风格备注

- 部分工具有 3 种策略（DatePicker、SelectOption），而多数工具只有 2 种（主策略 + 回退）。3 策略工具使用顺序的 try/except 块而非嵌套结构。
- `form_test_flow.py` 是最长的文件（461 行），同时包含状态管理和编排逻辑。可考虑将状态更新逻辑分离。
- `DOMExtractorTool` 在 Python 多行字符串中嵌入了大段 JavaScript（100+ 字符宽），突破了 88 字符规范，但从 JS 可读性角度来看是务实的选择。

---

## 文档评估

### 现有文档

| 文档 | 状态 | 备注 |
|------|------|------|
| `AGENTS.md` | 全面 | 202 行。涵盖项目概览、环境配置、构建/运行命令、项目结构、代码风格指南、命名规范、工具模式、错误处理、测试规范、Pydantic 模式、配置、NL 解析架构、已知问题。作为主要开发者指南。 |
| `README.md` | 存在 | 项目级说明文档（未详细审计）。 |
| `.env.example` | 存在 | 环境配置示例文件。 |
| 内联文档字符串 | 部分 | `main.py` 和测试模块有模块级文档字符串。解析器和部分流程方法有函数文档字符串。工具类使用 `description` 字段而非文档字符串。 |
| 代码注释 | 稀少 | 注释解释了非显而易见的逻辑（如"关闭弹出窗口"、"自愈回退"、"CrewAI Flow 关于直接方法调用的注意事项"）。未过度注释。 |

### 文档缺口

- 缺少架构图（应有展示 Flow -> Crew -> Agent -> Tool 层次结构的可视化图表）
- 无 API 参考自动生成（Sphinx、pdoc 等）
- 无变更日志或版本历史
- 无贡献指南
- 测试数据格式文档仅存在于 AGENTS.md 和解析器代码内联注释中
- Flask 测试服务器（`test_server/app.py`）无文档说明

---

## 依赖健康度

### 核心依赖

| 包 | 用途 | 风险 |
|---|------|------|
| `crewai` | 多智能体编排 | 活跃开发中，但 API 演进较快。Flow API 尤其不稳定。 |
| `playwright` | 浏览器自动化 | 稳定，由 Microsoft 良好维护 |
| `pydantic` + `pydantic-settings` | 数据模型与配置 | 稳定、成熟 |
| `click` | CLI 框架 | 稳定、成熟 |
| `loguru` | 日志 | 稳定、低风险 |
| `jinja2` | HTML 模板 | 稳定、成熟 |
| `openai` | VLM API 客户端 | 稳定，仅 ScreenshotAnalysisTool 使用 |
| `openpyxl` | Excel 解析 | 稳定、成熟 |
| `pyyaml` | YAML 解析 | 稳定、成熟 |

### 风险提示

- **CrewAI 依赖**是最高风险项。Flow 事件系统（`@listen`、`@router`、`@start`）有已知注意事项：直接方法调用会绕过事件系统。代码库通过 `_run_page_loop()` 解决了此问题，但未来 CrewAI 更新可能破坏此模式。
- 审计中未发现可见的依赖版本锁定（需检查 `pyproject.toml` 中的版本约束）。

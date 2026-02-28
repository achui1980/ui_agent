# 业务概述 - UI Agent

**AI-DLC 阶段**: 启动 / 逆向工程
**生成日期**: 2026-02-28
**项目**: UI Agent - AI 驱动的 Web 表单测试系统

---

## 1. 业务背景

UI Agent 是一套 AI 驱动的自动化测试系统，专为保险和金融行业中常见的复杂多步骤 Web 表单而设计。这类表单具有独特的测试难点：多页向导式流程、条件字段、联动下拉框（例如 省份 -> 城市）、日期选择器、文件上传以及动态校验逻辑。人工测试此类表单不仅效率低下，而且容易出错、成本高昂。

本系统采用四个协同工作的 LLM 智能体（由 CrewAI 编排），分别负责分析、理解、填写和验证 Web 表单——以智能自适应的表单交互方式，取代传统自动化中脆弱的、基于选择器的方法。测试数据支持结构化格式（JSON、YAML、CSV、Excel）以及自然语言文本描述。

### 目标领域

- 保险申请表单（多步骤向导）
- 金融服务开户表单
- 任何包含多页导航、下拉框、日期选择器、文件上传和校验逻辑的复杂 Web 表单

### 核心价值主张

- **语义理解**：LLM 智能体按语义含义匹配测试数据与表单字段，而非依赖测试脚本中硬编码的 CSS 选择器
- **自愈能力**：当主要交互策略失败时（例如 `fill()` 调用抛出异常），工具会自动尝试回退策略并报告 `HEALED` 状态
- **视觉分析**：可选的 VLM（视觉语言模型）分析能够识别仅靠 DOM 检查容易误判的 UI 组件（例如一个文本输入框实际上是 react-select 下拉框）
- **自然语言输入**：QA 工程师可以用自然语言描述测试数据，无需编写结构化 JSON

---

## 2. 核心业务流程

### 2.1 表单测试执行 (`ui-agent run`)

主要业务流程。端到端自动化表单填写与验证。

**流程**：
1. 解析测试数据文件（JSON/YAML/CSV/Excel/NL）为 `TestCase` 对象
2. 启动浏览器（Playwright Chromium）并导航至目标 URL
3. 对每个表单页面（最多 `max_pages` 页，默认 50）：
   a. **Page Analyzer** 智能体提取 DOM 字段 + 截图 + 可选 VLM 分析
   b. **Field Mapper** 智能体将测试数据键值与发现的表单字段进行语义匹配
   c. **Form Filler** 智能体通过浏览器工具执行填写/选择/点击/上传操作
   d. **Result Verifier** 智能体检查校验错误、页面跳转或完成状态
4. 验证失败时重试当前页面（最多 `max_retries` 次，默认 3）
5. 验证通过时进入下一页
6. 生成 JSON + HTML 报告，包含逐字段结果、耗时、Token 用量和截图

**输入**：测试文件路径、目标 URL、最大页数、最大重试次数
**输出**：`TestReport`（JSON + HTML），整体状态为 PASS/FAIL/PARTIAL

### 2.2 测试文件校验 (`ui-agent validate`)

解析并校验测试用例文件，不执行任何浏览器操作。

**流程**：
1. 根据文件扩展名检测格式
2. 对 `.txt`（自然语言）文件：启动浏览器，提取 DOM 字段，然后结合页面上下文使用 LLM 解析自然语言
3. 对结构化文件：直接解析
4. 在控制台展示解析后的测试用例（ID、URL、字段数量、数据、预期结果）

**输入**：测试文件路径，可选 URL（`.txt` 文件必须提供）
**输出**：控制台输出解析后的测试用例

### 2.3 页面分析 (`ui-agent analyze`)

提取并展示目标 URL 的表单字段信息，不填写任何字段。

**流程**：
1. 启动浏览器，导航至 URL
2. 提取 DOM 字段（选择器、类型、标签、选项、按钮、错误信息）
3. 截图
4. 可选运行 VLM 视觉分析以识别自定义 UI 组件

**输入**：目标 URL，是否启用视觉分析（默认启用）
**输出**：控制台输出 DOM 提取 JSON、截图路径、VLM 分析结果

### 2.4 自然语言测试解析（两阶段流程）

将自由格式的自然语言测试描述转换为结构化的 `TestCase` 对象。

**第一阶段 - 页面预分析**：
1. Flow 检测到 `.txt` 扩展名，路由至 `pre_analyze_page()`
2. 启动浏览器，导航至目标 URL
3. 运行 `DOMExtractorTool` 提取字段 ID、标签、类型和选项
4. 将结果存储为 `page_context`

**第二阶段 - 上下文感知的自然语言解析**：
1. NL 解析器接收 `page_context` 并构建具有字段感知能力的 LLM 提示词
2. 提示词包含来自 DOM 的实际表单字段名称、类型和选项
3. LLM 将自然语言描述映射到表单字段键
4. 解析器根据 DOM 标签构建 `preferred_key` 建议（例如用 `first_name` 替代 `firstNameInput`）
5. 返回结构化的 `TestCase`，其中 `data: dict[str, str]`

**关键设计决策**：
- 自然语言文件必须提供 URL（`--url` 参数为必填项）
- 不硬编码日期格式——LLM 从页面上下文推断格式
- NL 解析器直接使用 CrewAI 的 `LLM` 类（而非智能体）进行结构化提取

---

## 3. 多智能体协作

四个智能体按顺序依次处理每个表单页面，每个智能体通过 CrewAI 的任务上下文链机制在前一个智能体的输出基础上工作：

| 智能体 | 角色 | 工具 | 输出 |
|---|---|---|---|
| **Page Analyzer** | DOM 提取 + VLM 视觉分析 + 截图 | DOMExtractorTool, ScreenshotTool, ScreenshotAnalysisTool | JSON：字段、按钮、错误、视觉备注 |
| **Field Mapper** | 测试数据与页面字段的语义匹配 | 无（纯 LLM 推理） | JSON：映射关系、未匹配字段、已消费键 |
| **Form Filler** | 执行填写/选择/点击/上传操作 | FillInputTool, SelectOptionTool, CheckboxTool, ClickButtonTool, DatePickerTool, UploadFileTool | JSON：字段结果、提交状态 |
| **Result Verifier** | 验证提交结果，检测错误/页面跳转 | ScreenshotTool, GetValidationErrorsTool | JSON：是否通过、页面跳转、错误、是否为最终页 |

### 智能体交互模式

```
Page Analyzer --> [context] --> Field Mapper --> [context] --> Form Filler --> [context] --> Result Verifier
                                                                                              |
                                                                     Result feeds back to Flow state
                                                                     (retry / next page / complete)
```

- Field Mapper 接收 Analyzer 的字段列表作为任务上下文
- Form Filler 接收 Mapper 的字段到值映射作为上下文
- Result Verifier 同时接收 Analyzer 的原始页面状态和 Filler 的操作结果

---

## 4. 支持的输入格式

| 格式 | 扩展名 | 解析器模块 | 备注 |
|---|---|---|---|
| JSON | `.json` | `json_parser.py` | 单个对象或测试用例数组 |
| YAML | `.yaml`, `.yml` | `yaml_parser.py` | 与 JSON 结构相同 |
| CSV | `.csv` | `csv_parser.py` | 每行一个测试用例，表头为字段名 |
| Excel | `.xlsx`, `.xls` | `excel_parser.py` | 使用 openpyxl，每行一个测试用例 |
| 自然语言 | `.txt` | `nl_parser.py` | 需要 URL，两阶段 LLM 解析 |

所有解析器都生成 `list[TestCase]`，每个 `TestCase` 包含：
- `test_id: str` -- 唯一标识符
- `url: str` -- 目标表单 URL
- `data: dict[str, str]` -- 规范化字段名到值的映射
- `description: str` -- 人类可读的摘要
- `expected_outcome: str` -- "success"（默认值）

---

## 5. 自愈模式

每个浏览器工具都遵循两层错误处理策略：

```
Primary Strategy
    |
    +-- SUCCESS --> return "SUCCESS: ..."
    |
    +-- Exception --> Fallback Strategy
                        |
                        +-- SUCCESS --> return "HEALED: ..."
                        |
                        +-- Exception --> return "FAILED: ..."
```

**示例**：
- `FillInputTool`：主策略使用 `locator.fill(value)`。回退策略使用 `locator.press_sequentially(value, delay=50)` 处理拒绝编程式 `fill` 的输入框。
- 需要关闭弹窗的工具（`FillInputTool`、`CheckboxTool`）在操作后按 `Escape` 键关闭可能阻碍后续交互的自动补全/日期选择器浮层。
- 工具不会向智能体抛出异常——它们返回状态字符串，由智能体决定如何继续。

**状态值**：
- `SUCCESS` -- 主策略成功
- `HEALED` -- 主策略失败但回退策略成功
- `FAILED` -- 两种策略均失败，包含错误信息

---

## 6. 报告生成

所有页面处理完成后，Flow 生成两种格式的报告：

### JSON 报告 (`reports/{test_case_id}_report.json`)
完整的机器可读报告，包含：
- `test_case_id`、`url`、`overall_status`（PASS/FAIL/PARTIAL）
- `total_pages`、`pages_completed`
- 逐页结果：`page_index`、`page_id`、`verification_passed`、`validation_errors`、`retry_count`
- 逐字段结果：`field_id`、`selector`、`value`、`status`、`error_message`
- 耗时：`duration_seconds`、`task_durations`（各智能体耗时：analyze/map/fill/verify）
- Token 用量：`total_tokens`、`prompt_tokens`、`completion_tokens`（所有页面的汇总）
- `screenshots`：截图文件路径列表
- `start_time`、`end_time`

### HTML 报告 (`reports/{test_case_id}_report.html`)
人类可读的报告，通过 Jinja2 模板（`templates/report.html`）渲染，以可视化格式呈现相同数据。

### 整体状态判定逻辑
- **PASS**：所有页面的 `verification_passed = true`
- **PARTIAL**：部分页面通过，部分失败
- **FAIL**：没有页面通过，或没有任何页面结果

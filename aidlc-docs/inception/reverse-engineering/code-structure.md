# 代码结构

**AI-DLC 阶段：** 启动 / 逆向工程
**日期：** 2026-02-28
**项目：** UI Agent - 基于 AI 的 Web 表单测试系统

---

## 概述

UI Agent 是一个 Python 3.11+ 项目，使用 CrewAI（多智能体编排）和 Playwright（浏览器自动化）来测试多步骤 Web 表单。四个协作的 LLM 智能体分别负责分析、映射、填写和验证表单页面，支持结构化或自然语言测试数据。

项目采用清晰的分层架构：CLI 入口 -> Flow 状态机 -> 每页一个 Crew -> 智能体配备工具 -> 通过 Playwright 操作浏览器。

---

## 目录结构

```
ui_agent/
├── src/                          # 应用源代码
│   ├── __init__.py
│   ├── main.py                   # CLI 入口（Click 命令）
│   ├── config.py                 # Pydantic Settings（读取 .env）
│   ├── agents/                   # CrewAI Agent 工厂函数（4 个智能体）
│   │   ├── __init__.py
│   │   ├── page_analyzer.py      # DOM + VLM 视觉分析智能体
│   │   ├── field_mapper.py       # 语义字段匹配智能体（纯 LLM）
│   │   ├── form_filler.py        # 填写/选择/点击操作智能体
│   │   └── result_verifier.py    # 提交后验证智能体
│   ├── browser/                  # Playwright 生命周期管理
│   │   ├── __init__.py
│   │   └── browser_manager.py    # 浏览器启动/导航/关闭
│   ├── flow/                     # CrewAI Flow 状态机
│   │   ├── __init__.py
│   │   ├── form_test_flow.py     # FormTestFlow 状态机 + FormTestState
│   │   └── page_crew.py          # 每页 4 智能体 Crew 构建器
│   ├── models/                   # Pydantic 数据模型
│   │   ├── __init__.py           # 重导出：TestCase、FieldActionResult、PageResult、TestReport
│   │   ├── test_case.py          # TestCase 模型
│   │   ├── page_result.py        # FieldActionResult、PageResult 模型
│   │   └── report.py             # TestReport 模型
│   ├── parsers/                  # 测试文件解析器（JSON/YAML/CSV/Excel/NL）
│   │   ├── __init__.py
│   │   ├── parser_factory.py     # 按文件扩展名分发
│   │   ├── json_parser.py        # JSON 结构化 + 扁平格式
│   │   ├── yaml_parser.py        # YAML 结构化 + 扁平格式
│   │   ├── csv_parser.py         # 含表头行的 CSV
│   │   ├── excel_parser.py       # Excel（.xlsx/.xls）含表头行
│   │   └── nl_parser.py          # 基于 LLM 的自然语言解析
│   ├── reporting/                # 报告生成器
│   │   ├── __init__.py
│   │   ├── json_report.py        # JSON 报告输出
│   │   └── html_report.py        # Jinja2 HTML 报告输出
│   ├── tools/                    # CrewAI Tool 封装（10 个工具）
│   │   ├── __init__.py           # 重导出全部 10 个工具类
│   │   ├── screenshot_tool.py         # 页面截图捕获
│   │   ├── screenshot_analysis_tool.py # VLM 视觉分析
│   │   ├── dom_extractor_tool.py      # DOM 表单元素提取
│   │   ├── fill_input_tool.py         # 文本输入填写
│   │   ├── select_option_tool.py      # 下拉选择（原生 + react-select + 通用）
│   │   ├── checkbox_tool.py           # 复选框/单选框切换
│   │   ├── click_button_tool.py       # 按钮点击（含导航等待）
│   │   ├── date_picker_tool.py        # 日期选择器填写（3 种策略）
│   │   ├── upload_file_tool.py        # 文件上传
│   │   └── validation_error_tool.py   # 验证错误提取
│   └── utils/                    # 工具模块
│       ├── __init__.py
│       └── logging.py            # Loguru 配置（stderr + 文件轮转）
├── tests/                        # pytest 测试套件（镜像 src/ 结构）
│   ├── __init__.py
│   ├── conftest.py               # 共享 fixtures：settings、sample_test_data、test_data_dir
│   ├── test_cli.py               # CLI 命令测试
│   ├── test_config.py            # 配置/Settings 测试
│   ├── test_flow/                # Flow 状态机测试
│   │   ├── __init__.py
│   │   └── test_flow.py
│   ├── test_parsers/             # 解析器测试（JSON、YAML、CSV、Excel、NL）
│   │   ├── __init__.py
│   │   └── test_parsers.py
│   ├── test_reporting/           # 报告生成器测试
│   │   ├── __init__.py
│   │   └── test_reporting.py
│   └── test_tools/               # 工具封装测试（模拟的 Playwright Page）
│       ├── __init__.py
│       └── test_tools.py
├── templates/
│   └── report.html               # Jinja2 HTML 报告模板（170 行）
├── test_data/                    # 示例测试用例文件
│   ├── sample_test.json          # JSON 格式示例
│   ├── sample_test.yaml          # YAML 格式示例
│   ├── sample_test.csv           # CSV 格式示例
│   ├── demoqa_practice_form.json # DemoQA 练习表单测试数据
│   ├── multi_step_form.json      # 多步骤表单测试数据
│   ├── multi_step_registration.yaml # 多步骤注册 YAML
│   └── demoqa_nl_test.txt        # 自然语言测试描述
├── test_server/
│   └── app.py                    # Flask 3 步保险表单（本地测试用）
├── AGENTS.md                     # 完整的代码库指南
├── README.md                     # 项目说明文档
├── .env.example                  # 环境配置示例
└── pyproject.toml                # 项目元数据与依赖
```

---

## 模块详解

### `src/main.py` -- CLI 入口

CLI 基于 Click 构建，提供三个命令：

- **`cli()`** -- Click 命令组。每次调用时执行 `setup_logging()`。
- **`run(test_file, url, max_pages, max_retries)`** -- 完整的表单测试执行。对于 `.txt`（NL）文件，创建单个 `FormTestFlow`，由 Flow 内部处理解析。对于其他格式，先通过 `parse_test_file()` 解析测试用例，然后遍历每个用例，为每个用例创建新的 `FormTestFlow`。
- **`validate(test_file, url)`** -- 仅解析验证。对于 `.txt` 文件，启动浏览器提取 DOM 页面上下文后再进行 NL 解析，然后显示解析结果。在 `finally` 块中清理浏览器。
- **`analyze(url, visual)`** -- 单页分析。启动浏览器，运行 `DOMExtractorTool`、`ScreenshotTool`，以及可选的 `ScreenshotAnalysisTool`（VLM）。将结果输出到 stdout。

### `src/config.py` -- 配置

- **`Settings(BaseSettings)`** -- Pydantic Settings 类，从 `.env` 读取配置。字段包括：`openai_api_key`、`openai_api_base`、`https_proxy`、`llm_model`（默认 `gpt-5.2`）、`vlm_model`、`llm_max_tokens`、`vlm_max_tokens`、`browser_headless`、`browser_timeout`、`browser_navigation_timeout`、`browser_viewport_width`、`browser_viewport_height`、`browser_proxy`、`awa_max_steps`、`awa_max_healing_attempts`、`awa_screenshot_dir`、`log_level`。
- **`get_settings()`** -- 工厂函数，返回新的 `Settings()` 实例。

### `src/agents/` -- 智能体工厂函数

每个模块导出一个遵循 `create_<role>(page, llm, settings=None) -> Agent` 模式的工厂函数。

| 模块 | 工厂函数 | 角色 | 使用的工具 |
|------|---------|------|-----------|
| `page_analyzer.py` | `create_page_analyzer(page, llm, settings)` | Page Analyzer | DOMExtractorTool、ScreenshotTool、ScreenshotAnalysisTool（根据 VLM 配置条件启用） |
| `field_mapper.py` | `create_field_mapper(llm)` | Field Mapper | 无（纯 LLM 推理） |
| `form_filler.py` | `create_form_filler(page, llm)` | Form Filler | FillInputTool、SelectOptionTool、CheckboxTool、ClickButtonTool、DatePickerTool、UploadFileTool |
| `result_verifier.py` | `create_result_verifier(page, llm, settings)` | Result Verifier | ScreenshotTool、GetValidationErrorsTool |

所有智能体设置 `verbose=True` 以启用 CrewAI 详细日志。

### `src/browser/browser_manager.py` -- 浏览器生命周期

- **`BrowserManager`** -- 管理完整的 Playwright 生命周期。持有 `_playwright`、`_browser`、`_context`、`_page` 作为私有状态。
  - `start() -> Page` -- 启动 Chromium，配置无头模式、代理、视口和超时。返回 `Page` 实例。
  - `navigate(url)` -- 导航到 URL，使用 `wait_until="networkidle"`。
  - `close()` -- 按顺序关闭 context、browser 和 playwright。将所有引用置为 null。
  - `page` 属性 -- 返回 `_page`，若未启动则抛出 `RuntimeError`。

### `src/flow/form_test_flow.py` -- Flow 状态机

- **`FormTestState(BaseModel)`** -- Flow 全局状态，包含输入路径、已解析的测试用例数据、页面循环状态（索引、已消费字段、结果、重试次数）以及最终报告状态（状态、截图、计时）。
- **`FormTestFlow(Flow[FormTestState])`** -- CrewAI Flow 子类，编排完整的测试运行。
  - `__init__(settings)` -- 初始化设置，将配置值（`awa_max_steps`、`awa_max_healing_attempts`）映射到状态。
  - `parse_test_case()` -- `@start()` 方法。检测 NL 还是结构化输入，返回 `"parsed"` 或 `"needs_page_analysis"`。
  - `route_after_parse()` -- `@router(parse_test_case)`。路由到 `"open_browser"` 或 `"pre_analyze"`。
  - `pre_analyze_page()` -- `@listen("pre_analyze")`。打开浏览器，提取 DOM，使用页面上下文解析 NL，然后调用 `_run_page_loop()`。
  - `open_browser_and_navigate()` -- `@listen("open_browser")`。启动浏览器（若尚未启动）并调用 `_run_page_loop()`。
  - `_run_page_loop()` -- 统一的页面循环引擎。在 while 循环中驱动 `process_page()`，包含重试/推进/完成逻辑。
  - `process_page()` -- 构建并启动 `PageCrew`，提取计时和 token 使用量，更新状态。
  - `_update_state_from_crew_result(result, ...)` -- 从 Crew 输出解析 JSON，提取验证状态、验证错误、已消费字段、字段结果。
  - `_extract_json(text)` -- 静态方法。先尝试完整 JSON 解析，再扫描最后一个 `{}` 块。
  - `generate_report()` -- `@listen("complete")`。计算总体状态，构建 `TestReport`，保存 JSON + HTML 报告，清理浏览器。
  - `_load_test_case(tc)` -- 将已解析的 `TestCase` 加载到 Flow 状态中。

### `src/flow/page_crew.py` -- Crew 构建器

- **`build_page_crew(page, settings) -> Crew`** -- 为处理单个表单页面构建 4 智能体、4 任务的顺序执行 `Crew`。创建 LLM 实例，实例化全部 4 个智能体，定义带上下文链的任务：
  1. **analyze_task** -- DOM 提取 + 视觉分析 + 截图（PageAnalyzer）
  2. **map_task** -- 将测试数据映射到页面字段，上下文来自 analyze_task（FieldMapper）
  3. **fill_task** -- 执行表单操作，上下文来自 map_task（FormFiller）
  4. **verify_task** -- 提交后验证，上下文来自 analyze_task + fill_task（ResultVerifier）

### `src/models/` -- 数据模型

| 模型 | 文件 | 字段 |
|------|------|------|
| `TestCase` | `test_case.py` | `test_id: str`、`url: str`、`data: dict[str, str]`、`description: str = ""`、`expected_outcome: str = "success"` |
| `FieldActionResult` | `page_result.py` | `field_id: str`、`selector: str`、`value: str`、`status: str`、`error_message: str = ""` |
| `PageResult` | `page_result.py` | `page_index: int`、`page_id: str`、`fields_filled: list[FieldActionResult]`、`verification_passed: bool`、`validation_errors: list[str]`、`retry_count: int`、`screenshot_path: str`、`duration_seconds: float`、`task_durations: dict[str, float]`、`token_usage: dict[str, int]` |
| `TestReport` | `report.py` | `test_case_id: str`、`url: str`、`overall_status: str`、`total_pages: int`、`pages_completed: int`、`pages: list[PageResult]`、`screenshots: list[str]`、`start_time: str`、`end_time: str`、`duration_seconds: float`、`total_tokens: int`、`prompt_tokens: int`、`completion_tokens: int` |

### `src/parsers/` -- 测试文件解析器

- **`parser_factory.py`** -- `parse_test_file(path, url, settings, page_context) -> list[TestCase]`。按扩展名分发：`.xlsx`/`.xls` -> `parse_excel`，`.csv` -> `parse_csv`，`.json` -> `parse_json`，`.yaml`/`.yml` -> `parse_yaml`，`.txt` -> `parse_natural_language`。对不支持的格式或缺少 NL 需求时抛出 `ValueError`。
- **`json_parser.py`** -- `parse_json(path, url) -> list[TestCase]`。支持结构化格式（包含 `data` 字典的对象）和扁平格式（整个对象作为字段->值映射）。单个对象自动包装为列表。
- **`yaml_parser.py`** -- `parse_yaml(path, url) -> list[TestCase]`。与 JSON 解析器结构相同，使用 `yaml.safe_load`。
- **`csv_parser.py`** -- `parse_csv(path, url) -> list[TestCase]`。使用 `csv.DictReader`。将元数据键（`test_id`、`url`、`description`、`expected_outcome`）与数据键分离。每行为一个测试用例。
- **`excel_parser.py`** -- `parse_excel(path, url) -> list[TestCase]`。使用 `openpyxl`。第一行为表头，后续行为测试用例。元数据/数据键分离方式与 CSV 相同。
- **`nl_parser.py`** -- `parse_natural_language(path, url, settings, page_context) -> list[TestCase]`。两阶段解析：通过 `_build_field_description()` 从 DOM 上下文构建字段描述，然后发送含表单字段 + 用户文本的 LLM 提示。从 LLM 响应中提取 JSON，去除 Markdown 代码围栏。要求必须提供 `page_context`（缺少时抛出 `ValueError`）。

### `src/reporting/` -- 报告生成器

- **`json_report.py`** -- `save_json_report(report, test_case_id) -> str`。写入 `reports/{test_case_id}_report.json`。
- **`html_report.py`** -- `save_html_report(report, test_case_id) -> str`。通过 Jinja2 渲染 `templates/report.html`，启用自动转义。写入 `reports/{test_case_id}_report.html`。

### `src/tools/` -- CrewAI Tool 封装

10 个工具类，均遵循 BaseTool 模式，包含 `_run()` 方法和自愈回退机制：

| 工具 | 名称 | 输入 Schema | 描述 |
|------|------|------------|------|
| `ScreenshotTool` | "Screenshot" | `ScreenshotInput(save_path)` | 全页截图，自动生成带时间戳的文件名 |
| `ScreenshotAnalysisTool` | "Screenshot Analysis" | `ScreenshotAnalysisInput(question)` | VLM 驱动：截图后 base64 编码，发送到 OpenAI 视觉 API |
| `DOMExtractorTool` | "DOM Extractor" | `DOMExtractorInput()`（无参数） | 通过 JavaScript `page.evaluate()` 提取所有表单字段、按钮、步骤指示器、错误 |
| `FillInputTool` | "Fill Input" | `FillInputInput(selector, value)` | 主策略：`locator.fill()` + Escape。回退：带延迟的 `press_sequentially()` |
| `SelectOptionTool` | "Select Option" | `SelectOptionInput(selector, label, value)` | 3 种策略：原生 `<select>`、react-select（输入 + 点击选项）、通用下拉框 |
| `CheckboxTool` | "Checkbox Toggle" | `CheckboxInput(selector, check)` | 主策略：`check()`/`uncheck()`。回退：点击 label、强制点击。预先关闭弹出层 |
| `ClickButtonTool` | "Click Button" | `ClickButtonInput(selector, wait_for_navigation)` | 主策略：Playwright 点击 + networkidle 等待。回退：JS `el.click()` |
| `DatePickerTool` | "Date Picker" | `DatePickerInput(selector, value)` | 3 种策略：三击 + 输入 + Escape、直接 fill、JS 值注入并触发事件 |
| `UploadFileTool` | "Upload File" | `UploadFileInput(selector, file_path)` | 验证文件存在后使用 `set_input_files()`。无回退策略 |
| `GetValidationErrorsTool` | "Get Validation Errors" | `GetValidationErrorsInput()`（无参数） | JavaScript 提取：基于 CSS 类 + HTML5 validity。按消息去重 |

### `src/utils/logging.py` -- 日志配置

- **`setup_logging()`** -- 配置 Loguru，包含两个输出：stderr（可配置级别，彩色格式）和文件（`reports/ui_agent.log`，DEBUG 级别，10MB 轮转，7 天保留）。

### `templates/report.html` -- Jinja2 报告模板

带 CSS 样式的 HTML 报告，包含：
- 摘要区域：状态徽章（PASS/FAIL/PARTIAL）、URL、耗时、token 统计
- 每页卡片：任务计时条（analyze/map/fill/verify）、字段结果表格、验证错误
- 响应式网格布局

### `test_server/app.py` -- Flask 测试服务器

一个 Flask 应用，提供 3 步保险表单，用于本地集成测试。

### `test_data/` -- 示例测试文件

7 个不同格式的示例文件：JSON（结构化）、JSON（扁平）、YAML、CSV、多步骤 JSON、多步骤 YAML 和 NL 文本。

---

## 命名规范

| 类别 | 规范 | 示例 |
|------|------|------|
| **文件** | `snake_case.py` | `form_test_flow.py`、`dom_extractor_tool.py`、`page_result.py` |
| **类** | `PascalCase` | `FormTestFlow`、`FillInputTool`、`BrowserManager`、`TestCase` |
| **函数/方法** | `snake_case` | `parse_test_file`、`create_page_analyzer`、`setup_logging` |
| **智能体工厂** | `create_<role>(page, llm, settings=None) -> Agent` | `create_page_analyzer`、`create_form_filler` |
| **工具类** | `<Action>Tool` + `<Action>Input` | `FillInputTool` / `FillInputInput`、`DatePickerTool` / `DatePickerInput` |
| **私有成员** | `_` 前缀 | `self._browser`、`self._settings`、`self._page` |
| **常量** | Pydantic `Field(default=...)` | 不使用模块级 `UPPER_CASE`；配置字段在 `Settings` 中定义 |
| **测试类** | `Test<ClassName>` | `TestFillInputTool`、`TestFormTestFlow` |
| **测试方法** | `test_<scenario>` | `test_fill_success`、`test_parse_json_structured` |

## 导入规范

- 所有模块以 `from __future__ import annotations` 开头（PEP 604 联合类型）。
- 导入顺序：标准库 -> 第三方库 -> 本地模块（`src.*`）。各组之间空一行。
- 从项目根目录使用绝对导入：`from src.models import TestCase`。
- 例外：解析器在包内使用相对导入：`from .json_parser import parse_json`。

## 格式规范

- 4 空格缩进，不使用制表符
- 最大行宽约 88 字符（兼容 Black）
- 多行集合和函数签名使用尾随逗号
- 全部使用双引号

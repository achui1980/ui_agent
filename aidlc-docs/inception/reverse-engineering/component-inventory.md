# 组件清单

**AI-DLC 阶段：** 启动 / 逆向工程
**日期：** 2026-02-28
**项目：** UI Agent - 基于 AI 的 Web 表单测试系统

---

## 概要

| 类别 | 数量 | 组件 |
|------|------|------|
| 智能体 | 4 | PageAnalyzer、FieldMapper、FormFiller、ResultVerifier |
| 工具 | 10 | Screenshot、ScreenshotAnalysis、DOMExtractor、FillInput、SelectOption、Checkbox、ClickButton、DatePicker、UploadFile、GetValidationErrors |
| 解析器 | 5+1 | JSON、YAML、CSV、Excel、NL + ParserFactory |
| 模型 | 4 | TestCase、FieldActionResult、PageResult、TestReport |
| 报告器 | 2 | JsonReport、HtmlReport |
| 流程 | 2 | FormTestFlow、PageCrew |
| 浏览器 | 1 | BrowserManager |
| 配置 | 1 | Settings + get_settings() |

---

## 智能体（4 个）

### 1. Page Analyzer

| 属性 | 值 |
|------|---|
| **工厂函数** | `create_page_analyzer(page, llm, settings)` |
| **文件** | `src/agents/page_analyzer.py` |
| **角色** | "Page Analyzer" |
| **职责** | 分析当前表单页面：提取所有字段的 CSS 选择器、标签、类型和选项。识别导航按钮和验证错误。结合 DOM 提取与 VLM 视觉分析，检测自定义组件（react-select、日期选择器）。 |
| **工具** | `DOMExtractorTool`、`ScreenshotTool`、`ScreenshotAnalysisTool`（有条件启用——仅在 `settings.vlm_model` 配置时添加） |
| **输入** | Playwright `Page` 实例、CrewAI `LLM`、可选 `Settings` |
| **输出** | 包含 `page_id`、`fields[]`、`nav_button`、`existing_errors[]`、`screenshot_path`、`visual_notes` 的 JSON |

### 2. Field Mapper

| 属性 | 值 |
|------|---|
| **工厂函数** | `create_field_mapper(llm)` |
| **文件** | `src/agents/field_mapper.py` |
| **角色** | "Field Mapper" |
| **职责** | 将测试数据字段名与页面表单字段标签进行语义匹配。处理名称差异、值格式转换、日期拆分，以及级联下拉框的字段排序。 |
| **工具** | 无（纯 LLM 推理） |
| **输入** | 仅需 CrewAI `LLM`（无需页面引用） |
| **输出** | 包含 `mappings[]`（field_id、selector、value、action_type、execution_order、wait_after_ms）、`unmapped_fields[]`、`consumed_keys[]` 的 JSON |
| **上下文** | 接收 analyze_task 的输出 |

### 3. Form Filler

| 属性 | 值 |
|------|---|
| **工厂函数** | `create_form_filler(page, llm)` |
| **文件** | `src/agents/form_filler.py` |
| **角色** | "Form Filler" |
| **职责** | 根据字段映射精确执行表单填写操作。按执行顺序处理字段，处理级联下拉框的等待，完成后点击提交/下一步。单个字段失败时继续执行。 |
| **工具** | `FillInputTool`、`SelectOptionTool`、`CheckboxTool`、`ClickButtonTool`、`DatePickerTool`、`UploadFileTool` |
| **输入** | Playwright `Page` 实例、CrewAI `LLM` |
| **输出** | 包含 `field_results[]`（field_id、selector、value、status、error_message）、`submit_clicked`、`submit_error` 的 JSON |
| **上下文** | 接收 map_task 的输出 |

### 4. Result Verifier

| 属性 | 值 |
|------|---|
| **工厂函数** | `create_result_verifier(page, llm, settings)` |
| **文件** | `src/agents/result_verifier.py` |
| **角色** | "Result Verifier" |
| **职责** | 验证表单提交结果。检测验证错误，确认页面跳转，识别包含确认号或成功消息的完成页面。 |
| **工具** | `ScreenshotTool`、`GetValidationErrorsTool` |
| **输入** | Playwright `Page` 实例、CrewAI `LLM`、可选 `Settings` |
| **输出** | 包含 `passed`、`page_transitioned`、`new_page_id`、`is_final_page`、`validation_errors[]`、`screenshot_path` 的 JSON |
| **上下文** | 接收 analyze_task + fill_task 的输出 |

---

## 工具（10 个）

所有工具继承自 `crewai.tools.BaseTool`，遵循统一模式：
- 每个工具都有 `<Name>Input(BaseModel)` 输入 Schema 类和 `<Name>Tool(BaseTool)` 工具类
- `page: Any` 字段持有 Playwright `Page` 实例（配置 `model_config = {"arbitrary_types_allowed": True}`）
- `_run()` 返回状态字符串：`"SUCCESS: ..."`、`"HEALED: ..."` 或 `"FAILED: ..."`
- 自愈机制：主策略在外层 try 中，回退策略在内层 try 中，`FAILED` 在内层 except 中

### 1. ScreenshotTool

| 属性 | 值 |
|------|---|
| **文件** | `src/tools/screenshot_tool.py` |
| **名称** | "Screenshot" |
| **输入** | `save_path: str = ""`（可选；自动生成带时间戳的文件名） |
| **输出** | `"SUCCESS: Screenshot saved to {path}"` 或 `"FAILED: ..."` |
| **行为** | 通过 `page.screenshot(full_page=True)` 进行全页截图。按需创建 `screenshot_dir` 目录。 |
| **配置** | `screenshot_dir: str = "reports/screenshots"` |
| **回退** | 无 |

### 2. ScreenshotAnalysisTool

| 属性 | 值 |
|------|---|
| **文件** | `src/tools/screenshot_analysis_tool.py` |
| **名称** | "Screenshot Analysis" |
| **输入** | `question: str`（默认为全面的表单分析提示） |
| **输出** | `"SUCCESS: Visual analysis of {path}:\n\n{analysis}"` 或 `"HEALED: Screenshot saved but VLM failed"` 或 `"FAILED: ..."` |
| **行为** | 截图后 base64 编码，发送到 OpenAI 视觉 API，附带关于表单元素、自定义组件、错误和布局的详细提示。 |
| **配置** | `vlm_model`、`vlm_api_key`、`vlm_api_base`、`vlm_max_tokens`、`screenshot_dir` |
| **回退** | 若 VLM 调用失败，返回 HEALED 并附带截图路径，建议依赖 DOM 提取 |

### 3. DOMExtractorTool

| 属性 | 值 |
|------|---|
| **文件** | `src/tools/dom_extractor_tool.py` |
| **名称** | "DOM Extractor" |
| **输入** | 无（无参数） |
| **输出** | 包含 `fields[]`、`buttons[]`、`step_indicator`、`existing_errors[]`、`page_title`、`url` 的 JSON 字符串 |
| **行为** | 通过 `page.evaluate()` 执行 JavaScript，查询所有 `input`、`select`、`textarea`、`[role="combobox"]`、`[role="listbox"]` 元素。提取 tag、type、id、name、selector、label、required、visible、enabled、value、options、group。同时检测按钮（`button`、`input[type="submit"]`、`[role="button"]`、`a.btn`）、步骤指示器（`[class*="step"]`、`[class*="progress"]`、`[class*="wizard"]`）和验证错误（`.error`、`.invalid`、`[role="alert"]`）。按 id/name 去重。 |
| **回退** | 无（单层 try/except） |

### 4. FillInputTool

| 属性 | 值 |
|------|---|
| **文件** | `src/tools/fill_input_tool.py` |
| **名称** | "Fill Input" |
| **输入** | `selector: str`、`value: str` |
| **输出** | `"SUCCESS: Filled '{selector}' with '{value}'"` 或 `"HEALED: Filled with slow typing"` 或 `"FAILED: ..."` |
| **行为** | 主策略：`locator.fill(value)` 然后 `press("Escape")` 关闭弹出窗口，等待 200ms。 |
| **回退** | 点击、清空、`press_sequentially(value, delay=50)`、Escape、等待 200ms |

### 5. SelectOptionTool

| 属性 | 值 |
|------|---|
| **文件** | `src/tools/select_option_tool.py` |
| **名称** | "Select Option" |
| **输入** | `selector: str`、`label: str = ""`、`value: str = ""` |
| **输出** | `"SUCCESS: ..."` 或 `"HEALED: ..."` 或 `"FAILED: ..."` |
| **行为** | 三策略方案： |
| **策略 1** | 原生 `<select>`：检测标签，使用 `select_option(label=...)` 或 `select_option(value=...)`。模糊匹配回退（大小写不敏感的子串匹配）。 |
| **策略 2** | React-select：查找 `id*='react-select'` 或 `role='combobox'` 的输入框，点击容器，输入过滤文本，点击匹配选项。回退：按 Enter 选择第一个过滤结果。最后手段：输入 + Enter。 |
| **策略 3** | 通用下拉框：点击触发器打开下拉，通过 `[role='option']`、`[role='listbox']` 或含匹配文本的 `li` 查找选项。 |

### 6. CheckboxTool

| 属性 | 值 |
|------|---|
| **文件** | `src/tools/checkbox_tool.py` |
| **名称** | "Checkbox Toggle" |
| **输入** | `selector: str`、`check: bool = True` |
| **输出** | `"SUCCESS: Checked/Unchecked '{selector}'"` 或 `"HEALED: ..."` 或 `"FAILED: ..."` |
| **行为** | 先按 `Escape` 键关闭覆盖层。主策略：`locator.check()` 或 `locator.uncheck()`。 |
| **回退 1** | 点击关联的 `label[for='...']` |
| **回退 2** | 强制点击元素 |

### 7. ClickButtonTool

| 属性 | 值 |
|------|---|
| **文件** | `src/tools/click_button_tool.py` |
| **名称** | "Click Button" |
| **输入** | `selector: str`、`wait_for_navigation: bool = True` |
| **输出** | `"SUCCESS: Clicked '{selector}'"` 或 `"HEALED: JS-clicked"` 或 `"FAILED: ..."` |
| **行为** | 主策略：Playwright `locator.click()` + 可选的 `wait_for_load_state("networkidle")`，超时 30 秒。 |
| **回退** | 通过 `eval_on_selector` 执行 JavaScript `el.click()`，同样等待导航 |

### 8. DatePickerTool

| 属性 | 值 |
|------|---|
| **文件** | `src/tools/date_picker_tool.py` |
| **名称** | "Date Picker" |
| **输入** | `selector: str`、`value: str`（YYYY-MM-DD、MM/DD/YYYY 或 'DD Mon YYYY'） |
| **输出** | `"SUCCESS: Date filled..."` 或 `"HEALED: ..."` 或 `"FAILED: ..."` |
| **策略 1** | 三击全选，`press_sequentially(value, delay=50)`，按 Escape 关闭日历，等待 300ms。适用于 react-datepicker。 |
| **策略 2** | 直接 `locator.fill(value)`。适用于原生日期输入。 |
| **策略 3** | JavaScript 值注入：通过 `HTMLInputElement.prototype.value` setter 设置值，触发 `input`、`change`、`blur` 事件。 |

### 9. UploadFileTool

| 属性 | 值 |
|------|---|
| **文件** | `src/tools/upload_file_tool.py` |
| **名称** | "Upload File" |
| **输入** | `selector: str`、`file_path: str` |
| **输出** | `"SUCCESS: Uploaded '{file_path}' to '{selector}'"` 或 `"FAILED: ..."` |
| **行为** | 通过 `os.path.isfile()` 验证文件存在后，使用 `locator.set_input_files(file_path)`。 |
| **回退** | 无 |

### 10. GetValidationErrorsTool

| 属性 | 值 |
|------|---|
| **文件** | `src/tools/validation_error_tool.py` |
| **名称** | "Get Validation Errors" |
| **输入** | 无（无参数） |
| **输出** | `{message, field_selector, field_label}` 对象的 JSON 数组字符串 |
| **行为** | 双策略 JavaScript 提取：（1）基于 CSS 类（`.error`、`.invalid`、`[role="alert"]` 等），通过最近的 `.form-group`/`.field-wrapper` 检测关联字段。（2）HTML5 validity API（`checkValidity()` + `validationMessage`）。按消息文本去重。 |
| **回退** | 无（单层 try/except） |

---

## 解析器（5 + 1 工厂）

### ParserFactory

| 属性 | 值 |
|------|---|
| **文件** | `src/parsers/parser_factory.py` |
| **函数** | `parse_test_file(path, url, settings=None, page_context=None) -> list[TestCase]` |
| **职责** | 根据文件扩展名分发到对应解析器。验证 NL 解析的前置条件（settings + page_context）。 |
| **扩展名** | `.xlsx`/`.xls` -> Excel、`.csv` -> CSV、`.json` -> JSON、`.yaml`/`.yml` -> YAML、`.txt` -> NL |

### JSON 解析器

| 属性 | 值 |
|------|---|
| **文件** | `src/parsers/json_parser.py` |
| **函数** | `parse_json(path, url) -> list[TestCase]` |
| **格式** | 结构化（带 `data` 键）和扁平（整个对象作为数据）。单个对象自动包装。 |

### YAML 解析器

| 属性 | 值 |
|------|---|
| **文件** | `src/parsers/yaml_parser.py` |
| **函数** | `parse_yaml(path, url) -> list[TestCase]` |
| **格式** | 与 JSON 解析器相同。使用 `yaml.safe_load`。 |

### CSV 解析器

| 属性 | 值 |
|------|---|
| **文件** | `src/parsers/csv_parser.py` |
| **函数** | `parse_csv(path, url) -> list[TestCase]` |
| **格式** | 表头行 + 数据行。元数据键（`test_id`、`url`、`description`、`expected_outcome`）与数据键分离。使用 `csv.DictReader`。 |

### Excel 解析器

| 属性 | 值 |
|------|---|
| **文件** | `src/parsers/excel_parser.py` |
| **函数** | `parse_excel(path, url) -> list[TestCase]` |
| **格式** | 与 CSV 结构相同。使用 `openpyxl.load_workbook(read_only=True)`。少于 2 行时抛出 `ValueError`。 |

### 自然语言解析器

| 属性 | 值 |
|------|---|
| **文件** | `src/parsers/nl_parser.py` |
| **函数** | `parse_natural_language(path, url, settings, page_context) -> list[TestCase]`、`_build_field_description(fields) -> str` |
| **职责** | 两阶段 NL 解析。从 DOM 上下文构建感知字段的 LLM 提示。LLM 提取与实际表单字段匹配的结构化键值对。处理 Markdown 代码围栏去除。 |
| **前置条件** | `page_context` 为必填（缺少时抛出 `ValueError`）。`Settings` 用于 LLM 配置。 |

---

## 模型（4 个）

### TestCase

| 属性 | 值 |
|------|---|
| **文件** | `src/models/test_case.py` |
| **字段** | `test_id: str`、`url: str`、`data: dict[str, str]`、`description: str = ""`、`expected_outcome: str = "success"` |
| **职责** | 单个测试用例的规范表示。`data` 将字段名映射到值。 |

### FieldActionResult

| 属性 | 值 |
|------|---|
| **文件** | `src/models/page_result.py` |
| **字段** | `field_id: str`、`selector: str`、`value: str`、`status: str`（success/failed/healed）、`error_message: str = ""` |
| **职责** | 单次字段填写操作的结果。 |

### PageResult

| 属性 | 值 |
|------|---|
| **文件** | `src/models/page_result.py` |
| **字段** | `page_index: int`、`page_id: str`、`fields_filled: list[FieldActionResult]`、`verification_passed: bool`、`validation_errors: list[str] = []`、`retry_count: int = 0`、`screenshot_path: str = ""`、`duration_seconds: float = 0.0`、`task_durations: dict[str, float] = {}`、`token_usage: dict[str, int] = {}` |
| **职责** | 处理单个表单页面的结果（包含所有重试）。 |

### TestReport

| 属性 | 值 |
|------|---|
| **文件** | `src/models/report.py` |
| **字段** | `test_case_id: str`、`url: str`、`overall_status: str`（PASS/FAIL/PARTIAL）、`total_pages: int`、`pages_completed: int`、`pages: list[PageResult]`、`screenshots: list[str]`、`start_time: str`、`end_time: str`、`duration_seconds: float`、`total_tokens: int = 0`、`prompt_tokens: int = 0`、`completion_tokens: int = 0` |
| **职责** | 完整的测试运行报告，包含汇总指标。 |

---

## 报告器（2 个）

### JSON 报告

| 属性 | 值 |
|------|---|
| **文件** | `src/reporting/json_report.py` |
| **函数** | `save_json_report(report: dict, test_case_id: str) -> str` |
| **输出** | `reports/{test_case_id}_report.json` |
| **行为** | 创建 `reports/` 目录，以 indent=2、ensure_ascii=False 写入 JSON。 |

### HTML 报告

| 属性 | 值 |
|------|---|
| **文件** | `src/reporting/html_report.py` |
| **函数** | `save_html_report(report: dict, test_case_id: str) -> str` |
| **输出** | `reports/{test_case_id}_report.html` |
| **行为** | 通过 Jinja2 `FileSystemLoader` 加载 `templates/report.html`，启用自动转义。以 `report` 上下文变量渲染。 |

---

## 流程组件（2 个）

### FormTestFlow

| 属性 | 值 |
|------|---|
| **文件** | `src/flow/form_test_flow.py` |
| **类** | `FormTestFlow(Flow[FormTestState])` |
| **状态** | `FormTestState(BaseModel)` -- 20 余个字段，跟踪输入、已解析的测试用例、页面循环状态和最终结果 |
| **职责** | 作为 CrewAI Flow 状态机编排完整的测试运行。处理 NL 预分析路由、带重试的页面处理循环以及最终报告生成。 |
| **关键方法** | `parse_test_case()`（@start）、`route_after_parse()`（@router）、`pre_analyze_page()`（@listen）、`open_browser_and_navigate()`（@listen）、`_run_page_loop()`、`process_page()`、`_update_state_from_crew_result()`、`generate_report()`（@listen）、`_load_test_case()`、`_extract_json()`（static） |
| **入口** | `flow.kickoff()` 返回 `dict`（序列化的 TestReport） |

### PageCrew（build_page_crew）

| 属性 | 值 |
|------|---|
| **文件** | `src/flow/page_crew.py` |
| **函数** | `build_page_crew(page: Page, settings: Settings) -> Crew` |
| **职责** | 为处理单个表单页面构建 4 智能体顺序执行的 `Crew`。创建 LLM 实例，实例化智能体，定义 4 个带上下文链的任务。 |
| **任务** | analyze -> map（上下文：analyze）-> fill（上下文：map）-> verify（上下文：analyze + fill） |
| **执行模式** | `Process.sequential` |

---

## 浏览器（1 个）

### BrowserManager

| 属性 | 值 |
|------|---|
| **文件** | `src/browser/browser_manager.py` |
| **类** | `BrowserManager` |
| **职责** | 管理 Playwright 浏览器生命周期：启动、导航、关闭。从 Settings 读取无头模式、代理、视口、超时等配置。 |
| **关键方法** | `start() -> Page`、`navigate(url: str) -> None`、`close() -> None` |
| **属性** | `page: Page`（未启动时抛出 `RuntimeError`） |
| **状态** | `_playwright`、`_browser`、`_context`、`_page`（均为私有，可为空） |

---

## 配置（1 个）

### Settings

| 属性 | 值 |
|------|---|
| **文件** | `src/config.py` |
| **类** | `Settings(BaseSettings)` |
| **职责** | 通过 `.env` 文件集中管理所有配置。17 个字段涵盖 LLM、浏览器、智能体工作流和日志设置。 |
| **工厂函数** | `get_settings() -> Settings` |
| **模型配置** | `env_file=".env"`、`env_file_encoding="utf-8"`、`extra="ignore"` |

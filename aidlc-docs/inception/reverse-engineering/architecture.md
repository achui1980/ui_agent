# 系统架构 - UI Agent

**AI-DLC 阶段**: 启动 / 逆向工程
**生成日期**: 2026-02-28
**项目**: UI Agent - AI 驱动的 Web 表单测试系统

---

## 1. 系统架构概览

系统分为四个层次，各层职责边界清晰：

```
+------------------------------------------------------------------+
|                        CLI Layer (Click)                          |
|  main.py: run | validate | analyze                               |
+------------------------------------------------------------------+
         |                    |                    |
         v                    v                    v
+------------------------------------------------------------------+
|                   Flow Layer (CrewAI Flow)                        |
|  FormTestFlow: state machine with @start/@listen/@router         |
|  FormTestState: Pydantic model for accumulated state             |
+------------------------------------------------------------------+
         |
         v  (per page, in a loop)
+------------------------------------------------------------------+
|                   Crew Layer (CrewAI Crew)                        |
|  build_page_crew(): 4-agent sequential Crew per page             |
|  Agents: PageAnalyzer -> FieldMapper -> FormFiller -> Verifier   |
+------------------------------------------------------------------+
         |
         v  (agents invoke tools)
+------------------------------------------------------------------+
|                  Tool Layer (Playwright)                          |
|  9 browser tools + 1 VLM tool                                   |
|  DOMExtractor | Screenshot | ScreenshotAnalysis | FillInput |   |
|  SelectOption | Checkbox | ClickButton | DatePicker |           |
|  UploadFile | GetValidationErrors                                |
+------------------------------------------------------------------+
         |
         v
+------------------------------------------------------------------+
|                   Browser (Playwright Chromium)                   |
|  BrowserManager: sync API lifecycle (start/navigate/close)       |
+------------------------------------------------------------------+
```

---

## 2. 各层详述

### 2.1 CLI 层 (`src/main.py`)

使用 Click 框架的入口点，包含三个命令：

| 命令 | 参数 | 说明 |
|---|---|---|
| `run` | `test_file --url --max-pages --max-retries` | 完整的表单测试执行 |
| `validate` | `test_file --url` | 仅解析和校验，不执行测试 |
| `analyze` | `url --visual/--no-visual` | 从页面提取表单字段信息 |

CLI 在顶层处理自然语言文件与结构化文件的路由分发：
- `.txt` 文件：将 `test_input_path` 传递给 Flow（解析过程需要浏览器）
- 其他文件：通过 `parse_test_file()` 预先解析，然后遍历 `TestCase` 对象

### 2.2 Flow 层 (`src/flow/form_test_flow.py`)

CrewAI Flow 状态机，管理整个测试生命周期。

**状态模型** (`FormTestState`)：
```
FormTestState(BaseModel):
  test_input_path, target_url          # 输入
  test_case_data, test_case_id         # 解析后的测试用例
  page_context                         # DOM 字段（用于 NL 解析）
  current_page_index, consumed_fields  # 页面循环追踪
  page_results                         # 累积的各页面结果
  verification_passed, retry_count     # 当前页面状态
  validation_errors                    # 当前页面错误
  overall_status, screenshots          # 最终输出
  start_time                           # 计时
```

**Flow 事件链（标准路径）**：
```
@start parse_test_case
    |
    +--[@router]--> "open_browser"
                       |
                       +--[@listen]--> open_browser_and_navigate
                                          |
                                          +--> _run_page_loop()
                                                  |
                                                  +--> process_page() [loop]
                                                  |       |
                                                  |       +--> build_page_crew()
                                                  |       +--> crew.kickoff()
                                                  |       +--> _update_state_from_crew_result()
                                                  |
                                                  +--> [decide: next_page / retry / complete]
                                                  |
                                                  +--> generate_report()
```

**Flow 事件链（NL 路径）**：
```
@start parse_test_case
    |
    +--[@router]--> "pre_analyze"
                       |
                       +--[@listen]--> pre_analyze_page
                                          |
                                          +--> BrowserManager.start()
                                          +--> DOMExtractorTool._run()
                                          +--> parse_test_file(page_context=...)
                                          +--> _run_page_loop()  (same loop)
```

**重要架构说明**：`_run_page_loop()` 是一个手动的 while 循环，直接驱动 `process_page()`。它不能使用 `@listen`/`@router` 装饰器，因为 CrewAI Flow 的事件系统仅在方法由 Flow 调度器调用时触发，通过直接 Python 调用则不会触发。

### 2.3 Crew 层 (`src/flow/page_crew.py`)

为每次页面迭代构建一个包含 4 个智能体的顺序执行 `Crew`。

```
build_page_crew(page, settings) -> Crew:
    +-- LLM(model, base_url, api_key)
    |
    +-- create_page_analyzer(page, llm, settings)  --> Agent + tools
    +-- create_field_mapper(llm)                    --> Agent (no tools)
    +-- create_form_filler(page, llm)               --> Agent + tools
    +-- create_result_verifier(page, llm, settings) --> Agent + tools
    |
    +-- Task chain: analyze -> map -> fill -> verify
    |   (each task receives context from previous tasks)
    |
    +-- Crew(process=Process.sequential, verbose=True)
```

Crew 在启动时接收以下输入：
- `test_data`：剩余测试用例字段的 JSON 字符串
- `consumed_fields`：已在先前页面填写的字段键的 JSON 列表
- `validation_errors`：上一次尝试的错误信息的 JSON 列表（用于重试）

### 2.4 Tool 层 (`src/tools/`)

十个工具类，各自封装 Playwright 浏览器操作：

| 工具 | 文件 | 说明 |
|---|---|---|
| DOM Extractor | `dom_extractor_tool.py` | 基于 JavaScript 的表单元素、按钮和错误信息提取 |
| Screenshot | `screenshot_tool.py` | 截取页面截图并保存到磁盘 |
| Screenshot Analysis | `screenshot_analysis_tool.py` | VLM 驱动的截图视觉分析 |
| Fill Input | `fill_input_tool.py` | 填写文本/邮箱/电话输入框（自愈机制：fill -> press_sequentially） |
| Select Option | `select_option_tool.py` | 按值或文本选择下拉选项 |
| Checkbox Toggle | `checkbox_tool.py` | 切换复选框/单选按钮（操作后按 Escape） |
| Click Button | `click_button_tool.py` | 按选择器点击任意按钮 |
| Date Picker | `date_picker_tool.py` | 填写日期选择器字段 |
| Upload File | `upload_file_tool.py` | 通过文件输入框上传文件 |
| Get Validation Errors | `validation_error_tool.py` | 从 DOM 检测校验错误信息 |

**智能体-工具分配关系**：
- Page Analyzer：DOMExtractor、Screenshot、ScreenshotAnalysis（可选）
- Field Mapper：（无——纯 LLM 推理）
- Form Filler：FillInput、SelectOption、Checkbox、ClickButton、DatePicker、UploadFile
- Result Verifier：Screenshot、GetValidationErrors

---

## 3. 数据流

### 3.1 端到端数据流

```
Test File                         Browser
(.json/.yaml/.csv/.xlsx/.txt)     (Playwright Chromium)
    |                                 |
    v                                 |
+----------+                          |
| Parser   |  TestCase                |
| Factory  |---+                      |
+----------+   |                      |
               v                      |
         +------------+               |
         | FormTest   |  start()      |
         | Flow       |-------------->|
         | (state     |               |
         |  machine)  |               |
         +-----+------+               |
               |                      |
               | per page loop        |
               v                      |
         +------------+               |
         | Page Crew  |               |
         | (4 agents) |               |
         +-----+------+               |
               |                      |
               | tool invocations     |
               v                      v
         +------------+     +-------------------+
         | Tool Layer |<--->| Playwright Page    |
         | (9 tools)  |     | (shared instance)  |
         +-----+------+     +-------------------+
               |
               | per-page results
               v
         +------------+
         | Report     |  JSON + HTML
         | Generator  |-----------> reports/
         +------------+
```

### 3.2 页面内部数据流（Crew 内部）

```
                      test_data (JSON)
                      consumed_fields
                      validation_errors
                            |
                            v
+------------------+   DOM fields JSON    +------------------+
| Page Analyzer    |--------------------->| Field Mapper     |
| (DOM + VLM +     |   screenshot path    | (pure LLM)      |
|  screenshot)     |                      |                  |
+------------------+                      +--------+---------+
                                                   |
                                          mappings JSON
                                          (field->value->selector)
                                                   |
                                                   v
                                          +------------------+
                                          | Form Filler      |
                                          | (6 browser tools)|
                                          +--------+---------+
                                                   |
                                          field_results JSON
                                                   |
                                                   v
                                          +------------------+
                                          | Result Verifier  |
                                          | (screenshot +    |
                                          |  error check)    |
                                          +--------+---------+
                                                   |
                                                   v
                                          verification JSON
                                          (passed, new_page_id,
                                           is_final_page, errors)
```

---

## 4. 状态管理

### 4.1 Flow 状态 (`FormTestState`)

一个 Pydantic `BaseModel`，在整个测试运行过程中累积数据：

- **页面追踪**：`current_page_index` 随页面递增，`consumed_fields` 随跨页面填写字段而增长
- **重试逻辑**：`retry_count` 在页面前进时重置为 0，在验证失败时递增（最多 `max_retries` 次）
- **页面结果**：`page_results: list[dict]` 累积各页面的结果，包含字段级详情、耗时和 Token 用量
- **验证状态**：`verification_passed`、`validation_errors` 和 `current_page_id` 在每次页面迭代时被覆盖

### 4.2 Crew 结果解析

Flow 从最后一个 Crew 任务（Result Verifier）的输出中提取结构化数据：
1. 首先尝试将整个输出作为 JSON 解析
2. 回退为从文本中提取最后一个 JSON 对象（通过花括号匹配）
3. 最终回退为启发式关键词检测（输出中的 `"error"`、`"fail"`）

提取的关键字段：`passed`、`new_page_id`、`is_final_page`、`validation_errors`、`consumed_keys`、`field_results`、`screenshot_path`

---

## 5. 浏览器生命周期

`BrowserManager`（`src/browser/browser_manager.py`）封装了 Playwright 同步 API：

```
BrowserManager(settings)
    |
    +-- start() -> Page
    |     sync_playwright().start()
    |     chromium.launch(headless=..., proxy=...)
    |     browser.new_context(viewport=...)
    |     context.set_default_timeout(...)
    |     context.new_page()
    |
    +-- navigate(url)
    |     page.goto(url, wait_until="networkidle")
    |
    +-- page (property)
    |     Returns the shared Page instance
    |
    +-- close()
          context.close()
          browser.close()
          playwright.stop()
```

- 单个 `Page` 实例在测试运行中被所有智能体和工具共享
- 浏览器启动一次，在报告生成后（或发生错误时）关闭
- 在 NL 路径中，浏览器在 `pre_analyze_page()` 期间启动，并在页面循环中复用
- 可配置项：无头模式、代理、视口尺寸、超时时间（均通过 `.env` / `Settings` 配置）

---

## 6. 配置架构

所有配置通过 `src/config.py:Settings`（Pydantic BaseSettings）统一管理：

```
.env file
    |
    v
+-------------------+
| Settings          |  (pydantic-settings, env_file=".env")
|  openai_api_key   |
|  openai_api_base  |
|  llm_model        |  default: "gpt-5.2"
|  vlm_model        |  default: "gpt-5.2"
|  vlm_max_tokens   |  default: 1000
|  browser_headless  |  default: False
|  browser_timeout   |  default: 10000
|  browser_proxy     |
|  awa_max_steps     |  default: 50 (max pages)
|  awa_max_healing   |  default: 3 (max retries)
|  awa_screenshot_dir|  default: "reports/screenshots"
|  log_level         |  default: "INFO"
+-------------------+
    |
    +---> get_settings() -> Settings (factory function)
```

Settings 被注入到以下组件：
- `FormTestFlow`（构造时）
- `build_page_crew()`（通过智能体工厂函数传递）
- `BrowserManager`（浏览器配置）
- `NL parser`（NL 提取的 LLM 配置）

---

## 7. 错误处理架构

三个层次的错误处理，各层采用不同策略：

| 层次 | 策略 | 示例 |
|---|---|---|
| **Tool 层** | 自愈（try/回退/失败字符串） | `FillInputTool`：fill() -> press_sequentially() -> "FAILED: ..." |
| **Crew 层** | 智能体根据工具状态字符串决定下一步操作 | Form Filler 在某个字段失败时继续填写其他字段 |
| **Flow 层** | 重试逻辑 + 优雅降级 | 重试页面直至 `max_retries`，然后报告 PARTIAL/FAIL 状态 |

- 工具不会向智能体抛出异常
- 智能体不会向 Flow 抛出异常（CrewAI 处理智能体错误）
- Flow 通过启发式回退捕获 Crew 输出的 JSON 解析失败
- CLI 捕获解析器抛出的 `ValueError` 并输出到 stderr

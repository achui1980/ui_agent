# 依赖关系 - UI Agent

**AI-DLC 阶段**: 启动 / 逆向工程
**生成日期**: 2026-02-28
**项目**: UI Agent - AI 驱动的 Web 表单测试系统

---

## 1. 外部依赖

### 1.1 运行时依赖（来自 `pyproject.toml`）

| 包 | 版本约束 | 用途 |
|---|---|---|
| `crewai[tools]` | >= 0.86.0 | 多智能体编排框架。提供 Agent、Task、Crew、Flow、LLM、BaseTool。`[tools]` 附加包含额外的工具基础设施 |
| `openai` | >= 1.0 | OpenAI API 客户端，用于 LLM 和 VLM 调用（通过 CrewAI 的 LLM 封装间接使用，ScreenshotAnalysisTool 中直接使用） |
| `playwright` | >= 1.49.0 | 浏览器自动化（Chromium）。同步 API 用于页面交互。安装后需运行 `playwright install chromium` |
| `pydantic` | >= 2.0 | 数据建模与校验。所有模型、工具输入 Schema 和 Flow 状态均继承自 `BaseModel` |
| `pydantic-settings` | >= 2.0 | 配置管理。`Settings(BaseSettings)` 读取 `.env` 文件 |
| `openpyxl` | >= 3.1.0 | Excel 文件解析（.xlsx/.xls），用于测试数据输入 |
| `pyyaml` | >= 6.0 | YAML 文件解析，用于测试数据输入 |
| `python-dotenv` | >= 1.0 | `.env` 文件加载（被 pydantic-settings 使用） |
| `loguru` | >= 0.7 | 应用全局结构化日志 |
| `jinja2` | >= 3.1 | HTML 报告模板渲染 |
| `click` | >= 8.1 | `ui-agent` 命令的 CLI 框架 |

### 1.2 开发依赖（来自 `pyproject.toml [project.optional-dependencies.dev]`）

| 包 | 版本约束 | 用途 |
|---|---|---|
| `pytest` | >= 8.0 | 测试框架 |
| `pytest-asyncio` | >= 0.23 | 异步测试支持 |
| `flask` | >= 3.0 | 集成测试用的测试服务器 |

### 1.3 标准库依赖（无需安装）

| 模块 | 使用位置 | 用途 |
|---|---|---|
| `json` | 解析器、Flow、报告、工具 | JSON 解析与序列化 |
| `csv` | `csv_parser.py` | CSV 测试文件解析 |
| `os` | 多个模块 | 文件路径、目录创建 |
| `time` | `form_test_flow.py` | 计时与时长追踪 |
| `re` | `nl_parser.py` | 正则表达式用于 camelCase 转空格分隔 |
| `sys` | `main.py` | 出错时调用 `sys.exit()` |
| `typing` | 多个模块 | Playwright Page 的 `Any` 类型提示 |
| `unittest.mock` | 测试 | 模拟 Playwright Page 对象 |

---

## 2. 内部模块依赖

### 2.1 依赖映射

```
src/main.py
  +-- src/config.py (get_settings, Settings)
  +-- src/utils/logging.py (setup_logging)
  +-- src/parsers/parser_factory.py (parse_test_file)
  +-- src/flow/form_test_flow.py (FormTestFlow)
  +-- src/browser/browser_manager.py (BrowserManager)  [validate, analyze]
  +-- src/tools/dom_extractor_tool.py (DOMExtractorTool)  [validate, analyze]
  +-- src/tools/screenshot_tool.py (ScreenshotTool)  [analyze]
  +-- src/tools/screenshot_analysis_tool.py (ScreenshotAnalysisTool)  [analyze]

src/flow/form_test_flow.py
  +-- src/config.py (Settings, get_settings)
  +-- src/browser/browser_manager.py (BrowserManager)
  +-- src/flow/page_crew.py (build_page_crew)
  +-- src/models/ (TestCase, TestReport, PageResult, FieldActionResult)
  +-- src/parsers/parser_factory.py (parse_test_file)
  +-- src/reporting/json_report.py (save_json_report)
  +-- src/reporting/html_report.py (save_html_report)
  +-- src/tools/dom_extractor_tool.py (DOMExtractorTool)  [NL path only]

src/flow/page_crew.py
  +-- src/config.py (Settings)
  +-- src/agents/page_analyzer.py (create_page_analyzer)
  +-- src/agents/field_mapper.py (create_field_mapper)
  +-- src/agents/form_filler.py (create_form_filler)
  +-- src/agents/result_verifier.py (create_result_verifier)

src/agents/page_analyzer.py
  +-- src/config.py (Settings)
  +-- src/tools/dom_extractor_tool.py (DOMExtractorTool)
  +-- src/tools/screenshot_tool.py (ScreenshotTool)
  +-- src/tools/screenshot_analysis_tool.py (ScreenshotAnalysisTool)

src/agents/field_mapper.py
  (no local dependencies -- pure LLM agent, no tools)

src/agents/form_filler.py
  +-- src/tools/fill_input_tool.py (FillInputTool)
  +-- src/tools/select_option_tool.py (SelectOptionTool)
  +-- src/tools/checkbox_tool.py (CheckboxTool)
  +-- src/tools/click_button_tool.py (ClickButtonTool)
  +-- src/tools/date_picker_tool.py (DatePickerTool)
  +-- src/tools/upload_file_tool.py (UploadFileTool)

src/agents/result_verifier.py
  +-- src/config.py (Settings)
  +-- src/tools/screenshot_tool.py (ScreenshotTool)
  +-- src/tools/validation_error_tool.py (GetValidationErrorsTool)

src/tools/*
  (all tools depend on Playwright Page object, passed at construction)
  (all tools depend on crewai.tools.BaseTool, pydantic.BaseModel)

src/parsers/parser_factory.py
  +-- src/config.py (Settings)
  +-- src/models/test_case.py (TestCase)
  +-- src/parsers/json_parser.py (parse_json)
  +-- src/parsers/yaml_parser.py (parse_yaml)
  +-- src/parsers/csv_parser.py (parse_csv)
  +-- src/parsers/excel_parser.py (parse_excel)
  +-- src/parsers/nl_parser.py (parse_natural_language)

src/parsers/nl_parser.py
  +-- src/config.py (Settings)
  +-- src/models/test_case.py (TestCase)
  +-- crewai.LLM (for LLM.call() -- NL extraction)

src/reporting/json_report.py
  (no local dependencies -- uses json stdlib)

src/reporting/html_report.py
  (no local dependencies -- uses jinja2)
  (reads templates/report.html)

src/browser/browser_manager.py
  +-- src/config.py (Settings)

src/config.py
  (no local dependencies -- leaf module)
```

### 2.2 依赖关系图（ASCII）

```
                          +----------+
                          | main.py  |
                          +----+-----+
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
        +-----------+   +----------+   +----------------+
        | config.py |   | parsers/ |   | flow/          |
        +-----------+   +----+-----+   | form_test_flow |
              ^              |         +-------+--------+
              |              |                 |
              |         +----+----+    +-------+--------+
              |         |         |    |                |
              |         v         v    v                v
              |    +--------+ +------+------+    +-----------+
              |    | models/| | nl_parser   |    | flow/     |
              |    +--------+ | (uses LLM)  |    | page_crew |
              |         ^     +-------------+    +-----+-----+
              |         |                              |
              |         |          +-------------------+
              |         |          |         |         |
              |         |          v         v         v
              |         |   +----------+ +--------+ +----------+
              |         |   | agents/  | | agents/| | agents/  |
              |         |   | page_    | | field_ | | form_    |
              |         |   | analyzer | | mapper | | filler   |
              |         |   +----+-----+ +--------+ +----+-----+
              |         |        |                        |
              |         |        v                        v
              |         |   +----------+            +----------+
              |         +---| tools/   |            | tools/   |
              |             | DOM, SS, |            | Fill,    |
              |             | VLM      |            | Select,  |
              |             +----+-----+            | Click,   |
              |                  |                  | etc.     |
              |                  v                  +----+-----+
              |         +----------------+               |
              +---------| browser/       |<--------------+
                        | browser_manager|
                        +-------+--------+
                                |
                                v
                        +----------------+
                        | Playwright     |
                        | (Chromium)     |
                        +----------------+
```

---

## 3. 依赖流向总结

### 3.1 导入方向规则

- **自顶向下**：`main.py` -> `flow` -> `crew` -> `agents` -> `tools`
- **共享服务**：`config.py` 和 `models/` 在每一层都被导入
- **无循环依赖**：工具不导入智能体，智能体不导入 Flow
- **解析器隔离**：解析器在包内使用相对导入（`from .json_parser import parse_json`）
- **浏览器隔离**：`BrowserManager` 仅被 `main.py`（`validate`/`analyze` 命令）和 `form_test_flow.py` 导入

### 3.2 依赖注入模式

Playwright `Page` 对象是主要的共享依赖：
1. `BrowserManager.start()` 创建 `Page`
2. `Page` 传递给 `build_page_crew(page, settings)`
3. `build_page_crew` 将 `page` 传递给每个智能体工厂函数
4. 智能体工厂函数将 `page` 传递给每个工具的构造函数
5. 工具将 `page` 存储为属性并在 `_run()` 中使用

这意味着在一次测试运行中，所有工具操作的是同一个浏览器页面实例。

---

## 4. 已知依赖问题

### 4.1 `requirements.txt` 与 `pyproject.toml`

两个文件同时存在。`pyproject.toml` 是权威的依赖声明文件：

| `pyproject.toml` 中 | `requirements.txt` 中 | 备注 |
|---|---|---|
| `crewai[tools]>=0.86.0` | `crewai[tools]>=0.86.0` | 一致 |
| `openai>=1.0` | （缺失） | `requirements.txt` 不完整 |
| `playwright>=1.49.0` | `playwright>=1.49.0` | 一致 |
| `pydantic>=2.0` | `pydantic>=2.0` | 一致 |
| `pydantic-settings>=2.0` | `pydantic-settings>=2.0` | 一致 |
| `openpyxl>=3.1.0` | `openpyxl>=3.1.0` | 一致 |
| `pyyaml>=6.0` | `pyyaml>=6.0` | 一致 |
| `python-dotenv>=1.0` | `python-dotenv>=1.0` | 一致 |
| `loguru>=0.7` | `loguru>=0.7` | 一致 |
| `jinja2>=3.1` | `jinja2>=3.1` | 一致 |
| `click>=8.1` | `click>=8.1` | 一致 |

`requirements.txt` 缺少 `openai>=1.0` 且不包含开发依赖。它是一个补充文件，而非主要安装途径。

### 4.2 CrewAI 传递依赖

`crewai[tools]` 包引入了大量传递依赖，包括 LangChain 组件。这些依赖由 pip 的解析器管理，未被显式固定版本。

### 4.3 Playwright 安装后步骤

Playwright 在 `pip install` 之后需要一个单独的二进制安装步骤：
```bash
playwright install chromium
```
此步骤不会被 `pip install` 自动执行，必须手动运行或在 CI 中执行。

### 4.4 Conda 与 pip

项目使用 conda 进行环境隔离（`conda activate ui_agent`），但使用 pip 安装包（`pip install -e ".[dev]"`）。CI 不使用 conda——直接使用 `setup-python`。这意味着 conda 环境是本地开发的便利工具，并非硬性要求。

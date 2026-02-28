# API 文档

**AI-DLC 阶段：** 启动 / 逆向工程
**日期：** 2026-02-28
**项目：** UI Agent - 基于 AI 的 Web 表单测试系统

---

## CLI API

CLI 基于 Click 实现，位于 `src/main.py`，通过 `pyproject.toml` 注册为 `ui-agent` 控制台脚本。所有命令执行前需先激活 `ui_agent` conda 环境。

### `ui-agent run`

完整的表单测试执行。

```
ui-agent run <test_file> --url <url> [--max-pages N] [--max-retries N]
```

**参数：**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `test_file` | 位置参数 | 是 | -- | 测试数据文件路径（.json、.yaml、.yml、.csv、.xlsx、.xls、.txt） |
| `--url`, `-u` | 选项 | 是 | -- | 目标表单 URL |
| `--max-pages` | 选项 | 否 | 50 | 最大处理页数 |
| `--max-retries` | 选项 | 否 | 3 | 验证失败时每页最大重试次数 |

**行为：**
1. 对于 `.txt`（NL）文件：创建单个 `FormTestFlow`，设置状态后调用 `kickoff()`。Flow 内部处理浏览器启动、DOM 提取、NL 解析和表单测试。
2. 对于其他格式：先通过 `parse_test_file()` 解析测试用例。遍历每个测试用例，为每个用例创建新的 `FormTestFlow`。每个 Flow 打开新浏览器、处理所有表单页面、生成报告并关闭浏览器。

**输出：**
- JSON 报告：`reports/{test_case_id}_report.json`
- HTML 报告：`reports/{test_case_id}_report.html`
- 截图：`reports/screenshots/page_{timestamp}.png`
- 日志：`reports/ui_agent.log`（DEBUG 级别，10MB 轮转）
- 标准输出：进度日志（含测试用例 ID）及最终状态摘要

**退出行为：** 测试失败时不设置非零退出码（仅记录日志）。

---

### `ui-agent validate`

仅解析和验证测试用例文件，不执行表单测试。

```
ui-agent validate <test_file> [--url <url>]
```

**参数：**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `test_file` | 位置参数 | 是 | -- | 测试数据文件路径 |
| `--url`, `-u` | 选项 | 有条件 | `""` | 目标 URL。**`.txt` 文件必填**（NL 解析需要浏览器上下文） |

**行为：**
1. 对于 `.txt` 文件：验证是否提供了 `--url`。启动浏览器，导航到 URL，通过 `DOMExtractorTool` 提取 DOM 字段，然后使用页面上下文解析 NL 文本。在 `finally` 块中关闭浏览器。
2. 对于其他格式：直接解析，无需浏览器。

**输出（标准输出）：**
```
Parsed N test case(s):

  ID: test_case_1
  URL: https://example.com/form
  Fields: 7
  Expected: success
  Description: Sample insurance form test
  Data: {
      "first_name": "John",
      "last_name": "Smith",
      ...
  }
```

**退出码：** `.txt` 文件缺少 URL 或解析失败时以退出码 1 退出。

---

### `ui-agent analyze`

分析单个页面的表单字段，不进行填写。

```
ui-agent analyze <url> [--visual/--no-visual]
```

**参数：**
| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|-------|------|
| `url` | 位置参数 | 是 | -- | 要分析的页面 URL |
| `--visual/--no-visual` | 标志 | 否 | `--visual` | 启用/禁用 VLM 视觉分析 |

**行为：**
1. 启动浏览器，导航到 URL
2. 运行 `DOMExtractorTool` -- 提取所有表单字段、按钮、步骤指示器、验证错误
3. 运行 `ScreenshotTool` -- 保存页面截图
4. 若启用 `--visual` 且配置了 `vlm_model`：运行 `ScreenshotAnalysisTool` -- VLM 截图分析

**输出（标准输出）：**
```
=== DOM Extraction ===
{
  "fields": [...],
  "buttons": [...],
  "step_indicator": "Step 1 of 3",
  "existing_errors": [],
  "page_title": "Insurance Application",
  "url": "https://example.com/form"
}

SUCCESS: Screenshot saved to reports/screenshots/page_1709164800.png

=== Visual Analysis (VLM) ===
SUCCESS: Visual analysis of reports/screenshots/analysis_1709164800.png:

The page shows a multi-step insurance form...
```

---

## 环境变量

所有配置通过 `.env` 文件加载，由 `pydantic-settings` 读入 `src/config.py:Settings`。

### LLM 配置

| 变量 | 类型 | 默认值 | 描述 |
|------|------|-------|------|
| `OPENAI_API_KEY` | str | `""` | LLM 和 VLM 调用的 API 密钥 |
| `OPENAI_API_BASE` | str | `""` | 自定义 API 基础 URL（用于代理或替代提供商） |
| `HTTPS_PROXY` | str | `""` | 出站请求的 HTTPS 代理 |
| `LLM_MODEL` | str | `"gpt-5.2"` | 文本 LLM 模型名称（4 个智能体共用） |
| `VLM_MODEL` | str | `"gpt-5.2"` | 视觉 LLM 模型名称（ScreenshotAnalysisTool 使用） |
| `LLM_MAX_TOKENS` | int | `4096` | 文本 LLM 响应最大 token 数 |
| `VLM_MAX_TOKENS` | int | `1000` | VLM 响应最大 token 数 |

### 浏览器配置

| 变量 | 类型 | 默认值 | 描述 |
|------|------|-------|------|
| `BROWSER_HEADLESS` | bool | `False` | 以无头模式运行浏览器 |
| `BROWSER_TIMEOUT` | int | `10000` | 默认操作超时（毫秒） |
| `BROWSER_NAVIGATION_TIMEOUT` | int | `60000` | 导航超时（毫秒） |
| `BROWSER_VIEWPORT_WIDTH` | int | `1280` | 浏览器视口宽度（像素） |
| `BROWSER_VIEWPORT_HEIGHT` | int | `720` | 浏览器视口高度（像素） |
| `BROWSER_PROXY` | str | `""` | 浏览器代理服务器 URL |

### 智能体/工作流配置

| 变量 | 类型 | 默认值 | 描述 |
|------|------|-------|------|
| `AWA_MAX_STEPS` | int | `50` | 每次测试运行最大处理页数（映射到 `max_pages` 状态） |
| `AWA_MAX_HEALING_ATTEMPTS` | int | `3` | 每页最大重试次数（映射到 `max_retries` 状态） |
| `AWA_SCREENSHOT_DIR` | str | `"reports/screenshots"` | 截图保存目录 |

### 日志配置

| 变量 | 类型 | 默认值 | 描述 |
|------|------|-------|------|
| `LOG_LEVEL` | str | `"INFO"` | stderr 日志级别（DEBUG、INFO、WARNING、ERROR） |

---

## 测试数据格式

系统支持 6 种输入格式。所有格式均产出 `list[TestCase]`，每个 `TestCase` 包含：`test_id`、`url`、`data`（字段名 -> 值的字典）、`description`、`expected_outcome`。

### JSON -- 结构化格式

```json
[
  {
    "test_id": "insurance_basic",
    "description": "Basic insurance form test",
    "expected_outcome": "success",
    "data": {
      "first_name": "John",
      "last_name": "Smith",
      "email": "john@example.com",
      "date_of_birth": "01/15/1990"
    }
  }
]
```

也接受单个对象（不包裹在数组中）。数组中的多个对象会产出多个测试用例。

### JSON -- 扁平格式

```json
{
  "first_name": "John",
  "last_name": "Smith",
  "email": "john@example.com"
}
```

当不存在 `data` 键时，整个对象被视为字段->值数据。`test_id` 自动生成为 `json_1`、`json_2` 等。

### YAML

```yaml
test_id: insurance_basic
description: Basic insurance form test
expected_outcome: success
data:
  first_name: John
  last_name: Smith
  email: john@example.com
```

与 JSON 结构相同。支持结构化（带 `data` 键）和扁平格式。对象列表产出多个测试用例。

### CSV

```csv
test_id,first_name,last_name,email,date_of_birth,expected_outcome
insurance_1,John,Smith,john@example.com,01/15/1990,success
insurance_2,Jane,Doe,jane@example.com,03/22/1985,success
```

第一行为表头。名为 `test_id`、`url`、`description`、`expected_outcome` 的列为元数据；其余均为数据字段。每行数据为一个测试用例。空值会被跳过。

### Excel（.xlsx、.xls）

与 CSV 结构相同。第一行为表头，后续行为测试用例。使用 `openpyxl` 读取。元数据键分离方式相同。需要安装 `openpyxl`。

### 自然语言（.txt）

```
Fill out the insurance form for John Smith, born January 15, 1990.
Email is john@example.com, phone number 555-123-4567.
He lives in Illinois and is male.
```

**要求：** `--url` 标志为必填项。系统处理流程：
1. 打开浏览器并导航到目标 URL
2. 提取 DOM 字段信息（标签、类型、选项）作为 `page_context`
3. 发送含表单字段 + 用户文本的 LLM 提示
4. LLM 返回包含 `test_id`、`data`、`description` 的结构化 JSON

字段键从表单标签派生（snake_case），而非原始 DOM ID。日期值保持自然格式——下游表单填写智能体负责格式转换。

---

## 内部 API

### Flow API

```python
from src.flow.form_test_flow import FormTestFlow
from src.config import get_settings

settings = get_settings()
flow = FormTestFlow(settings=settings)
flow.state.test_input_path = "test.json"
flow.state.target_url = "https://example.com/form"
flow.state.max_pages = 50
flow.state.max_retries = 3
result = flow.kickoff()  # Returns dict (TestReport.model_dump())
```

### Parser API

```python
from src.parsers.parser_factory import parse_test_file
from src.config import get_settings

# 结构化格式
test_cases = parse_test_file("test.json", "https://example.com", get_settings())

# NL 格式（需要 page_context）
test_cases = parse_test_file("test.txt", "https://example.com", settings, page_context=dom_dict)
```

### Tool API

所有工具遵循以下模式：

```python
from src.tools.fill_input_tool import FillInputTool

tool = FillInputTool(page=playwright_page)
result = tool._run(selector="#first_name", value="John")
# result: "SUCCESS: Filled '#first_name' with 'John'"
#     or: "HEALED: Filled '#first_name' with slow typing"
#     or: "FAILED: Could not fill '#first_name': ..."
```

### Report API

```python
from src.reporting.json_report import save_json_report
from src.reporting.html_report import save_html_report

json_path = save_json_report(report_dict, "test_case_1")  # -> "reports/test_case_1_report.json"
html_path = save_html_report(report_dict, "test_case_1")  # -> "reports/test_case_1_report.html"
```

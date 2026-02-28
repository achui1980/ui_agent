# 技术栈 - UI Agent

**AI-DLC 阶段**: 启动 / 逆向工程
**生成日期**: 2026-02-28
**项目**: UI Agent - AI 驱动的 Web 表单测试系统

---

## 1. 运行时环境

| 组件 | 版本 | 备注 |
|---|---|---|
| **Python** | 3.11+ | 必需（`requires-python = ">=3.11"`）。使用小写泛型（`list[str]`、`dict[str, str]`），通过 `from __future__ import annotations` 支持 PEP 604 联合类型 |
| **Conda** | 任意版本 | 虚拟环境管理，环境名称：`ui_agent` |

---

## 2. AI / 智能体框架

| 组件 | 版本 | 作用 |
|---|---|---|
| **CrewAI** | >= 0.86.0 (`crewai[tools]`) | 多智能体编排框架。提供 `Agent`、`Task`、`Crew`、`Process`、`Flow`、`LLM`、`BaseTool`。`[tools]` 附加包含内置工具依赖 |
| **OpenAI API** | >= 1.0 (`openai`) | LLM 供应商（文本 + 视觉）。通过 CrewAI 的 `LLM` 封装访问。可配置模型、API 地址和 API 密钥（通过 `.env`） |

### 使用的 AI 模型

| 配置项 | 默认值 | 用途 |
|---|---|---|
| `LLM_MODEL` | `gpt-5.2` | 全部 4 个智能体和 NL 解析器使用的主 LLM |
| `VLM_MODEL` | `gpt-5.2` | 用于截图分析的视觉语言模型 |
| `VLM_MAX_TOKENS` | 1000 | VLM 响应的最大 Token 数 |
| `LLM_MAX_TOKENS` | 4096 | LLM 响应的最大 Token 数 |

系统通过配置 `OPENAI_API_BASE` 支持任何 OpenAI 兼容的 API。

---

## 3. 浏览器自动化

| 组件 | 版本 | 作用 |
|---|---|---|
| **Playwright** | >= 1.49.0 (`playwright`) | 浏览器自动化。仅使用同步 API（非异步）。Chromium 浏览器 |

### Playwright 使用方式

- **同步 API**：`sync_playwright().start()`、`chromium.launch()`、`page.goto()`、`page.locator()`、`page.evaluate()`
- **浏览器**：仅 Chromium（通过 `playwright install chromium` 安装）
- **共享 Page**：整个测试运行中所有工具共享单个 `Page` 实例
- **JavaScript 执行**：`DOMExtractorTool` 使用 `page.evaluate()` 配合内联 JS 来提取表单元素
- **可配置项**：无头模式、代理、视口尺寸、默认超时、导航超时

---

## 4. 数据建模

| 组件 | 版本 | 作用 |
|---|---|---|
| **Pydantic** | >= 2.0 (`pydantic`) | 数据模型（`TestCase`、`PageResult`、`FieldActionResult`、`TestReport`、`FormTestState`）。工具输入 Schema（`FillInputInput` 等） |
| **pydantic-settings** | >= 2.0 (`pydantic-settings`) | 配置管理。`Settings(BaseSettings)` 从 `.env` 文件读取配置，使用 `model_config = {"env_file": ".env", "extra": "ignore"}` |

### 主要模型

| 模型 | 位置 | 用途 |
|---|---|---|
| `TestCase` | `src/models/test_case.py` | 解析后的测试输入：`test_id`、`url`、`data: dict[str, str]`、`expected_outcome` |
| `FieldActionResult` | `src/models/page_result.py` | 逐字段结果：`field_id`、`selector`、`value`、`status`、`error_message` |
| `PageResult` | `src/models/page_result.py` | 逐页结果：已填写字段、验证状态、耗时、Token 用量 |
| `TestReport` | `src/models/report.py` | 完整测试报告：各页面、整体状态、持续时间、Token 汇总 |
| `FormTestState` | `src/flow/form_test_flow.py` | Flow 状态机：累积的页面结果、已消费字段、重试状态 |
| `Settings` | `src/config.py` | 所有配置（LLM、浏览器、日志） |

---

## 5. CLI

| 组件 | 版本 | 作用 |
|---|---|---|
| **Click** | >= 8.1 (`click`) | 命令行界面框架。`@click.group()` 包含 3 个子命令：`run`、`validate`、`analyze` |

在 `pyproject.toml` 中注册为控制台脚本：`ui-agent = "src.main:cli"`。

---

## 6. 解析器

| 组件 | 版本 | 作用 |
|---|---|---|
| **json** | 标准库 | JSON 测试文件解析 |
| **PyYAML** | >= 6.0 (`pyyaml`) | YAML 测试文件解析 |
| **openpyxl** | >= 3.1.0 (`openpyxl`) | Excel（.xlsx/.xls）测试文件解析 |
| **csv** | 标准库 | CSV 测试文件解析 |
| **CrewAI LLM** | （通过 crewai） | 自然语言（.txt）解析——使用 `LLM.call()` 进行结构化提取 |

解析器分发由 `parser_factory.py` 根据文件扩展名路由：
- `.json` -> `json_parser.parse_json()`
- `.yaml`/`.yml` -> `yaml_parser.parse_yaml()`
- `.csv` -> `csv_parser.parse_csv()`
- `.xlsx`/`.xls` -> `excel_parser.parse_excel()`
- `.txt` -> `nl_parser.parse_natural_language()`（需要 `page_context` 和 `settings`）

---

## 7. 报告

| 组件 | 版本 | 作用 |
|---|---|---|
| **Jinja2** | >= 3.1 (`jinja2`) | 从 `templates/report.html` 渲染 HTML 报告 |
| **json** | 标准库 | JSON 报告序列化 |

报告保存至 `reports/` 目录：
- `reports/{test_case_id}_report.json` -- 机器可读
- `reports/{test_case_id}_report.html` -- 人类可读（Jinja2 模板）

---

## 8. 日志

| 组件 | 版本 | 作用 |
|---|---|---|
| **Loguru** | >= 0.7 (`loguru`) | 应用全局结构化日志。在 `src/utils/logging.py` 中设置。通过 `from loguru import logger` 使用 |

通过 `LOG_LEVEL` 环境变量配置（默认：`INFO`）。

---

## 9. 环境与配置

| 组件 | 版本 | 作用 |
|---|---|---|
| **python-dotenv** | >= 1.0 (`python-dotenv`) | `.env` 文件加载（被 pydantic-settings 使用） |

主要环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | （必填） | LLM/VLM 供应商的 API 密钥 |
| `OPENAI_API_BASE` | `""` | 自定义 API 地址（用于 OpenAI 兼容供应商） |
| `HTTPS_PROXY` | `""` | API 调用的 HTTP 代理 |
| `LLM_MODEL` | `gpt-5.2` | 主 LLM 模型名称 |
| `VLM_MODEL` | `gpt-5.2` | 视觉模型名称 |
| `BROWSER_HEADLESS` | `False` | 以无头模式运行浏览器 |
| `BROWSER_PROXY` | `""` | 浏览器代理服务器 |
| `BROWSER_VIEWPORT_WIDTH` | `1280` | 浏览器视口宽度 |
| `BROWSER_VIEWPORT_HEIGHT` | `720` | 浏览器视口高度 |
| `BROWSER_TIMEOUT` | `10000` | 默认操作超时（毫秒） |
| `BROWSER_NAVIGATION_TIMEOUT` | `60000` | 导航超时（毫秒） |
| `AWA_MAX_STEPS` | `50` | 最大处理页数 |
| `AWA_MAX_HEALING_ATTEMPTS` | `3` | 每页最大重试次数 |
| `AWA_SCREENSHOT_DIR` | `reports/screenshots` | 截图输出目录 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

---

## 10. 测试

| 组件 | 版本 | 作用 |
|---|---|---|
| **pytest** | >= 8.0 (`pytest`) | 测试框架。测试位于 `tests/` 目录下，与 `src/` 结构对应 |
| **pytest-asyncio** | >= 0.23 (`pytest-asyncio`) | 异步测试支持（开发依赖） |
| **unittest.mock** | 标准库 | 为工具单元测试模拟 Playwright `Page` 对象 |
| **Flask** | >= 3.0 (`flask`) | 开发依赖（可能用于测试服务器 fixture） |

### 测试规范
- 测试按类分组：`class TestFillInputTool`
- 浏览器工具使用 `MagicMock` 页面对象测试——无需真实浏览器
- 共享 fixture 在 `tests/conftest.py` 中
- 状态关键词断言：`assert "SUCCESS" in result`

---

## 11. CI/CD

| 组件 | 配置 | 备注 |
|---|---|---|
| **GitHub Actions** | `.github/workflows/ci.yml` | 在推送/PR 到 `main` 时运行 |
| **Python 矩阵** | 3.11, 3.12 | 针对两个版本进行测试 |
| **测试命令** | `pytest -v --tb=short` | 详细输出，简短回溯 |

CI 流水线：
1. 检出代码
2. 设置 Python（矩阵：3.11, 3.12）
3. 安装依赖（`pip install -e ".[dev]"`）
4. 使用虚拟 `OPENAI_API_KEY` 运行测试

---

## 12. 包管理

| 组件 | 作用 |
|---|---|
| **pip** | 包安装器 |
| **setuptools** | 构建后端（`setuptools >= 68.0`、`wheel`） |
| **pyproject.toml** | 主要依赖声明（PEP 621） |
| **requirements.txt** | 补充文件（`pyproject.toml` 依赖的子集，缺少 `openai`） |
| **conda** | 环境管理（不用于依赖解析） |

安装方式：`pip install -e ".[dev]"`（包含开发依赖的可编辑安装）

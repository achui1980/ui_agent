# UI Agent 全面改进实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 全面提升 UI Agent 项目的功能完整性、代码质量、测试覆盖率和工程化水平。

**Architecture:** 分 4 个阶段依次推进——先修复核心功能 bug，再清理代码质量问题，然后补充测试覆盖，最后完善项目工程化。每个阶段独立可交付，前一阶段的改进不会被后续阶段破坏。

**Tech Stack:** Python 3.11+, CrewAI, Playwright, Pydantic, pytest, Click

---

## Phase 1: 功能完善（核心 Bug 修复）

### Task 1.1: 修复 `fields_filled` 始终为空的问题

**Files:**
- Modify: `src/flow/form_test_flow.py:264-325` (_update_state_from_crew_result)
- Modify: `src/flow/form_test_flow.py:367-381` (generate_report)
- Test: `tests/test_flow/test_flow.py`

**问题:** `generate_report()` 在第 373 行硬编码了 `fields_filled=[]`。crew 的 fill_task 输出包含 `field_results` 但从未被解析为 `FieldActionResult` 对象。

**Step 1: 写失败测试**

在 `tests/test_flow/test_flow.py` 的 `TestUpdateStateFromCrewResult` 类中添加测试验证 field_results 被解析并存入 page_results。在 `TestGenerateReport` 类中添加测试验证 fields_filled 被正确填充为 FieldActionResult 对象。

**Step 2: 运行测试确认失败**

Run: `conda activate ui_agent && pytest tests/test_flow/test_flow.py -v -k "test_field_results_parsed or test_fields_filled_populated"`

**Step 3: 实现修复**

1. 在 `_update_state_from_crew_result()` 中，从 parsed JSON 中提取 `field_results` 并存入 `page_results` 字典。
2. 在 `generate_report()` 中，将 `field_results` 解析为 `FieldActionResult` 对象列表，替代硬编码的 `fields_filled=[]`。

**Step 4: 运行测试确认通过**

Run: `conda activate ui_agent && pytest tests/test_flow/test_flow.py -v`

**Step 5: Commit**

```bash
git add src/flow/form_test_flow.py tests/test_flow/test_flow.py
git commit -m "fix: parse crew field_results into PageResult.fields_filled for report"
```

---

### Task 1.2: 支持多 test case 执行

**Files:**
- Modify: `src/main.py:27-40` (run command)
- Test: `tests/test_flow/test_flow.py`

**问题:** `form_test_flow.py:87` 只取 `test_cases[0]`，忽略后续 case。

**设计决策:** 在 `main.py` 的 `run` 命令中循环多个 test case，每个 case 创建一个新的 `FormTestFlow` 实例。Flow 内部的 `tc = test_cases[0]` 行为不变（每个 flow 实例只处理一个 case），但外层循环确保所有 case 都被执行。

**Step 1: 写测试验证 parser 返回所有 case**

```python
class TestMultipleTestCases:
    def test_parse_loads_all_cases(self, tmp_path):
        import json
        data = [
            {"test_id": "TC1", "data": {"name": "Alice"}},
            {"test_id": "TC2", "data": {"name": "Bob"}},
        ]
        path = tmp_path / "multi.json"
        path.write_text(json.dumps(data))
        from src.parsers.parser_factory import parse_test_file
        cases = parse_test_file(str(path), "http://example.com")
        assert len(cases) == 2
```

**Step 2: 修改 main.py 的 run 命令**

循环所有 test cases，每个 case 创建新 Flow 实例并执行。

**Step 3: 运行全部测试确认通过**

**Step 4: Commit**

---

### Task 1.3: 连接 Config 字段与运行时行为

**Files:**
- Modify: `src/flow/form_test_flow.py:62-66` (__init__)
- Modify: `src/tools/screenshot_tool.py`
- Modify: `src/tools/screenshot_analysis_tool.py`
- Modify: `src/agents/page_analyzer.py`
- Modify: `src/flow/page_crew.py`
- Test: `tests/test_flow/test_flow.py`

**问题:** `awa_max_steps`/`awa_max_healing_attempts`/`awa_screenshot_dir` 在 Settings 中定义但未被使用。

**修复:**
1. `FormTestFlow.__init__` 用 settings 值初始化 state 的 max_pages 和 max_retries。
2. Screenshot tools 添加 `screenshot_dir` 属性，替代硬编码的 `"reports/screenshots"`。
3. Agent 工厂和 page_crew 在创建 tool 时传入 `settings.awa_screenshot_dir`。

---

## Phase 2: 代码质量清理

### Task 2.1: 删除 SelectOptionTool 死代码

- Remove: `src/tools/select_option_tool.py:153-183` (不可达的重复代码块)

### Task 2.2: 修复未使用的 import

- Remove: `src/tools/screenshot_tool.py:3` (`import base64`)
- Remove: `tests/test_parsers/test_parsers.py:6` (`import tempfile`)

### Task 2.3: 添加缺失的 `from __future__ import annotations`

- Add to: `src/config.py`, `src/models/test_case.py`, `src/models/page_result.py`, `src/models/report.py`, `src/utils/logging.py`

### Task 2.4: 移动 `import re` 到模块顶级

- Modify: `src/parsers/nl_parser.py:37` → move to top of file

### Task 2.5: 导出 ScreenshotAnalysisTool

- Modify: `src/tools/__init__.py` — add import and `__all__` entry

### Task 2.6: 同步 requirements.txt 与 pyproject.toml

- Remove `pytest>=8.0` from `requirements.txt`

---

## Phase 3: 测试覆盖

### Task 3.1: Excel 解析器测试
### Task 3.2: NL 解析器测试 (mock LLM)
### Task 3.3: 报告生成测试 (JSON + HTML)
### Task 3.4: Config/Settings 测试
### Task 3.5: CLI 测试
### Task 3.6: SelectOptionTool 测试修正 + 自愈路径测试
### Task 3.7: ScreenshotAnalysisTool 测试

---

## Phase 4: 项目工程化

### Task 4.1: 创建 .env.example
### Task 4.2: 创建 README.md
### Task 4.3: 添加 flask 到 dev 依赖
### Task 4.4: 显式声明 openai 依赖
### Task 4.5: 添加 GitHub Actions CI

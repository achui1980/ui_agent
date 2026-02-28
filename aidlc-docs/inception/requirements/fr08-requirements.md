# FR-08 需求文档 — 动态测试数据生成

## 意图分析

- **用户请求**: 在 agent 看到页面后动态生成测试数据，而非事先准备测试数据文件再访问页面
- **请求类型**: 新功能
- **范围**: 多组件（新增 Agent、修改 Flow 逻辑、修改 Crew 构建、新增 CLI 命令、新增测试）
- **复杂度**: 中等偏高

---

## 功能需求

### FR-08-01: Data Generator Agent 创建（优先级 1）

**描述**: 新增第 5 个 CrewAI Agent —— Data Generator，位于 Page Analyzer 和 Field Mapper 之间。该 Agent 接收页面分析结果（字段列表、类型、选项、约束），为每个字段生成语义合理的测试数据。使用纯 LLM 推理（无工具），依靠 LLM 的通用知识自动推断领域和约束。

**验收标准**:
- 创建 `src/agents/data_generator.py`，工厂函数签名 `create_data_generator(llm: LLM) -> Agent`
- Agent role 为 "Test Data Generator"
- Agent 使用纯 LLM 推理（`tools=[]`），与 Field Mapper 模式一致
- Agent 能根据字段语义生成合理数据（如看到 "Medicare" 相关字段自动生成 65+ 年龄）
- 下拉框/单选框字段从给定选项中选择值
- 日期字段根据 placeholder 和 label 推断格式
- 输出格式为 JSON：`{"generated_data": {"field_name": "value", ...}, "persona": {...}}`

**涉及文件**:
- 新建: `src/agents/data_generator.py`

---

### FR-08-02: Crew 构建条件分支（优先级 2）

**描述**: 修改 `page_crew.py` 中的 `build_page_crew()` 函数，支持条件分支：当 `generation_mode == "dynamic"` 时构建 5-agent crew（含 Data Generator），否则保持现有 4-agent crew 不变。

**验收标准**:
- `build_page_crew()` 签名新增 `generation_mode: str = "static"` 参数
- `generation_mode == "dynamic"` 时：
  - 实例化 Data Generator Agent
  - 创建 `generate_task`，`context=[analyze_task]`
  - `generate_task` 的 description 中包含 `{generation_persona}` 模板变量
  - `map_task` 的 `context` 变为 `[analyze_task, generate_task]`
  - Crew 的 agents 和 tasks 列表包含 5 个 agent/task
- `generation_mode == "static"` 时：完全保持现有 4-agent 行为不变
- 现有单元测试全部通过（不破坏 static 模式）

**涉及文件**:
- 修改: `src/flow/page_crew.py`

---

### FR-08-03: Flow 状态扩展与 Persona 机制（优先级 3）

**描述**: 修改 `FormTestState` 和 `FormTestFlow`，支持动态生成模式和跨页面 Persona 一致性。Persona 全自动生成，无需用户配置。

**验收标准**:
- `FormTestState` 新增字段：
  - `generation_mode: str = "static"` — 标识当前模式
  - `generation_persona: dict[str, str] = {}` — 跨页面累积的人物画像数据
- `process_page()` 中 `crew.kickoff(inputs=...)` 新增传递 `generation_persona` 和 `generation_mode`
- `_update_state_from_crew_result()` 中：动态模式下从 crew 结果提取 `generated_data`，合并到 `generation_persona`
- 多步表单中 persona 数据跨页面累积（第 1 页生成的姓名在后续页面保持一致）
- `build_page_crew()` 调用传入 `generation_mode` 参数

**涉及文件**:
- 修改: `src/flow/form_test_flow.py`

---

### FR-08-04: 数据格式双层适配（优先级 4）

**描述**: Data Generator 尽量从页面分析结果（placeholder、validation pattern、label 提示）推断并匹配正确的数据格式，Field Mapper 做最终格式适配。两者结合确保数据格式符合表单要求。

**验收标准**:
- Data Generator 的 task description 中明确要求参考字段的 placeholder、pattern、label 来决定格式
- Data Generator 输出的数据尽量符合目标格式（如日期字段有 placeholder "MM/DD/YYYY" 则生成该格式）
- Field Mapper 仍然负责最终的格式校验和转换（作为安全网）
- 不需要修改 Field Mapper agent 的代码，只需 generate_task 的 prompt 设计得当

**涉及文件**:
- 涉及: `src/flow/page_crew.py`（generate_task 和 map_task 的 description 设计）

---

### FR-08-05: CLI generate 子命令（优先级 5）

**描述**: 新增独立的 `ui-agent generate <url>` CLI 子命令，用户只需提供 URL，无需测试数据文件。系统自动访问页面、分析表单、生成数据并填写。

**验收标准**:
- 新增 `generate` 子命令：`ui-agent generate <url> [--max-pages N] [--max-retries N]`
- 不需要 `test_file` 参数
- 创建 `FormTestFlow`，设置 `generation_mode="dynamic"`
- 设置合理的默认 `test_case_id`（如 `"GEN_{timestamp}"`）
- 现有 `run`、`validate`、`analyze` 命令完全不受影响
- 帮助文本清晰描述功能

**涉及文件**:
- 修改: `src/main.py`

---

### FR-08-06: TestCase 模型适配（优先级 6）

**描述**: 修改 TestCase 模型，使 `data` 字段在动态生成模式下可以为空。

**验收标准**:
- `TestCase.data` 改为可选：`data: dict[str, str] = {}`
- 现有解析器（JSON/YAML/CSV/Excel/NL）不受影响
- 现有测试全部通过

**涉及文件**:
- 修改: `src/models/test_case.py`

---

### FR-08-07: 单元测试与 E2E 测试（优先级 7）

**描述**: 为动态生成功能编写单元测试（mock LLM）和 E2E 测试场景。

**验收标准**:
- 新建 `tests/test_agents/test_data_generator.py`：Data Generator agent 创建测试
- `tests/test_flow/test_flow.py` 中新增：dynamic 模式的 flow 状态管理、persona 累积、crew 构建条件分支测试
- `tests/test_cli.py` 中新增：`generate` 子命令参数解析测试
- `tests/test_e2e/test_e2e_flow.py` 中新增：dynamic 模式 E2E 场景（标记 `@pytest.mark.e2e`）
- 所有现有测试通过（不破坏回归）

**涉及文件**:
- 新建: `tests/test_agents/__init__.py`
- 新建: `tests/test_agents/test_data_generator.py`
- 修改: `tests/test_flow/test_flow.py`
- 修改: `tests/test_cli.py`
- 修改: `tests/test_e2e/test_e2e_flow.py`

---

## 非功能需求

### NFR-03: 动态生成数据的 PII 脱敏

**描述**: 动态生成的测试数据虽然是假数据，但在日志中仍需与真实数据一视同仁，在 INFO+ 级别进行 PII 脱敏处理。

**验收标准**:
- 现有 PII 脱敏 filter（`utils/logging.py`）自动覆盖动态生成的数据，无需额外代码
- 验证动态生成的姓名、邮箱、电话等在 INFO 级别日志中被脱敏
- DEBUG 级别保留完整数据

**涉及文件**:
- 无需修改（现有 filter 已覆盖）
- 新增测试验证

---

## 扩展配置

| 扩展 | 启用状态 | 决定时间 | 说明 |
|------|---------|---------|------|
| 安全基线 | 沿用上轮配置 | 需求分析 | NFR-03 确认动态数据与真实数据同等脱敏处理 |

---

## 实施优先级

| 优先级 | 需求 | 预估复杂度 | 依赖 |
|--------|------|-----------|------|
| 1 | FR-08-06: TestCase 模型适配 | 低 | 无 |
| 2 | FR-08-01: Data Generator Agent 创建 | 中 | 无 |
| 3 | FR-08-02: Crew 构建条件分支 | 中 | FR-08-01 |
| 4 | FR-08-03: Flow 状态扩展与 Persona 机制 | 中 | FR-08-02 |
| 5 | FR-08-04: 数据格式双层适配 | 低 | FR-08-01, FR-08-02 |
| 6 | FR-08-05: CLI generate 子命令 | 低 | FR-08-03 |
| 7 | FR-08-07: 单元测试与 E2E 测试 | 中 | FR-08-01~06 |
| — | NFR-03: PII 脱敏验证 | 低 | FR-08-07 |

# Tasks

- [x] Task 1: 修复 4 个已知测试失败
  - [x] SubTask 1.1: 移除 `ContextBuilder` 导入和测试行（test_project.py L120, L151-152）
  - [x] SubTask 1.2: 更新 Agent 期望数量 8→6（test_project.py L268）
  - [x] SubTask 1.3: 替换 `get_all_agents()` 为 `registry.list_all()`（test_project.py L274-282）
  - [x] SubTask 1.4: 移除不存在的 `/api/agents` 端点调用（test_project.py L356-357）
  - [x] 验证: `python test_project.py` 输出 99/99 通过 ✓

- [x] Task 2: 激活 v4.0 Loop 架构 — 后端 API 端点
  - [x] SubTask 2.1: 在 `main.py` 新增 `/api/orchestrator/start-loop` 端点，调用 `orchestrator.run_all_loop()`
  - [x] SubTask 2.2: 修改 `/api/orchestrator/start` 端点默认使用 `run_all_loop` 模式
  - [x] SubTask 2.3: 新增 `/api/orchestrator/start-linear` 兼容端点
  - [x] 验证: 后端编译通过 ✓

- [x] Task 3: 清理死代码
  - [x] SubTask 3.1: 删除 `main.py` 中 `_get_llm_client_for_config` 函数
  - [x] 验证: `python -m py_compile src/backend/main.py` 无错误 ✓

- [x] Task 4: 修复并发安全问题 — Agent 类属性
  - [x] SubTask 4.1: 在 `orchestrator.py` 的 `run_stage` 中将 `agent.DEFAULT_TEMPERATURE = ...` 改为 `agent._temperature_override = ...`
  - [x] SubTask 4.2: 在 `base.py` 新增 `_temperature_override` 实例属性和三级回退链
  - [x] 验证: 代码审查确认 Agent 类属性不再被修改 ✓

- [x] Task 5: 修复 Anthropic Provider 流式缺失
  - [x] SubTask 5.1: 在 `llm/client.py` 的 `AnthropicProvider` 中实现 `generate_stream` 方法
  - [x] 验证: `python -m py_compile src/backend/llm/client.py` 无错误 ✓

- [x] Task 6: SSL 验证按 Provider 区分
  - [x] SubTask 6.1: 修改 `OpenAICompatibleProvider.generate()` 和 `generate_stream()` 中的 `verify=False`，改为仅对 `custom_openai` 和 `ollama` 禁用
  - [x] 验证: 代码审查确认公网 provider 默认启用 SSL 验证 ✓

- [x] Task 7: 更新前端 OrchestratorPage 支持 Loop 模式
  - [x] SubTask 7.1: 在 `OrchestratorPage.tsx` 添加模式选择器（循环模式/线性模式）
  - [x] SubTask 7.2: 循环模式调用 `/api/orchestrator/stream` 端点
  - [x] SubTask 7.3: 添加 `loop_start`/`loop_done` SSE 事件监听和 onmessage 回退
  - [x] 验证: `npx vite build` 通过，无 TypeScript 错误 ✓

- [x] Task 8: 更新项目文档同步
  - [x] SubTask 8.1: 更新 `PROJECT_ARCHITECTURE.md` — Agent 数量 8→6、添加 Loop 架构说明、端口号修正
  - [x] SubTask 8.2: 更新 `CLAUDE.md` — Agent 数量 8→6、Loop 架构说明
  - [x] SubTask 8.3: 更新 `README.md` — 端口号修正（8080）、访问地址修正
  - [x] 验证: 文档中所有数值与代码一致 ✓

# Task Dependencies
- Task 7 依赖 Task 2（前端 Loop 模式需要后端端点先就绪）
- Task 1、3、4、5、6、8 互相独立，可并行执行
# Checklist

- [x] 测试修复: `python test_project.py` 输出 99/99 通过，0 失败
- [x] Loop 端点: `/api/orchestrator/start-loop` 端点已创建，调用 `run_all_loop()`
- [x] 默认编排: `/api/orchestrator/start` 默认使用 `run_all_loop` 模式
- [x] 线性兼容: `/api/orchestrator/start-linear` 端点保留线性模式
- [x] 死代码清理: `_get_llm_client_for_config` 函数已删除，编译无错误
- [x] 并发安全: `orchestrator.py` 使用 `_temperature_override` 实例属性，不再修改 Agent 类属性
- [x] Anthropic 流式: `AnthropicProvider.generate_stream()` 方法已实现
- [x] SSL 安全: 公网 provider 的 HTTPS 请求启用 TLS 证书验证，仅 ollama/custom_openai 跳过
- [x] 前端 Loop 模式: OrchestratorPage 有循环/线性模式选择器，支持 loop_start/loop_done 事件
- [x] 前端构建: `npx vite build` 无 TypeScript 错误
- [x] 文档同步: PROJECT_ARCHITECTURE.md 中 Agent 数量为 6、包含 Loop 架构说明
- [x] 文档同步: CLAUDE.md 中 Agent 数量为 6、端口为 8080
- [x] 文档同步: README.md 中端口和访问地址与实际一致
- [x] 后端编译: 4 个核心文件全部编译通过
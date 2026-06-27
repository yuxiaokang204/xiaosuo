# 全项目功能审计与优化 Spec

## Why
项目经过多轮迭代后存在多个已知问题：4 个测试失败、v4.0 Loop 架构未被激活、死代码积压、文档与实际代码不一致、部分安全风险。需要系统性审计所有功能并提出优化方案。

## What Changes
- 修复 4 个已知测试失败（test_project.py 未跟随业务代码更新）
- 激活 v4.0 Loop 架构（`run_all_loop` 方法未绑定任何 API 端点）
- 清理死代码和未引用文件
- 修复并发安全问题（Agent 类属性修改）
- 更新项目文档与代码同步
- 修复 Anthropic 流式调用缺失
- **BREAKING**: 删除 `_get_llm_client_for_config` 死代码函数

## Impact
- Affected specs: 全项目
- Affected code: `test_project.py`, `main.py`, `orchestrator.py`, `llm/client.py`, `agents/base.py`, `PROJECT_ARCHITECTURE.md`, `CLAUDE.md`, `README.md`

## ADDED Requirements

### Requirement: v4.0 Loop 架构 API 端点
系统 SHALL 提供一个 API 端点，使前端可以触发 `run_all_loop` 循环架构模式来生成小说。

#### Scenario: 用户通过前端触发 Loop 模式编排
- **WHEN** 用户在前端界面选择"循环模式"并点击"开始编排"
- **THEN** 系统调用 `run_all_loop` 方法，按 SKELETON → DETAIL → POLISH 三层循环生成章节

#### Scenario: 用户通过 API 直接调用 Loop 模式
- **WHEN** 客户端 POST `/api/orchestrator/start-loop` 并传入小说 ID
- **THEN** 系统返回 SSE 流，实时推送各阶段进度

### Requirement: 前端 Loop 模式入口
前端 OrchestratorPage SHALL 提供"循环模式"和"线性模式"两种编排方式的选择。

#### Scenario: 用户选择循环模式
- **WHEN** 用户在编排页面选择"循环模式"
- **THEN** 前端调用 `/api/orchestrator/start-loop` 端点，UI 显示三层循环进度

### Requirement: 测试覆盖率修复
系统 SHALL 修复 `test_project.py` 中 4 个已知失败，确保 91/91 测试全部通过。

#### Scenario: 运行全部测试
- **WHEN** 执行 `python test_project.py`
- **THEN** 91/91 测试全部通过，0 个失败

### Requirement: 项目文档同步
PROJECT_ARCHITECTURE.md、CLAUDE.md、README.md SHALL 与当前代码（6-Skill + Loop 架构）保持一致。

#### Scenario: 文档与代码一致
- **WHEN** 开发者阅读项目文档
- **THEN** 文档中描述的 Agent 数量（6 个 Skill）、Loop 架构、端口号、数据库文件名与实际代码一致

## MODIFIED Requirements

### Requirement: 全局编排端点
`/api/orchestrator/start` 端点 SHALL 修改为默认使用 `run_all_loop` 循环模式，确保 v4.0 架构被实际使用。

#### Scenario: 默认编排模式
- **WHEN** 用户不指定模式启动编排
- **THEN** 系统默认使用 v4.0 Loop 循环架构

### Requirement: LLM 客户端 SSL 验证
SSL 证书验证 SHALL 仅对 `custom_openai` provider 禁用，公网 provider（OpenAI、DeepSeek、Google 等）默认开启验证。

#### Scenario: 公网 API 调用
- **WHEN** 用户使用 OpenAI/DeepSeek/Google 等公网 provider
- **THEN** HTTPS 请求启用 TLS 证书验证

#### Scenario: 内网自定义 API 调用
- **WHEN** 用户使用 `custom_openai` provider 且配置了内网自签名证书
- **THEN** HTTPS 请求禁用 TLS 证书验证（保持现有行为）

### Requirement: Anhropic Provider 流式支持
AnthropicProvider SHALL 实现 `generate_stream` 方法，支持流式内容生成。

#### Scenario: 使用 Anthropic 模型进行流式章节生成
- **WHEN** 系统通过 Anthropic provider 调用流式生成
- **THEN** 内容以 token 粒度实时推送到前端

## REMOVED Requirements

### Requirement: _get_llm_client_for_config 死代码函数
**Reason**: 该函数从未被任何端点调用，且引用了未导入的 `MockProvider`，是死代码。
**Migration**: 无需迁移，直接删除。实际 LLM 客户端获取使用 `_get_llm_client_from_db`。
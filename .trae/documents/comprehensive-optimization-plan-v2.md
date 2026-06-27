# 小说创作Agent系统 v1.1.0 → v2.0 全面优化方案

> 生成日期：2026-06-19 | 基于项目全量代码审计 + 行业前沿参考

---

## 一、项目现状总览

### 1.1 已完成（v1.0 → v5.3）

| 版本 | 主要变更 |
|------|---------|
| v1.0 | 8-Agent 线性编排 |
| v2.0 | 3层记忆系统 + 一致性检查 |
| v3.0 | 6-Skill 角色化 + 平台适配 |
| v4.0 | SKELETON→DETAIL→POLISH Loop 架构 |
| v5.0 | Prompt 持久化 + 可视化管理 |
| v5.1 | MemoryCoordinationEngine 统一记忆协调 |
| v5.2 | 4个Agent 接入 LLM + ContinuityEngine |
| v5.3 | 后端模块化 (14个Router) + LLM韧性层 + 状态持久化 + 前端Zustand/TanStack Query + ChromaDB向量存储 |

### 1.2 当前架构图

```
┌──────────────── 前端 (React 18 + Vite + Zustand + TanStack Query) ────────┐
│  13个页面, api.ts 统一 HTTP/SSE                                              │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ Vite Proxy /api → :8080
┌────────────────────────────── 后端 (FastAPI) ──────────────────────────────┐
│  main.py (159行) → 14个 api/ router 模块                                    │
│  ├─ /api/create/*     12 endpoints                                          │
│  ├─ /api/orchestrator/* 13 endpoints (SSE stream)                           │
│  ├─ /api/llm/*        10 endpoints                                          │
│  ├─ /api/prompts/*    10 endpoints                                          │
│  ├─ /api/continuity/*  5 endpoints                                          │
│  ├─ /api/novels/*      6 endpoints                                          │
│  ├─ /api/settings/*    9 endpoints                                          │
│  └─ /api/memory|learning|agents|executor/* 16 endpoints                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  核心模块 (16个文件)                                                          │
│  orchestrator.py → chapter_pipeline.py → memory_coordination.py             │
│  → continuity_engine.py → prompt_resolver.py → learning_engine.py           │
│  → memory.py → state_tracker.py → global_summary.py → vector_memory.py      │
│  → resilience.py (未集成) → consistency_checker.py                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  Agent Skill (6个活跃 + 6个旧版保留)                                          │
│  story_architect / world / character / opening_hook / draft / style_editor  │
├─────────────────────────────────────────────────────────────────────────────┤
│  LLM (10+ Provider) | DB (SQLite + 14 Model) | ChromaDB (向量存储)           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 已知问题清单

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | `_call_llm` 缺少 try-except，LLM API 超时导致进程崩溃 | P0 | ✅ 已修复 (本次会话) |
| 2 | httpx 超时 180s 过长 | P0 | ✅ 已修复 (本次会话) |
| 3 | `ResilientLLMClient` 已创建但未集成到 Agent 调用链 | P0 | ❌ 待修复 |
| 4 | `LearningEngine` 实例化但未传入 `NovelOrchestrator` | P1 | ❌ 待修复 |
| 5 | 4个Agent在 ChapterPipeline 中不调用 LLM（硬编码文本） | P1 | ❌ 待修复 |
| 6 | `PromptResolver` 仅覆盖 2/6 Agent | P1 | ❌ 待修复 |
| 7 | 记忆系统纯内存，ChromaDB 向量存储已创建但未集成 | P1 | ❌ 待集成 |
| 8 | 自定义状态机，无 LangGraph 的断点续传/可视化/并行能力 | P2 | 待评估 |
| 9 | 无可观测性（无 OpenTelemetry/LangFuse 追踪） | P2 | 待实施 |
| 10 | 前端无组件库，所有样式手写 CSS | P2 | 待优化 |
| 11 | 旧版 Agent 文件冗余（6个已废弃） | P3 | 待清理 |
| 12 | 配置管理分散（.env + 硬编码 + DB 混合） | P3 | 待统一 |

---

## 二、行业前沿参考

### 2.1 2026 年 Agent 编排标准

| 框架 | 定位 | 核心优势 |
|------|------|---------|
| **LangGraph** | Agent 编排标准 | 78% 企业级 Agent 采用，内置 Checkpoint、Human-in-the-Loop、时间旅行 |
| **CrewAI** | 角色化多Agent | 简化的角色分配 + 任务委派，适合非技术用户 |
| **DeerFlow 2.0** (字节) | 通用 Agent 框架 | 23K+ Stars，MCP 协议支持，插件化架构 |
| **AutoGen** (微软) | 多Agent对话 | 会话驱动，适合对话式协作场景 |

### 2.2 2026 年 Agent Memory 架构趋势

- **四层渐进式记忆**：L0 原始对话 → L1 原子记忆 → L2 情景记忆 → L3 语义记忆
- **AgentMemory** (5.5K Stars)：免数据库持久记忆，95.2% R@5 召回率，16+ Agent 共享
- **GraphRAG**：用知识图谱增强向量检索，解决"答案正确但上下文错误"问题
- **Mem0** (20K+ Stars)：LLM 记忆层，自动记忆提取 + 去重 + 更新

### 2.3 2026 年 LLM 应用可观测性

- **LangFuse**：开源 LLM 追踪平台，支持 token 消耗、延迟、质量评分
- **OpenTelemetry**：分布式追踪标准，LangChain/LangGraph 已原生集成
- **结构化日志**：JSON 格式 + request_id/novel_id/chapter_idx 注入

### 2.4 参考项目

| 项目 | GitHub | 参考价值 |
|------|--------|----------|
| LangGraph | langchain-ai/langgraph | Agent 编排标准范式 |
| CrewAI | crewAIInc/crewAI | 角色化多Agent协作 |
| Mem0 | mem0ai/mem0 | LLM 记忆层设计 |
| AgentMemory | agentmemory/agentmemory | 持久记忆基础设施 |
| LangFuse | langfuse/langfuse | LLM 可观测性 |
| DeerFlow 2.0 | bytedance/deerflow | 插件化 Agent 架构 |
| Dify | langgenius/dify | LLM 应用开发平台 |
| Sudowrite | (商业) | AI 小说创作产品形态 |
| GraphRAG | microsoft/graphrag | 知识图谱增强 RAG |

---

## 三、优化方案（按优先级分三阶段）

### Phase 1: 稳定性修复（P0 — 本周完成）

#### 3.1 集成 ResilientLLMClient 到 Agent 调用链

**现状**：`src/backend/llm/resilience.py` 已创建 `ResilientLLMClient`（重试/限流/缓存），但 Agent 仍直接调用 `get_default_llm_client()`。

**修改文件**：
- `src/backend/agents/base.py` — `_call_llm()` 方法改用 `ResilientLLMClient` 包装
- `src/backend/llm/resilience.py` — 确保与现有 `LLMClient` 接口兼容

**实现方案**：
```python
# base.py _call_llm() 中
from ..llm.resilience import ResilientLLMClient

client = get_default_llm_client()
resilient = ResilientLLMClient(
    client=client,
    max_retries=3,
    rate_limit_rpm=30,
    cache_enabled=True,
)
response = await resilient.generate(messages, system_prompt, temperature, max_tokens)
```

**收益**：
- 自动重试：网络抖动不中断流程
- 速率限制：避免触发 API 限流
- 语义缓存：相同 prompt 不重复调用

#### 3.2 修复 LearningEngine 未传入 Orchestrator 问题

**现状**：`main.py` 中 `learning_engine = LearningEngine()` 实例化后，创建 `NovelOrchestrator` 时未传入 `learning_engine` 参数。

**修改文件**：
- `src/backend/api/orchestrator.py` — 在 `_create_orchestrator()` 中传入 `learning_engine`
- `src/backend/api/deps.py` — 确保 `learning_engine` 全局变量可访问

**实现方案**：
```python
# api/orchestrator.py
from .deps import learning_engine

orch = NovelOrchestrator(
    ...
    learning_engine=learning_engine,  # 传入学习引擎
)
```

**收益**：
- 衔接强度动态调整生效（高评分→软约束，低评分→硬约束）
- 用户反馈真正影响生成质量

#### 3.3 修复 ChapterPipeline 中 4 个 Agent 不调用 LLM

**现状**：`_agent_world`、`_agent_character`、`_agent_opening_hook`、`_agent_style_editor_full` 在 ChapterPipeline 中仅生成硬编码文本，不调用 LLM。

**修改文件**：
- `src/backend/core/chapter_pipeline.py` — 4 个 `_agent_*` 方法改为调用 `WorldAgent`/`CharacterAgent`/`OpeningHookAgent`/`StyleEditorAgent` 的 `process()` 方法

**实现方案**：
```python
# _agent_world 改为:
async def _agent_world(self, chapter_idx, context, loop_metadata=None):
    agent = WorldAgent()
    result = await agent.process({
        "theme": context.get("theme", ""),
        "existing_world": context.get("world", ""),
        "depth_level": loop_metadata.get("depth_level", 1),
    })
    return AgentContribution(
        agent_name="世界观构建师",
        content=result.get("data", {}).get("description", ""),
        llm=True,
        fallback=result.get("fallback", False),
    )
```

**收益**：
- 每章生成时 6 个 Agent 全部调用 LLM，产出质量提升
- PromptResolver 覆盖全部 6 个 Agent

#### 3.4 扩展 PromptResolver 覆盖全部 6 个 Agent

**现状**：`PromptResolver` 仅覆盖 `story_architect` 和 `draft` 两个 Agent。

**修改文件**：
- `src/backend/core/chapter_pipeline.py` — 在 `_agent_world`、`_agent_character`、`_agent_opening_hook`、`_agent_style_editor_full` 中调用 `PromptResolver`

**收益**：
- 用户自定义的 Prompt 模板对所有 Agent 生效
- 前端 Prompt 管理页面价值最大化

---

### Phase 2: 能力提升（P1 — 2周内完成）

#### 3.5 向量记忆系统集成

**现状**：`src/backend/core/vector_memory.py` 已创建 ChromaDB 向量存储（含 fallback），但 `NovelMemory` 和 `MemoryCoordinationEngine` 未使用。

**修改文件**：
- `src/backend/core/memory_coordination.py` — 集成 `VectorMemoryStore` 进行语义搜索
- `src/backend/core/memory.py` — 记忆项同步写入 ChromaDB
- `src/backend/core/orchestrator.py` — 初始化时创建 `VectorMemoryStore`

**实现方案**：
```python
# memory_coordination.py
class MemoryCoordinationEngine:
    def __init__(self, ..., vector_store=None):
        self.vector_store = vector_store or VectorMemoryStore()
    
    async def semantic_search(self, query: str, top_k: int = 5):
        """语义搜索：支持"主角第一次遇到反派的场景"等自然语言查询"""
        return await self.vector_store.search(query, top_k)
```

**收益**：
- 语义搜索"主角第一次遇到反派的场景"
- 跨小说复用角色/世界观模板
- 长期记忆自动衰减和淘汰
- 前端 SemanticSearchPage 真正可用

#### 3.6 工作流编排增强 — 引入 LangGraph

**现状**：`NovelOrchestrator` 是自定义状态机，支持线性模式和 Loop 循环模式，但：
- 无断点续传（重启丢失进度）
- 无可视化调试
- 无并行执行（worldbuilding + characters 可并行）
- 无 Human-in-the-Loop（用户审核节点）

**评估**：LangGraph 在 2026 年已成为企业级 Agent 编排标准（78% 采用率），其 `StateGraph` + `Checkpoint` 机制与项目需求高度匹配。

**方案对比**：

| 能力 | 当前自定义状态机 | LangGraph 替代 |
|------|-----------------|----------------|
| 断点续传 | 手动 `_save_run_state()` | 内置 `SqliteSaver` 自动 Checkpoint |
| 并行执行 | 全部串行 | `Send()` API 并行分支 |
| 可视化 | 无 | LangGraph Studio |
| 人工审核 | 无 | `interrupt()` 节点 |
| 时间旅行 | 无 | `get_state_history()` |
| 条件分支 | 手写 if-else | `add_conditional_edges()` |

**迁移方案**（渐进式，不破坏现有功能）：

```
Step 1: 新建 src/backend/core/orchestrator_graph.py
  ├─ 定义 NovelState (TypedDict)
  ├─ 每个阶段作为独立 Node 函数
  └─ 构建 StateGraph

Step 2: 在 main.py 中同时保留两种模式
  ├─ /api/orchestrator/start → 使用 LangGraph (新)
  └─ /api/orchestrator/start-legacy → 使用旧状态机 (兼容)

Step 3: 验证后切换默认 → 删除旧代码
```

**核心代码示例**：
```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

class NovelState(TypedDict):
    novel_id: str
    title: str
    theme: str
    current_stage: str
    world_settings: dict
    characters: list
    chapters: list
    errors: list

def build_novel_graph() -> StateGraph:
    graph = StateGraph(NovelState)
    
    graph.add_node("worldbuilding", worldbuilding_node)
    graph.add_node("characters", characters_node)
    graph.add_node("outlining", outlining_node)
    graph.add_node("drafting", drafting_node)
    graph.add_node("polish", polish_node)
    
    graph.add_edge("worldbuilding", "characters")
    graph.add_edge("characters", "outlining")
    graph.add_edge("outlining", "drafting")
    graph.add_edge("drafting", "polish")
    graph.add_edge("polish", END)
    
    graph.set_entry_point("worldbuilding")
    
    memory = SqliteSaver.from_conn_string("checkpoints.db")
    return graph.compile(checkpointer=memory)
```

**收益**：
- 断点续传：重启后自动从断点恢复
- 并行执行：worldbuilding + characters 可同时进行
- 人工审核：在 SKELETON → DETAIL 之间插入审核节点
- 可视化调试：LangGraph Studio 查看执行图

#### 3.7 可观测性集成

**现状**：仅使用 `print()` 和 `logger.info/warning`，无结构化日志、无指标、无追踪。

**方案**：集成 LangFuse（最小侵入，装饰器方式）

**修改文件**：
- `src/backend/llm/client.py` — 添加 `@observe()` 装饰器
- `src/backend/agents/base.py` — 添加 `@observe()` 装饰器
- `src/backend/core/orchestrator.py` — 关键节点添加追踪

**实现方案**：
```python
# 最小侵入：只需在关键函数上加装饰器
from langfuse.decorators import observe

@observe()
async def generate(self, messages, ...):
    ...

@observe()
async def _call_llm(self, system_prompt, user_prompt, ...):
    ...
```

**收益**：
- 追踪每个 LLM 调用的 token 消耗、延迟、成功率
- 定位"哪个 Agent 在什么阶段产出低质量内容"
- 监控记忆系统 token 预算占比
- 生成质量仪表盘

---

### Phase 3: 体验优化（P2 — 按需推进）

#### 3.8 前端组件库引入

**现状**：13 个页面，所有样式手写 CSS，无组件库。

**方案**：引入 shadcn/ui（基于 Radix，GitHub 80K+ Stars，2026 年 React 生态首选）

**实施步骤**：
1. `npx shadcn@latest init` 初始化
2. 逐步替换现有页面组件（Button → Card → Dialog → Tabs → Select）
3. 优先替换 OrchestratorPage、LLMConfigPage、PromptManagerPage

**收益**：
- 统一设计语言，视觉一致性
- 内置无障碍支持（WCAG 2.1 AA）
- 减少 CSS 维护成本

#### 3.9 旧代码清理

**清理清单**：
- `src/backend/agents/outline_agent.py` — 被 `story_architect_agent.py` 替代
- `src/backend/agents/style_agent.py` — 被 `style_editor_agent.py` 替代
- `src/backend/agents/plot_agent.py` — 被 `story_architect_agent.py` 替代
- `src/backend/agents/edit_agent.py` — 被 `style_editor_agent.py` 替代
- `src/backend/agents/review_agent.py` — 被 `style_editor_agent.py` 替代
- `src/backend/agents/old/` 目录（如有）

**清理前需确认**：这些文件没有被任何 import 引用。

#### 3.10 配置管理统一

**现状**：配置分散在 `.env`（LLM）、`OrchestratorState` dataclass（运行时）、`SkillLoopConfig`（硬编码默认值）。

**方案**：统一 `config.yaml` + Pydantic Settings

```python
# src/backend/core/config.py
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        yaml_file="config.yaml",
        env_prefix="NOVEL_",
    )
    
    # LLM
    llm_provider: str = "custom_openai"
    llm_model: str = "qwen36-35b"
    llm_api_key: str = ""
    llm_api_base: str = ""
    
    # Orchestrator
    max_loops: int = 3
    quality_threshold: float = 6.5
    chapters_per_draft_loop: int = 5
    
    # Resilience
    max_retries: int = 3
    rate_limit_rpm: int = 30
    request_timeout: int = 60
    
    # Memory
    vector_db_path: str = "./data/vector_memory"
    memory_token_budget: int = 4000
```

---

## 四、实施路线图

```
Phase 1 (1周) — 稳定性修复
├── 3.1 ResilientLLMClient 集成到 Agent 调用链
├── 3.2 LearningEngine 传入 Orchestrator
├── 3.3 ChapterPipeline 4个Agent 调用 LLM
└── 3.4 PromptResolver 覆盖全部 6 Agent

Phase 2 (2周) — 能力提升
├── 3.5 向量记忆系统集成
├── 3.6 LangGraph 替换自定义状态机
└── 3.7 可观测性集成 (LangFuse)

Phase 3 (1周) — 体验优化
├── 3.8 前端组件库引入 (shadcn/ui)
├── 3.9 旧代码清理
└── 3.10 配置管理统一
```

---

## 五、验证清单

### Phase 1 验证
- [ ] `python test_project.py` 99/99 通过
- [ ] 全流程编排中 LearningEngine 衔接强度动态生效
- [ ] ChapterPipeline 6 个 Agent 全部调用 LLM（非硬编码）
- [ ] 前端 Prompt 管理修改后，6 个 Agent 均使用新模板
- [ ] LLM API 超时后自动重试，不崩溃

### Phase 2 验证
- [ ] 语义搜索"主角第一次遇到反派"返回正确结果
- [ ] LangGraph 编排器支持断点续传（重启后恢复）
- [ ] worldbuilding + characters 阶段并行执行
- [ ] LangFuse 仪表盘显示 LLM 调用追踪

### Phase 3 验证
- [ ] 前端 shadcn/ui 组件替换后，`npx vite build` 无错误
- [ ] 删除旧 Agent 文件后，全项目编译通过
- [ ] config.yaml 配置生效，热更新可用

---

## 六、风险与注意事项

1. **LangGraph 迁移风险**：渐进式迁移，保留旧状态机作为 fallback，确保不中断现有功能
2. **向量数据库依赖**：ChromaDB 需要额外安装 `pip install chromadb`，已在 `vector_memory.py` 中实现 fallback 到内存模式
3. **LangFuse 依赖**：可选集成，默认不启用，通过环境变量 `LANGFUSE_ENABLED=true` 开启
4. **shadcn/ui 迁移**：渐进式替换，先替换通用组件（Button/Input），再替换页面级组件
5. **代码清理风险**：删除前用 `rg` 全局搜索确认无引用
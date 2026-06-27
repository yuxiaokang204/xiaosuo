# 小说创作Agent系统 v1.1.0 — 全功能架构文档

## 一、项目架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         前端 (React + TypeScript + Vite)                  │
│                         http://127.0.0.1:3001                            │
├─────────────────────────────────────────────────────────────────────────┤
│  App.tsx (路由) ── Sidebar.tsx (13个导航入口)                             │
│  ├─ OverviewPage     系统总览                                            │
│  ├─ OrchestratorPage 全流程编排 (SSE实时流)                               │
│  ├─ NovelManagerPage 小说管理 (CRUD)                                     │
│  ├─ NovelReadPage    阅读模式                                            │
│  ├─ StandaloneDraftPage 独立草稿                                         │
│  ├─ StandaloneEditPage  独立编辑                                         │
│  ├─ CharactersPage   角色管理                                            │
│  ├─ WorldPage        世界观设定                                          │
│  ├─ SemanticSearchPage 语义搜索                                          │
│  ├─ LearningPage     学习引擎                                            │
│  ├─ DashboardPage    仪表盘                                              │
│  ├─ LLMConfigPage    LLM 配置                                            │
│  └─ PromptManagerPage Prompt 管理                                        │
├─────────────────────────────────────────────────────────────────────────┤
│  api.ts (HTTP/SSE 客户端) ── Vite Proxy /api → localhost:8080            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        后端 (FastAPI + Python)                            │
│                         http://localhost:8080                            │
├─────────────────────────────────────────────────────────────────────────┤
│  main.py (81个API端点)                                                    │
│  ├─ /api/agents/*          Agent 注册与查询                               │
│  ├─ /api/create/*          单步创作 (大纲/草稿/编辑/世界观/角色/风格)        │
│  ├─ /api/orchestrator/*    全流程编排 (SSE流/暂停/恢复/仪表盘)              │
│  ├─ /api/llm/*             LLM 配置管理 (多Provider)                      │
│  ├─ /api/prompts/*         Prompt 模板管理 (CRUD/激活/缓存)                │
│  ├─ /api/continuity/*      章节衔接引擎 (钩子/评分/学习)                    │
│  ├─ /api/novels/*          小说/章节 CRUD                                │
│  ├─ /api/settings/*        角色/世界观预设 CRUD                            │
│  ├─ /api/memory/*          记忆系统统计                                   │
│  ├─ /api/learning/*        学习引擎反馈                                   │
│  └─ /api/presets           预设角色/世界观列表                              │
├─────────────────────────────────────────────────────────────────────────┤
│  核心模块 (src/backend/core/)                                             │
│  ├─ orchestrator.py       工作流编排器 (线性模式 + Loop循环模式)            │
│  ├─ chapter_pipeline.py   6-Skill 协同写作管道 (SKELETON/DETAIL/POLISH)   │
│  ├─ memory_coordination.py 记忆协调引擎 (统一5个记忆组件)                   │
│  ├─ continuity_engine.py   章节衔接引擎 (钩子提取/生成/保存)                │
│  ├─ prompt_resolver.py     Prompt 两级 fallback 链 (DB → 硬编码)           │
│  ├─ learning_engine.py     学习引擎 (用户反馈 + 衔接强度)                   │
│  ├─ memory.py              三层记忆系统 (工作/短期/长期)                    │
│  ├─ state_tracker.py       角色/地点/伏笔状态追踪                           │
│  ├─ global_summary.py      全局摘要 (章节摘要 + 场景锚点)                    │
│  ├─ consistency_checker.py 跨章节一致性验证                                │
│  ├─ agent_registry.py      Agent 注册与发现                                │
│  ├─ agent_executor.py      Agent 执行追踪                                 │
│  ├─ shared_context.py      共享上下文管理                                  │
│  ├─ chunked_generator.py   流式内容生成器                                  │
│  └─ event_extractor.py     事件提取器                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  Agent Skill (src/backend/agents/)                                       │
│  ├─ story_architect_agent.py  故事架构师 (大纲/结构)                       │
│  ├─ world_agent.py            世界观构建师 (地理/规则/势力)                  │
│  ├─ character_agent.py        角色塑造师 (性格/背景/弧线)                    │
│  ├─ opening_hook_agent.py     开篇钩子师 (黄金三章)                         │
│  ├─ draft_agent.py            专业写手 (章节正文生成)                       │
│  ├─ style_editor_agent.py     文风精修师 (编辑/审查/评分)                    │
│  ├─ outline_agent.py          大纲规划师 (旧版, 保留)                       │
│  ├─ world_agent.py            世界观构建师 (旧版)                           │
│  ├─ character_agent.py        角色塑造师 (旧版)                             │
│  ├─ style_agent.py            风格设计师 (旧版)                             │
│  ├─ plot_agent.py             情节分析 (旧版)                               │
│  ├─ edit_agent.py             编辑 (旧版)                                  │
│  ├─ review_agent.py           审查 (旧版)                                  │
│  ├─ base.py                   Agent 基类                                  │
│  └─ prompts.py                Prompt 模板库 (build_*_system_prompt)       │
├─────────────────────────────────────────────────────────────────────────┤
│  数据层 (src/backend/db/)                                                 │
│  ├─ models.py         14个SQLAlchemy数据模型                              │
│  ├─ database.py       异步数据库连接 (SQLite/aiosqlite)                    │
│  └─ crud.py           CRUD 操作                                          │
├─────────────────────────────────────────────────────────────────────────┤
│  LLM 客户端 (src/backend/llm/)                                            │
│  └─ client.py         10+ Provider (OpenAI/DeepSeek/Anthropic/Google/     │
│                         Qwen/Moonshot/Ollama/OpenRouter/CustomOpenAI/Mock) │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 二、数据流向图

### 全流程编排 (run_all_loop) 数据流

```
用户输入 (title/theme/tone/chapter_count)
  │
  ▼
NovelOrchestrator.__init__()
  ├─ StateTracker()          ← 角色/地点/伏笔状态
  ├─ GlobalSummary()         ← 章节摘要/场景锚点
  ├─ NovelMemory()           ← 三层记忆(工作/短期/长期)
  ├─ MemoryCoordinationEngine() ← 统合4个记忆组件
  └─ _ensure_agents()        ← 6个Skill延迟加载
  │
  ▼
run_all_loop(max_loops=3)
  │
  ├─ Loop 0: SKELETON (骨架层)
  │   ├─ agents["world"].process()      → 粗略世界观
  │   ├─ agents["character"].process()  → 主角卡片
  │   ├─ agents["opening_hook"].process() → 黄金三章设计
  │   ├─ agents["style_editor"].process() → 关键词汇
  │   └─ agents["story_architect"].process() → 大纲骨架
  │
  ├─ Loop 1: DETAIL (细节层)
  │   ├─ agents["world"].process()      → 细化世界观
  │   ├─ agents["character"].process()  → 关系网+弧线
  │   ├─ agents["style_editor"].process() → 完整文风
  │   ├─ agents["story_architect"].process() → 细化大纲
  │   ├─ agents["opening_hook"].process() → 钩子重审
  │   └─ ChapterPipeline (逐章写作) ← 核心管线
  │       │
  │       ├─ _agent_outline()        → LLM + PromptResolver [✅]
  │       ├─ _agent_world()          → 硬编码文本 [❌ 不调LLM]
  │       ├─ _agent_character()      → 硬编码文本 [❌ 不调LLM]
  │       ├─ _agent_opening_hook()   → 硬编码文本 [❌ 不调LLM]
  │       ├─ _agent_draft()          → LLM + PromptResolver + MemoryEngine [✅]
  │       │   ├─ memory_engine.generate_context_for_next_chapter()
  │       │   │   ├─ story_bible (StateTracker)
  │       │   │   ├─ state_card (StateTracker)
  │       │   │   ├─ continuity_instruction (ContinuityEngine)
  │       │   │   ├─ scene_anchors (GlobalSummary)
  │       │   │   ├─ foreshadowing_summary (StateTracker)
  │       │   │   ├─ recent_summaries (GlobalSummary)
  │       │   │   └─ long_term_highlights (NovelMemory)
  │       │   └─ LLM stream → 章节正文 (逐token推送前端)
  │       ├─ _agent_style_editor_full() → 正则替换 [❌ 不调LLM]
  │       └─ memory_engine.update_after_chapter()
  │           ├─ StateTracker.set_last_ending()
  │           ├─ GlobalSummary.add_chapter_summary()
  │           ├─ NovelMemory.update_with_chapter()
  │           └─ ContinuityEngine.extract_continuity_hooks() → save_continuity_to_db()
  │
  └─ Loop 2: POLISH (精修层)
      ├─ agents["style_editor"].process() → 逐章精修+审查
      └─ agents["story_architect"].process() → 调整低分章节
  │
  ▼
持久化: _save_novel_to_db() + _export_novel_to_file()
```

### SSE 实时推送数据流

```
前端 OrchestratorPage
  │
  ├─ EventSource("/api/orchestrator/stream?...")
  │
  ▼
后端 main.py event_generator()
  │
  ├─ asyncio.Queue()  ← orchestrator 通过 _emit() 推送事件
  │
  ├─ Event类型:
  │   ├─ stage_start       → 阶段开始
  │   ├─ worldbuilding      → 世界观生成结果
  │   ├─ characters         → 角色生成结果
  │   ├─ opening_hook       → 开篇钩子
  │   ├─ style              → 风格指南
  │   ├─ outlining          → 大纲
  │   ├─ chapter_start      → 单章开始
  │   ├─ chapter_token      → 流式正文 (逐token)
  │   ├─ chapter_done       → 单章完成
  │   ├─ pipeline_step      → 管道步骤
  │   ├─ loop_iteration     → 循环迭代
  │   ├─ loop_done          → 循环完成
  │   ├─ heartbeat          → 心跳 (30s)
  │   ├─ final_result       → 最终结果
  │   └─ error              → 错误
  │
  ▼
前端 addEventListener 监听具名事件 → 实时渲染
```

### Prompt 解析数据流

```
PromptResolver.resolve_system_prompt(agent_type, depth_level)
  │
  ├─ 1. 查询 AgentPromptDB (is_active=1)
  │   └─ 优先匹配 novel_id 专属 → 其次通用模板
  │
  ├─ 2. Fallback: prompts.py build_*_system_prompt(depth_level)
  │
  ├─ 缓存: (_CACHE dict) → 热更新: clear_cache()
  │
  └─ 当前覆盖: _agent_outline + _agent_draft [仅2/6]
     └─ 待修复: _agent_world + _agent_character + _agent_opening_hook + _agent_style_editor_full
```

### 衔接引擎数据流

```
MemoryCoordinationEngine
  │
  ├─ generate_context_for_next_chapter()  ← 生成前调用
  │   ├─ StateTracker.build_story_bible()
  │   ├─ StateTracker.build_state_card()
  │   ├─ ContinuityEngine.generate_continuity_instruction()
  │   │   └─ 衔接强度: LearningEngine.get_continuity_intensity() [❌ 未传入]
  │   ├─ GlobalSummary.get_scene_anchors_text()
  │   ├─ StateTracker.get_foreshadowing_summary()
  │   ├─ GlobalSummary._summaries[-3:]
  │   └─ NovelMemory.top_items(5)
  │
  └─ update_after_chapter()  ← 生成后调用
      ├─ StateTracker.set_last_ending()
      ├─ GlobalSummary.add_chapter_summary()
      ├─ NovelMemory.update_with_chapter()
      └─ ContinuityEngine.extract_continuity_hooks() → save_continuity_to_db()
```

---

## 三、全部功能点清单

### 3.1 API 端点 (81个)

| 分类 | 端点 | 方法 | 功能 |
|------|------|------|------|
| 系统 | `/` | GET | 根路径，返回欢迎信息 |
| 系统 | `/health` | GET | 健康检查 |
| 系统 | `/api/health` | GET | API 健康检查 |
| Agent | `/api/agents` | GET | 列出所有已注册 Agent |
| Agent | `/api/agents/{agent_id}` | GET | 获取单个 Agent 信息 |
| Agent | `/api/agents/capability/{capability}` | GET | 按能力查询 Agent |
| 记忆 | `/api/memory/stats` | GET | 记忆系统统计 |
| 记忆 | `/api/memory/characters` | POST | 存储角色到记忆 |
| 记忆 | `/api/memory/world` | POST | 存储世界观到记忆 |
| 学习 | `/api/learning/stats` | GET | 学习引擎统计 |
| 学习 | `/api/learning/feedback` | POST | 提交用户反馈 |
| 学习 | `/api/learning/clear` | POST | 清除学习数据 |
| 创作 | `/api/create/outline` | POST | 生成大纲 |
| 创作 | `/api/create/draft` | POST | 生成草稿 |
| 创作 | `/api/create/draft-stream` | POST | SSE 流式生成草稿 |
| 创作 | `/api/create/edit` | POST | 编辑章节 |
| 创作 | `/api/create/edit-stream` | POST | SSE 流式编辑 |
| 创作 | `/api/create/review` | POST | 审查章节 |
| 创作 | `/api/create/world` | POST | AI 生成世界观 |
| 创作 | `/api/create/character` | POST | AI 生成角色 |
| 创作 | `/api/create/style` | POST | 生成风格指南 |
| 创作 | `/api/create/plot` | POST | 情节分析 |
| 创作 | `/api/create/full` | POST | 完整创作流程 |
| 创作 | `/api/create/world-auto` | POST | AI 自动生成世界观 |
| 创作 | `/api/create/character-auto` | POST | AI 自动生成角色 |
| LLM | `/api/llm/providers` | GET | 列出所有 LLM Provider |
| LLM | `/api/llm/config` | GET | 获取当前 LLM 配置 |
| LLM | `/api/llm/config` | POST | 设置 LLM 配置 |
| LLM | `/api/llm/test` | POST | 测试 LLM 连接 |
| LLM | `/api/llm/models` | POST | 获取远程模型列表 |
| LLM | `/api/llm/configs` | GET | 获取所有已保存配置 |
| LLM | `/api/llm/configs` | POST | 保存新配置 |
| LLM | `/api/llm/configs/{config_id}` | PUT | 更新配置 |
| LLM | `/api/llm/configs/{config_id}` | DELETE | 删除配置 |
| LLM | `/api/llm/configs/{config_id}/set-default` | POST | 设为默认配置 |
| 编排 | `/api/orchestrator/start` | POST | 启动 Loop 编排 |
| 编排 | `/api/orchestrator/start-loop` | POST | 启动 Loop 编排 (显式) |
| 编排 | `/api/orchestrator/start-linear` | POST | 启动线性编排 |
| 编排 | `/api/orchestrator/stage` | POST | 执行单阶段 |
| 编排 | `/api/orchestrator/status` | GET | 获取编排状态 |
| 编排 | `/api/orchestrator/export` | GET | 导出小说 |
| 编排 | `/api/orchestrator/list` | GET | 列出活跃编排器 |
| 编排 | `/api/orchestrator/{novel_id}/pause` | POST | 暂停编排 |
| 编排 | `/api/orchestrator/{novel_id}/resume` | POST | 恢复编排 |
| 编排 | `/api/orchestrator/{novel_id}/dashboard` | GET | 编排仪表盘 |
| 编排 | `/api/orchestrator/{novel_id}/check-consistency` | POST | 一致性审查 |
| 编排 | `/api/orchestrator/{novel_id}/memory-search` | GET | 语义搜索记忆 |
| 编排 | `/api/orchestrator/stream` | GET | SSE 实时流 |
| 小说 | `/api/novels` | GET | 列出小说 |
| 小说 | `/api/novels` | POST | 创建小说 |
| 小说 | `/api/novels/{novel_id}` | GET | 获取小说详情 |
| 小说 | `/api/novels/{novel_id}` | DELETE | 删除小说 |
| 小说 | `/api/novels/{novel_id}/chapters/{chapter_id}/content` | GET | 获取章节内容 |
| 小说 | `/api/novels/{novel_id}/chapters/{chapter_id}` | PUT | 更新章节 |
| 预设 | `/api/presets` | GET | 获取预设角色/世界观 |
| 预设 | `/api/settings/world` | POST | 保存世界观 |
| 预设 | `/api/settings/world/{setting_id}` | GET | 获取世界观详情 |
| 预设 | `/api/settings/world/{setting_id}` | PUT | 更新世界观 |
| 预设 | `/api/settings/world/{setting_id}` | DELETE | 删除世界观 |
| 预设 | `/api/settings/character` | POST | 保存角色 |
| 预设 | `/api/settings/character/{character_id}` | GET | 获取角色详情 |
| 预设 | `/api/settings/character/{character_id}` | PUT | 更新角色 |
| 预设 | `/api/settings/character/{character_id}` | DELETE | 删除角色 |
| Prompt | `/api/prompts` | GET | 列出 Prompt 模板 |
| Prompt | `/api/prompts/{prompt_id}` | GET | 获取 Prompt 详情 |
| Prompt | `/api/prompts` | POST | 新建 Prompt |
| Prompt | `/api/prompts/{prompt_id}` | PUT | 更新 Prompt |
| Prompt | `/api/prompts/{prompt_id}` | DELETE | 删除 Prompt |
| Prompt | `/api/prompts/{prompt_id}/activate` | POST | 激活 Prompt |
| Prompt | `/api/prompts/active/{agent_type}` | GET | 获取激活的 Prompt |
| Prompt | `/api/prompts/save-from-run` | POST | 批量保存 Prompt |
| Prompt | `/api/prompts/cache-clear` | POST | 清除缓存 (热更新) |
| Prompt | `/api/prompts/seed-defaults` | POST | 初始化默认模板 |
| 衔接 | `/api/continuity/save` | POST | 保存章节钩子 |
| 衔接 | `/api/continuity/{novel_id}` | GET | 获取衔接记录 |
| 衔接 | `/api/continuity/{novel_id}/instruction` | GET | 生成衔接指令 |
| 衔接 | `/api/continuity/{novel_id}/feedback` | POST | 提交衔接评分 |
| 衔接 | `/api/continuity/{novel_id}/stats` | GET | 衔接评分统计 |
| 执行 | `/api/executor/stats` | GET | 执行器统计 |
| 执行 | `/api/executor/recent` | GET | 最近执行记录 |

### 3.2 前端页面 (13个)

| 页面 | 组件 | 功能 |
|------|------|------|
| 系统总览 | OverviewPage | 系统状态概览、快速入口 |
| 全流程编排 | OrchestratorPage | 小说创作全流程、SSE 实时进度、参数配置 |
| 小说管理 | NovelManagerPage | 小说 CRUD、列表浏览 |
| 阅读模式 | NovelReadPage | 章节内容阅读 |
| 独立草稿 | StandaloneDraftPage | 单章草稿生成 |
| 独立编辑 | StandaloneEditPage | 单章内容编辑 |
| 角色管理 | CharactersPage | 角色 CRUD、预设管理 |
| 世界观设定 | WorldPage | 世界观 CRUD、预设管理 |
| 语义搜索 | SemanticSearchPage | 记忆内容语义搜索 |
| 学习引擎 | LearningPage | 用户反馈提交、学习统计 |
| 仪表盘 | DashboardPage | 编排器状态监控 |
| LLM 配置 | LLMConfigPage | 多 Provider 配置、模型管理 |
| Prompt 管理 | PromptManagerPage | 6个 Agent Prompt 模板 CRUD |

### 3.3 核心模块 (16个)

| 模块 | 文件 | 核心功能 |
|------|------|----------|
| 编排器 | orchestrator.py | 线性模式 + Loop 循环模式，状态机管理 |
| 写作管道 | chapter_pipeline.py | 6-Skill 协同管道，SKELETON/DETAIL/POLISH 三层 |
| 记忆协调 | memory_coordination.py | 统一协调 5 个记忆组件，token 预算管理 |
| 章节衔接 | continuity_engine.py | 章末钩子提取、衔接指令生成、DB 存储 |
| Prompt 解析 | prompt_resolver.py | 两级 fallback (DB → 硬编码)，缓存热更新 |
| 学习引擎 | learning_engine.py | 用户反馈学习、衔接强度动态调整 |
| 三层记忆 | memory.py | 工作/短期/长期记忆，重要度评分 |
| 状态追踪 | state_tracker.py | 角色/地点/伏笔状态，story_bible/state_card |
| 全局摘要 | global_summary.py | 章节摘要链、场景感官锚点 |
| 一致性检查 | consistency_checker.py | 跨章节世界观/角色/情节一致性 |
| Agent 注册 | agent_registry.py | Agent 发现与注册 |
| Agent 执行 | agent_executor.py | 执行追踪、日志 |
| 共享上下文 | shared_context.py | 上下文管理 |
| 流式生成 | chunked_generator.py | 分块流式内容生成 |
| 事件提取 | event_extractor.py | 事件提取 |
| Agent 初始化 | agent_registry_initializer.py | 启动时注册所有 Agent |

### 3.4 Agent Skill (14个文件，6个活跃)

| Agent | 文件 | 角色 | 能力 |
|-------|------|------|------|
| 故事架构师 | story_architect_agent.py | 大纲/结构 | outline, planning |
| 世界观构建师 | world_agent.py | 世界观 | world_building, setting |
| 角色塑造师 | character_agent.py | 角色 | character_design, development |
| 开篇钩子师 | opening_hook_agent.py | 开篇 | hook, opening |
| 专业写手 | draft_agent.py | 写作 | writing, draft |
| 文风精修师 | style_editor_agent.py | 编辑/审查 | editing, review, style |
| 大纲规划师 (旧) | outline_agent.py | 大纲 | outline (保留兼容) |
| 风格设计 (旧) | style_agent.py | 风格 | hook, opening (保留兼容) |
| 情节分析 (旧) | plot_agent.py | 情节 | plot, structure (保留兼容) |
| 编辑 (旧) | edit_agent.py | 编辑 | editing, review (保留兼容) |
| 审查 (旧) | review_agent.py | 审查 | review, analysis (保留兼容) |

### 3.5 数据库模型 (14个表)

| 模型 | 表名 | 核心字段 |
|------|------|----------|
| NovelDB | novels | id, title, genre, status, theme, tone, chapter_count, platform, word_count |
| VolumeDB | volumes | id, novel_id, title, index |
| ChapterDB | chapters | id, novel_id, volume_id, title, content, word_count, status, index |
| ChapterVersionDB | chapter_versions | id, chapter_id, content, version, created_at |
| AgentConfigDB | agent_configs | id, agent_type, config, is_active |
| CharacterDB | characters | id, name, role, personality, background, world_id, created_at, updated_at |
| CharacterRelationshipDB | character_relationships | id, character_id, related_id, relation_type |
| WorldSettingDB | world_settings | id, name, description, rules, key_locations, factions, created_at, updated_at |
| StyleGuideDB | style_guides | id, novel_id, style_data |
| UserFeedbackDB | user_feedback | id, feedback_type, before_text, after_text, created_at |
| AgentExecutionDB | agent_executions | id, agent_type, novel_id, input, output, duration_ms, success |
| LLMConfigDB | llm_configs | id, provider, api_key, model, api_base, is_default |
| AgentPromptDB | agent_prompts | id, agent_type, depth_level, prompt_type, title, content, quality_score, usage_count, is_active, novel_id, meta_info |
| ChapterContinuityDB | chapter_continuities | id, novel_id, chapter_idx, hooks, created_at |

### 3.6 LLM Provider (10+)

| Provider | 类名 | 说明 |
|----------|------|------|
| OpenAI | OpenAIProvider | GPT-4/GPT-3.5 等 |
| DeepSeek | DeepSeekProvider | DeepSeek-V3/R1 等 |
| Anthropic | AnthropicProvider | Claude 系列 |
| Google | GoogleProvider | Gemini 系列 |
| Qwen | QwenProvider | 通义千问 |
| Moonshot | MoonshotProvider | Kimi |
| Ollama | OllamaProvider | 本地模型 |
| OpenRouter | OpenRouterProvider | 聚合平台 |
| CustomOpenAI | CustomOpenAIProvider | 兼容 OpenAI API 的自定义服务 |
| Mock | MockProvider | 测试用 Mock |

---

## 四、已知问题

| 问题 | 严重程度 | 描述 |
|------|----------|------|
| 4个Agent不调LLM | 高 | _agent_world/character/opening_hook/style_editor_full 在管道中只生成硬编码文本 |
| LearningEngine 未集成 | 高 | orchestrator 未传入 learning_engine，衔接强度始终默认值 |
| PromptResolver 仅覆盖2/6 | 中 | 只有 story_architect 和 draft 使用 PromptResolver |
| 旧版 Agent 冗余 | 低 | outline_agent/plot_agent/edit_agent/review_agent/style_agent 已废弃但保留 |

---

## 五、文档说明

本文档基于 `d:\trae\novel-agent-system-v1.1.0` 项目代码实时分析生成，覆盖:

- 前端: 13个页面, 1个 API 客户端, 30+ 个 API 函数
- 后端: 81个 API 端点, 16个核心模块, 14个 Agent 文件, 10+ LLM Provider
- 数据库: 14个 SQLAlchemy 模型 (SQLite)
- 架构: 线性模式 + Loop 循环模式, SSE 实时流, 6-Skill 协同管道, 记忆协调引擎
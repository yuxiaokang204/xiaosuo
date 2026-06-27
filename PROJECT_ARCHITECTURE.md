# 小说创作Agent系统 - 项目架构文档 v1.1.0

> AI驱动的多Agent协作小说创作平台

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [核心模块设计](#3-核心模块设计)
4. [Agent系统设计](#4-agent系统设计)
5. [数据模型](#5-数据模型)
6. [API接口规范](#6-api接口规范)
7. [前端界面设计](#7-前端界面设计)
8. [技术栈](#8-技术栈)
9. [部署与运行](#9-部署与运行)
10. [测试体系](#10-测试体系)
11. [核心功能流程](#11-核心功能流程)
12. [扩展与优化](#12-扩展与优化)

---

## 1. 项目概述

### 1.1 项目定位

小说创作Agent系统是一个基于多Agent协作的AI小说创作辅助平台。它通过多个专业智能Agent协同工作，帮助用户从构思大纲、撰写章节、优化风格到完善人物，形成完整的创作流程。

### 1.2 核心价值

- **协作创作**：6个专业Skill分工协作，覆盖小说创作全流程
- **智能学习**：从用户反馈中学习风格偏好，持续优化输出
- **长上下文管理**：支持128K上下文，自动管理和选择记忆片段
- **可扩展架构**：服务注册与发现机制，支持灵活扩展Agent能力

### 1.3 项目目标

| 目标 | 描述 | 状态 |
|------|------|------|
| 多Agent协作 | 6个智能Skill协同创作 | ✅ 已实现 |
| 128K上下文 | 动态上下文窗口管理 | ✅ 已实现 |
| 风格学习 | 从用户反馈自动学习 | ✅ 已实现 |
| 完整创作流程 | 大纲→草稿→编辑→审查 | ✅ 已实现 |
| 数据持久化 | SQLite + ORM存储 | ✅ 已实现 |
| Web界面 | React + TypeScript | ✅ 已实现 |
| RESTful API | FastAPI服务层 | ✅ 已实现 |

---

## 2. 系统架构

### 2.1 整体架构分层

```
┌─────────────────────────────────────────────────────────┐
│                    用户界面层 (Frontend)                 │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐          │
│  │ NovelList │  │NovelEditor│  │CharacterMgr│ ...    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘          │
└────────┼──────────────┼──────────────┼──────────────────┘
         │              │              │
         ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                   API层 (FastAPI)                        │
│  ┌────────────────────────────────────────────────────┐ │
│  │   /api/novels/*   /api/agents/*   /api/*         │ │
│  └────────────────────────────────────────────────────┘ │
└────────┬──────────────┬──────────────┬──────────────────┘
         │              │              │
         ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                核心服务层 (Core)                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐          │
│  │  Agent    │  │  Memory   │  │ Learning  │          │
│  │ Registry  │  │  System   │  │  Engine   │          │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘          │
└────────┼──────────────┼──────────────┼──────────────────┘
         │              │              │
         ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│               Skill层 (6个专业智能体)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  故事   │  │ 世界观  │  │  角色   │ ... x6      │
│  │ 架构师  │  │ 构建师  │  │ 塑造师  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└────────┬──────────────┬──────────────┬──────────────────┘
         │              │              │
         ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│               数据层 (Database)                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │  models.py  │  crud.py  │  database.py            │ │
│  │  (ORM定义)  │ (数据操作) │ (连接管理)             │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
用户请求 → FastAPI接口层 → Core业务层
                          ↓
   响应数据 ← ORM查询 ← 数据模型层
       ↓
   React前端渲染 ← TypeScript类型
```

### 2.3 目录结构

```
/workspace
├── src/
│   ├── backend/                     # 后端核心代码
│   │   ├── main.py                  # FastAPI主入口
│   │   ├── agents/                  # 6个专业Skill实现
│   │   │   ├── base.py              # Skill抽象基类
│   │   │   ├── outline_agent.py     # 故事架构师 (大纲/情节规划)
│   │   │   ├── draft_agent.py       # 专业写手 (正文生成)
│   │   │   ├── edit_agent.py        # 文风精修师 (润色/审查)
│   │   │   ├── review_agent.py      # 质量审查
│   │   │   ├── world_agent.py       # 世界观构建师
│   │   │   ├── character_agent.py   # 角色塑造师
│   │   │   ├── style_agent.py       # 开篇钩子师 (前三章)
│   │   │   └── plot_agent.py        # 情节分析
│   │   ├── core/                    # 核心服务模块
│   │   │   ├── agent_registry.py        # Agent注册中心
│   │   │   ├── agent_registry_initializer.py  # Agent注册初始化
│   │   │   ├── memory.py            # 上下文记忆系统
│   │   │   ├── learning_engine.py   # 学习引擎
│   │   │   ├── orchestrator.py      # Agent编排器
│   │   │   └── shared_context.py    # 共享上下文总线
│   │   ├── db/                      # 数据持久层
│   │   │   ├── models.py            # SQLAlchemy模型
│   │   │   ├── crud.py              # CRUD操作
│   │   │   └── database.py          # 数据库连接管理
│   │   ├── models/                  # 数据模型
│   │   │   └── schemas.py           # Pydantic Schema (40+模型)
│   │   └── api/                     # API接口层
│   │       └── novels.py            # 小说相关API
│   └── frontend/                    # 前端代码
│       ├── src/
│       │   ├── main.tsx             # React入口
│       │   ├── App.tsx              # 主应用组件
│       │   ├── api.ts               # API调用封装
│       │   ├── types.ts             # TypeScript类型定义
│       │   └── components/          # UI组件
│       │       ├── NovelList.tsx    # 小说列表页
│       │       └── NovelEditor.tsx  # 小说编辑器
│       └── package.json             # 前端依赖
├── .env.example                     # 环境变量示例
├── pyproject.toml                   # Python项目配置
├── requirements.txt                 # 后端依赖
├── start.sh                         # 启动脚本
├── run.py                           # 简易启动脚本
├── test_project.py                  # 综合测试脚本 (111项测试)
└── PROJECT_ARCHITECTURE.md          # 本文档
```

---

## 3. 核心模块设计

### 3.1 Agent注册中心 (AgentRegistry)

**位置**: [src/backend/core/agent_registry.py](file:///workspace/src/backend/core/agent_registry.py)

#### 设计目标

实现服务注册与发现机制，提供统一的Agent管理入口，支持：
- 动态注册与注销Agent
- 按能力查询Agent
- 最佳Agent选择算法
- Agent启用/禁用控制

#### 核心类

```python
@dataclass
class AgentRegistration:
    id: str                          # Agent唯一ID
    name: str                        # Agent名称
    agent_type: AgentType            # WORKFLOW / SPECIALIST
    capabilities: List[str]          # 能力列表
    input_schema: Dict[str, Any]     # 输入Schema
    output_schema: Dict[str, Any]    # 输出Schema
    dependencies: List[str]          # 依赖Agent
    version: str = "1.0.0"          # 版本
    is_enabled: bool = True          # 是否启用
    config: Dict[str, Any]           # 配置项
```

```python
class AgentRegistry:
    _agents: Dict[str, AgentRegistration]       # id → Agent映射
    _capability_index: Dict[str, List[str]]     # 能力名 → [AgentID]

    # 核心方法
    register(agent: AgentRegistration)          # 注册Agent
    unregister(agent_id: str)                   # 注销Agent
    get(agent_id: str)                          # 获取Agent
    get_by_capability(capability: str)          # 按能力查询
    list_all()                                  # 所有Agent列表
    find_best_agent(required_capability: str)   # 最佳Agent选择
    enable(agent_id: str)                       # 启用
    disable(agent_id: str)                      # 禁用
    update_config(agent_id: str, config: Dict)  # 更新配置
    to_dict()                                   # 字典格式输出
```

#### 能力索引机制

```
注册时:
   AgentRegistration
        ↓
  capabilities = ["outline", "planning"]
        ↓
  _capability_index["outline"].append(agent_id)
  _capability_index["planning"].append(agent_id)

查询时:
   get_by_capability("outline")
        ↓
  _capability_index["outline"] → [id1, id2, ...]
        ↓
  [_agents[id] for id in ids if enabled]
```

### 3.2 Agent注册初始化器 (AgentRegistryInitializer)

**位置**: [src/backend/core/agent_registry_initializer.py](file:///workspace/src/backend/core/agent_registry_initializer.py)

#### 设计目标

在系统启动时自动完成所有Agent的注册和初始化工作。

#### 初始化流程

1. 创建新的AgentRegistry实例
2. 实例化所有6个Skill
3. 为每个Skill创建AgentRegistration元数据
4. 调用registry.register()完成注册
5. 验证完整性 (确保6个Skill都成功注册)

#### 注册的Skill列表

| ID | 名称 | 类型 | 能力 |
|----|------|------|------|
| outline_agent | 故事架构师 | WORKFLOW | outline, planning |
| draft_agent | 专业写手 | WORKFLOW | writing, draft |
| edit_agent | 文风精修师 | WORKFLOW | editing, review |
| review_agent | 质量审查 | WORKFLOW | review, analysis |
| world_agent | 世界观构建师 | SPECIALIST | world_building, setting |
| character_agent | 角色塑造师 | SPECIALIST | character_design, development |
| style_agent | 开篇钩子师 | SPECIALIST | hook, opening |
| plot_agent | 情节分析 | SPECIALIST | plot, structure |

### 3.3 记忆系统 (NovelMemory)

**位置**: [src/backend/core/memory.py](file:///workspace/src/backend/core/memory.py)

#### 设计目标

实现三层记忆架构，解决长文本上下文管理问题：
- **工作记忆**: 当前活跃的3个章节内容
- **短期记忆**: 最近的摘要链
- **长期记忆**: 角色信息、世界设定、未解决伏笔等

#### 重要性评分机制

```
ImportanceLevel (4级):
    CRITICAL (3) = 世界规则、魔法系统等
    HIGH     (2) = 角色信息、最近情节
    MEDIUM   (1) = 普通摘要
    LOW      (0) = 边缘信息

上下文窗口预算:
    model_context_size (默认128K)
    max_context_tokens = 128K * 0.6 = 76.8K tokens
    → 预留40%给模型生成内容
```

#### 核心数据结构

```python
class NovelMemory:
    # 三层记忆
    working_memory: List[str]          # 最近3章内容
    short_term_memory: List[Dict]      # 章节摘要
    long_term_memory: Dict[str, Any]   # 角色/世界观/伏笔

    # 上下文配置
    model_context_size: int            # 128000 (GPT-4o)
    max_context_tokens: int            # 76800 = 128K * 0.6

    # 重要性缓存
    importance_cache: Dict[str, ImportanceLevel]

    # 预设重要性等级
    world_rules_importance = CRITICAL
    character_importance = HIGH
    plot_importance = HIGH
    summary_importance = MEDIUM
```

#### 上下文构建流程

```
get_context(chapter) → Context:
    ├─ 收集世界规则 (CRITICAL)
    │   → 从long_term_memory["world_settings"]读取
    │   → 每个规则生成MemoryItem(tag="world")
    │
    ├─ 收集活跃角色信息 (HIGH)
    │   → 从long_term_memory["characters"]读取
    │   → 整合name/role/personality/background
    │   → 生成MemoryItem(tag="character")
    │
    ├─ 收集最近5章摘要 (HIGH/MEDIUM)
    │   → 从summary_chain[-5:]读取
    │   → 前2章HIGH，后3章MEDIUM
    │   → 生成MemoryItem(tag="summary")
    │
    ├─ 收集未解决伏笔 (HIGH)
    │   → 从long_term_memory["unresolved_foreshadowing"]读取
    │   → 生成MemoryItem(tag="foreshadowing")
    │
    └─ ContextBuilder.build()
       → 按importance排序
       → 逐项填入直到达到max_context_tokens
       → 按tags分类到Context.summaries/characters/world/foreshadowing
```

#### ContextBuilder算法

```
输入: [MemoryItem(importance=CRITICAL), MemoryItem(HIGH), ...]
流程:
    1. 按importance.value降序排序
    2. 初始化: current_tokens = 0
    3. 遍历每个item:
       item_tokens = len(item.content) // 3 + 100
       if current_tokens + item_tokens <= max_context_tokens:
           加入结果集
           current_tokens += item_tokens
       else:
           跳过 (窗口已满)
    4. 按tags分类到4个列表
输出: Context(summaries=[...], characters=[...], world=[...], foreshadowing=[...])
```

#### 记忆更新机制

```python
# 新章节写入时调用
update(chapter: Chapter):
    → 维护working_memory (保留最近3章)
    → 追加summary_chain ("章节标题 + 前100字...")
    → 追加未解决伏笔 (chapter.foreshadowing)
    → 移除已回收的伏笔 (chapter.callbacks)
```

### 3.4 学习引擎 (LearningEngine)

**位置**: [src/backend/core/learning_engine.py](file:///workspace/src/backend/core/learning_engine.py)

#### 设计目标

Phase 1 (规则驱动阶段): 从用户反馈中学习风格偏好，应用到文本优化。

#### 核心数据结构

```python
class LearningEngine:
    # 学到的模式
    style_patterns: Dict[str, PatternFrequency]
        → key = 修改前文本前缀(50字)
        → value = {count: 出现次数, last_seen: 时间}

    word_preferences: Dict[str, List[str]]
        → key = 原词
        → value = [偏好替换词1, 偏好替换词2, ...]

    anti_ai_patterns: List[Dict]
        → [{"pattern": "眼中闪过一丝", "replacements": ["眼神微动", ...]}, ...]

    feedback_history: List[UserFeedback]   # 所有历史反馈
    style_guide_updates: Dict[str, int]    # 风格指南更新统计
```

#### 学习流程

```
用户提交FeedbackRequest:
    ├─ feedback_type: STYLE_EDIT | CHARACTER_EDIT | PLOT_EDIT | DELETION | LIKE
    ├─ before_text: 修改前的文本片段
    ├─ after_text: 修改后的文本片段
    └─ metadata: {character_name, chapter_id, ...}

learn_from_feedback(feedback):
    │
    ├─ 记录到feedback_history
    │
    ├─ 根据feedback_type分支处理:
    │   ├─ STYLE_EDIT: 记录style_patterns + word_preferences
    │   ├─ CHARACTER_EDIT: 记录该角色style_guide_updates
    │   └─ DELETION: 将before_text加入anti_ai_patterns
    │
    └─ 通用分析: _analyze_pattern_changes(before, after)
       → 逐词对比，构建 word_preferences[原词] = [偏好词]
```

#### 应用偏好到文本

```python
apply_preference(content: str) -> str:
    result = content
    │
    ├─ Step 1: _remove_ai_taste(result)
    │   → 遍历anti_ai_patterns
    │   → 随机选择replacement替换pattern
    │
    ├─ Step 2: _apply_word_preferences(result)
    │   → 遍历word_preferences
    │   → 随机选择偏好词替换原词
    │
    └─ Step 3: _apply_style_patterns(result)
        → 取top10高频style_patterns
        → 用word_preferences中的首个偏好词替换

    return result
```

#### 内置反AI味表达库

| 模式 | 替换选项 |
|------|---------|
| 眼中闪过一丝 | 眼神微动 / 目光一凝 / 眼底掠过 |
| 心中涌起一股 | 心底 / 心头 / 胸腔中 |
| 忍不住 | 不由得 / 禁不住 / 不禁 |
| 与此同时 | 这时 / 此刻 / 就在这时 |

#### 学习约束与统计

```python
get_learned_constraints() -> Dict:
    {
        "style_patterns_count": 15,       # 已学风格模式
        "word_preferences_count": 200,    # 词汇偏好
        "anti_ai_patterns_count": 8,      # 反AI模式
        "feedback_count": 120,            # 总反馈数
        "top_patterns": [                 # Top5高频模式
            {"pattern": "...", "count": 8},
            ...
        ]
    }
```

### 3.5 共享上下文总线 (SharedContext)

**位置**: [src/backend/core/shared_context.py](file:///workspace/src/backend/core/shared_context.py)

#### 设计目标

确保多Agent间信息一致性，实现数据共享和冲突检测。

#### 核心功能

- 维护全局上下文状态
- 提供Agent间数据通信通道
- 检测和解决上下文冲突
- 记录Agent执行轨迹

### 3.6 章节生成管道 (ChapterPipeline)

**位置**: [src/backend/core/chapter_pipeline.py](file:///workspace/src/backend/core/chapter_pipeline.py)

#### 设计目标

6-Skill 协同写作管道，每个 Skill 都是内容创作者。通过多阶段规划→生成→审查，产出高质量章节正文。

#### 6个Skill

| Skill | 名称 | 职责 |
|-------|------|------|
| Skill 1 | 故事架构师 | 规划本章大纲结构、关键事件、情节线索和转折点 |
| Skill 2 | 世界观构建师 | 补充本章需要的世界观细节（地点、规则、势力） |
| Skill 3 | 角色塑造师 | 设计本章角色对白、动作、心理变化 |
| Skill 4 | 开篇钩子师 | 前三章使用，设计开篇悬念和钩子 |
| Skill 5 | 专业写手 | 注入所有 Skill 的建议，流式生成正文 |
| Skill 6 | 文风精修师 | 每5章完整审查，润色修改 |

#### 生成流程

```
Phase 1: 协同规划（4个Skill并行）
  ├── Skill 1: 故事架构师 → 大纲结构 + 关键事件
  ├── Skill 2: 世界观构建师 → 世界细节
  ├── Skill 3: 角色塑造师 → 角色行为设计
  └── Skill 4: 开篇钩子师 → 开篇悬念（仅前三章）

Phase 2: 核心生成
  └── Skill 5: 专业写手 → 流式生成正文

Phase 3: 质量审查（每5章或深度>=2时）
  └── Skill 6: 文风精修师 → 一致性审查 + 润色

#### Loop 架构（逐章迭代优化）

系统采用 SKELETON → DETAIL → POLISH 三层循环架构，逐章迭代提升质量：

```
SKELETON（骨架层）
  └── 快速生成：故事架构师 + 世界观构建师 + 角色塑造师 → 本章大纲 + 关键事件

DETAIL（血肉层）
  └── 正文生成：专业写手注入所有 Skill 建议 → 流式产出完整正文

POLISH（打磨层）
  └── 质量审查：文风精修师每5章或深度模式 → 一致性审查 + 润色修改
```

每一章经过 SKELETON → DETAIL → POLISH 三阶段后产出，确保章节质量逐层递进。
```

### 3.7 状态追踪器 (StateTracker)

**位置**: [src/backend/core/state_tracker.py](file:///workspace/src/backend/core/state_tracker.py)

#### 设计目标

追踪角色状态、故事时间线、伏笔、场景锚点等动态信息，在每章生成前构建"故事圣经"注入 prompt。

#### 核心方法

| 方法 | 说明 |
|------|------|
| `track_character()` | 追踪角色状态变化 |
| `set_last_ending(chapter, ending_text)` | 记录上一章结尾场景 |
| `get_last_ending()` | 获取上一章结尾 |
| `plant_foreshadowing()` | 埋设伏笔 |
| `resolve_foreshadowing()` | 回收伏笔 |
| `get_unresolved_foreshadowings()` | 获取未回收伏笔清单 |
| `build_story_bible()` | 构建故事圣经（核心设定+事件+状态+伏笔+场景锚点） |
| `build_state_card()` | 构建动态状态卡（简化实时状态） |
| `get_character_snapshot()` | 获取角色状态快照（位置、情绪、目标、持有物品） |

### 3.8 全局摘要 (GlobalSummary)

**位置**: [src/backend/core/global_summary.py](file:///workspace/src/backend/core/global_summary.py)

#### 设计目标

维护全篇小说的章节摘要，生成章节间衔接指令，管理场景感官锚点。

#### 核心方法

| 方法 | 说明 |
|------|------|
| `add_chapter_summary()` | 添加章节摘要 |
| `get_recent_context()` | 获取最近N章摘要 |
| `get_connection_instruction()` | 生成强制衔接指令（基于摘要） |
| `get_connection_instruction_with_text()` | 生成强制衔接指令（基于原文，优先使用） |
| `register_scene_anchor()` | 注册场景感官锚点 |
| `get_scene_anchors_text()` | 获取场景感官锚点文本 |

### 3.9 章节衔接机制（v1.1.0 新增）

#### 问题

旧版章节生成时，`_agent_draft` 的 prompt 中不包含上一章原文结尾，导致 LLM 不知道上一章写到了哪里，章节间缺乏连贯性。

#### 优化方案

建立"上一章结尾 → 下一章开头"的强制衔接链：

```
上一章正文内容
  ├── 提取 last_ending（最后 500-800 字原文）
  ├── 提取角色状态快照（位置、情绪、持有物品、当前目标）
  └── 注入到下一章的 ↓
      ├── _agent_draft prompt（核心注入点）— 上一章原文结尾区块
      ├── _agent_outline prompt（规划衔接）— 上一章结尾场景
      └── connection_instruction（衔接指令）— 基于原文的强制衔接
```

#### 数据流

```
Orchestrator.run_stage("drafting")
  ├── 提取上一章 chapters[-1].content[-800:] → previous_chapter_text
  ├── 传递到 ChapterPipeline.run(previous_chapter_text=...)
  │   ├── context["previous_chapter_text"] 注入到:
  │   │   ├── _agent_outline: 上一章结尾场景（规划参考）
  │   │   ├── _agent_draft: 【上一章结尾（请直接从此处接续）】区块
  │   │   ├── get_connection_instruction_with_text(): 基于原文的衔接指令
  │   │   └── get_character_snapshot(): 角色状态快照
  │   └── 生成正文
  └── 保存章末结尾 → state_tracker.set_last_ending()
```

#### 关键改进

1. **上一章原文注入 draft prompt**：`previous_chapter_text[-500:]` 直接出现在 prompt 中
2. **衔接指令使用原文**：`get_connection_instruction_with_text()` 优先使用原文而非摘要
3. **规划 Agent 感知上一章结尾**：`_agent_outline` 能看到上一章最后 300 字
4. **角色状态快照**：`get_character_snapshot()` 提供角色位置、情绪、目标等动态信息

---

## 4. Skill系统设计

### 4.1 Skill基类 (BaseAgent)

**位置**: [src/backend/agents/base.py](file:///workspace/src/backend/agents/base.py)

```python
class BaseAgent(ABC):
    def __init__(self, llm_client=None):
        self.llm_client = llm_client       # 可选的LLM客户端

    @abstractmethod
    async def process(self, context: Dict[str, Any]) -> Any:
        """处理上下文，返回结果"""
        pass
```

### 4.2 6个专业Skill详解

| Skill | 名称 | 文件 | 能力 | 职责 |
|-------|------|------|------|------|
| Skill 1 | 故事架构师 | outline_agent.py | outline, planning | 规划本章大纲结构、关键事件、情节线索 |
| Skill 2 | 世界观构建师 | world_agent.py | world_building, setting | 补充本章世界观细节（地点、规则、势力） |
| Skill 3 | 角色塑造师 | character_agent.py | character_design, development | 设计角色对白、动作、心理变化 |
| Skill 4 | 开篇钩子师 | style_agent.py | hook, opening | 前三章使用，设计开篇悬念和钩子 |
| Skill 5 | 专业写手 | draft_agent.py | writing, draft | 注入所有 Skill 建议，流式生成正文 |
| Skill 6 | 文风精修师 | edit_agent.py | editing, review | 每5章完整审查，润色修改 |

#### 4.2.1 故事架构师 (OutlineAgent)

**位置**: [src/backend/agents/outline_agent.py](file:///workspace/src/backend/agents/outline_agent.py)

**能力**: outline, planning

**输入**:
```python
{
    "theme": "穿越异世界冒险",
    "tone": "史诗",
    "chapter_count": 10
}
```

**输出**:
```python
{
    "success": True,
    "outline": [
        {"chapter": "第1章", "title": "...", "outline": "..."},
        ...
    ]
}
```

#### 4.2.2 世界观构建师 (WorldAgent)

**位置**: [src/backend/agents/world_agent.py](file:///workspace/src/backend/agents/world_agent.py)

**能力**: world_building, setting

**功能**: 设计世界规则、地理、历史、魔法系统

#### 4.2.3 角色塑造师 (CharacterAgent)

**位置**: [src/backend/agents/character_agent.py](file:///workspace/src/backend/agents/character_agent.py)

**能力**: character_design, development

**功能**: 设计角色、角色弧、关系图谱

#### 4.2.4 开篇钩子师 (StyleAgent)

**位置**: [src/backend/agents/style_agent.py](file:///workspace/src/backend/agents/style_agent.py)

**能力**: hook, opening

**功能**: 前三章使用，设计开篇悬念和钩子

#### 4.2.5 专业写手 (DraftAgent)

**位置**: [src/backend/agents/draft_agent.py](file:///workspace/src/backend/agents/draft_agent.py)

**能力**: writing, draft

**输入**: 章节大纲、上下文、角色信息、世界观细节

**输出**: 流式生成章节正文

#### 4.2.6 文风精修师 (EditAgent)

**位置**: [src/backend/agents/edit_agent.py](file:///workspace/src/backend/agents/edit_agent.py)

**能力**: editing, review

**功能**: 每5章或深度模式下执行一致性审查与润色修改

### 4.3 Skill类型与分工矩阵

```
Skill类型:
    WORKFLOW: 直接参与写作流程 (故事架构师/专业写手/文风精修师)
    SPECIALIST: 提供专业领域支持 (世界观构建师/角色塑造师/开篇钩子师)

分工矩阵:
    ┌──────────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
    │ 阶段/Skill   │故事架构师│世界观构建师│角色塑造师│开篇钩子师│专业写手  │文风精修师│
    ├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
    │ SKELETON骨架 │    ✅    │    ✅    │    ✅    │    ✅    │          │          │
    │ DETAIL 血肉  │          │          │          │          │    ✅    │          │
    │ POLISH 打磨  │          │          │          │          │          │    ✅    │
    └──────────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

---

## 5. 数据模型

### 5.1 Pydantic业务模型

**位置**: [src/backend/models/schemas.py](file:///workspace/src/backend/models/schemas.py)

#### 5.1.1 核心实体模型

```python
# 小说
class Novel(BaseModel):
    id: str                                # 唯一ID
    title: str                             # 小说标题
    genre: Optional[str] = None            # 类型
    target_word_count: Optional[int] = None  # 目标字数
    current_word_count: int = 0            # 当前字数
    status: NovelStatus = PLANNING         # 状态
    volumes: Optional[List[object]] = None # 分卷
    characters: Optional[List[object]] = None # 角色
    created_at: datetime
    updated_at: datetime

# 分卷
class Volume(BaseModel):
    id: str
    novel_id: str
    title: str
    description: Optional[str]
    word_count: int = 0
    order: int

# 章节
class Chapter(BaseModel):
    id: str
    volume_id: str
    title: str
    outline: Optional[str]                 # 大纲
    content: Optional[str]                 # 正文
    word_count: int = 0
    status: ChapterStatus = OUTLINE        # outline/draft/edited/completed
    characters_present: List[str]          # 出场角色
    locations: List[str]                   # 场景位置
    foreshadowing: List[str]               # 本章埋下的伏笔
    callbacks: List[str]                   # 本章回收的伏笔
    order: int
    created_at, updated_at

# 角色
class Character(BaseModel):
    id: str
    novel_id: str
    name: str
    aliases: List[str]
    role: str = "supporting"               # main/supporting/villain...
    personality: Optional[str]             # 性格
    background: Optional[str]              # 背景
    goals: List[str]                       # 目标
    conflicts: List[str]                   # 冲突
    arc: Optional[CharacterArc]            # 角色弧
    relationships: List[Relationship]      # 关系
    speech_pattern: Optional[str]          # 说话方式
    appearance: Optional[str]              # 外貌

# 世界观设定
class WorldSetting(BaseModel):
    id: str
    novel_id: str
    name: str
    category: str                          # geography/history/magic/society...
    description: Optional[str]
    rules: List[str]                       # 世界规则
    history: List[TimelineEvent]           # 历史时间线
    locations: List[Location]              # 地点
    factions: List[Faction]                # 势力
    magic_system: Optional[MagicSystem]    # 魔法系统

# 风格指南
class StyleGuide(BaseModel):
    id: str
    novel_id: str
    vocabulary_preference: List[str]       # 词汇偏好
    sentence_patterns: List[str]           # 句式
    pacing_preference: Optional[str]       # 节奏
    tone: Optional[str]                    # 语调
    anti_patterns: List[str]               # 禁用表达
    reference_works: List[str]             # 参考作品
```

#### 5.1.2 复杂嵌套模型

```python
class CharacterArc(BaseModel):
    start_state: str                       # 起点状态
    mid_state: str                         # 中段状态
    end_state: str                         # 终点状态
    key_events: List[str]                  # 关键事件

class Relationship(BaseModel):
    target_character_id: str               # 目标角色
    relationship_type: str                 # 关系类型
    description: str                       # 描述

class TimelineEvent(BaseModel):
    date: str                              # 时间
    event: str                             # 事件
    impact: str                            # 影响

class Location(BaseModel):
    name: str
    description: str
    coordinates: Optional[str]

class Faction(BaseModel):
    name: str
    description: str
    members: List[str]

class MagicSystem(BaseModel):
    name: str
    rules: List[str]
    power_levels: List[str]
```

#### 5.1.3 上下文与反馈模型

```python
class Context(BaseModel):
    summaries: List[str]
    characters: List[str]
    world: List[str]
    foreshadowing: List[str]

class UserFeedback(BaseModel):
    id: Optional[str]
    novel_id: str
    chapter_id: Optional[str]
    feedback_type: FeedbackType            # style/character/plot/deletion/like
    before_text: Optional[str]             # 修改前文本
    after_text: Optional[str]              # 修改后文本
    metadata: Optional[dict]               # 元数据
    created_at: datetime
```

#### 5.1.4 请求/响应模型

```python
# 创作请求
class OutlineRequest(BaseModel):
    theme: str; tone: Optional[str]; chapter_count: int = 10

class DraftRequest(BaseModel):
    chapter_id: str; additional_context: Optional[str]

class EditRequest(BaseModel):
    chapter_id: str; instructions: Optional[str]

class FeedbackRequest(BaseModel):
    chapter_id: Optional[str]
    feedback_type: FeedbackType
    before_text: Optional[str]
    after_text: Optional[str]
    metadata: Optional[dict]

# 结果响应
class DraftResult(BaseModel):
    success: bool; content: Optional[str]; word_count: int

class EditResult(BaseModel):
    success: bool; edited_content: Optional[str]; changes_count: int

class ExportResult(BaseModel):
    success: bool; file_path: Optional[str]; error: Optional[str]
```

#### 5.1.5 枚举类型

```python
class NovelStatus(str, Enum):
    PLANNING = "planning"                  # 构思中
    WRITING = "writing"                    # 撰写中
    COMPLETED = "completed"                # 已完成

class ChapterStatus(str, Enum):
    OUTLINE = "outline"                    # 大纲
    DRAFT = "draft"                        # 草稿
    EDITED = "edited"                      # 已编辑
    COMPLETED = "completed"                # 已完成

class FeedbackType(str, Enum):
    STYLE_EDIT = "style_edit"
    CHARACTER_EDIT = "character_edit"
    PLOT_EDIT = "plot_edit"
    DELETION = "deletion"
    LIKE = "like"

class CollaborationMode(str, Enum):
    AUTO = "auto"
    SEMI_AUTO = "semi_auto"
    MANUAL = "manual"

class ExportFormat(str, Enum):
    MARKDOWN = "markdown"
    EPUB = "epub"
    DOCX = "docx"
```

### 5.2 SQLAlchemy持久化模型

**位置**: [src/backend/db/models.py](file:///workspace/src/backend/db/models.py)

#### 5.2.1 表定义

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| novels | 小说元数据 | id, title, genre, status, word_count |
| volumes | 分卷信息 | id, novel_id(FK), title, word_count |
| chapters | 章节内容 | id, volume_id(FK), title, content, version |
| chapter_versions | 章节版本历史 | chapter_id, version_number, content, diff |
| agent_configs | Agent配置 | agent_id, agent_type, config, is_enabled |
| characters | 角色信息 | novel_id, name, personality, background, arc_data |
| character_relationships | 角色关系 | character_id, target, type, description |
| world_settings | 世界观设定 | novel_id, name, category, rules, history |
| style_guides | 风格指南 | novel_id, vocabulary, anti_patterns, tone |
| user_feedback | 用户反馈 | novel_id, chapter_id, type, before/after_text |
| agent_executions | Agent执行日志 | novel_id, agent_type, task_type, duration |

#### 5.2.2 JSON字段处理

```python
class JSONType(TypeDecorator):
    """Python对象 ↔ JSON字符串自动转换"""
    impl = TEXT

    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value else None

    def process_result_value(self, value, dialect):
        return json.loads(value) if value else None

# 使用方式:
class ChapterDB(Base):
    characters_present = Column(MutableList.as_mutable(JSONType), default=list)
    foreshadowing = Column(MutableList.as_mutable(JSONType), default=list)
    # MutableList: 列表元素修改自动触发脏检测
```

#### 5.2.3 关系映射

```
NovelDB  1──*  VolumeDB  1──*  ChapterDB
   │           │
   │ 1──* CharacterDB  1──* CharacterRelationshipDB
   │
   │ 1──* WorldSettingDB
   │
   │ 1──* StyleGuideDB
   │
   │ 1──* UserFeedbackDB
   │
   └── 1──* AgentExecutionDB

删除策略: cascade="all, delete-orphan"
→ 删除novel时，级联删除所有关联数据
```

#### 5.2.4 特殊设计说明

- **chapter_versions表**: 支持章节版本回溯，记录diff差异
- **agent_configs表**: 支持Agent配置持久化，运行时可修改
- **user_feedback表**: 反馈独立存储，为学习引擎提供训练数据源
- **metadata字段冲突解决**:
  - `metadata`是SQLAlchemy保留字段名
  - Python属性名: `feedback_metadata`
  - 数据库列名: `metadata` (通过`Column("metadata", JSONType)`)

---

## 6. API接口规范

### 6.1 FastAPI主应用

**位置**: [src/backend/main.py](file:///workspace/src/backend/main.py)

#### 启动生命周期

```python
@app.on_event("lifespan")
async def lifespan(app: FastAPI):
    # 启动:
    await init_db()                                   # 初始化数据库
    agent_initializer = AgentRegistryInitializer()    # 创建注册初始化器
    agent_initializer.initialize()                    # 注册6个Skill
    novel_memory = NovelMemory(GPT_4o=128000)         # 创建记忆系统
    learning_engine = LearningEngine()                # 创建学习引擎
    yield  # 开始处理请求
    # 关闭: (无)
```

#### CORS配置

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 开发环境允许所有
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

### 6.2 端点清单

#### 系统端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 系统信息 (version 1.0.0) |
| GET | `/health` | 健康检查 |

#### Agent管理端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/agents` | 列出所有已注册Agent |
| GET | `/api/agents/{agent_id}` | 获取单个Agent信息 |
| GET | `/api/agents/capability/{capability}` | 按能力查询Agent |

**响应示例** `GET /api/agents`:
```json
{
    "agents": {
        "outline_agent": {
            "id": "outline_agent",
            "name": "大纲Agent",
            "agent_type": "workflow",
            "capabilities": ["outline", "planning"],
            "version": "1.0.0",
            "is_enabled": true
        },
        "draft_agent": { ... },
        "... 6个Skill"
    }
}
```

#### 记忆系统端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/memory/stats` | 获取记忆系统统计 |

**响应示例**:
```json
{
    "stats": {
        "model_context_size": 128000,
        "max_context_tokens": 76800,
        "cached_importance_count": 0,
        "working_memory_count": 0,
        "summary_chain_length": 0
    }
}
```

#### 学习系统端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/learning/stats` | 获取学习统计 |
| POST | `/api/learning/clear` | 清空学习数据 |

**响应示例** `GET /api/learning/stats`:
```json
{
    "stats": {
        "total_feedback": 0,
        "style_edits": 0,
        "character_edits": 0,
        "learned_patterns": 0,
        "top_10_patterns": []
    }
}
```

#### 小说业务端点 (示例)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/novels` | 获取小说列表 |
| POST | `/api/novels` | 创建新小说 |
| GET | `/api/novels/{id}` | 获取小说详情 |
| PUT | `/api/novels/{id}` | 更新小说信息 |
| DELETE | `/api/novels/{id}` | 删除小说 |
| POST | `/api/novels/{id}/outline` | 生成大纲 |
| POST | `/api/novels/{id}/draft` | 生成草稿 |
| POST | `/api/novels/{id}/edit` | 编辑优化 |
| POST | `/api/novels/{id}/feedback` | 提交用户反馈 |
| POST | `/api/novels/{id}/export` | 导出小说 |

---

## 7. 前端界面设计

### 7.1 技术栈

- **框架**: React 18
- **语言**: TypeScript
- **样式**: CSS Modules
- **构建**: Vite
- **API调用**: Fetch API

### 7.2 组件结构

```
App.tsx (根组件)
    ├─ state: viewMode ('list' | 'editor')
    ├─ state: novels (小说列表)
    ├─ state: selectedNovelId
    │
    ├─ NovelList.tsx (列表视图)
    │   └─ 创建/选择小说
    │
    └─ NovelEditor.tsx (编辑视图)
        ├─ 章节管理
        ├─ 大纲编辑
        ├─ 草稿撰写
        └─ 角色/世界观管理
```

### 7.3 TypeScript类型定义

**位置**: [src/frontend/src/types.ts](file:///workspace/src/frontend/src/types.ts)

```typescript
enum NovelStatus { PLANNING, WRITING, COMPLETED }

interface NovelSummary {
    id: string;
    title: string;
    genre: string;
    status: NovelStatus;
    current_word_count: number;
    target_word_count: number;
    updated_at: Date;
}

interface Volume { id: string; novel_id: string; title: string; ... }
interface Character { id: string; novel_id: string; name: string; role: string; ... }
interface WorldSetting { id: string; novel_id: string; name: string; category: string; ... }
// ...与后端Pydantic模型一一对应
```

### 7.4 API调用封装

**位置**: [src/frontend/src/api.ts](file:///workspace/src/frontend/src/api.ts)

```typescript
const API_BASE = 'http://localhost:8080';

export const api = {
    // 小说管理
    getNovels: async (): Promise<NovelSummary[]> => { ... },
    createNovel: async (title: string, genre: string): Promise<Novel> => { ... },
    getNovel: async (id: string): Promise<Novel> => { ... },

    // Agent管理
    getAgents: async () => { ... },
    getAgent: async (agentId: string) => { ... },

    // 记忆统计
    getMemoryStats: async () => { ... },

    // 学习统计
    getLearningStats: async () => { ... },
    clearLearning: async () => { ... }
};
```

---

## 8. 技术栈

### 8.1 后端技术栈

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| Web框架 | FastAPI | ^0.104 | API服务层 |
| ASGI服务器 | Uvicorn | ^0.24 | 异步HTTP服务器 |
| 数据验证 | Pydantic | ^2.5 | Schema验证 |
| ORM | SQLAlchemy | ^2.0 | 数据库ORM |
| 数据库 | SQLite | - | 本地数据存储 |
| 异步驱动 | aiosqlite | ^0.19 | SQLite异步 |
| 语言 | Python | 3.10+ | 编程语言 |

### 8.2 前端技术栈

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| UI框架 | React | ^18.2 | 前端框架 |
| 语言 | TypeScript | ^5.3 | 类型安全 |
| 构建工具 | Vite | ^5.0 | 快速构建/热更新 |
| 包管理 | npm | - | 依赖管理 |
| 样式 | CSS Modules | - | 样式隔离 |

### 8.3 Python依赖 (pyproject.toml)

```toml
[project]
name = "novel-agent-system"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.19.0",
    "python-dotenv>=1.0.0",
]
```

---

## 9. 部署与运行

### 9.1 环境准备

```bash
# 1. 安装Python 3.10+
python --version  # Python 3.10.x

# 2. 安装后端依赖
cd /workspace
pip install -r requirements.txt
# 或使用:
pip install fastapi uvicorn pydantic sqlalchemy aiosqlite python-dotenv

# 3. 安装前端依赖 (可选，若需构建前端)
cd /workspace/src/frontend
npm install
```

### 9.2 配置环境变量

复制 `.env.example` 为 `.env` 并修改:

```bash
cp /workspace/.env.example /workspace/.env
```

`.env` 内容:
```
# 数据库 (默认SQLite，无需修改即可运行)
DATABASE_URL=sqlite+aiosqlite:///./novel_agent.db

# 应用配置
APP_NAME=小说创作Agent系统
APP_ENV=development
DEBUG=true

# LLM API (可选 - 集成OpenAI/Anthropic等时填入)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

### 9.3 启动服务

#### 方式1: 使用start.sh脚本

```bash
cd /workspace
chmod +x start.sh
./start.sh
# → 启动在 http://localhost:8080
```

#### 方式2: 使用run.py

```bash
cd /workspace
python run.py
# → 启动在 http://localhost:8080
```

#### 方式3: 直接调用uvicorn

```bash
cd /workspace
python -m uvicorn src.backend.main:app --reload --host 0.0.0.0 --port 8080
# --reload: 代码变更自动重启 (仅开发环境)
```

### 9.4 验证部署

```bash
# 1. 检查健康端点
curl http://localhost:8080/health
# {"status": "healthy"}

# 2. 检查系统信息
curl http://localhost:8080/
# {"message": "小说创作Agent系统", "version": "1.0.0"}

# 3. 检查Agent注册
curl http://localhost:8080/api/agents
# 应返回6个已注册Skill的列表

# 4. 浏览器访问交互式API文档
# 打开: http://localhost:8080/docs
```

### 9.5 生产部署建议

```
方案A: Docker容器化
    ├─ FROM python:3.10-slim
    ├─ WORKDIR /app
    ├─ COPY . .
    ├─ RUN pip install -r requirements.txt
    └─ CMD ["uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8080"]

方案B: 传统服务器部署
    ├─ Nginx反向代理: 80/443 → 8080
    ├─ systemd管理uvicorn进程
    ├─ SQLite文件定期备份
    └─ 日志轮转 (logrotate)

方案C: 云平台部署 (Vercel/AWS/Azure)
    └─ FastAPI原生支持各种Serverless平台
```

---

## 10. 测试体系

### 10.1 综合测试脚本

**位置**: [test_project.py](file:///workspace/test_project.py)

#### 测试范围 (111项，100%通过)

| 模块 | 测试数 | 覆盖内容 |
|------|--------|---------|
| Agent注册系统 | 10 | 注册/注销/查询/按能力查询/启用/禁用/字典化 |
| 记忆系统 | 8 | 初始化/统计/角色存储/世界观/上下文构建/重要性 |
| 学习引擎 | 7 | 初始化/反馈学习/偏好应用/统计/清除/约束 |
| Agent实现 | 16 | 6个Skill的实例化+process方法存在性 |
| 注册初始化器 | 10 | 6个Skill完整注册、完整性验证 |
| Pydantic Schema | 52 | 40个模型定义存在性 + 核心模型实例化验证 |
| FastAPI主应用 | 8 | 健康检查/Agent API/记忆统计/学习统计端点 |

#### 运行测试

```bash
cd /workspace
python test_project.py

# 预期输出:
# [PASS] 1.1 AgentRegistry 实例创建
# [PASS] 1.2 Agent 注册功能
# ...
# [PASS] 7.8 学习统计API端点
# ============================================================
# 测试完成: 111 通过, 0 失败, 0 跳过 (耗时: 0.73s)
# ============================================================
# 结论: 100% 通过 - 项目架构正常
```

### 10.2 测试模块详解

#### 模块1: Agent注册系统

```
测试: registry.register() / get() / list_all()
      get_by_capability() / find_best_agent()
      enable() / disable() / to_dict()
验证: 能力索引正确性 / 最佳Agent算法 / 状态转换一致性
```

#### 模块2: 记忆系统

```
测试: NovelMemory(GPT_4o=128K) 初始化
      store_characters() / store_world_settings()
      get_context_stats() 输出结构
      ContextBuilder.build() 算法正确性
验证: 重要性等级 CRITICAL > HIGH > MEDIUM > LOW
      上下文窗口 max_context_tokens = 76800
```

#### 模块3: 学习引擎

```
测试: learn_from_feedback(STYLE_EDIT/CHARACTER_EDIT/DELETION)
      apply_preference() 应用到文本
      get_statistics() / get_learned_constraints()
      clear_learning() 重置
验证: 反AI味表达被正确替换
      词偏好正确学习和应用
```

#### 模块4: Agent实现

```
测试: OutlineAgent/DraftAgent/EditAgent/ReviewAgent
      WorldAgent/CharacterAgent/StyleAgent/PlotAgent
      每个Agent: isinstance(x, BaseAgent)
                hasattr(x, 'process')
                x.process() is awaitable
验证: 6个Skill正确继承BaseAgent抽象基类
```

#### 模块5: 注册初始化器

```
测试: initializer.initialize() 成功
      registry.list_all() 返回6个Skill
      预期AgentID集合 = 实际注册AgentID集合
验证: 没有遗漏注册、没有重复注册
```

#### 模块6: Pydantic Schema

```
测试: 40个Schema定义在schemas.py中存在
      Novel/Chapter/Character/WorldSetting 可实例化
      枚举值 NovelStatus/FeedbackType 正确
验证: 所有必填字段有合理默认值
      类型注解与数据库模型一致
```

#### 模块7: FastAPI主应用

```
测试: TestClient(app) 初始化
      GET / → 200 + version字段
      GET /health → 200
      GET /api/agents → 包含6个Skill
      GET /api/memory/stats → model_context_size存在
      GET /api/learning/stats → total_feedback存在
验证: 所有API端点响应状态码200
      JSON响应结构符合设计预期
```

---

## 11. 核心功能流程

### 11.1 小说创建流程

```
用户点击"创建小说"
      ↓
POST /api/novels (title="xxx", genre="xxx")
      ↓
CRUD.create_novel() → 写入novels表
      ↓
返回Novel对象给前端
      ↓
前端跳转到NovelEditor视图
```

### 11.2 大纲生成流程

```
用户输入主题 + 章节数
      ↓
POST /api/novels/{id}/outline
      ↓
① AgentRegistry.find_best_agent("outline") → OutlineAgent
② 从NovelMemory获取世界观/角色上下文
③ 调用 outline_agent.process({theme, tone, chapter_count})
④ 返回章节大纲列表
      ↓
将大纲写入chapters表 (status=OUTLINE)
      ↓
前端展示章节列表，等待用户进入下一步
```

### 11.3 草稿生成流程（v1.1.0 增强章节衔接）

```
用户选择章节，点击"生成草稿"
      ↓
POST /api/novels/{id}/draft/{chapter_id}
      ↓
① AgentRegistry.find_best_agent("draft") → DraftAgent
② NovelMemory.get_context(chapter) → 构建上下文
   → 包含: 世界观规则/角色信息/最近摘要/未解决伏笔
③ draft_agent.process({outline, context})
④ learning_engine.apply_preference(草稿内容)
   → 移除AI味表达 + 应用学习到的风格偏好
      ↓
更新chapters表 (content=草稿, status=DRAFT)
novel_memory.update(chapter)  # 写入记忆链
      ↓
前端展示草稿内容，等待编辑或反馈
```

#### 全流程编排中的章节衔接增强（v1.1.0）

```
Orchestrator.run_stage("drafting") 逐章循环:
      ↓
① 提取上一章结尾原文 chapters[-1].content[-800:] → previous_chapter_text
      ↓
② 传递到 ChapterPipeline.run(previous_chapter_text=...)
      ↓
③ context["previous_chapter_text"] 注入到:
   ├── _agent_outline: 上一章结尾场景（规划大纲时参考）
   ├── _agent_draft: 【上一章结尾（请直接从此处接续）】区块
   ├── get_connection_instruction_with_text(): 基于原文的强制衔接指令
   └── get_character_snapshot(): 角色状态快照（位置/情绪/目标）
      ↓
④ LLM 生成正文时，prompt 中包含上一章最后 500 字原文
      ↓
⑤ 保存章末结尾 → state_tracker.set_last_ending()
   更新 global_summary → 为下一章衔接做准备
```

### 11.4 用户反馈学习流程

```
用户在编辑器中修改文本
      ↓
POST /api/novels/{id}/feedback
      {feedback_type: "style_edit",
       before_text: "眼中闪过一丝...",
       after_text: "眼神微动...",
       metadata: {chapter_id, character_name}}
      ↓
① learning_engine.learn_from_feedback(feedback)
   → 记录到style_patterns
   → 记录到word_preferences
   → 写入user_feedback表
② learning_engine.get_statistics() 更新统计
      ↓
下次生成草稿时自动应用新学到的偏好
```

### 11.5 上下文窗口管理流程

```
写作第N章
    ↓
novel_memory.update(chapter_N):
    ├─ working_memory = [章N-2, 章N-1, 章N]   (保留最近3章)
    ├─ summary_chain.append("章N标题 + 前100字...")
    ├─ 追加 chapter_N.foreshadowing → unresolved_foreshadowing
    └─ 从unresolved_foreshadowing中移除chapter_N.callbacks

写作第N+1章
    ↓
context = novel_memory.get_context(chapter_N+1):
    ├─ 收集: 世界规则(CRITICAL) + 角色(HIGH) +
    │        最近5章摘要(前2章HIGH, 后3章MEDIUM) +
    │        未解决伏笔(HIGH)
    ├─ ContextBuilder:
    │   → 按importance排序
    │   → 逐项计算tokens
    │   → 直到达到76800上限
    └─ 按tags分类到Context.summaries/characters/world/foreshadowing
    ↓
传递给DraftAgent.process()使用
```

---

## 12. 扩展与优化

### 12.1 短期优化目标 (v1.1)

| 目标 | 优先级 | 技术方案 |
|------|--------|---------|
| 真正的LLM集成 | 高 | 接入OpenAI/DeepSeek API，替换当前的占位生成 |
| 章节版本管理UI | 高 | 前端展示chapter_versions表，支持版本切换 |
| Agent配置持久化 | 中 | UI修改agent_configs表，runtime热更新 |
| 学习引擎可视化 | 中 | 展示top_patterns / anti_ai_patterns统计 |
| 多用户支持 | 中 | 引入用户表 + JWT认证 |

### 12.2 中期架构优化 (v2.0)

| 目标 | 技术方案 |
|------|---------|
| Agent异步编排 | Celery + Redis / RabbitMQ，将Agent调用移至后台队列 |
| 向量数据库集成 | 使用FAISS/Chroma，将长文本记忆转为向量相似度检索 |
| 学习引擎Phase 2 | 引入规则引擎 + 简单ML模型，从反馈历史训练偏好分类器 |
| 缓存层 | Redis缓存频繁访问的上下文和统计数据 |
| 消息总线 | NATS / Kafka，实现Agent间事件驱动协作 |

### 12.3 长期演进方向 (v3.0+)

| 方向 | 描述 |
|------|------|
| 多用户协作 | 多人协作创作，实时编辑同步 (WebSocket + CRDT) |
| Agent市场 | 用户可上传/分享/下载自定义Agent插件 |
| 智能推荐 | 基于用户写作历史推荐角色/情节/风格方向 |
| 生成对抗审查 | ReviewAgent + 人类反馈形成RLHF闭环 |
| 多语言翻译 | 自动中英文小说翻译与本地化 |

### 12.4 代码质量保障

```
静态检查:
    ├─ mypy / pyright: 类型检查
    ├─ flake8: 代码风格 (PEP 8)
    ├─ black: 自动代码格式化
    └─ isort: 导入排序

运行时检查:
    ├─ 111项单元测试 (test_project.py)
    ├─ FastAPI依赖注入确保类型安全
    └─ Pydantic数据验证确保输入完整性

监控 (未来):
    ├─ Agent执行日志 (agent_executions表)
    ├─ 性能统计: 每次Agent调用duration_ms
    └─ 错误追踪: error_log字段记录异常信息
```

### 12.5 安全注意事项

```
当前默认开发环境: CORS=*, DB=SQLite, NO AUTH

生产部署必须:
    ├─ 限制CORS_ORIGINS = ["https://yourdomain.com"]
    ├─ 数据库迁移到PostgreSQL/MySQL
    ├─ 添加JWT/OAuth2认证
    ├─ .env中的密钥不要提交到仓库
    └─ 所有API请求添加速率限制
```

---

## 13. v6.0 角色代入式创作（Character Roleplay）

### 13.1 设计理念

v6.0 引入"角色代入式创作"机制，核心目标：**保证人物行为一致性**。

- **角色不是被描述的对象，而是被代入的身份**：每个角色基于其设定和经历记忆行动
- **角色不能"失忆"**：角色行为基于"原始性格 + 经历记忆塑造的新认知"综合决策
- **角色不能"全知"**：角色只能基于自己应该知道的信息行动
- **多线程并行代入**：所有出场角色同时代入，无需先主角后配角
- **角色生命周期管理**：角色不再出现即视为退场，退场角色不再代入

### 13.2 核心组件

#### 13.2.1 CharacterRoleplayAgent（角色代入Agent）
- **文件**: `src/backend/agents/character_roleplay_agent.py`
- **职责**:
  - `generate_roleplay_card`: 为单个角色生成代入卡（内心独白/行为倾向/对话风格/记忆影响/关键决策/情绪状态/一致性校验）
  - `generate_roleplay_cards_parallel`: 多线程并行代入所有出场角色（asyncio.gather）
  - `extract_character_memory`: 从章节正文提取角色经历记忆
  - `extract_memories_parallel`: 多线程并行提取所有角色经历记忆
  - `format_roleplay_cards`: 格式化代入卡列表为注入DraftAgent的文本
  - `detect_scene_type`: 识别场景类型（narrative/perspective/dialogue）

#### 13.2.2 角色经历记忆链（CharacterExperienceMemory）
- **文件**: `src/backend/core/state_tracker.py`
- **数据结构**:
  - `chapter`: 章节序号
  - `experienced_events`: 该角色在此章经历的所有重要事件（第一人称视角）
  - `emotional_trajectory`: 情绪变化轨迹（如"平静→震惊→愤怒→释然"）
  - `cognition_updates`: 认知更新（新获得的认知/信念改变）
  - `personality_shifts`: 性格微调（因此章经历产生的性格变化）
  - `decisions_made`: 该角色在此章做出的关键决策
  - `information_gained`: 该角色在此章获得的关键信息
  - `relationships_change`: 该角色对他人看法的改变
- **管理方法**:
  - `append_character_memory`: 章节生成后追加角色经历记忆
  - `get_character_memory_chain`: 获取角色截至某章的完整经历记忆链
  - `get_character_behavior_context`: 生成角色行为上下文摘要（用于代入卡生成）

#### 13.2.3 数据库扩展
- **CharacterDB 新增字段**:
  - `psychological_profile`: 心理画像（JSON）
  - `behavior_tags`: 行为标签（JSON数组）
  - `relationship_webs`: 关系网（JSON数组）
  - `speech_fingerprint`: 语言指纹（JSON）
  - `first_appear_chapter`: 首次出场章节
  - `last_appear_chapter`: 最后出场章节（null表示未退场）
  - `character_status`: 角色状态（active/exited/dead）
- **WorldSettingDB 新增字段**:
  - `key_locations`: 关键地点（JSON数组，含感官锚点）
  - `factions`: 势力格局（JSON数组）
  - `unique_appeal`: 独特卖点
- **CharacterMemoryDB（新表）**: 角色经历记忆持久化存储

### 13.3 创作流程整合

#### 13.3.1 故事走向生成（story_direction）
- **时机**: outlining 阶段完成后、drafting 前
- **作用**: 为角色代入和章节生成提供故事方向指引（主线脉络、关键转折、情感基调、爽点分布）
- **方法**: `NovelOrchestrator._generate_story_direction()`

#### 13.3.2 章节生成流程（ChapterPipeline.run）
1. Skill 1-3: 故事架构师/世界观/角色协同规划
2. **v6.0 角色代入**（Skill 3.5）: 多线程并行代入所有出场角色
   - `_get_active_characters_for_chapter`: 基于角色生命周期过滤活跃角色
   - `_agent_character_roleplay_parallel`: 并行生成角色代入卡
   - 代入卡注入 `context["roleplay_cards"]`
3. Skill 4: 开篇钩子师（仅前三章）
4. Skill 5: 专业写手流式生成（注入角色代入卡和故事走向）
5. Skill 6: 文风精修师（每5章完整审查）
6. **v6.0 记忆更新**: 章节生成后并行提取所有角色经历记忆，追加到记忆链

#### 13.3.3 角色代入触发条件
- `depth_level >= 1`（Loop 0 SKELETON 跳过，Loop 1+ 触发）
- 章节有活跃角色（基于生命周期过滤）

#### 13.3.4 记忆更新触发条件
- `depth_level >= 1` 且章节内容非空

### 13.4 一致性保障

#### 13.4.1 ConsistencyChecker 扩展
- **新增方法**: `check_roleplay_consistency`
- **校验维度**:
  1. 语言指纹一致性（禁用词检查）
  2. 行为标签一致性
  3. 角色经历记忆一致性（避免"失忆"）
- **调用位置**: `check_chapter` 方法中，传入 `character_memories` 参数

#### 13.4.2 Loop 0 串行化
- **问题**: Loop 0 世界观和角色并行生成，角色生成时 `world_info` 为空
- **修复**: Loop 0 改为串行（先世界观后角色），Loop 1+ 保持并行（已有世界观）

### 13.5 前端类型适配
- **文件**: `src/frontend/src/types.ts`
- Character 接口新增: psychological_profile、behavior_tags、relationship_webs、speech_fingerprint、first_appear_chapter、last_appear_chapter、character_status
- WorldSetting 接口新增: key_locations、factions、unique_appeal

### 13.6 验证日志
创建新小说时，日志应出现：
- `[Orchestrator] ✅ 故事走向生成完成`
- `[Roleplay] 第X章角色代入完成：N个角色，场景类型=xxx`
- `[Roleplay] 第X章角色经历记忆更新完成：N个角色`

---



## 附录: 设计参考文档

| 文档 | 路径 | 内容 |
|------|------|------|
| 设计评审报告 | [novel-agent-design-review.md](file:///workspace/novel-agent-design-review.md) | 架构设计评审意见 |
| 设计文档 | [novel-agent-design.md](file:///workspace/novel-agent-design.md) | 原始设计方案 |
| README | [README.md](file:///workspace/README.md) | 项目说明 |
| 测试报告 | 运行 `python test_project.py` | 最新测试结果 |

---

*文档版本: 1.0.0*
*最后更新: 基于项目当前代码自动生成*

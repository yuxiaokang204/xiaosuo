# 小说创作Agent系统 v2.0 重构方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 对现有 novel-agent-system-v1.1.0 进行全面重构，引入分层编排架构、向量记忆系统、风格指纹学习引擎、Next.js 14 前端。

**Architecture:** 采用三层架构（L1 规划层 + L2 执行层 + L3 工具层），使用 ChromaDB 实现语义向量记忆，通过统计式风格指纹实现个性化写作，前端迁移到 Next.js 14 App Router。

**Tech Stack:**
- **后端**: Python 3.12+, FastAPI, SQLAlchemy, SQLite, ChromaDB, httpx
- **前端**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, shadcn/ui
- **AI**: 多Provider LLM 抽象层（10+ 支持）
- **向量检索**: ChromaDB + sentence-transformers

---

## 目录

1. [现有问题分析](#1-现有问题分析)
2. [新架构设计](#2-新架构设计)
3. [后端模块设计](#3-后端模块设计)
4. [前端模块设计](#4-前端模块设计)
5. [数据模型设计](#5-数据模型设计)
6. [API 接口设计](#6-api-接口设计)
7. [数据流设计](#7-数据流设计)
8. [实施计划](#8-实施计划)
9. [迁移策略](#9-迁移策略)

---

## 1. 现有问题分析

### 1.1 架构问题

| 问题 | 严重程度 | 影响 |
|------|---------|------|
| `main.py` 2924行，违反单一职责 | 🔴 高 | 无法维护、无法测试、无法扩展 |
| Agent 系统单层扁平，8个Agent无层次 | 🟡 中 | 协作效率低、调度逻辑混乱 |
| LOOP 循环和线性架构并存（v3.0 + v4.0） | 🟡 中 | 代码冗余、逻辑复杂 |
| 记忆系统 TF-IDF 精度有限 | 🟡 中 | 长篇小说上下文质量下降 |
| 学习引擎纯规则驱动 | 🟢 低 | 风格对齐效果一般 |

### 1.2 代码组织问题

```
当前结构:
src/backend/
├── main.py              # 2924行 - 所有路由 + 初始化 + 业务逻辑
├── core/
│   ├── orchestrator.py  # 1335行 - LOOP + 线性混合
│   ├── memory.py        # 400行 - TF-IDF 语义搜索
│   └── learning_engine.py # 227行 - 规则替换
└── agents/
    └── *.py             # 8个Agent扁平排列
```

### 1.3 前端问题

- 纯 React SPA，无 SSR/SSG
- 无叙事可视化组件
- 组件风格不统一（自定义 CSS）

---

## 2. 新架构设计

### 2.1 三层架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      前端层 (Next.js 14)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │ 叙事面板  │ │ 创作面板  │ │ 管理面板  │ │ 可视化面板     │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │ SSE / REST
┌─────────────────────────────────────────────────────────────┐
│                  API 网关层 (FastAPI 模块化)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │ /api/novels││/api/orch││/api/agent││ /api/memory     │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  L1 规划层 (Planner)                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          NovelPlannerAgent (总调度)                    │   │
│  │  - 全局规划生成                                        │   │
│  │  - 阶段决策                                            │   │
│  │  - 质量门控判断                                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  L2 执行层 (Specialists)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │Outline   │ │World     │ │Character │ │Draft          │ │
│  │Agent     │ │Agent     │ │Agent     │ │Agent          │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │Edit      │ │Review    │ │Style     │ │Plot           │ │
│  │Agent     │ │Agent     │ │Agent     │ │Agent          │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  L3 工具层 (Tools)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │Memory    │ │Learning  │ │Consist.  │ │PromptManager  │ │
│  │Service   │ │Service   │ │Checker   │ │Service        │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  基础设施层 (Infrastructure)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │LLM       │ │ChromaDB  │ │SQLite    │ │SSE            │ │
│  │Gateway   │ │Vector    │ │ORM       │ │Streaming      │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
src/
├── backend/
│   ├── main.py                    # FastAPI 入口（仅导入和路由注册）
│   ├── config/
│   │   ├── settings.py            # 配置管理（环境变量 + .env）
│   │   └── logging.py             # 日志配置
│   ├── routes/                    # 模块化路由
│   │   ├── __init__.py
│   │   ├── novels.py              # 小说管理 CRUD
│   │   ├── orchestrator.py        # 编排器控制
│   │   ├── agents.py              # Agent 调用
│   │   ├── memory.py              # 记忆系统
│   │   ├── learning.py            # 学习引擎
│   │   ├── llm_config.py          # LLM 配置
│   │   └── prompts.py             # Prompt 管理
│   ├── core/
│   │   ├── planner.py             # L1 规划器（替代 orchestrator.py）
│   │   ├── workflow.py            # 工作流引擎（LOOP 循环）
│   │   └── event_bus.py           # 事件总线（Agent 间通信）
│   ├── agents/                    # L2 执行层
│   │   ├── base.py                # Agent 基类
│   │   ├── outline_agent.py
│   │   ├── world_agent.py
│   │   ├── character_agent.py
│   │   ├── style_agent.py
│   │   ├── draft_agent.py
│   │   ├── edit_agent.py
│   │   ├── review_agent.py
│   │   └── plot_agent.py
│   ├── services/                  # L3 工具层
│   │   ├── memory_service.py      # 记忆服务（ChromaDB）
│   │   ├── learning_service.py    # 学习服务（风格指纹）
│   │   ├── consistency_checker.py # 一致性检查
│   │   └── prompt_manager.py      # Prompt 管理
│   ├── models/                    # Pydantic 模型
│   │   ├── schemas.py
│   │   └── enums.py
│   ├── db/
│   │   ├── database.py            # SQLAlchemy 连接
│   │   ├── models.py              # ORM 模型
│   │   └── crud.py                # CRUD 操作
│   └── llm/
│       ├── client.py              # LLM 客户端抽象
│       ├── provider.py            # Provider 基类
│       └── providers/             # 各 Provider 实现
│           ├── base.py
│           ├── openai.py
│           ├── anthropic.py
│           └── ...
├── frontend/
│   ├── app/                       # Next.js 14 App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx               # 首页（叙事总览）
│   │   ├── novels/
│   │   │   ├── page.tsx           # 小说列表
│   │   │   └── [id]/
│   │   │       ├── page.tsx       # 小说详情
│   │   │       ├── create/        # 创建小说
│   │   │       └── [novelId]/
│   │   │           ├── page.tsx       # 小说主页
│   │   │           ├── chapters/      # 章节列表
│   │   │           ├── timeline/      # 时间线可视化
│   │   │           ├── characters/    # 角色管理
│   │   │           └── world/         # 世界观管理
│   │   ├── api/                   # Next.js API Routes（BFF层）
│   │   │   └── [...proxy]/        # 代理到后端
│   │   └── components/
│   │       ├── ui/                # shadcn/ui 组件
│   │       ├── narrative/         # 叙事可视化组件
│   │       │   ├── Timeline.tsx
│   │       │   ├── CharacterGraph.tsx
│   │       │   └── SceneMap.tsx
│   │       └──创作/               # 创作相关组件
│   │           ├── ChapterEditor.tsx
│   │           └── AgentPanel.tsx
│   ├── lib/
│   │   ├── api.ts                 # API 客户端
│   │   └── utils.ts
│   └── types/
│       └── index.ts               # TypeScript 类型
└── tests/
    ├── test_backend/
    │   ├── test_planner.py
    │   ├── test_agents/
    │   └── test_services/
    └── test_frontend/
        └── *.test.tsx
```

---

## 3. 后端模块设计

### 3.1 L1 规划器 (`core/planner.py`)

**职责:** 全局规划、阶段决策、质量门控

```python
class NovelPlannerAgent:
    """L1 规划层 - 总调度 Agent"""
    
    async def create_plan(self, novel_config: NovelConfig) -> WorkflowPlan:
        """根据小说配置创建全局工作流计划"""
        pass
    
    async def decide_next_stage(self, current_state: OrchestratorState) -> Stage:
        """决定下一步执行哪个阶段"""
        pass
    
    async def quality_gate_check(self, chapter_content: str) -> QualityResult:
        """质量门控 - 判断章节是否达标"""
        pass
```

**工作流状态机:**
```
planning → worldbuilding → characters → style → outlining → 
  [draft_loop] → drafting → editing → review → [done | back_to_drafting]
```

### 3.2 L2 执行层 (`agents/*.py`)

每个 Agent 继承自 `BaseAgent`，统一接口:

```python
class BaseAgent(ABC):
    """Agent 基类"""
    
    AGENT_ID: str = "base"
    AGENT_NAME: str = "Base Agent"
    CAPABILITIES: List[str] = []
    
    def __init__(self, llm_gateway: LLMGateway, memory_service: MemoryService):
        self.llm = llm_gateway
        self.memory = memory_service
    
    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行 Agent 任务"""
        pass
    
    async def _call_llm(self, prompt: str, **kwargs) -> str:
        """调用 LLM（带缓存和重试）"""
        pass
```

**Agent 间通信:**
- 通过 `EventBus` 发布/订阅事件
- 通过 `MemoryService` 共享上下文

### 3.3 L3 工具层 (`services/*.py`)

#### 3.3.1 记忆服务 (`services/memory_service.py`)

**基于 ChromaDB 的向量记忆系统:**

```python
import chromadb
from chromadb.config import Settings

class MemoryService:
    """基于 ChromaDB 的语义记忆服务"""
    
    def __init__(self, collection_name: str = "novel_memory"):
        self.client = chromadb.Client(Settings(
            persist_directory="./chroma_data"
        ))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # 余弦相似度
        )
    
    async def store_chapter(self, chapter_id: str, content: str, metadata: dict):
        """存储章节内容到向量库"""
        self.collection.upsert(
            ids=[chapter_id],
            documents=[content],
            metadatas=[metadata]
        )
    
    async def semantic_search(self, query: str, top_k: int = 5) -> List[Match]:
        """语义搜索"""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        return self._format_results(results)
    
    async def get_context(self, novel_id: str, chapter_idx: int) -> Context:
        """构建章节上下文（自动向量检索相关章节）"""
        pass
```

**记忆分层策略:**
- **工作记忆**: 最近 5 章完整内容（ChromaDB 集合 `working_memory`）
- **短期记忆**: 章节摘要链（ChromaDB 集合 `short_term_memory`）
- **长期记忆**: 
  - 角色档案（ChromaDB 集合 `long_term_characters`）
  - 世界观设定（ChromaDB 集合 `long_term_world`）
  - 伏笔追踪（ChromaDB 集合 `long_term_foreshadowing`）

#### 3.3.2 学习服务 (`services/learning_service.py`)

**轻量级风格指纹引擎:**

```python
from collections import defaultdict
import re
import jieba  # 中文分词

class LearningService:
    """统计式风格指纹学习服务"""
    
    def __init__(self):
        self.style_fingerprints: Dict[str, StyleFingerprint] = {}
    
    def learn_from_edit(self, original: str, edited: str, user_id: str):
        """从用户编辑中学习风格偏好"""
        fingerprint = self._extract_fingerprint(original, edited)
        self._update_fingerprint(user_id, fingerprint)
    
    def _extract_fingerprint(self, original: str, edited: str) -> StyleFingerprint:
        """提取风格指纹"""
        # 1. 词汇偏好
        changed_words = self._find_replacements(original, edited)
        
        # 2. 句式偏好
        sentence_patterns = self._analyze_patterns(original, edited)
        
        # 3. 风格标记
        style_tags = self._detect_style_tags(edited)
        
        return StyleFingerprint(
            preferred_words=changed_words,
            sentence_patterns=sentence_patterns,
            style_tags=style_tags
        )
    
    def apply_style_constraints(self, prompt: str, fingerprint: StyleFingerprint) -> str:
        """将风格指纹注入到 Prompt 中"""
        constraints = self._build_constraints(fingerprint)
        return f"{prompt}\n\n【风格约束】\n{constraints}"
```

**风格指纹数据结构:**
```python
@dataclass
class StyleFingerprint:
    """风格指纹"""
    preferred_words: Dict[str, List[str]]  # 原词 → 偏好替换词
    sentence_patterns: List[str]           # 偏好句式（如"短句优先"）
    anti_patterns: List[str]               # 反模式（AI 味用语）
    style_tags: Dict[str, float]          # 风格标签权重（冷峻:0.8, 温情:0.6）
```

### 3.4 工作流引擎 (`core/workflow.py`)

**LOOP 循环架构（统一 v3.0 + v4.0）:**

```python
class WorkflowEngine:
    """工作流引擎 - 支持 LOOP 循环"""
    
    async def run_loop(self, novel_id: str, loop_config: LoopConfig):
        """执行 LOOP 循环"""
        
        # Loop 0: SKELETON（骨架）- 并行执行
        await self._run_parallel([
            OutlineAgent,
            WorldAgent,
            CharacterAgent,
        ])
        
        # Loop 1: DETAIL（血肉）- 逐章生成
        for chapter in chapters:
            content = await DraftAgent.execute({
                "outline": chapter_outline,
                "context": await memory_service.get_context(...)
            })
            
            # 每 5 章执行一次 POLISH
            if chapter_idx % 5 == 0:
                await EditAgent.execute(content, consistency_check=True)
        
        # Loop 2: REFINE（精修）- 全局优化
        await self._global_optimization(novel_id)
```

### 3.5 LLM 网关 (`llm/gateway.py`)

**统一 LLM 调用接口（缓存 + 重试 + 限流）:**

```python
class LLMGateway:
    """LLM 网关 - 统一管理所有 Provider"""
    
    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        self.cache = LRUCache(maxsize=500)
        self.rate_limiter = RateLimiter(rpm=30)
    
    async def generate(self, provider: str, prompt: str, **kwargs) -> LLMResponse:
        """统一生成接口"""
        
        # 1. 检查缓存
        cache_key = self._cache_key(prompt, provider, kwargs)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # 2. 限流
        await self.rate_limiter.wait(provider)
        
        # 3. 调用 Provider
        provider_instance = self.providers[provider]
        response = await provider_instance.generate(prompt, **kwargs)
        
        # 4. 缓存结果
        self.cache[cache_key] = response
        
        return response
    
    async def generate_stream(self, provider: str, prompt: str, **kwargs):
        """流式生成接口（SSE）"""
        pass
```

---

## 4. 前端模块设计

### 4.1 技术栈

| 技术 | 用途 |
|------|------|
| **Next.js 14** | App Router, Server Components, API Routes |
| **React 18** | UI 库 |
| **TypeScript** | 类型安全 |
| **Tailwind CSS** | 原子化 CSS |
| **shadcn/ui** | 高质量组件库 |
| **TanStack Query** | 服务端状态管理 |
| **Zustand** | 客户端状态管理 |
| **Mermaid.js** | 叙事时间线可视化 |
| **React Flow** | 角色关系图谱 |

### 4.2 页面路由

```
/                          → 叙事总览（Dashboard）
/novels                    → 小说列表
/novels/create             → 创建小说
/novels/[id]               → 小说主页
/novels/[id]/chapters      → 章节列表
/novels/[id]/chapters/[chapId] → 章节阅读/编辑
/novels/[id]/timeline      → 时间线可视化
/novels/[id]/characters    → 角色管理
/novels/[id]/world         → 世界观管理
/novels/[id]/orchestrate   → 编排面板（启动/监控创作流程）
/settings/llm              → LLM 配置
/settings/learning         → 学习引擎设置
```

### 4.3 核心组件

#### 4.3.1 叙事时间线 (`components/narrative/Timeline.tsx`)

```tsx
interface TimelineEvent {
  chapter: number;
  title: string;
  time: string;       // 故事内时间
  characters: string[];
  location: string;
  events: string[];
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <div className="timeline-container">
      {events.map((event) => (
        <TimelineNode key={event.chapter} event={event} />
      ))}
    </div>
  );
}
```

#### 4.3.2 角色关系图谱 (`components/narrative/CharacterGraph.tsx`)

```tsx
import ReactFlow, { Background, Controls } from 'react-flow-renderer';

export function CharacterGraph({ characters, relationships }: Props) {
  const nodes = characters.map(c => ({
    id: c.id,
    position: { x: c.x, y: c.y },
    data: { label: c.name, role: c.role }
  }));
  
  const edges = relationships.map(r => ({
    id: `${r.from}-${r.to}`,
    source: r.from,
    target: r.to,
    label: r.type  // "朋友", "敌人", "恋人"
  }));
  
  return (
    <ReactFlow nodes={nodes} edges={edges}>
      <Background />
      <Controls />
    </ReactFlow>
  );
}
```

#### 4.3.3 编排面板 (`components创作/AgentPanel.tsx`)

```tsx
export function AgentPanel({ novelId }: Props) {
  const { data: orchestrator } = useOrchestrator(novelId);
  
  return (
    <div className="agent-panel">
      <StageIndicator stages={orchestrator.stages} />
      <AgentStatus agents={orchestrator.active_agents} />
      <SSEEventListener onEvent={handleOrchestratorEvent} />
    </div>
  );
}
```

### 4.4 状态管理

```typescript
// Zustand stores
const useNovelStore = create((set) => ({
  currentNovel: null as Novel | null,
  setCurrentNovel: (novel) => set({ currentNovel: novel }),
  
  chapters: [] as Chapter[],
  addChapter: (chapter) => set((state) => ({
    chapters: [...state.chapters, chapter]
  })),
}));

const useAgentStore = create((set) => ({
  activeAgents: [] as AgentStatus[],
  setActiveAgents: (agents) => set({ activeAgents: agents }),
}));
```

---

## 5. 数据模型设计

### 5.1 SQLAlchemy ORM 模型 (`db/models.py`)

```python
class Novel(Base):
    """小说模型"""
    __tablename__ = "novels"
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    genre = Column(String)               # 题材（玄幻、都市、科幻等）
    outline = Column(Text)               # 大纲
    status = Column(Enum(NovelStatus))   # drafting, paused, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    # 关系
    chapters = relationship("Chapter", back_populates="novel")
    characters = relationship("Character", back_populates="novel")
    world_settings = relationship("WorldSetting", back_populates="novel")

class Chapter(Base):
    """章节模型"""
    __tablename__ = "chapters"
    
    id = Column(String, primary_key=True)
    novel_id = Column(String, ForeignKey("novels.id"))
    chapter_number = Column(Integer)
    title = Column(String)
    content = Column(Text)               # 完整章节内容
    outline = Column(Text)               # 章节大纲
    status = Column(Enum(ChapterStatus)) # outlined, drafted, edited, reviewed
    word_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    novel = relationship("Novel", back_populates="chapters")
    feedbacks = relationship("ChapterFeedback", back_populates="chapter")

class Character(Base):
    """角色模型"""
    __tablename__ = "characters"
    
    id = Column(String, primary_key=True)
    novel_id = Column(String, ForeignKey("novels.id"))
    name = Column(String)
    role = Column(String)                # 主角、配角、反派
    personality = Column(Text)           # 性格描述
    background = Column(Text)            # 背景故事
    goals = Column(Text)                 # 目标
    relationships = Column(Text)         # 角色关系（JSON）
    state_history = Column(Text)         # 状态历史（JSON）

class WorldSetting(Base):
    """世界观设定模型"""
    __tablename__ = "world_settings"
    
    id = Column(String, primary_key=True)
    novel_id = Column(String, ForeignKey("novels.id"))
    category = Column(String)            # 地理、魔法、社会、经济
    name = Column(String)
    description = Column(Text)
    rules = Column(Text)                 # 规则列表（JSON）
    key_locations = Column(Text)         # 关键地点（JSON）

class ChapterFeedback(Base):
    """章节反馈模型"""
    __tablename__ = "chapter_feedbacks"
    
    id = Column(String, primary_key=True)
    novel_id = Column(String, ForeignKey("novels.id"))
    chapter_id = Column(String, ForeignKey("chapters.id"))
    feedback_type = Column(Enum(FeedbackType))
    original_text = Column(Text)
    edited_text = Column(Text)
    rating = Column(Integer)             # 1-10 评分
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    chapter = relationship("Chapter", back_populates="feedbacks")
```

### 5.2 Pydantic 模型 (`models/schemas.py`)

```python
class NovelCreate(BaseModel):
    title: str
    genre: str
    outline: Optional[str] = None

class NovelResponse(BaseModel):
    id: str
    title: str
    genre: str
    status: str
    chapter_count: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ChapterCreate(BaseModel):
    chapter_number: int
    title: str
    outline: str

class ChapterResponse(BaseModel):
    id: str
    novel_id: str
    chapter_number: int
    title: str
    content: Optional[str] = None
    status: str
    word_count: int

class OrchestratorStartRequest(BaseModel):
    novel_id: str
    mode: str = "loop"  # "loop" or "linear"
    chapter_count: int = 30
```

---

## 6. API 接口设计

### 6.1 小说管理 (`/api/novels`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/novels` | 获取小说列表 |
| POST | `/api/novels` | 创建小说 |
| GET | `/api/novels/{id}` | 获取小说详情 |
| PUT | `/api/novels/{id}` | 更新小说信息 |
| DELETE | `/api/novels/{id}` | 删除小说 |
| GET | `/api/novels/{id}/chapters` | 获取章节列表 |
| POST | `/api/novels/{id}/chapters` | 创建章节 |
| GET | `/api/novels/{id}/chapters/{chapId}` | 获取章节详情 |
| PUT | `/api/novels/{id}/chapters/{chapId}` | 更新章节内容 |
| POST | `/api/novels/{id}/chapters/{chapId}/feedback` | 提交反馈 |

### 6.2 编排器 (`/api/orchestrator`)

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/orchestrator/{novelId}/start` | 启动创作流程 |
| POST | `/api/orchestrator/{novelId}/pause` | 暂停创作 |
| POST | `/api/orchestrator/{novelId}/resume` | 恢复创作 |
| GET | `/api/orchestrator/{novelId}/status` | 获取状态 |
| GET | `/api/orchestrator/{novelId}/stream` | SSE 实时推送 |

### 6.3 Agent 调用 (`/api/agents`)

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/agents/outline` | 生成大纲 |
| POST | `/api/agents/world` | 生成世界观 |
| POST | `/api/agents/characters` | 生成角色 |
| POST | `/api/agents/draft` | 生成章节 |
| POST | `/api/agents/edit` | 精修章节 |
| POST | `/api/agents/review` | 审查章节 |

### 6.4 记忆系统 (`/api/memory`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/memory/{novelId}/context` | 获取上下文 |
| POST | `/api/memory/{novelId}/search` | 语义搜索 |
| GET | `/api/memory/{novelId}/stats` | 记忆统计 |

### 6.5 学习引擎 (`/api/learning`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/learning/fingerprint/{userId}` | 获取风格指纹 |
| POST | `/api/learning/update` | 更新风格指纹 |
| GET | `/api/learning/statistics` | 学习统计 |

---

## 7. 数据流设计

### 7.1 章节创作流程（LOOP 循环）

```
用户点击"开始创作"
    │
    ▼
L1 规划器创建全局计划 ──────────────────────────┐
    │                                          │
    ▼                                          │
Loop 0: SKELETON（骨架）                       │
├─ OutlineAgent 生成大纲 ──────────────────────┤
├─ WorldAgent 生成世界观（并行）                │
└─ CharacterAgent 生成角色（并行）              │
    │                                          │
    ▼                                          │
Loop 1: DETAIL（血肉）                         │
├─ 逐章执行:                                  │
│  ├─ MemoryService 检索上下文 ────────────────┤
│  ├─ DraftAgent 生成章节内容                  │
│  ├─ LLMGateway 流式推送到前端                │
│  └─ MemoryService 存储到 ChromaDB ──────────┤
│                                              │
│  每 5 章执行 POLISH:                         │
│  ├─ EditAgent 精修内容                       │
│  ├─ ConsistencyChecker 检查一致性            │
│  └─ 更新记忆系统                             │
│                                              │
    ▼                                          │
Loop 2: REFINE（精修）                         │
├─ ReviewAgent 全局审查                        │
├─ QualityGate 判断是否达标 ───────────────────┤
│                                              │
│  ┌─ 达标 ──→ 标记完成 ──────────────────────┤
│  └─ 不达标 ──→ 回退到 DraftAgent 重写 ──────┘
    │
    ▼
通知用户完成
```

### 7.2 风格学习流程

```
用户在编辑器修改文本
    │
    ▼
LearningService 捕获编辑
    │
    ▼
_extract_fingerprint(original, edited)
├─ 检测词汇替换
├─ 检测句式变化
└─ 检测风格标记
    │
    ▼
_update_fingerprint(user_id, fingerprint)
    │
    ▼
下次生成章节时:
LearningService.apply_style_constraints(prompt, fingerprint)
    │
    ▼
将风格约束注入 Prompt
    │
    ▼
LLM 生成符合用户风格的章节
```

### 7.3 语义搜索流程

```
用户搜索"主角与反派的初次冲突"
    │
    ▼
MemoryService.semantic_search(query, top_k=5)
    │
    ▼
ChromaDB 向量检索
├─ 将查询文本编码为向量（sentence-transformers）
├─ 在 collection 中查找最近邻
└─ 返回相似度最高的 5 条记忆
    │
    ▼
返回结果:
[
  {"chapter": 3, "content": "...", "similarity": 0.92},
  {"chapter": 7, "content": "...", "similarity": 0.87},
  ...
]
```

---

## 8. 实施计划

### 阶段 1: 基础设施（1周）

**目标:** 搭建新架构骨架，跑通基本流程

| 任务 | 文件 | 预估时间 |
|------|------|---------|
| 1.1 项目初始化 | `pyproject.toml`, `package.json` | 2h |
| 1.2 FastAPI 模块化路由 | `routes/__init__.py`, `main.py` | 3h |
| 1.3 Next.js 14 项目迁移 | `frontend/app/` | 4h |
| 1.4 ChromaDB 集成 | `services/memory_service.py` | 3h |
| 1.5 LLM 网关重写 | `llm/gateway.py` | 4h |
| 1.6 数据库迁移脚本 | `db/migrate.py` | 2h |

**交付物:** 
- 后端模块化骨架可启动
- 前端 Next.js 14 可运行
- ChromaDB 集成测试通过

### 阶段 2: L1 规划层（1周）

**目标:** 实现总调度 Agent 和工作流引擎

| 任务 | 文件 | 预估时间 |
|------|------|---------|
| 2.1 规划器核心 | `core/planner.py` | 6h |
| 2.2 工作流引擎 | `core/workflow.py` | 8h |
| 2.3 事件总线 | `core/event_bus.py` | 4h |
| 2.4 质量门控 | `core/quality_gate.py` | 4h |
| 2.5 API 路由 | `routes/orchestrator.py` | 4h |

**交付物:**
- 规划器可创建全局计划
- LOOP 循环架构可执行
- API 端点可调用

### 阶段 3: L2 执行层（2周）

**目标:** 重构所有 Agent，统一接口

| 任务 | 文件 | 预估时间 |
|------|------|---------|
| 3.1 Agent 基类重构 | `agents/base.py` | 4h |
| 3.2 OutlineAgent | `agents/outline_agent.py` | 4h |
| 3.3 WorldAgent | `agents/world_agent.py` | 4h |
| 3.4 CharacterAgent | `agents/character_agent.py` | 4h |
| 3.5 StyleAgent | `agents/style_agent.py` | 4h |
| 3.6 DraftAgent | `agents/draft_agent.py` | 6h |
| 3.7 EditAgent | `agents/edit_agent.py` | 4h |
| 3.8 ReviewAgent | `agents/review_agent.py` | 4h |
| 3.9 PlotAgent | `agents/plot_agent.py` | 4h |
| 3.10 Agent API 路由 | `routes/agents.py` | 4h |

**交付物:**
- 所有 Agent 统一接口
- Agent 间可通过 EventBus 通信
- 所有 Agent API 可调用

### 阶段 4: L3 工具层（1周）

**目标:** 实现记忆服务、学习服务、一致性检查

| 任务 | 文件 | 预估时间 |
|------|------|---------|
| 4.1 记忆服务完整实现 | `services/memory_service.py` | 8h |
| 4.2 ChromaDB 初始化脚本 | `scripts/init_chroma.py` | 3h |
| 4.3 学习服务（风格指纹） | `services/learning_service.py` | 8h |
| 4.4 一致性检查器 | `services/consistency_checker.py` | 6h |
| 4.5 Prompt 管理器 | `services/prompt_manager.py` | 4h |
| 4.6 API 路由 | `routes/memory.py`, `routes/learning.py` | 4h |

**交付物:**
- ChromaDB 向量记忆可用
- 风格指纹学习可用
- 一致性检查可用

### 阶段 5: 前端核心页面（2周）

**目标:** 实现核心页面和组件

| 任务 | 文件 | 预估时间 |
|------|------|---------|
| 5.1 shadcn/ui 集成 | `frontend/components/ui/` | 6h |
| 5.2 叙事总览页 | `frontend/app/page.tsx` | 6h |
| 5.3 小说管理页 | `frontend/app/novels/` | 8h |
| 5.4 章节编辑页 | `frontend/app/novels/[id]/chapters/` | 10h |
| 5.5 编排面板 | `frontend/components/创作/AgentPanel.tsx` | 8h |
| 5.6 LLM 配置页 | `frontend/app/settings/llm` | 4h |
| 5.7 API 代理层 | `frontend/app/api/[...proxy]/` | 4h |

**交付物:**
- 核心页面可访问
- 章节编辑器可用
- 编排面板可显示实时状态

### 阶段 6: 前端可视化（1周）

**目标:** 实现叙事时间线、角色关系图

| 任务 | 文件 | 预估时间 |
|------|------|---------|
| 6.1 叙事时间线 | `frontend/components/narrative/Timeline.tsx` | 8h |
| 6.2 角色关系图谱 | `frontend/components/narrative/CharacterGraph.tsx` | 8h |
| 6.3 场景地图 | `frontend/components/narrative/SceneMap.tsx` | 6h |
| 6.4 小说详情页 | `frontend/app/novels/[id]/page.tsx` | 6h |

**交付物:**
- 时间线可视化可用
- 角色关系图可用
- 小说详情页完整

### 阶段 7: 测试和优化（1周）

**目标:** 全面测试、性能优化、Bug 修复

| 任务 | 内容 | 预估时间 |
|------|------|---------|
| 7.1 后端单元测试 | `tests/test_backend/` | 12h |
| 7.2 前端组件测试 | `tests/test_frontend/` | 8h |
| 7.3 集成测试 | E2E 测试 | 8h |
| 7.4 性能优化 | ChromaDB 索引、缓存策略 | 6h |
| 7.5 Bug 修复 | 根据测试结果修复 | 8h |

**交付物:**
- 测试覆盖率 > 80%
- 首屏加载 < 2s
- 无 P0/P1 级别 Bug

---

## 9. 迁移策略

### 9.1 数据库迁移

```python
# db/migrate.py
"""
从 v1.1 数据库迁移到 v2.0
- 保留所有小说数据
- 重建 ChromaDB 索引
- 初始化风格指纹
"""

def migrate_from_v1_to_v2():
    # 1. 读取 v1.1 数据库
    novels = v1_db.query(Novel).all()
    
    # 2. 写入 v2.0 数据库（自动创建新表结构）
    for novel in novels:
        v2_db.save(novel)
    
    # 3. 初始化 ChromaDB 索引
    init_chroma_collection(novels)
    
    # 4. 重建风格指纹
    for novel in novels:
        build_style_fingerprint(novel)
```

### 9.2 渐进式迁移

```
第1周: 新架构上线，旧架构保留（双写）
第2-3周: 新功能在新架构上实现
第4周: 旧架构下线，完全切换到新架构
```

### 9.3 回滚策略

- 保留 v1.1 数据库备份
- ChromaDB 可从 SQLite 重建索引
- 前端与后端通过 API 解耦，可独立回滚

---

## 10. 依赖清单

### 10.1 后端新增依赖

```toml
[project.dependencies]
# 新增
chromadb = "^0.4.24"      # 向量数据库
sentence-transformers = "^2.2.2"  # 文本嵌入
jieba = "^0.42.1"          # 中文分词（风格指纹）
pydantic = "^2.5.0"        # 升级到 v2
```

### 10.2 前端新增依赖

```json
{
  "dependencies": {
    "next": "^14.2.0",
    "@radix-ui/react-*": "^1.0.0",      // shadcn/ui 基础组件
    "tailwindcss": "^3.4.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^4.4.0",
    "react-flow-renderer": "^10.3.0",   // 关系图谱
    "mermaid": "^10.0.0",                // 时间线
    "react-markdown": "^9.0.0"           // Markdown 渲染
  },
  "devDependencies": {
    "@testing-library/react": "^15.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "msw": "^2.0.0"                      // API Mock
  }
}
```

---

## 11. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| ChromaDB 索引构建时间长 | 首次启动慢 | 异步构建 + 进度显示 |
| Next.js 迁移学习成本 | 开发效率下降 | 提供迁移指南 + 模板代码 |
| 风格指纹数据不足 | 学习效果差 | 提供默认风格模板 + 冷启动策略 |
| LLM API 限流 | 生成速度慢 | 智能缓存 + 排队机制 |
| 数据迁移丢失 | 用户数据丢失 | 双写策略 + 完整备份 |

---

## 12. 成功指标

| 指标 | 当前 (v1.1) | 目标 (v2.0) |
|------|------------|------------|
| main.py 行数 | 2924 行 | < 200 行 |
| 最大文件行数 | 2924 行 (main.py) | < 500 行 |
| 记忆检索精度 (NDCG) | 0.65 (TF-IDF) | 0.85 (向量) |
| 首屏加载时间 | 1.5s | < 1.0s |
| 代码可测试性 | 低（单文件） | 高（模块化 + 单元测试） |
| 风格对齐度 (用户评分) | 6.5/10 | 8.0/10 |

---

## 附录 A: 关键技术选型理由

### ChromaDB vs 其他向量数据库

| 方案 | 优点 | 缺点 | 选择理由 |
|------|------|------|---------|
| **ChromaDB** ✅ | 嵌入式、零依赖、Python 原生 | 不适合超大规模（>100万向量） | 小说场景足够，部署简单 |
| Qdrant | 高性能、分布式 | 需要独立服务 | 过度工程 |
| Weaviate | 功能丰富 | 资源占用高 | 过度工程 |
| FAISS | 极致性能 | 无持久化、需自己实现搜索逻辑 | 开发成本高 |

### Next.js 14 vs 保持 React SPA

| 方案 | 优点 | 缺点 | 选择理由 |
|------|------|------|---------|
| **Next.js 14** ✅ | SSR/SSG、API Routes、更好的 SEO | 学习成本 | 企业级应用标准 |
| Vite + React SPA ✅ | 简单 | 无 SSR、首屏慢 | 已选择 Next.js |

### 风格指纹 vs 微调模型

| 方案 | 优点 | 缺点 | 选择理由 |
|------|------|------|---------|
| **风格指纹** ✅ | 零延迟、零成本、立即可用 | 精度有限 | 小说场景足够，性价比高 |
| LoRA 微调 | 精度高 | 需要 GPU、大量数据 | 过度工程 |
| RLHF | 最智能 | 工程复杂度极高 | 不适合个人开发者 |

---

## 附录 B: 参考项目

1. **Google DeepMind - Tell Me A Story**: [github.com/google-deepmind/tell_me_a_story](https://github.com/google-deepmind/tell_me_a_story)
   - 多 Agent 叙事生成框架
   - 参考其 Agent 协作模式

2. **MetaGPT**: [github.com/geekan/MetaGPT](https://github.com/geekan/MetaGPT) (59.4k⭐)
   - SOP 驱动的多 Agent 框架
   - 参考其分层编排思想

3. **CrewAI**: [github.com/crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) (25k⭐)
   - 灵活的多 Agent 编排
   - 参考其 Agent 间通信机制

4. **ChromaDB**: [github.com/chroma-core/chroma](https://github.com/chroma-core/chroma)
   - 嵌入式向量数据库
   - 本项目的向量记忆基础

---

## 文档版本

- **版本**: v2.0
- **创建日期**: 2026-06-21
- **重构范围**: 全方位重构（后端 + 前端 + AI 系统）
- **决策记录**:
  - 架构风格: 分层编排（L1 + L2 + L3）
  - 记忆系统: ChromaDB 向量检索
  - 学习引擎: 轻量级风格指纹
  - 前端: Next.js 14 App Router

# 小说创作Agent系统设计方案

## 1. 项目概述

### 1.1 项目定位
构建一个专业级AI小说创作Agent系统，参考Hermes Agent的自主进化能力、Claude Code的工程化设计以及Sudowrite的创作辅助理念，打造能够理解用户需求、自主规划创作流程、多Agent协作完成长篇小说创作的智能系统。

### 1.2 核心能力
- **全自动创作模式**：给定主题/大纲后，Agent自动完成从设定到成书的全流程
- **交互式协作模式**：用户与Agent共同创作，Agent负责续写、润色、角色管理
- **自主学习优化**：基于用户反馈和参考作品持续优化创作风格
- **多Agent协作**：角色分工+流程分工的混合协作模式

### 1.3 目标用户
- 网络小说作者（需要快速生成初稿、突破创作瓶颈）
- 创意写作爱好者（需要AI辅助实现创意）
- 出版行业编辑（需要快速评估故事可行性）

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Tauri Desktop Application                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  项目管理    │  │  创作工作台  │  │  设定/角色/世界观    │  │
│  │  (Project)   │  │  (Editor)   │  │  (Bible)            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  大纲视图    │  │  AI助手面板  │  │  导出/发布          │  │
│  │  (Outline)   │  │  (Agent)    │  │  (Export)           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend Service                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Novel Agent Core (创作引擎)                  │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │ │
│  │  │Orchestrator│ │OutlineAgent│ │DraftAgent │ │EditAgent │  │ │
│  │  │ (调度器)   │ │ (大纲Agent)│ │ (草稿Agent)│ │ (编辑Agent)│  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │ │
│  │  │WorldAgent │ │Character │ │StyleAgent │ │ReviewAgent│  │ │
│  │  │(世界观)   │ │Agent(角色)│ │(文风)     │ │(审核)     │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │  Memory System   │  │     Learning & Optimization      │ │
│  │  (记忆系统)       │  │     (学习与优化系统)              │ │
│  └──────────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │
┌─────────────────────────────────────────────────────────────┐
│              Existing Infrastructure (复用现有)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │LLMManager│  │VectorStore│  │GraphStore│  │Resource  │    │
│  │(模型管理) │  │(向量检索) │  │(知识图谱) │  │Store(资源)│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块划分

| 模块 | 职责 | 技术选型 |
|------|------|----------|
| **Frontend (Tauri)** | 桌面级创作工作台UI | Tauri + React + TypeScript |
| **Agent Core** | 多Agent调度与协作引擎 | Python + 自研状态机 |
| **Memory System** | 长文本记忆、上下文管理 | 向量数据库 + 摘要链 |
| **Learning System** | 风格学习、反馈优化 | Embedding + 强化学习 |
| **Export Engine** | 多格式导出 | Pandoc + 自定义模板 |
| **LLM Layer** | 复用现有LLMManager | 现有适配器 |

---

## 3. 核心模块设计

### 3.1 多Agent协作引擎 (Agent Core)

#### 3.1.1 Agent类型定义

**流程型Agent（按创作阶段分工）：**

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **OutlineAgent** | 生成故事大纲、章节规划 | 主题、类型、字数要求 | 三级大纲（卷/章/节） |
| **DraftAgent** | 根据大纲生成正文 | 章节大纲、角色设定、前文 | 章节正文 |
| **EditAgent** | 润色、修改、去AI味 | 初稿、修改意见 | 润色稿 |
| **ReviewAgent** | 逻辑审核、一致性检查 | 完整章节/小说 | 审核报告 |

**角色型Agent（按专业领域分工）：**

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **WorldAgent** | 世界观构建、设定管理 | 类型、风格偏好 | 完整世界设定文档 |
| **CharacterAgent** | 角色设计、弧光规划 | 故事需求、角色关系 | 角色卡、成长弧线 |
| **StyleAgent** | 文风模仿、语气调整 | 参考文本、风格描述 | 风格指南、改写建议 |
| **PlotAgent** | 情节设计、冲突构建 | 大纲、当前进度 | 情节细节、转折点 |

#### 3.1.2 Orchestrator调度器

参考Claude Code的Spec-Driven设计，采用**"规划-执行-验证"**循环：

```python
class NovelOrchestrator:
    """
    小说创作调度器
    管理创作流程的状态机和Agent调度
    """
    
    def __init__(self):
        self.state = NovelState.INIT
        self.agents = {
            "outline": OutlineAgent(),
            "world": WorldAgent(),
            "character": CharacterAgent(),
            "plot": PlotAgent(),
            "draft": DraftAgent(),
            "edit": EditAgent(),
            "review": ReviewAgent(),
            "style": StyleAgent()
        }
        self.memory = NovelMemory()
        self.learning = LearningEngine()
    
    async def create_novel(self, request: NovelRequest) -> Novel:
        """主流程：从需求到成书"""
        # Phase 1: 需求分析与规划
        spec = await self._analyze_requirements(request)
        
        # Phase 2: 世界观与角色设定
        world = await self.agents["world"].create(spec)
        characters = await self.agents["character"].design(spec, world)
        
        # Phase 3: 大纲生成
        outline = await self.agents["outline"].generate(spec, world, characters)
        
        # Phase 4: 章节创作（迭代循环）
        novel = Novel()
        for chapter in outline.chapters:
            # 获取相关记忆和上下文
            context = self.memory.get_context(chapter)
            
            # 生成初稿
            draft = await self.agents["draft"].write(chapter, context)
            
            # 编辑润色
            edited = await self.agents["edit"].polish(draft)
            
            # 审核检查
            review = await self.agents["review"].check(edited, novel)
            
            if not review.passed:
                # 审核不通过，返回修改
                edited = await self._fix_issues(edited, review.issues)
            
            novel.add_chapter(edited)
            self.memory.update(edited)
        
        # Phase 5: 全局审核与导出
        final_review = await self.agents["review"].check_full(novel)
        return novel
```

#### 3.1.3 状态机设计

```
[INIT] → [REQUIREMENT_ANALYSIS] → [WORLD_BUILDING] → [CHARACTER_DESIGN]
    ↓
[OUTLINE_GENERATION] → [CHAPTER_WRITING] → [EDITING] → [REVIEW]
    ↑                                    ↓
    └──────────────── [REVISION] ←───────┘
    ↓
[COMPLETION] → [EXPORT]
```

### 3.2 记忆系统 (Memory System)

#### 3.2.1 三层记忆架构

参考Hermes Agent的记忆机制：

| 层级 | 存储内容 | 实现方式 | 容量 |
|------|----------|----------|------|
| **工作记忆** | 当前章节、近期上下文 | 内存缓存 | 最近3章 |
| **短期记忆** | 本章细节、角色当前状态 | 向量数据库 | 当前卷 |
| **长期记忆** | 世界观、角色档案、全文摘要 | 结构化存储+摘要链 | 全本小说 |

#### 3.2.2 记忆检索机制

```python
class NovelMemory:
    """
    小说创作专用记忆系统
    解决长文本创作的上下文遗忘问题
    """
    
    def get_context(self, chapter: Chapter) -> Context:
        """
        为当前章节检索相关上下文
        1. 必须包含：前文摘要（每3章一个摘要节点）
        2. 角色状态：当前活跃角色的最新状态
        3. 世界观：本章涉及的世界设定
        4. 伏笔回收：前文埋下的未回收伏笔
        """
        
        # 获取前文摘要链
        summaries = self._get_summary_chain(chapter.index)
        
        # 获取角色状态快照
        character_states = self._get_character_states(chapter)
        
        # 获取相关世界观设定
        world_settings = self._get_relevant_world(chapter)
        
        # 获取待回收伏笔
        foreshadowing = self._get_unresolved_foreshadowing(chapter)
        
        return Context(
            summaries=summaries,
            characters=character_states,
            world=world_settings,
            foreshadowing=foreshadowing
        )
```

### 3.3 学习与优化系统 (Learning System)

#### 3.3.1 学习维度

| 维度 | 学习内容 | 数据来源 | 应用方式 |
|------|----------|----------|----------|
| **风格模仿** | 句式、词汇、叙事节奏 | 用户上传的参考小说 | Embedding相似度 + Few-shot Prompt |
| **情节偏好** | 冲突模式、节奏偏好 | 用户反馈（点赞/修改） | 强化学习奖励模型 |
| **角色塑造** | 角色 archetype、对话风格 | 用户编辑历史 | 角色卡模板学习 |
| **去AI味** | 避免套话、模板化表达 | 用户删除/修改的内容 | 负面样本训练 |

#### 3.3.2 反馈闭环

```
用户操作 → 行为编码 → 偏好更新 → 模型微调 → 效果验证
   ↑                                                    │
   └────────────────────────────────────────────────────┘
```

```python
class LearningEngine:
    """
    创作偏好学习引擎
    """
    
    def learn_from_feedback(self, feedback: UserFeedback):
        """
        从用户反馈中学习
        - 用户修改了哪些内容？
        - 用户删除了哪些内容？
        - 用户点赞了哪些内容？
        """
        
        # 编码用户行为
        behavior_vector = self._encode_behavior(feedback)
        
        # 更新用户偏好向量
        self.preference_vector = self._update_preference(
            self.preference_vector, 
            behavior_vector,
            weight=feedback.importance
        )
        
        # 更新风格指南
        if feedback.type == FeedbackType.STYLE_EDIT:
            self.style_guide.update(feedback.before, feedback.after)
        
        # 更新角色模板
        if feedback.type == FeedbackType.CHARACTER_EDIT:
            self.character_templates.update(feedback.character_id, feedback.changes)
    
    def apply_preference(self, prompt: str) -> str:
        """
        将学习到的偏好应用到Prompt中
        """
        # 添加风格约束
        style_constraints = self.style_guide.get_constraints()
        
        # 添加角色约束
        character_constraints = self.character_templates.get_constraints()
        
        # 添加去AI味约束
        anti_ai_constraints = self._get_anti_ai_prompts()
        
        return f"""
{prompt}

【创作约束】
{style_constraints}
{character_constraints}
{anti_ai_constraints}
"""
```

### 3.4 创作工作台 (Frontend)

#### 3.4.1 界面布局

参考Scrivener和Sudowrite的设计理念：

```
┌─────────────────────────────────────────────────────────────┐
│  菜单栏  │  项目: 《XXX》                    [导出] [设置]   │
├─────────┼───────────────────────────────────────────────────┤
│         │  ┌─────────────────────────────────────────────┐  │
│  项目   │  │              编辑器（富文本/Markdown）          │  │
│  导航   │  │                                             │  │
│         │  │   第X章 XXXXX                               │  │
│  - 卷一  │  │                                             │  │
│    - 章1 │  │   XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX   │  │
│    - 章2 │  │   XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX   │  │
│    - 章3 │  │   XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX   │  │
│  - 卷二  │  │                                             │  │
│         │  └─────────────────────────────────────────────┘  │
│         │  ┌─────────────────────────────────────────────┐  │
│  设定   │  │              AI助手面板                        │  │
│  面板   │  │  [续写] [润色] [扩写] [缩略] [去AI味] [自定义]  │  │
│         │  │                                             │  │
│  - 世界观│  │  Agent: DraftAgent                          │  │
│  - 角色 │  │  状态: 正在生成...                            │  │
│  - 大纲 │  │                                             │  │
│  - 伏笔 │  │  进度: ████████░░ 80%                        │  │
│         │  └─────────────────────────────────────────────┘  │
├─────────┴───────────────────────────────────────────────────┤
│  状态栏: 字数: 12,345 │ 当前Agent: DraftAgent │ 模型: Qwen   │
└─────────────────────────────────────────────────────────────┘
```

#### 3.4.2 核心交互

| 功能 | 交互方式 | Agent调用 |
|------|----------|-----------|
| **续写** | 光标位置点击"续写" | DraftAgent.write_next() |
| **润色** | 选中文字点击"润色" | EditAgent.polish_selection() |
| **扩写** | 选中文字点击"扩写" | DraftAgent.expand() |
| **缩略** | 选中文字点击"缩略" | EditAgent.condense() |
| **去AI味** | 选中文字点击"去AI味" | StyleAgent.remove_ai_tone() |
| **生成大纲** | 点击"生成大纲" | OutlineAgent.generate() |
| **角色建议** | 选中角色名右键 | CharacterAgent.suggest_arc() |

---

## 4. 数据模型

### 4.1 核心实体

```python
class Novel(BaseModel):
    """小说项目"""
    id: str
    title: str
    genre: str  # 类型：玄幻/都市/科幻等
    target_word_count: int
    current_word_count: int
    status: NovelStatus  # 规划中/创作中/已完成
    world_id: str  # 关联世界观
    characters: List[Character]
    volumes: List[Volume]
    style_guide: StyleGuide
    created_at: datetime
    updated_at: datetime

class Volume(BaseModel):
    """卷/部"""
    id: str
    novel_id: str
    title: str
    description: str
    chapters: List[Chapter]
    word_count: int
    order: int

class Chapter(BaseModel):
    """章节"""
    id: str
    volume_id: str
    title: str
    outline: str  # 本章大纲
    content: str  # 正文内容
    word_count: int
    status: ChapterStatus  # 大纲/初稿/润色/完成
    characters_present: List[str]  # 出场角色
    locations: List[str]  # 场景
    foreshadowing: List[str]  # 埋下的伏笔
    callbacks: List[str]  # 回收的伏笔
    order: int

class Character(BaseModel):
    """角色卡"""
    id: str
    novel_id: str
    name: str
    aliases: List[str]  # 别名
    role: str  # 主角/配角/反派等
    personality: str  # 性格
    background: str  # 背景故事
    goals: List[str]  # 目标
    conflicts: List[str]  # 内心冲突
    arc: CharacterArc  # 成长弧线
    relationships: List[Relationship]  # 人物关系
    speech_pattern: str  # 说话风格
    appearance: str  # 外貌

class WorldSetting(BaseModel):
    """世界观设定"""
    id: str
    novel_id: str
    name: str
    category: str  # 地理/历史/文化/规则等
    description: str
    rules: List[str]  # 世界规则
    history: List[TimelineEvent]  # 历史时间线
    locations: List[Location]
    factions: List[Faction]
    magic_system: Optional[MagicSystem]  # 力量体系（可选）

class StyleGuide(BaseModel):
    """风格指南（学习系统输出）"""
    id: str
    novel_id: str
    vocabulary_preference: List[str]  # 偏好词汇
    sentence_patterns: List[str]  # 句式偏好
    pacing_preference: str  # 节奏偏好
    tone: str  # 语气
    anti_patterns: List[str]  # 避免的模式（去AI味）
    reference_works: List[str]  # 参考作品
```

### 4.2 数据库设计

复用现有SQLite存储，新增表：

```sql
-- 小说项目表
CREATE TABLE novels (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    genre TEXT,
    target_word_count INTEGER,
    current_word_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'planning',
    world_id TEXT,
    style_guide_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 卷表
CREATE TABLE volumes (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    word_count INTEGER DEFAULT 0,
    sort_order INTEGER,
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
);

-- 章节表
CREATE TABLE chapters (
    id TEXT PRIMARY KEY,
    volume_id TEXT NOT NULL,
    title TEXT NOT NULL,
    outline TEXT,
    content TEXT,
    word_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'outline',
    characters_present TEXT, -- JSON array
    locations TEXT, -- JSON array
    foreshadowing TEXT, -- JSON array
    callbacks TEXT, -- JSON array
    sort_order INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (volume_id) REFERENCES volumes(id) ON DELETE CASCADE
);

-- 角色表
CREATE TABLE characters (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    aliases TEXT, -- JSON array
    role TEXT,
    personality TEXT,
    background TEXT,
    goals TEXT, -- JSON array
    conflicts TEXT, -- JSON array
    speech_pattern TEXT,
    appearance TEXT,
    arc_data TEXT, -- JSON
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
);

-- 角色关系表
CREATE TABLE character_relationships (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    target_character_id TEXT NOT NULL,
    relationship_type TEXT, -- 朋友/敌人/恋人等
    description TEXT,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
);

-- 世界观设定表
CREATE TABLE world_settings (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    rules TEXT, -- JSON array
    history TEXT, -- JSON
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
);

-- 风格指南表（学习系统）
CREATE TABLE style_guides (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    vocabulary_preference TEXT, -- JSON
    sentence_patterns TEXT, -- JSON
    pacing_preference TEXT,
    tone TEXT,
    anti_patterns TEXT, -- JSON
    reference_works TEXT, -- JSON
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
);

-- 用户反馈表（学习系统）
CREATE TABLE user_feedback (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    chapter_id TEXT,
    feedback_type TEXT, -- style_edit/character_edit/plot_edit/deletion/like
    before_text TEXT,
    after_text TEXT,
    metadata TEXT, -- JSON
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Agent执行记录表
CREATE TABLE agent_executions (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    agent_type TEXT,
    task_type TEXT,
    input_summary TEXT,
    output_summary TEXT,
    status TEXT, -- running/success/failed
    duration_ms INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. 技术难点与解决方案

### 5.1 难点一：长文本上下文管理

**问题描述：**
长篇小说通常10万字以上，LLM的上下文窗口（4K-128K）无法容纳全本内容，导致：
- 角色设定遗忘（前后性格不一致）
- 伏笔丢失（前文埋的伏笔后文不回收）
- 世界观冲突（设定前后矛盾）

**解决方案：**

1. **分层摘要机制**
   - 每3章生成一个摘要节点
   - 每卷生成一个卷摘要
   - 全文生成一个总摘要
   - 形成树状摘要结构，检索时按需加载

2. **关键信息强制注入**
   - 角色状态快照：每次生成时注入当前活跃角色的最新状态
   - 世界观规则：按章节内容检索相关设定
   - 伏笔追踪：维护"已埋未收"伏笔列表

3. **向量检索增强**
   - 将前文内容向量化存入VectorStore
   - 生成当前章节时，检索语义相似的前文片段
   - 复用现有LanceDB向量存储

```python
class ContextAssembler:
    """
    上下文组装器
    在有限的上下文窗口内，组装最关键的信息
    """
    
    MAX_CONTEXT_TOKENS = 8000  # 预留空间给生成内容
    
    def assemble(self, chapter: Chapter) -> str:
        parts = []
        used_tokens = 0
        
        # 优先级1: 角色状态（必须完整）
        character_context = self._get_character_context(chapter)
        parts.append(character_context)
        used_tokens += self._count_tokens(character_context)
        
        # 优先级2: 相关世界观设定
        world_context = self._get_world_context(chapter)
        parts.append(world_context)
        used_tokens += self._count_tokens(world_context)
        
        # 优先级3: 前文摘要链（按优先级截断）
        remaining = self.MAX_CONTEXT_TOKENS - used_tokens
        summary_chain = self._get_summary_chain(chapter, max_tokens=remaining * 0.6)
        parts.append(summary_chain)
        used_tokens += self._count_tokens(summary_chain)
        
        # 优先级4: 相似片段检索（剩余空间）
        remaining = self.MAX_CONTEXT_TOKENS - used_tokens
        similar_chunks = self._retrieve_similar(chapter, max_tokens=remaining)
        parts.append(similar_chunks)
        
        return "\n\n".join(parts)
```

### 5.2 难点二：去AI味

**问题描述：**
LLM生成的小说有明显的"AI味"：
- 过度使用"然而"、"但是"、"与此同时"等转折词
- 描写模式化（"眼中闪过一丝..."）
- 情感表达空洞（"他感到无比的..."）
- 节奏单一（每段长度相似，缺乏变化）

**解决方案：**

1. **负面样本学习**
   - 收集用户删除/大幅修改的内容作为负面样本
   - 构建"AI味"检测模型
   - 生成时实时检测并提示修改

2. **风格迁移**
   - 用户上传参考作品后，提取其风格特征
   - 使用Embedding相似度约束生成内容
   - Few-shot Prompt：提供参考作品的片段作为示例

3. **后处理规则**
   - 限制转折词使用频率
   - 强制段落长度变化（短句/长句交替）
   - 替换模板化表达

```python
class AIToneRemover:
    """
    AI味去除器
    """
    
    # 常见AI味模式
    AI_PATTERNS = [
        r"眼中闪过一丝.*?",
        r"心中涌起一股.*?",
        r"不禁.*?",
        r"与此同时.*?",
        r"然而.*?",
        r"但是.*?",
    ]
    
    # 替换库
    REPLACEMENTS = {
        "眼中闪过一丝": ["眼神微动", "目光一凝", "眼底掠过", ""],
        "心中涌起一股": ["心底", "心头", "胸腔中", ""],
    }
    
    def remove(self, text: str) -> str:
        """去除AI味"""
        # 检测并标记AI味片段
        markers = self._detect_ai_patterns(text)
        
        # 对标记片段进行改写
        for marker in markers:
            alternatives = self._generate_alternatives(marker)
            best = self._select_best(alternatives, context=marker.context)
            text = text.replace(marker.text, best)
        
        # 节奏调整：确保段落长度有变化
        text = self._adjust_rhythm(text)
        
        return text
    
    def _detect_ai_patterns(self, text: str) -> List[AIMarker]:
        """检测AI味模式"""
        markers = []
        for pattern in self.AI_PATTERNS:
            for match in re.finditer(pattern, text):
                markers.append(AIMarker(
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    pattern=pattern
                ))
        return markers
```

### 5.3 难点三：多Agent协作一致性

**问题描述：**
多个Agent独立工作可能导致：
- 角色性格不一致（CharacterAgent和DraftAgent理解不同）
- 情节冲突（PlotAgent设计的转折与WorldAgent的设定矛盾）
- 风格不统一（不同Agent生成的文本风格差异）

**解决方案：**

1. **共享上下文总线**
   - 所有Agent通过共享的Context Bus通信
   - 关键决策（角色性格、世界观规则）写入共享存储
   - 每个Agent读取时获取最新版本

2. **审核-修正循环**
   - ReviewAgent在每个阶段后执行一致性检查
   - 发现问题后触发Revision循环
   - 使用结构化输出（JSON）确保信息传递准确

3. **风格锁定**
   - 一旦StyleAgent生成风格指南，后续Agent必须遵守
   - 在Prompt中强制注入风格约束
   - 生成后使用StyleAgent验证

```python
class SharedContextBus:
    """
    共享上下文总线
    确保所有Agent看到一致的信息
    """
    
    def __init__(self):
        self._store = {}
        self._locks = {}
        self._history = []
    
    def write(self, key: str, value: Any, agent: str):
        """
        Agent写入共享数据
        自动记录变更历史
        """
        old_value = self._store.get(key)
        self._store[key] = value
        self._history.append({
            "timestamp": datetime.now(),
            "agent": agent,
            "key": key,
            "old": old_value,
            "new": value
        })
    
    def read(self, key: str, agent: str) -> Any:
        """
        Agent读取共享数据
        记录读取历史，用于追踪信息流动
        """
        value = self._store.get(key)
        self._history.append({
            "timestamp": datetime.now(),
            "agent": agent,
            "key": key,
            "action": "read",
            "value": value
        })
        return value
    
    def check_consistency(self) -> List[Inconsistency]:
        """
        检查数据一致性
        返回发现的不一致项
        """
        issues = []
        
        # 检查角色一致性
        character_states = self._store.get("character_states", {})
        for char_id, state in character_states.items():
            # 检查性格描述是否矛盾
            if self._has_contradictory_traits(state):
                issues.append(Inconsistency(
                    type="character",
                    entity_id=char_id,
                    description=f"角色 {char_id} 存在矛盾的性格描述"
                ))
        
        # 检查世界观一致性
        world_rules = self._store.get("world_rules", [])
        # ...
        
        return issues
```

### 5.4 难点四：创作流程的灵活性与可控性

**问题描述：**
用户需要：
- 全自动模式：Agent自主完成所有工作
- 半自动模式：用户控制关键节点（大纲审核、章节确认）
- 手动模式：用户主导，Agent仅辅助
- 随时切换模式，干预创作过程

**解决方案：**

1. **人机协作协议**
   - 定义标准协作节点（大纲完成、章节完成、审核完成）
   - 每个节点可配置：自动通过 / 等待确认 / 人工编辑
   - 支持"暂停-恢复"机制

2. **实时干预**
   - 创作过程中用户可随时发送指令
   - Agent保存当前状态，执行用户指令
   - 完成后恢复创作流程

3. **版本分支**
   - 支持"如果...会怎样"探索
   - 用户可要求Agent生成多个版本
   - 版本对比和合并功能

```python
class CollaborationProtocol:
    """
    人机协作协议
    """
    
    # 标准协作节点
    CHECKPOINTS = [
        "requirement_confirmed",  # 需求确认
        "world_building_done",    # 世界观完成
        "characters_done",        # 角色设计完成
        "outline_done",           # 大纲完成
        "chapter_outline_done",   # 章纲完成
        "draft_done",             # 初稿完成
        "edit_done",              # 润色完成
        "review_done",            # 审核完成
    ]
    
    def __init__(self, mode: CollaborationMode):
        self.mode = mode
        self.checkpoint_settings = {
            cp: self._default_setting(mode) 
            for cp in self.CHECKPOINTS
        }
    
    async def run(self, novel: Novel, orchestrator: NovelOrchestrator):
        """
        执行协作流程
        """
        for checkpoint in self.CHECKPOINTS:
            setting = self.checkpoint_settings[checkpoint]
            
            if setting == "auto":
                # 自动通过
                await orchestrator.execute_until(checkpoint)
            
            elif setting == "confirm":
                # 执行到节点，等待用户确认
                result = await orchestrator.execute_until(checkpoint)
                yield CollaborationEvent(
                    type="checkpoint_reached",
                    checkpoint=checkpoint,
                    data=result,
                    requires_action=True
                )
                # 等待用户响应
                user_action = await self._wait_for_user()
                if user_action == "reject":
                    # 用户拒绝，进入修正循环
                    await orchestrator.revise(checkpoint, user_action.feedback)
            
            elif setting == "manual":
                # 完全手动，Agent仅提供建议
                result = await orchestrator.generate_suggestion(checkpoint)
                yield CollaborationEvent(
                    type="suggestion_ready",
                    checkpoint=checkpoint,
                    data=result,
                    requires_action=True
                )
```

### 5.5 难点五：Tauri与Python后端的深度集成

**问题描述：**
选择Tauri作为前端框架，需要解决：
- Tauri(Rust)与Python后端的进程通信
- 桌面级文件系统访问（项目文件管理）
- 本地模型调用（Ollama等）的性能优化

**解决方案：**

1. **进程架构**
   ```
   Tauri (Rust + WebView)
     ├── Frontend (React) - UI渲染
     └── Rust Layer - 系统调用、文件IO
   
   Python Backend (独立进程)
     ├── FastAPI - HTTP服务
     └── Agent Core - 创作引擎
   
   通信: HTTP + WebSocket
   ```

2. **启动管理**
   - Tauri启动时自动启动Python后端
   - 后端端口自动发现（避免冲突）
   - 进程守护（后端崩溃自动重启）

3. **文件系统**
   - 小说项目存储在用户文档目录
   - Rust层负责文件IO（性能更好）
   - Python通过API访问文件内容

```rust
// Tauri Command示例
#[tauri::command]
async fn create_novel_project(
    app_handle: AppHandle,
    title: String,
    genre: String
) -> Result<NovelProject, String> {
    // 1. 创建本地目录
    let project_dir = get_projects_dir(&app_handle)?
        .join(sanitize_filename(&title));
    fs::create_dir_all(&project_dir)
        .map_err(|e| e.to_string())?;
    
    // 2. 调用Python后端创建项目
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/api/novels")
        .json(&json!({
            "title": title,
            "genre": genre,
            "project_path": project_dir.to_string_lossy()
        }))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    let project: NovelProject = response
        .json()
        .await
        .map_err(|e| e.to_string())?;
    
    Ok(project)
}
```

---

## 6. API设计

### 6.1 核心API

```python
# novels.py - 小说项目管理
@router.post("/api/novels")
async def create_novel(request: CreateNovelRequest) -> Novel

@router.get("/api/novels")
async def list_novels() -> List[NovelSummary]

@router.get("/api/novels/{novel_id}")
async def get_novel(novel_id: str) -> Novel

@router.put("/api/novels/{novel_id}")
async def update_novel(novel_id: str, request: UpdateNovelRequest) -> Novel

@router.delete("/api/novels/{novel_id}")
async def delete_novel(novel_id: str)

# chapters.py - 章节管理
@router.post("/api/novels/{novel_id}/chapters")
async def create_chapter(novel_id: str, request: CreateChapterRequest) -> Chapter

@router.get("/api/novels/{novel_id}/chapters/{chapter_id}")
async def get_chapter(novel_id: str, chapter_id: str) -> Chapter

@router.put("/api/novels/{novel_id}/chapters/{chapter_id}")
async def update_chapter(novel_id: str, chapter_id: str, request: UpdateChapterRequest) -> Chapter

# agent.py - Agent执行
@router.post("/api/novels/{novel_id}/agent/outline")
async def generate_outline(novel_id: str, request: OutlineRequest) -> Outline

@router.post("/api/novels/{novel_id}/agent/draft")
async def generate_draft(novel_id: str, chapter_id: str, request: DraftRequest) -> DraftResult

@router.post("/api/novels/{novel_id}/agent/edit")
async def edit_chapter(novel_id: str, chapter_id: str, request: EditRequest) -> EditResult

@router.post("/api/novels/{novel_id}/agent/continue")
async def continue_writing(novel_id: str, chapter_id: str, request: ContinueRequest) -> ContinueResult

# WebSocket for streaming
@router.websocket("/ws/novels/{novel_id}/agent")
async def agent_websocket(websocket: WebSocket, novel_id: str):
    """
    WebSocket连接，用于：
    - 实时接收Agent生成内容（流式）
    - 发送用户干预指令
    - 接收Agent状态更新
    """

# learning.py - 学习系统
@router.post("/api/novels/{novel_id}/feedback")
async def submit_feedback(novel_id: str, request: FeedbackRequest)

@router.post("/api/novels/{novel_id}/style/learn")
async def learn_from_reference(novel_id: str, file_id: str) -> StyleGuide

@router.get("/api/novels/{novel_id}/style/guide")
async def get_style_guide(novel_id: str) -> StyleGuide

# export.py - 导出
@router.post("/api/novels/{novel_id}/export")
async def export_novel(novel_id: str, request: ExportRequest) -> ExportResult
```

---

## 7. 实现路线图

### Phase 1: 基础架构（2-3周）
- [ ] Tauri项目搭建 + React前端框架
- [ ] Python后端Agent Core框架
- [ ] 数据库表创建
- [ ] Tauri-Python进程通信
- [ ] 基础项目管理（创建/打开/保存）

### Phase 2: 核心创作流程（3-4周）
- [ ] OutlineAgent实现
- [ ] DraftAgent实现（基础版本）
- [ ] 记忆系统（三层架构）
- [ ] 基础工作台UI（编辑器+大纲视图）
- [ ] 章节管理（CRUD）

### Phase 3: 多Agent协作（2-3周）
- [ ] WorldAgent + CharacterAgent
- [ ] EditAgent + ReviewAgent
- [ ] Orchestrator调度器
- [ ] 共享上下文总线
- [ ] 人机协作协议

### Phase 4: 学习系统（2-3周）
- [ ] 风格学习（参考作品分析）
- [ ] 反馈收集与编码
- [ ] 去AI味模块
- [ ] 偏好应用（Prompt增强）

### Phase 5: 高级功能（2-3周）
- [ ] 多格式导出（EPUB/DOCX/Markdown）
- [ ] 全文搜索与替换
- [ ] 版本历史
- [ ] 性能优化

---

## 8. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM生成质量不稳定 | 高 | 多模型fallback、后处理规则、人工审核节点 |
| 长文本上下文超出限制 | 高 | 分层摘要、向量检索、关键信息注入 |
| Tauri+Python集成复杂 | 中 | 清晰的进程边界、完善的错误处理 |
| 学习系统效果不明显 | 中 | 从规则-based开始，逐步引入ML |
| 项目范围膨胀 | 高 | 严格按Phase交付，每Phase可独立使用 |

---

## 9. 参考项目

| 项目 | 参考点 |
|------|--------|
| **Hermes Agent** | 自主进化、记忆机制、多Agent协作 |
| **Claude Code** | Spec-Driven设计、人机协作协议、工程化实践 |
| **Sudowrite** | 创作辅助交互、去AI味、风格迁移 |
| **novelWriter** | 项目管理、大纲视图、场景组织 |
| **LangGraph** | 状态机设计、Agent调度模式 |

---

*文档版本: 1.0*
*更新日期: 2026-06-08*

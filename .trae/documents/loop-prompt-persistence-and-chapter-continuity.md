# Loop 提示词持久化 + Agent 提示词可视化管理 + 章节衔接引擎 — 设计方案

## 一、背景与问题

**现状：**

1. **提示词不可持久化** — `src/backend/agents/prompts.py` 中 12 个 `build_*_prompt()` 函数和 6 个 `build_*_system_prompt()` 都是硬编码 Python 字符串，每次 loop 生成的优质提示词无法保存、无法复用、无法回看
2. **提示词不可可视化管理** — 前端没有提示词管理界面，无法增删改查 agent 提示词；开发者只能手动改 Python 源码
3. **章节衔接简陋** — 目前"上一章结尾"只是把上一章最后 500-800 个字符原样塞进 prompt，没有结构化的章末钩子（角色位置/情节点/悬念），LLM 经常忽略这个大块文字导致章节之间脱节
4. **学习引擎不参与衔接** — `learning_engine.py` 只做反 AI 味词 + 词汇偏好替换，完全没有"学习"用户认为衔接失败的地方

**代码定位（修改涉及的文件）：**

| 功能 | 当前位置 | 状态 |
|---|---|---|
| Prompt 构建函数 | `src/backend/agents/prompts.py:144-1230` | ✅ 需增加 DB 读写层 |
| 章节 pipeline（调用 prompt） | `src/backend/core/chapter_pipeline.py:25-34, 640-826` | ✅ 需注入 DB prompt resolver + 章末钩子 |
| 学习引擎 | `src/backend/core/learning_engine.py:1-171` | ✅ 需新增 continuity 模块 |
| DB models | `src/backend/db/models.py` | ✅ 需新增 `AgentPromptDB`、`ChapterContinuityDB` |
| DB CRUD | `src/backend/db/crud.py` | ✅ 需新增 `AgentPromptService`、`ChapterContinuityService` |
| API 路由 | `src/backend/main.py` | ✅ 需新增 /api/prompts/* + /api/continuity/* 端点 |
| Pydantic schemas | `src/backend/models/schemas.py` | ✅ 需新增 `AgentPrompt`, `ChapterContinuityHook` |
| 前端 API 客户端 | `src/frontend/src/api.ts` | ✅ 需新增 prompt API 调用 |
| 前端页面 | `src/frontend/src/pages/` + `src/frontend/src/App.tsx` | ✅ 需新增 PromptManagerPage + 在编排页显示 hook |
| Prompt 自动记录 | `src/backend/core/chapter_pipeline.py` 的 `run()` | ✅ 需在 loop 中自动保存 prompt 快照 |

## 二、总体架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                         前端 UI                               │
│  ┌──────────┐  ┌────────────┐  ┌────────────────────────┐    │
│  │ Prompt   │  │ Orchestrator│  │ NovelReadPage         │    │
│  │ Manager  │  │ Page      │  │ (显示 hook)            │    │
│  │ 增删改查 │  │ (loop模式) │  │                        │    │
│  └────┬─────┘  └────┬───────┘  └────────────────────────┘    │
└───────┼────────────┼──────────────────────────────────────────┘
        │            │
        │ GET/PUT/DELETE
        │            │ SSE stream (新增: continuity_hook 事件)
        ▼            ▼
┌────────────────────────────────────────────────────────────────────┐
│  API 层 (src/backend/main.py)                                      │
│  /api/prompts/*               /api/continuity/*                    │
│  ├─ GET /list                  ├─ GET /novel/{id}/hooks           │
│  ├─ POST /create               ├─ POST /hook (手动保存)           │
│  ├─ PUT /update                └─ POST /feedback (衔接反馈)        │
│  └─ DELETE /remove                                             │
└────────────┬────────────────────────────────────────────────────────┘
             │ SQLAlchemy AsyncSession
             ▼
┌────────────────────────────────────────────────────────────────────┐
│  持久化层 (src/backend/db/)                                        │
│  AgentPromptDB             ChapterContinuityDB  (新增)             │
│  ├ id (主键)              ├ id                                    │
│  ├ agent_type (技能类型)   ├ novel_id                              │
│  ├ prompt_key (唯一标识)   ├ chapter_idx                           │
│  ├ depth_level (深度)      ├ hook_type (scene/character/tension)   │
│  ├ content (JSON)          ├ ending_text (原文结尾)                 │
│  ├ system_prompt           ├ character_positions (JSON)            │
│  ├ user_prompt             ├ plot_nodes (JSON)                      │
│  ├ tokens (大致消耗)       ├ unresolved_mystery (JSON)              │
│  ├ source ("loop"|"manual")├ score (用户评分 0-10)                   │
│  ├ loop_iteration          └─ created_at                            │
│  ├ is_active (是否当前生效) │
│  └─ created_at, updated_at│
└────────────┬────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Prompt 解析层 (新: AgentPromptResolver)                           │
│  src/backend/core/chapter_pipeline.py 的内部辅助类                   │
│  └ get_effective_prompt(agent_type, depth_level, prompt_key)       │
│     ├ 优先: DB 中 is_active=True 的 prompt                          │
│     └ fallback: prompts.py 的 build_*_prompt() 默认实现              │
│  └ save_used_prompt(...) → 每次使用后存入 AgentPromptDB             │
└────────────┬────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│  章节衔接引擎 (新: ChapterContinuityEngine)                        │
│  src/backend/core/learning_engine.py 新增                           │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ extract_end_hook(chapter_content, idx)                  │     │
│  │   └ 从生成的章节中提取结构化钩子                           │     │
│  │      【场景】当前地点 + 时间  【角色】主角此刻状态           │     │
│  │      【情节】未解决节点     【张力】当前悬念/冲突           │     │
│  │ save_hook_to_db(hook) → ChapterContinuityDB              │     │
│  │ learn_from_continuity_feedback(feedback_type, ...)       │     │
│  │   └ 从用户反馈中学习：上一章开头"跳了" → 加强下一章衔接指令 │     │
│  │ build_next_chapter_context(chapter_idx, novel_id)        │     │
│  │   └ 读取上一章 hook + 学习到的偏好 → 生成结构化衔接上下文 │     │
│  │   (替代当前的 prev_chapter_text[-500:])                 │     │
│  └─────────────────────────────────────────────────────────┘     │
└────────────┬────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│  LLM 调用 (client.py)                                              │
│  提示词内容不变，但结构更紧凑：                                       │
│   [衔接上下文引擎] → [故事圣经] → [角色快照] → [本章任务]           │
└────────────────────────────────────────────────────────────────────┘
```

## 三、功能 1 — Loop 生成的提示词持久化保存

### 3.1 实现思路

在 `ChapterPipeline.run()` 方法中（即每章的 loop 执行体），在每个 `_agent_*()` 被调用后（或者更准确：在 LLM 调用前的 prompt 构建时），将 `system_prompt` 和 `user_prompt` 原文（或截断后的摘要）存入 `AgentPromptDB`。

关键修改点：
- `chapter_pipeline.py` 的 `_agent_draft()` 方法（line ~640）中，`system_prompt = build_draft_system_prompt(depth_level)` 这行之后新增保存逻辑
- 同样对 `_agent_outline()` 的 system_prompt 构建处（line ~146）新增保存
- 其他 `_agent_world/character/opening_hook/style_editor_full` 同理

### 3.2 数据结构

```python
class AgentPromptDB(Base):
    __tablename__ = "agent_prompts"

    id = Column(String, primary_key=True)            # 随机 ID
    novel_id = Column(String, index=True)            # 小说 ID (可为空: 通用模板)
    agent_type = Column(String, index=True)          # "story_architect"/"world_builder"/"character_designer"/"opening_hook"/"writer"/"style_editor"
    prompt_key = Column(String, index=True)          # 如"story_architect.depth_0"
    depth_level = Column(Integer, default=1)          # SKELETON=0, DETAIL=1, POLISH=2
    source = Column(String)                           # "loop_auto" (自动保存) | "manual" (用户手工创建)
    system_prompt = Column(Text, default="")          # 系统提示词原文
    user_prompt_template = Column(Text, default="")   # 用户提示词模板（可含 {placeholders}）
    is_active = Column(Integer, default=0)             # 1=当前使用, 0=历史版本
    loop_iteration = Column(Integer, default=0)         # 第几次 loop
    tokens_used = Column(Integer, default=0)
    notes = Column(Text, default="")                   # 用户备注 (前端显示)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)
```

字段设计要点：
- `novel_id` 可为空 — 区分 "通用模板" 和 "小说专用"
- `depth_level` + `agent_type` + `prompt_key` 形成定位 — 让前端可以按"技能 x 深度"组织管理界面
- `is_active` 是开关 — pipeline 生成时优先用 active 的 DB 版本，回落到 prompts.py 默认

### 3.3 修改点

**① models.py — 新增 AgentPromptDB**

在 `LLMConfigDB` 之后新增 class，和 `NovelDB` 建立关系（可选）。

**② crud.py — 新增 AgentPromptService**

```python
class AgentPromptService:
    @staticmethod
    async def list_by_novel(db, novel_id): ...
    @staticmethod
    async def get_active(db, agent_type, depth_level, novel_id=None): ...
    @staticmethod
    async def create(db, data): ...
    @staticmethod
    async def update(db, prompt_id, data): ...
    @staticmethod
    async def delete(db, prompt_id): ...
    @staticmethod
    async def set_active(db, prompt_id, is_active): ...
    @staticmethod
    async def snapshot_loop(db, novel_id, agent_type, depth_level, system_prompt, user_prompt_template, loop_iter):
        """Loop 每次使用后保存为一条记录（不设 active）"""
```

**③ schemas.py — 新增 Pydantic AgentPrompt**

```python
class AgentPromptCreate(BaseModel):
    agent_type: str
    prompt_key: str
    depth_level: int = 1
    system_prompt: str
    user_prompt_template: str = ""
    notes: str = ""

class AgentPromptUpdate(BaseModel):
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[int] = None

class AgentPrompt(BaseModel):
    id: str
    novel_id: Optional[str]
    agent_type: str
    prompt_key: str
    depth_level: int
    source: str
    system_prompt: str
    user_prompt_template: str
    is_active: int
    loop_iteration: int
    notes: str
    created_at: datetime
    updated_at: datetime
    class Config: from_attributes = True
```

**④ main.py — 新增 /api/prompts/* 路由**

```python
@app.get("/api/prompts")
async def list_prompts(novel_id: Optional[str] = None, agent_type: Optional[str] = None):
    ...

@app.post("/api/prompts")
async def create_prompt(data: AgentPromptCreate):
    ...

@app.put("/api/prompts/{prompt_id}")
async def update_prompt(prompt_id: str, data: AgentPromptUpdate):
    ...

@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    ...

@app.post("/api/prompts/{prompt_id}/activate")
async def activate_prompt(prompt_id: str):
    # 将这条 prompt 设为该 agent_type+depth_level 的 active
    ...

@app.get("/api/prompts/history")
async def get_prompt_history(novel_id: str, agent_type: str, limit: int = 20):
    # 返回某本小说+某技能的历史提示词（用于对比和回溯）
    ...
```

**⑤ chapter_pipeline.py — 注入 PromptResolver + 自动保存**

```python
# 新方法: ChapterPipeline 中新增
async def _resolve_and_save_prompt(
    self,
    agent_type: str,
    depth_level: int,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    1. 若 DB 中有该 agent_type + depth_level 的 is_active=True prompt → 返回它
    2. 否则返回传入的默认 system_prompt
    3. 无论 1/2, 都保存一条 source="loop_auto" 的历史记录 (用于回看)
    """
    ...
```

然后在每个 `_agent_*()` 中调用它：
```python
# 修改前:
system_prompt = build_story_architect_system_prompt(depth_level)

# 修改后:
system_prompt = await self._resolve_and_save_prompt(
    "story_architect",
    depth_level,
    build_story_architect_system_prompt(depth_level),
    user_prompt_str,
)
```

**重要决策：** 对于 `_agent_draft()` 这种 user_prompt 里含 `{chapter_title}` 占位符的 — 保存时我们存储 `user_prompt_template`（带 `{placeholders}`），而不是替换后的具体文本。这样用户在前端可以看到"模板"，而不是固定一次生成的文本。

## 四、功能 2 — 6 个 Agent 提示词可视化管理

### 4.1 设计思路

新增一个前端页面 `PromptManagerPage.tsx`，页面结构如下：

```
┌──────────────────────────────────────────────────────────────┐
│ 顶部:                                                         │
│  [切换小说: ▼《XX小说》 / 通用模板]                            │
│  [深度过滤: ▼ 全部 / SKELETON(0) / DETAIL(1) / POLISH(2) ]     │
│                                                                │
│ 主体: 6 列网格或 Tab 切换                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ①故事架构师  ②世界观构建师  ③角色塑造师  ④开篇钩子师     │  │
│  │ ⑤专业写手    ⑥文风精修师                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ 每个技能卡片:                                                  │
│  ┌────────────────────────────────────────────┐              │
│  │ ★ SKELETON (depth=0)  [启用中]             │              │
│  │ System Prompt:                              │              │
│  │ ┌────────────────────────────────────┐    │              │
│  │ │ 文本编辑器 (代码样式: 行号、等宽)   │    │              │
│  │ └────────────────────────────────────┘    │              │
│  │ User Prompt Template:                      │              │
│  │ ┌────────────────────────────────────┐    │              │
│  │ │ ...                              │    │              │
│  │ └────────────────────────────────────┘    │              │
│  │ [保存为当前版本]  [设为启用]  [删除]         │              │
│  └────────────────────────────────────────────┘              │
│                                                                │
│ 底部: 历史版本对比 (可在两个版本间 diff)                         │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 技术实现

**前端新增文件：** `src/frontend/src/pages/PromptManagerPage.tsx`

```typescript
// 1. 在 App.tsx 注册:
import { PromptManagerPage } from "./pages/PromptManagerPage";
const PAGE_COMPONENTS = {
  ...
  prompts: PromptManagerPage,   // 新增
};

// 2. 在导航中新增菜单项:
const NAV_ITEMS = [
  { id: "overview", label: "概览" },
  { id: "orchestrator", label: "编排创作" },
  { id: "novels", label: "小说管理" },
  { id: "prompts", label: "提示词管理" },     // 新增
  { id: "characters", label: "角色管理" },
  { id: "world", label: "世界观管理" },
  { id: "llm", label: "LLM 配置" },
  { id: "learning", label: "学习引擎" },
  { id: "dashboard", label: "仪表盘" },
];
```

**前端 API 扩展：** `src/frontend/src/api.ts`

```typescript
interface AgentPrompt {
  id: string;
  novel_id: string | null;
  agent_type: string;
  prompt_key: string;
  depth_level: number;
  source: string;
  system_prompt: string;
  user_prompt_template: string;
  is_active: number;
  loop_iteration: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

listPrompts: (novel_id?: string, agent_type?: string) => Promise<{prompts: AgentPrompt[]}>
  => http("GET", "/api/prompts", undefined, { novel_id, agent_type }),

createPrompt: (prompt: Partial<AgentPrompt>) => Promise<AgentPrompt>
  => http("POST", "/api/prompts", prompt),

updatePrompt: (id: string, data: Partial<AgentPrompt>) => Promise<AgentPrompt>
  => http("PUT", `/api/prompts/${id}`, data),

deletePrompt: (id: string) => Promise<any>
  => http("DELETE", `/api/prompts/${id}`),

activatePrompt: (id: string) => Promise<any>
  => http("POST", `/api/prompts/${id}/activate`),

getPromptHistory: (novel_id: string, agent_type: string) => Promise<{prompts: AgentPrompt[]}>
  => http("GET", "/api/prompts/history", undefined, { novel_id, agent_type, limit: 20 }),
```

### 4.3 前端交互逻辑

- 用户选中某个 `agent_type + depth_level`，前端发送 `GET /api/prompts?agent_type=xxx&depth_level=0`
- 显示该组合下所有历史版本（按时间倒序），最新的 `is_active=1` 用 ★ 标记
- 用户编辑当前版本 → `PUT /api/prompts/{id}` 更新文本
- 用户点击"设为启用" → `POST /api/prompts/{id}/activate` 将该 prompt 的 `is_active=1`，并将同组合其他 prompt 设为 0

### 4.4 编辑体验

- 用 `<textarea style="font-family: monospace; font-size: 13px; line-height: 1.6; white-space: pre-wrap; tab-size: 2;">` 编辑大段文本
- 每个 agent 显示 6 个提示词区域（3 depth × system_prompt + user_prompt_template）
- 提供"恢复默认"按钮（返回 prompts.py 中硬编码的初始版本）
- 提供"从历史版本 X 恢复"功能

## 五、功能 3 — 章节衔接引擎（整合 LearningEngine）

### 5.1 问题诊断

当前 (`chapter_pipeline.py:697-706`) 的衔接方式：

```python
prompt_parts.append(f"""═══════════════════════════════════════════
         上一章结尾（请直接从此处接续）
═══════════════════════════════════════════

{prev_chapter_text[-500:]}

↑ 本章开头必须直接接续以上场景，不得跳跃或重新开始。""")
```

**问题：**
1. 只是**原样粘 500 字** — LLM 读到的是零散文字，而不是"我需要衔接的关键要点"
2. 没有结构化信息 — "主角此刻在哪里？有谁和他在一起？上一章结尾的核心悬念是什么？"
3. **没有"学习"** — 用户如果标记"这一章衔接得差"，系统不会在下一次生成时更加注意

### 5.2 新设计：ChapterContinuityEngine

在 `src/backend/core/learning_engine.py` 中增加 **章节衔接引擎**（或作为独立模块 `src/backend/core/continuity_engine.py`）。

**核心流程：**

```
第 N 章生成完毕 → 自动调用:
  extract_end_hook(chapter_content, chapter_idx)
     │
     ├► 解析: 当前地点/时间 → 角色位置 → 未解决悬念 → 张力点
     └► 存入 ChapterContinuityDB

第 N+1 章开始生成 → 在 _agent_draft 的 prompt 构建前调用:
  build_next_chapter_context(chapter_idx=N+1, novel_id)
     │
     ├► 读取上一章 hook (ChapterContinuityDB)
     ├► 读取学习引擎学到的衔接偏好
     └► 返回一个结构化的衔接指令字符串（更紧凑、更有效）
```

**数据结构：**

```python
class ChapterContinuityDB(Base):
    __tablename__ = "chapter_continuity"

    id = Column(String, primary_key=True)
    novel_id = Column(String, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_idx = Column(Integer, index=True)
    ending_text = Column(Text)                         # 章末原文 (最后 300 字)

    # 结构化钩子 (JSON)
    scene = Column(JSONType, default=dict)              # {"location": "北麓山崖", "time": "午夜", "weather": "雪"}
    character_states = Column(JSONType, default=list)   # [{"name": "林墨", "action": "站在崖边凝视", "emotion": "凝重", "phys_state": "受伤"}]
    plot_nodes = Column(JSONType, default=list)         # [{"type": "unresolved_mystery", "text": "黑衣人的身份"}, ...]
    tension_points = Column(JSONType, default=list)     # [{"type": "physical_danger", "text": "追兵将至"}]
    unresolved_items = Column(JSONType, default=list)   # 本层未解决的线索/冲突/问题

    # 学习相关
    continuity_score = Column(Integer, default=7)        # 用户评分 (下次若低分则加强衔接)
    feedback_comments = Column(Text, default="")          # 用户备注"开头跳了""衔接不自然"
    auto_gen_notes = Column(Text, default="")             # LLM 分析输出的衔接要点

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)
```

### 5.3 extract_end_hook() 的实现思路

**方案 A（推荐初始版本，轻量实现）：**
不调用 LLM，用规则提取 — 快、可靠、零消耗

```python
def extract_end_hook(content: str, chapter_idx: int) -> dict:
    """
    轻量规则提取:
    1. ending_text = content[-300:]
    2. 从结尾中提取专有名词 (简单正则/分词: 2-4个中文字且是角色/地名)
    3. 识别最后 5 段里的动作动词
    4. 识别结尾的悬念关键词 ("可是...","但是...","突然...","没想到...")
    """
    hook = {
        "ending_text": content[-300:].strip(),
        "scene": {},
        "character_states": [],
        "plot_nodes": [],
        "tension_points": [],
    }

    # 规则1: 从结尾段找地点/时间/天气关键词
    # 规则2: 提取主角最近动作
    # 规则3: 查找悬念句式 (简单关键词匹配)
    return hook
```

**方案 B（推荐优化版本，LLM 辅助）：**
用一个**轻量级** LLM 调用，给它末尾 500 字，让它返回 JSON：

```
prompt = f"请分析以下小说结尾，提取结构化钩子，返回严格 JSON:
{{\"scene\": {{\"location\": \"地点\"}},
 \"character_states\": [{{\"name\": \"\", \"action\": \"\", \"emotion\": \"\"}}],
 \"plot_nodes\": [{{\"type\": \"unresolved_mystery/conflict/promise\", \"text\": \"\"}}],
 \"tension_points\": [{{\"type\": \"physical/emotional/reveal\", \"text\": \"\"}}]
}}

结尾内容: {content[-500:]}"
```

**实施路径：** 先用方案 A 出第一个可运行版本，确认"确实让衔接变好了"之后再切换为方案 B。这样避免一次改动太多导致调试困难。

### 5.4 build_next_chapter_context() 的实现

这是**真正影响生成质量的关键函数**。它的作用是：**用紧凑、结构化、强制的语言告诉 LLM 如何衔接上一章。**

```python
async def build_next_chapter_context(self,
                                      chapter_idx: int,
                                      novel_id: str,
                                      learning_engine: LearningEngine) -> str:
    """
    返回像这样的文本:
    ┌──────────────────────────────────────────┐
    │ 【强制衔接指令】第 5 章开头必须直接接续第 4 章结尾:
    │ 当前场景: 北麓山崖, 午夜, 大雪
    │ 主角状态: 林墨站在崖边, 手上有伤, 表情凝重
    │ 必须接续的情节: 黑衣人尚未揭露身份
    │ 当前张力: 山下追兵即将赶到
    │
    │ 【学习提示】上次用户反馈: 开头太突兀 → 请用3-5句自然承接上一章结尾
    │ 【禁止】开头出现"第二天""与此同时""镜头一转"等跳跃表达
    └──────────────────────────────────────────┘
    """

    # 1. 从 DB 读上一章 hook
    prev_hook = await db.query(ChapterContinuityDB) \
        .filter(ChapterContinuityDB.novel_id == novel_id) \
        .filter(ChapterContinuityDB.chapter_idx == chapter_idx - 1) \
        .first()

    if not prev_hook:
        # 第1章或无数据: 不做特殊处理（返回空）
        return ""

    # 2. 从 learning engine 读取学到的衔接偏好
    continuity_prefs = learning_engine.get_continuity_preferences(novel_id)
    # 例如: {"avg_score": 5.3, "issues_found": ["开头跳跃", "角色状态不一致"], "extra_rules": "..."}

    # 3. 构建紧凑的衔接指令
    parts = [f"【强制衔接指令】本章开头必须直接接续第{chapter_idx-1}章结尾:"]

    if prev_hook.scene:
        scene = prev_hook.scene
        loc = scene.get("location", "")
        tm = scene.get("time", "")
        if loc or tm:
            parts.append(f"- 当前场景: {loc}, {tm}")

    if prev_hook.character_states:
        for cs in prev_hook.character_states[:3]:  # 只取前3个主要角色
            name = cs.get("name", "")
            action = cs.get("action", "")
            if name and action:
                parts.append(f"- 主角状态: {name}正{action}")

    if prev_hook.plot_nodes:
        for pn in prev_hook.plot_nodes[:2]:
            parts.append(f"- 必须接续的情节: {pn.get('text', '')}")

    if prev_hook.tension_points:
        for tp in prev_hook.tension_points[:2]:
            parts.append(f"- 当前张力: {tp.get('text', '')}")

    # 4. 附加学习到的规则
    if continuity_prefs:
        if continuity_prefs.get("avg_score", 10) < 6:
            parts.append("\n【学习提示】本章用户对开头衔接的评分低于 6/10, 请:")
            parts.append("  1. 用 3-5 句自然承接上一章结尾")
            parts.append("  2. 不要使用'第二天''与此同时''镜头一转'等跳跃表达")
            parts.append("  3. 先写主角当下的感受/动作, 再拉远到场景描写")
        if continuity_prefs.get("issues_found"):
            for issue in continuity_prefs["issues_found"][:2]:
                parts.append(f"  4. 避免: {issue}")

    parts.append("\n【原文结尾参考】")
    parts.append(prev_hook.ending_text[-200:])

    return "\n".join(parts)
```

**和现有代码的接入点：**

目前的 pipeline 调用链：
```
orchestrator.run_all_loop() → chapter_pipeline.run(previous_chapter_text=...)
  → _agent_draft() 读取 context["previous_chapter_text"]
```

**新的调用链：**
```
orchestrator.run_all_loop()
  → continuity_engine.extract_end_hook(prev_chapter_content) → 保存 DB
  → continuity_engine.build_next_chapter_context(next_idx, novel_id, learning_engine)
  → chapter_pipeline.run(continuity_context=..., previous_chapter_text=...)
    → _agent_draft() 中用 continuity_context 替换/增强 旧的"上一章结尾"块
```

**特别注意：** `continuity_context` 出现在 prompt 顶部（在 story_bible 之前）或紧邻 story_bible 之后 — 让它成为**第一个被 LLM 读**的指令，从而提高被遵守的概率。

### 5.5 学习引擎增强

给 `LearningEngine` 增加两类新方法：

```python
# 在 src/backend/core/learning_engine.py 新增:

class LearningEngine:
    # ... 现有方法 ...

    # ── 新: 章节衔接相关 ──────────────────────────
    def record_continuity_feedback(self,
                                    novel_id: str,
                                    chapter_idx: int,
                                    score: int,
                                    comment: str = ""):
        """保存用户对"章节衔接自然度"的评分 (1-10)"""
        self._continuity_feedback.append({
            "novel_id": novel_id,
            "chapter_idx": chapter_idx,
            "score": score,
            "comment": comment,
            "created_at": datetime.now(),
        })
        # 同时持久化到 ChapterContinuityDB
        ...

    def get_continuity_preferences(self, novel_id: str) -> dict:
        """从历史反馈中推断当前小说的衔接偏好"""
        novel_fb = [f for f in self._continuity_feedback if f["novel_id"] == novel_id]
        if not novel_fb:
            return {}
        avg_score = sum(f["score"] for f in novel_fb) / len(novel_fb)
        low_score_comments = [f["comment"] for f in novel_fb if f["score"] < 6 and f["comment"]]
        return {
            "avg_score": avg_score,
            "issues_found": low_score_comments,
            "feedback_count": len(novel_fb),
        }

    # 持久化 (补充)
    _continuity_feedback: List[dict] = []
```

**API 层新增 2 个端点：**

```python
# main.py 中新增
@app.post("/api/continuity/hook")
async def save_hook(novel_id: str, chapter_idx: int, content: str):
    """手动触发 hook 提取 (前端"重新分析本章结尾"按钮)"""

@app.post("/api/continuity/feedback")
async def submit_continuity_feedback(novel_id: str, chapter_idx: int, score: int, comment: str = ""):
    """用户对"本章与上一章的衔接自然度"评分 (1-10)"""
```

### 5.6 前端配合

1. **OrchestratorPage** 的 SSE 流中新增 `continuity_hook` 事件 — 实时显示"上一章结尾钩子分析"
2. **NovelReadPage**（或 NovelEditPage）底部加一个**小卡片评分组件**：

```
┌──────────────────────────────────────────┐
│ 第3章衔接评分                            │
│ 与上一章衔接自然度: ★★★★☆☆☆☆☆☆ (滑杆 1-10) │
│ 备注: [开头有点跳, 直接进入对话...]         │
│ [提交反馈]                                │
└──────────────────────────────────────────┘
```

提交后 → `POST /api/continuity/feedback` → learning_engine 记录 + 更新 ChapterContinuityDB

## 六、章节 pipeline 中的具体修改位置

这是最关键的代码改动点，需要精确定位：

### 6.1 chapter_pipeline.py: `_agent_draft()` (line ~640)

**原代码块** (line ~697-706):
```python
# ── 上一章原文结尾（直接衔接，修改2）──
prev_chapter_text = context.get("previous_chapter_text", "")
if prev_chapter_text and chapter_idx > 1:
    prompt_parts.append(f"""═══════════════════════════════════════════
          上一章结尾（请直接从此处接续）
═══════════════════════════════════════════

{prev_chapter_text[-500:]}

↑ 本章开头必须直接接续以上场景，不得跳跃或重新开始。""")
```

**修改为：**
```python
# ── 新: 结构化章节衔接引擎 ──
if chapter_idx > 1:
    continuity_context = context.get("continuity_context", "")
    if continuity_context:
        prompt_parts.append(continuity_context)  # ★ 这个放在最前面
    else:
        # fallback: 保留旧的 500 字方案
        prev_chapter_text = context.get("previous_chapter_text", "")
        if prev_chapter_text:
            prompt_parts.append(f"""═══════ ...旧的 500 字块...""")
```

### 6.2 chapter_pipeline.py: `run()` 方法 (line ~1073)

**新增步骤：** 在 `run()` 方法的**开始阶段**，读取 `context` 中由 orchestrator 注入的 `continuity_context`

### 6.3 orchestrator.py: `run_all_loop()` 的章节生成循环 (line ~890)

**原逻辑** (line ~476-488):
```python
prev_content = chapters[-1].get("content", "")
prev_ending = prev_content[-800:] if len(prev_content) > 800 else prev_content
chapter_pipeline.run(..., previous_chapter_text=prev_ending)
```

**新逻辑:**
```python
prev_content = chapters[-1].get("content", "")
prev_ending = prev_content[-800:] if len(prev_content) > 800 else prev_content

# ★ 新增: 提取并持久化 hook
from src.backend.core.continuity_engine import extract_hook_and_save
await extract_hook_and_save(novel_id, chapter_idx, prev_content)

# ★ 新增: 构建结构化衔接上下文
from src.backend.core.continuity_engine import build_next_chapter_context
continuity_context = await build_next_chapter_context(
    novel_id=novel_id,
    chapter_idx=next_idx,
    learning_engine=self.learning_engine,
)

context["previous_chapter_text"] = prev_ending  # 保留旧字段 (向后兼容)
context["continuity_context"] = continuity_context  # ★ 新字段

await chapter_pipeline.run(..., context=context)
```

### 6.4 自动保存 Loop 提示词

在 `_agent_draft()` 的 prompt 构建完成**并调用 LLM 之前**，插入保存逻辑：

```python
# prompt_parts 组装完毕后:
user_prompt = "\n".join(prompt_parts)

# ★ 自动保存 prompt 快照 (仅 DETAIL/POLISH 层, SKELETON 不存以免噪音)
if depth_level >= 1 and hasattr(self, '_prompt_saver') and self._prompt_saver:
    asyncio.create_task(self._prompt_saver(
        novel_id=context.get("novel_id", ""),
        agent_type="writer",
        depth_level=depth_level,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt[:3000],  # 截断, 避免 DB 膨胀
        loop_iter=loop_metadata.get("loop", 0),
    ))
```

其中 `_prompt_saver` 是 `ChapterPipeline.__init__` 中注入的一个异步保存函数（避免强耦合，测试时可替换）。

## 七、数据库初始化与迁移

项目已有自动建表机制 (`main.py` 中 `Base.metadata.create_all(...)` 或 `db/database.py` 中类似调用)。新增两张表会在下次启动时自动创建 — **无需要手动迁移。**

**但需注意事项：**
1. `prompt_text` 字段可能较长（系统提示词可达 2000-5000 字符），SQLite 的 `Text` 类型支持，但建议设置**字段上限**或在写入时截断。策略: 最多保存 5000 字符 (≈10KB/条)，如果超了截断并保存前半部分
2. `novel_id` 允许为 NULL（用于"通用模板"），所以 SQLAlchemy 中要设 `nullable=True`
3. 若表已存在于旧版本数据库中（字段缺失），需要补字段。参照项目已有的 `db/database.py` 中 migration 机制

## 八、预计的代码变化规模

| 文件 | 新增行数 (约) | 改动方式 |
|---|---|---|
| `src/backend/db/models.py` | +50 | 新增 2 个 Model class |
| `src/backend/db/crud.py` | +80 | 新增 AgentPromptService + ChapterContinuityService |
| `src/backend/models/schemas.py` | +40 | 新增 Pydantic schemas |
| `src/backend/core/chapter_pipeline.py` | +60 | 注入 prompt resolver, 替换 prompt 构建处, 新增自动保存 |
| `src/backend/core/learning_engine.py` | +120 | 新增 continuity 相关方法 |
| 或 `src/backend/core/continuity_engine.py` | +150 | **可选**: 新建独立文件，放 extract_hook 和 build_context |
| `src/backend/main.py` | +150 | 新增 /api/prompts/* + /api/continuity/* 约 8-10 个端点 |
| `src/frontend/src/pages/PromptManagerPage.tsx` | +400 | 新页面 (技能网格 + 编辑器 + 历史版本) |
| `src/frontend/src/App.tsx` | +10 | 注册新页面到导航 |
| `src/frontend/src/api.ts` | +30 | 新增前端 API 客户端方法 |

**总计: ~1100 行新增代码，~50 行修改代码**

## 九、实施顺序

建议分三个版本发布，每个都是"可用状态"：

### Phase 1: 基础持久化（1 天）

**目标：** prompt 可以保存到数据库，前端可以看到历史记录（只读）

1. `models.py` 新增 `AgentPromptDB`
2. `crud.py` 新增 `AgentPromptService` 的 CRUD 基本实现
3. `schemas.py` 新增 Pydantic models
4. `main.py` 新增 `GET /api/prompts`, `POST /api/prompts`（只读 + 创建）
5. `chapter_pipeline.py` 新增 `_resolve_and_save_prompt()` 自动保存调用
6. `PromptManagerPage.tsx` v1 — 只显示历史，不允许编辑

### Phase 2: 完整可视化管理（1 天）

**目标：** 前端可以完整增删改查 + 设为启用

1. `main.py` 完善 `PUT/DELETE/activate` 端点
2. `chapter_pipeline.py` 让 prompt 解析器真正生效（优先从 DB 读取 active prompt）
3. `PromptManagerPage.tsx` v2 — 完整编辑器 + 历史版本对比
4. `api.ts` 完善前端 API 客户端

### Phase 3: 章节衔接引擎（1-2 天）

**目标：** 结构化 hook 提取 + learning_engine 反馈学习

1. `models.py` 新增 `ChapterContinuityDB`
2. `continuity_engine.py` (新建) — extract_hook (A 方案规则版) + build_context
3. `learning_engine.py` 新增 continuity 学习逻辑
4. `orchestrator.py` 接入新引擎到章节循环
5. `chapter_pipeline.py` — 用新的 continuity_context 替换旧的 500 字块
6. `main.py` 新增 `/api/continuity/*` 端点
7. `OrchestratorPage.tsx` 新增 hook 显示卡片
8. `NovelReadPage.tsx` 新增用户评分组件

**总计：** 3-4 天完成全部三项功能

## 十、验证清单

- [ ] 运行 `python test_project.py` 全量测试通过 (保持原有 99+ 通过)
- [ ] 数据库有新表 `agent_prompts`, `chapter_continuity`
- [ ] Loop 模式下，每次生成后自动写入 1 条 agent_prompt 记录
- [ ] 前端"提示词管理"页面能看到历史记录
- [ ] 编辑并激活一条 prompt 后，下次生成时确实使用这条
- [ ] 用"恢复默认"按钮能回退到 prompts.py 初始版本
- [ ] 第 N 章生成后, 第 N+1 章的 prompt 顶部出现"【强制衔接指令】"块
- [ ] 用户在阅读页评分 1-10 后, learning_engine 中记录到反馈
- [ ] 低分小说（平均 < 6）在下一次生成时, prompt 中出现"【学习提示】"块

## 十一、风险与注意事项

1. **prompt 文本膨胀** — 每条 system_prompt 可能 2-5KB，每章 loop 生成 6 条。100 章小说 = 600 条 × 5KB = 3MB。SQLite 能承受，但要注意只在 depth>=1 时保存
2. **LLM 调用频率增加** — 如果方案 B (LLM 提取 hook) 上线，每章多 1 次调用。方案 A (规则) 不增加调用
3. **DB 写入在热路径上** — 为避免阻塞生成，使用 `asyncio.create_task()` 异步保存（见 6.4），而不是 await
4. **向后兼容** — 所有旧字段（如 `previous_chapter_text`）保留不删，只是 prompt 中改用新结构。新 prompt 不存在时回退到旧行为
5. **用户误用** — 用户可能会把 system_prompt 改错导致产出下降。需要"恢复默认"按钮 + 显示最近 N 次产出评分

# 6 个 Agent/Skill 提示词 Loop 优化方案

## 一、概述

将 6 个 Skill 的 System Prompt 和 User Prompt 改造为 loop 深度感知模式，在 SKELETON (depth=0) → DETAIL (depth=1) → POLISH (depth=2) 三层循环中逐层深化产出质量。

## 二、现状分析

### 2.1 当前 Loop 架构

| Loop | 深度名称 | 深度值 | 温度 | 主要行为 |
|------|---------|--------|------|---------|
| 0 | SKELETON | 0 | 0.85 | 快速构建世界观/角色/大纲骨架 |
| 1 | DETAIL | 1 | 0.70 | 细化设定 + 逐章写作 |
| 2 | POLISH | 2 | 0.55 | 逐章精修 + 品质审查 |
| 3+ | REFINE | 3+ | ≤0.40 | 低分章节重写 |

### 2.2 核心问题

所有 6 个 Skill 的 `depth_level`/`loop_metadata` 参数已接收，但提示词在 depth=0/1/2 三层中**完全相同**，未根据 loop 深度动态调整指令粒度。

具体表现为：

| Skill | 方法 | 问题 |
|-------|------|------|
| S1 故事架构师 | `_agent_outline()` | `depth_level` 接收但未使用，system_prompt 是硬编码字符串 |
| S2 世界观构建师 | `_agent_world()` | `depth_level` 接收但未使用，prompt 和 fallback 与深度无关 |
| S3 角色塑造师 | `_agent_character()` | `depth_level` 接收但未使用 |
| S4 开篇钩子师 | `_agent_opening_hook()` | 按 `chapter_idx` 区分而非 `depth_level` |
| S5 专业写手 | `_agent_draft()` | 仅字数使用 `depth_level`，system_prompt 和创作指令完全相同 |
| S6 文风精修师 | `_agent_style_editor_full()` | `depth_level` 接收但未使用，仅检查 AI 味表达和段落长度 |
| (旧) 风格润色师 | `_agent_style()` | 无 `loop_metadata` 参数 |
| (旧) 编辑润色 | `_agent_edit()` | 无 `depth_level` 参数，硬编码 temperature=0.3/max_tokens=5000 |
| (旧) 质量审查 | `_agent_review()` | 无 `depth_level` 参数，硬编码评分阈值 |

### 2.3 影响范围

- **`src/backend/agents/prompts.py`**: 6 个 System Prompt 常量 + 6 个 `build_*_user_prompt` 函数
- **`src/backend/core/chapter_pipeline.py`**: 9 个 Agent 方法（`_agent_outline` ~ `_agent_review`）+ `run()` 方法

## 三、深度差异化策略

### 3.1 三级渐进式模型

```
depth 0 (SKELETON): 骨架层 — 快速、粗粒度、结构优先
  → 产出：3-5 个结构要点、粗略角色卡、关键词汇场
  → 温度：0.85（高创意）
  → 字数：300-800 字

depth 1 (DETAIL): 细节层 — 完整、丰富、内容优先
  → 产出：完整大纲、详细角色关系、完整文风指南、2500 字正文
  → 温度：0.70（中等创意）
  → 字数：2000-3000 字

depth 2 (POLISH): 精修层 — 高质量、严格、品质优先
  → 产出：精修正文、7 维度评分、一致性检查、禁用词清零
  → 温度：0.55（低创意）
  → 字数：2500-3500 字
```

### 3.2 各 Skill 深度行为定义

#### S1 故事架构师 (Story Architect)

| 深度 | 行为 | System Prompt 关键差异 |
|------|------|----------------------|
| 0 | 快速产出 3-5 个结构要点, 不展开细节 | "你正在快速构建故事骨架，只需输出 3-5 个核心结构要点" |
| 1 | 完整大纲含 key_events/foreshadowing/turning_points | "你正在细化故事架构，需输出完整大纲含所有细节" |
| 2 | 审查大纲连贯性，调整因果链 | "你正在审查大纲质量，重点检查因果链和节奏分布" |

#### S2 世界观构建师 (World Builder)

| 深度 | 行为 | System Prompt 关键差异 |
|------|------|----------------------|
| 0 | 1-2 个核心规则 + 1 个关键地点 | "只需输出核心规则和关键地点，不需展开细节" |
| 1 | 完整规则体系 + 3+ 地点含感官锚点 + 势力格局 | "需输出完整世界观，含规则、地点感官锚点、势力冲突" |
| 2 | 一致性审查，检查与正文的设定冲突 | "审查世界观与正文的一致性，标记任何矛盾" |

#### S3 角色塑造师 (Character Designer)

| 深度 | 行为 | System Prompt 关键差异 |
|------|------|----------------------|
| 0 | 主角名 + 核心驱动力 + 1 个行为标签 | "只需输出主角卡片：名称、核心驱动力、一个行为标签" |
| 1 | 完整心理画像 + 语言指纹 + 成长弧线 + 关系网 | "需输出完整角色档案，含心理画像、语言指纹、成长弧线" |
| 2 | 审查角色行为一致性，检查弧线进度 | "审查角色行为与设定的一致性，检查成长弧线进度" |

#### S4 开篇钩子师 (Opening Hook)

| 深度 | 行为 | System Prompt 关键差异 |
|------|------|----------------------|
| 0 | 基础钩子类型提示（冲突/悬念/反差/危机） | "只需提示钩子类型和方向，不展开具体设计" |
| 1 | 黄金三章详细钩子设计（场景+悬念+反转） | "需设计完整的黄金三章开篇方案" |
| 2 | 重审钩子有效性，检查与大纲的匹配度 | "审查钩子是否有效，检查与细化大纲的匹配度" |

#### S5 专业写手 (Writer)

| 深度 | 行为 | System Prompt 关键差异 |
|------|------|----------------------|
| 0 | 精简快速生成 300-800 字骨架草稿 | "快速写出骨架草稿，300-800 字即可，不要求完整" |
| 1 | 标准完整生成 2000-3000 字，含钩子 | "完整写作，2000-3000 字，需包含所有细节和场景" |
| 2 | 高质量精修级生成 2500-3500 字，严格表达规范 | "精修级写作，2500-3500 字，严格执行禁用词清单" |

#### S6 文风精修师 (Style Editor)

| 深度 | 行为 | System Prompt 关键差异 |
|------|------|----------------------|
| 0 | 关键词汇场输出（核心术语 + 禁用词） | "只需输出关键词汇场和禁用词清单" |
| 1 | 完整文风指南 + 编辑审查 + 7 维度评分 | "需输出完整文风指南并进行编辑审查" |
| 2 | 严格标准精修 + 前章一致性检查 + 低分重写 | "严格精修，重点检查一致性，低分章节需重写" |

## 四、具体修改方案

### 4.1 文件：`src/backend/agents/prompts.py`

#### 修改 1：新增 Loop 感知 System Prompt 构建函数

为每个 Skill 新增一个 `build_*_system_prompt(depth_level: int)` 函数，返回对应深度的 System Prompt。保留原有常量作为 depth=1 的默认值（向后兼容）。

新增函数列表：

```python
def build_story_architect_system_prompt(depth_level: int) -> str:
    """根据 depth_level 返回对应的 System Prompt"""

def build_world_system_prompt(depth_level: int) -> str:
    """根据 depth_level 返回对应的 System Prompt"""

def build_character_system_prompt(depth_level: int) -> str:
    """根据 depth_level 返回对应的 System Prompt"""

def build_opening_hook_system_prompt(depth_level: int) -> str:
    """根据 depth_level 返回对应的 System Prompt"""

def build_draft_system_prompt(depth_level: int) -> str:
    """根据 depth_level 返回对应的 System Prompt"""

def build_style_editor_system_prompt(depth_level: int) -> str:
    """根据 depth_level 返回对应的 System Prompt"""
```

**实现方式**：每个函数内部定义三个 prompt 变体，根据 depth_level 选择：

```python
def build_story_architect_system_prompt(depth_level: int) -> str:
    if depth_level <= 0:
        return SKELETON 版本
    elif depth_level == 1:
        return DETAIL 版本（即当前 STORY_ARCHITECT_SYSTEM_PROMPT）
    else:
        return POLISH 版本
```

#### 修改 2：增强现有 `build_*_user_prompt` 函数

为每个 `build_*_user_prompt` 函数添加 `depth_level: int = 1` 参数，根据深度调整 User Prompt 的输出要求。

关键修改点：

- `build_story_architect_user_prompt()`: depth 0 时要求"仅输出 3-5 个结构要点，不需要完整 JSON"；depth 2 时追加"审查因果链"
- `build_world_user_prompt()`: depth 0 时要求"仅输出核心规则和 1 个关键地点"
- `build_character_user_prompt()`: depth 0 时要求"仅输出主角名、核心驱动力、1 个行为标签"
- `build_opening_hook_user_prompt()`: depth 0 时要求"仅输出钩子类型提示"
- `build_draft_user_prompt()`: depth 0 时要求"300-800 字骨架草稿
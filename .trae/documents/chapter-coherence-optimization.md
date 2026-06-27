# 章节衔接连贯性优化方案

## 1. 问题摘要

当前项目生成的小说章节之间缺乏衔接和连贯性，表现为：
- 新章节开头未接续上一章结尾的场景/动作
- 角色状态、位置、情绪在章节间跳跃不一致
- 已埋设的线索/伏笔在后续章节中丢失
- 章末钩子与下一章开头脱节

## 2. 当前状态分析

### 2.1 章节生成流程

```
Orchestrator.run_stage("drafting")
  ├── 构建 shared_context（世界观、角色、风格）
  ├── 逐章循环:
  │   ├── ChapterPipeline.run(chapter_idx, title, summary, context, existing_text[-4000:])
  │   │   ├── Phase 1: 4个Skill协同规划
  │   │   │   ├── _agent_outline       → 仅用 summaries[:600]
  │   │   │   ├── _agent_world         → 仅用 world[:800]
  │   │   │   ├── _agent_character     → 仅用 characters[:600]
  │   │   │   └── _agent_opening_hook  → 仅用 world[:300]
  │   │   ├── Phase 2: _agent_draft 生成正文
  │   │   │   ├── 注入 story_bible（state_tracker）
  │   │   │   ├── 注入 connection_instruction（global_summary）
  │   │   │   ├── 注入 state_card（state_tracker）
  │   │   │   ├── 注入 scene_anchors（global_summary）
  │   │   │   └── ⚠️ existing_chapters_text 未注入 draft prompt
  │   │   └── Phase 3: 保存章末结尾 + 提取场景锚点
  │   └── 更新 existing_text += 本章内容
  └── 完成
```

### 2.2 根因分析

| 问题 | 根因 | 影响 |
|------|------|------|
| **A. 上一章正文未注入 draft prompt** | `existing_chapters_text` 仅传给 `_agent_style_editor_full`（审查用），未传给 `_agent_draft`（生成用） | 生成新章节时 LLM 不知道上一章写到了哪里 |
| **B. 衔接指令仅用摘要，非原文** | `get_connection_instruction()` 只用 `last_paragraph[:200]`，来自 `global_summary` 的摘要，而非 `existing_chapters_text` 的实际原文 | 摘要可能丢失关键细节，衔接指令不够精确 |
| **C. 规划 Agent 不知道上一章结尾** | `_agent_outline` 只用 `summaries[:600]`，`_agent_character` 只用 `characters[:600]`，都不包含上一章实际正文 | 大纲规划、角色设计无法基于故事最新的进展 |
| **D. existing_text 窗口太小** | 仅传 `existing_text[-4000:]`（约1000-1500字），多章累积后前文上下文丢失 | 第5章以后无法回顾第1-2章的关键事件 |
| **E. 章末衔接数据流断裂** | `state_tracker.set_last_ending()` 和 `global_summary.get_last_chapter_ending()` 两套数据源不一致 | `set_last_ending` 保存 `content[-300:]`，但 `get_connection_instruction` 用的是 `global_summary._summaries[-1].last_paragraph`，两者可能不同 |
| **F. 缺乏角色状态快照** | `state_tracker.build_state_card()` 有角色状态，但 `_agent_draft` 的 prompt 中角色信息仅来自 `context.get("characters")[:400]`（静态设定），不是动态状态 | 角色跨章行为不一致 |

## 3. 优化方案

### 3.1 核心思路：建立"上一章结尾 → 下一章开头"的强制衔接链

```
上一章正文内容
  ├── 提取 last_ending（最后500字原文）
  ├── 提取角色状态快照（位置、情绪、持有物品、当前目标）
  ├── 提取场景锚点（地点、感官描述）
  └── 注入到下一章的 ↓
      ├── _agent_draft prompt（核心注入点）
      ├── _agent_outline prompt（规划衔接）
      └── _agent_character prompt（角色连续性）
```

### 3.2 具体修改

#### 修改 1: orchestrator.py — 传递上一章原文到 pipeline

**文件**: `src/backend/core/orchestrator.py`（第 470-477 行）

**现状**:
```python
result = await pipeline.run(
    chapter_idx=chapter_idx,
    title=ch_title,
    summary=ch_summary,
    chapter_outline_ch=ch_outline,
    context=shared_context,
    existing_chapters_text=existing_text[-4000:],
)
```

**改为**: 新增 `previous_chapter_text` 参数，传递上一章完整结尾（最后 800 字），同时保留 `existing_chapters_text` 作为全文上下文。

```python
# 提取上一章结尾（用于衔接）
prev_ending = ""
if chapters:
    prev_content = chapters[-1].get("content", "")
    prev_ending = prev_content[-800:] if len(prev_content) > 800 else prev_content

result = await pipeline.run(
    chapter_idx=chapter_idx,
    title=ch_title,
    summary=ch_summary,
    chapter_outline_ch=ch_outline,
    context=shared_context,
    existing_chapters_text=existing_text[-4000:],
    previous_chapter_text=prev_ending,  # 新增
)
```

#### 修改 2: chapter_pipeline.py — `_agent_draft` 注入上一章原文

**文件**: `src/backend/core/chapter_pipeline.py`（第 477-596 行）

**现状**: `_agent_draft` 的 prompt 中不包含上一章原文，仅靠 `connection_instruction` 的摘要。

**改为**: 在 prompt 中新增 `【上一章结尾（请直接接续）】` 区块，注入上一章的最后 500 字原文。

在 `prompt_parts` 中，`connection_instruction` 之后插入：

```python
# ── 上一章原文结尾（直接衔接）──
prev_chapter_text = context.get("previous_chapter_text", "")
if prev_chapter_text and chapter_idx > 1:
    prompt_parts.append(f"""═══════════════════════════════════════════
          上一章结尾（请直接从此处接续）
═══════════════════════════════════════════

{prev_chapter_text[-500:]}

↑ 本章开头必须直接接续以上场景。""")
    prompt_parts.append("")
```

#### 修改 3: chapter_pipeline.py — `run()` 方法接收新参数

**文件**: `src/backend/core/chapter_pipeline.py`（第 846-864 行）

**现状**: `run()` 方法签名中无 `previous_chapter_text` 参数。

**改为**: 新增参数并传入 context。

```python
async def run(self, chapter_idx: int, title: str, summary: str,
              chapter_outline_ch: dict = None, context: Dict = None,
              existing_chapters_text: str = "",
              previous_chapter_text: str = "",  # 新增
              loop_metadata: Optional[Dict] = None) -> ChapterPipelineResult:
    context = context or {}
    context["previous_chapter_text"] = previous_chapter_text  # 注入 context
    ...
```

#### 修改 4: chapter_pipeline.py — 规划 Agent 接收上一章结尾

**文件**: `src/backend/core/chapter_pipeline.py`（第 126-231 行）

**现状**: `_agent_outline` 的 prompt 中只有 `recent_summaries[:600]`，没有上一章原文。

**改为**: 在 `_agent_outline` 的 prompt 中新增上一章结尾信息。

```python
# 在 user_prompt 中新增
prev_chapter_text = context.get("previous_chapter_text", "")
if prev_chapter_text and chapter_idx > 1:
    prev_ending_info = f"\n上一章结尾场景（本章开头必须接续）:\n{prev_chapter_text[-300:]}"

# 在 user_prompt 末尾（大纲规划要求中）插入
```

#### 修改 5: state_tracker.py — 增强角色状态快照

**文件**: `src/backend/core/state_tracker.py`（第 419-436 行）

**现状**: `build_state_card()` 返回角色状态，但缺少"上一章结束时角色在做什么"的信息。

**改为**: 新增方法 `get_character_snapshot()` 返回更详细的角色状态，包含位置、动作、情绪。

```python
def get_character_snapshot(self) -> str:
    """获取角色状态快照（用于注入下一章 prompt）"""
    parts = ["【角色状态快照 — 上一章结束时】"]
    for name, char in self._characters.items():
        parts.append(f"- {name}: 位置={char.location or '未知'}, "
                     f"状态={char.physical_state}, 情绪={char.emotional_state}")
        if char.goals:
            parts.append(f"  当前目标: {char.goals[0]}")
        if char.key_items:
            parts.append(f"  持有: {', '.join(char.key_items[:3])}")
    if self._last_chapter_ending:
        parts.append(f"\n上一章结尾场景: {self._last_chapter_ending[:200]}")
    return "\n".join(parts)
```

#### 修改 6: global_summary.py — 增强衔接指令，使用原文

**文件**: `src/backend/core/global_summary.py`（第 144-171 行）

**现状**: `get_connection_instruction()` 仅使用 `last_paragraph[:200]`（来自摘要），不够精确。

**改为**: 新增 `get_connection_instruction_with_text()` 方法，接收上一章原文作为参数。

```python
def get_connection_instruction_with_text(self, chapter_idx: int, 
                                          prev_chapter_text: str = "") -> str:
    """生成强制衔接指令，优先使用原文"""
    if chapter_idx <= 1:
        return ""
    
    # 优先使用原文结尾
    ending = prev_chapter_text[-500:] if prev_chapter_text else ""
    if not ending:
        # 回退到摘要
        if not self._summaries:
            return ""
        prev = self._summaries[-1]
        ending = prev.last_paragraph if prev and prev.last_paragraph else ""
    
    if not ending:
        return ""
    
    parts = ["【衔接指令 — 必须遵守】"]
    parts.append(f"1. 本章开头必须直接接续上一章结尾的场景/动作/对话。")
    parts.append(f"   上一章结尾是: \"{ending[:300]}\"")
    parts.append(f"2. 本章必须呼应前文2-3个关键细节（如角色状态、未完成动作、对话中的暗示）")
    parts.append(f"3. 本章结尾留下下一章的钩子，格式为: \"就在这时，______\"")
    return "\n".join(parts)
```

#### 修改 7: chapter_pipeline.py — `_agent_draft` 中注入角色状态快照

**文件**: `src/backend/core/chapter_pipeline.py`（第 477-596 行）

**现状**: draft prompt 中角色信息来自 `context.get("characters")[:400]`（静态设定）。

**改为**: 额外注入 `state_tracker.get_character_snapshot()` 动态角色状态。

```python
# 在 prompt_parts 中添加角色状态快照（在 state_card 之后）
character_snapshot = ""
if self.state_tracker:
    character_snapshot = self.state_tracker.get_character_snapshot()

if character_snapshot:
    prompt_parts.append(character_snapshot)
    prompt_parts.append("")
```

#### 修改 8: PROJECT_ARCHITECTURE.md — 更新文档

**文件**: `PROJECT_ARCHITECTURE.md`

更新以下内容：
- 章节生成流程图中增加"上一章衔接数据流"
- 新增"章节衔接机制"章节，描述优化后的衔接设计
- 更新 `state_tracker` 和 `global_summary` 的职责说明
- 更新 `chapter_pipeline` 的 prompt 结构说明

## 4. 修改文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `src/backend/core/orchestrator.py` | 修改 | 传递 `previous_chapter_text` 到 pipeline |
| `src/backend/core/chapter_pipeline.py` | 修改 | `run()` 接收新参数；`_agent_draft` 注入上一章原文；`_agent_outline` 注入上一章结尾 |
| `src/backend/core/state_tracker.py` | 新增方法 | `get_character_snapshot()` 角色状态快照 |
| `src/backend/core/global_summary.py` | 新增方法 | `get_connection_instruction_with_text()` 基于原文的衔接指令 |
| `PROJECT_ARCHITECTURE.md` | 更新 | 补充章节衔接机制说明 |

## 5. 验证方法

1. **单元验证**: 运行 `python test_project.py` 确保现有测试通过
2. **衔接验证**: 生成 3 章测试小说，检查：
   - 第 2 章开头是否直接接续第 1 章结尾场景
   - 角色状态（位置、情绪）在章间是否一致
   - 第 1 章结尾的钩子是否在第 2 章得到呼应
3. **日志验证**: 检查 `run.log` 中 prompt 是否包含上一章原文结尾
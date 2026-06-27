"""
创作流程端点 — /api/create (outline/draft/edit/review/world/character/style/plot/full)
"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .deps import (
    _call_agent_process, _safe_parse_json, _get_llm_client_from_db,
)
from .models import (
    OutlineRequest, DraftRequest, EditRequest, ReviewRequest,
    WorldRequest, CharacterRequest, StyleRequest, PlotRequest,
    AutoGenWorldRequest, AutoGenCharacterRequest,
)

router = APIRouter(prefix="/api/create", tags=["创作"])


@router.post("/outline")
async def create_outline(req: OutlineRequest):
    """生成小说大纲"""
    result = await _call_agent_process("outline_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/draft")
async def create_draft(req: DraftRequest):
    """生成章节草稿（建议先调用/create/outline）"""
    result = await _call_agent_process("draft_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/draft-stream", description="SSE 流式生成章节草稿，逐 token 推送")
async def create_draft_stream(req: DraftRequest):
    """SSE 流式生成章节草稿"""
    from ...agents.prompts import DRAFT_SYSTEM_PROMPT, build_draft_user_prompt
    from ...llm.client import LLMMessage, get_default_llm_client

    user_prompt = build_draft_user_prompt(
        req.chapter_title,
        req.chapter_outline,
        req.summaries or "",
        req.characters or "",
        req.world or "",
        req.foreshadowing or "",
        req.style_guide or "",
    )

    async def event_generator():
        client = get_default_llm_client()
        try:
            async for token_chunk in client.generate_stream(
                messages=[LLMMessage(role="user", content=user_prompt)],
                system_prompt=DRAFT_SYSTEM_PROMPT,
                temperature=0.8,
                max_tokens=4000,
            ):
                if token_chunk.get("type") == "token":
                    yield f"data: {json.dumps({'token': token_chunk['content']}, ensure_ascii=False)}\n\n"
                elif token_chunk.get("type") == "error":
                    yield f"data: {json.dumps({'error': token_chunk.get('error', 'unknown')}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )


@router.post("/edit")
async def create_edit(req: EditRequest):
    """编辑优化章节"""
    result = await _call_agent_process("edit_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/edit-stream", description="SSE 流式编辑章节，逐 token 推送")
async def create_edit_stream(req: EditRequest):
    """SSE 流式编辑章节"""
    from ...agents.prompts import EDIT_SYSTEM_PROMPT, build_edit_user_prompt
    from ...llm.client import LLMMessage, get_default_llm_client

    user_prompt = build_edit_user_prompt(req.content, req.instructions)

    async def event_generator():
        client = get_default_llm_client()
        try:
            async for token_chunk in client.generate_stream(
                messages=[LLMMessage(role="user", content=user_prompt)],
                system_prompt=EDIT_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=10000,
            ):
                if token_chunk.get("type") == "token":
                    yield f"data: {json.dumps({'token': token_chunk['content']}, ensure_ascii=False)}\n\n"
                elif token_chunk.get("type") == "error":
                    yield f"data: {json.dumps({'error': token_chunk.get('error', 'unknown')}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )


@router.post("/review")
async def create_review(req: ReviewRequest):
    """审查与评分章节"""
    result = await _call_agent_process("review_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/world", description="AI 生成世界观设定")
async def create_world(req: WorldRequest):
    """生成世界观设定"""
    result = await _call_agent_process("world_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/character", description="AI 生成角色设计")
async def create_character(req: CharacterRequest):
    """生成角色设计"""
    result = await _call_agent_process("character_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/style")
async def create_style(req: StyleRequest):
    """生成写作风格指南"""
    result = await _call_agent_process("style_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/plot")
async def analyze_plot(req: PlotRequest):
    """分析当前情节并给出推进建议"""
    result = await _call_agent_process("plot_agent", req.model_dump())
    return {"success": True, "data": result}


@router.post("/full")
async def create_full_pipeline(req: OutlineRequest):
    """一键示例：生成大纲 → 生成第一章草稿 → 返回结果
    注意：这是一个串行演示，生产环境建议改为异步任务队列
    """
    # 1. 大纲
    outline = await _call_agent_process("outline_agent", req.model_dump())
    chapters = outline.get("chapters", []) if isinstance(outline, dict) else []

    # 2. 取第一章生成草稿
    first_chapter = chapters[0] if chapters and isinstance(chapters, list) else None
    title = first_chapter.get("title", "第一章") if first_chapter else "第一章"
    summary = first_chapter.get("summary", "") if first_chapter else ""

    draft_ctx = DraftRequest(
        chapter_title=title,
        chapter_outline=summary,
        summaries="",
        characters="",
        world="",
    )
    draft = await _call_agent_process("draft_agent", draft_ctx.model_dump())

    return {
        "success": True,
        "step": "outline → draft 示例流程",
        "outline": outline,
        "first_chapter_draft": draft,
    }


@router.post("/world-auto", description="AI根据名称+类型自动生成世界观描述/规则/历史")
async def auto_gen_world(req: AutoGenWorldRequest):
    """AI自动生成世界观详情"""
    from fastapi import HTTPException
    from ...llm.client import LLMMessage

    config_id = req.config_id.strip() if req.config_id else None
    client = await _get_llm_client_from_db(config_id)

    prompt = f"""请为以下世界观自动生成详细设定。必须以JSON格式返回。

世界观名称：{req.name}
世界观类型：{req.category}

请生成以下内容（纯中文，不要有任何英文）：
1. description: 世界观描述（200-400字），包括地理、时代、核心特色
2. rules: 世界规则列表（5-8条），包括力量体系、社会结构、自然规律
3. history: 世界历史列表（3-5条），包括重大事件、转折点

JSON格式：
{{
  "description": "这个世界是...",
  "rules": ["规则1", "规则2", ...],
  "history": ["事件1", "事件2", ...]
}}"""

    try:
        result = await client.generate(
            [LLMMessage(role="user", content=prompt)],
            system_prompt=f"你是一个专业的小说世界观设计师，擅长{req.category}类世界观的设定。请严格输出JSON格式，全中文，确保JSON完整闭合。",
            temperature=0.7,
            max_tokens=1500,
        )
        content = result.content.strip()
        data, err = _safe_parse_json(content)
        if err:
            raise HTTPException(500, err)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"AI生成失败: {str(e)}")


@router.post("/character-auto", description="AI根据世界观自动生成角色属性")
async def auto_gen_character(req: AutoGenCharacterRequest):
    """AI根据世界观自动生成角色性格/背景/外貌/目标"""
    from fastapi import HTTPException
    from ...llm.client import LLMMessage

    config_id = req.config_id.strip() if req.config_id else None
    client = await _get_llm_client_from_db(config_id)

    world_ctx = ""
    if req.world_name:
        world_ctx = f"""
所属世界：{req.world_name}
世界类型：{req.world_category}
世界描述：{req.world_description[:300]}
世界规则：{chr(10).join('- ' + r for r in (req.world_rules or [])[:5])}
"""

    prompt = f"""请根据以下信息自动生成角色详细设定。必须以JSON格式返回。

角色名称：{req.name}
角色定位：{req.role}
{world_ctx}

请生成以下内容（纯中文，不要有任何英文），必须符合该世界的设定：
1. personality: 性格特征（30-80字），包括核心性格、行为习惯、内在矛盾
2. background: 人物背景（80-200字），包括出身、关键经历、与世界观相关的背景
3. appearance: 外貌描述（30-80字），包括标志性特征、着装习惯
4. goals: 目标列表（3-5个），从小到大排列
5. conflicts: 冲突列表（2-4个），内在冲突和外在冲突
6. speech_pattern: 说话方式（10-30字），包括语气、口头禅、语速特点
7. aliases: 别名列表（1-3个）

JSON格式：
{{
  "personality": "性格描述",
  "background": "背景故事",
  "appearance": "外貌描述",
  "goals": ["目标1", "目标2", ...],
  "conflicts": ["冲突1", "冲突2", ...],
  "speech_pattern": "说话方式",
  "aliases": ["别名1", "别名2"]
}}"""

    try:
        result = await client.generate(
            [LLMMessage(role="user", content=prompt)],
            system_prompt=f"你是一个专业的角色设计师，擅长根据世界观设定创作有深度、可信的角色。请严格输出JSON格式，全中文，确保JSON完整闭合。",
            temperature=0.75,
            max_tokens=1200,
        )
        content = result.content.strip()
        data, err = _safe_parse_json(content)
        if err:
            raise HTTPException(500, err)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"AI生成失败: {str(e)}")
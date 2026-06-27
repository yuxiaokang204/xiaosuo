"""
Prompt 管理器 - L3 工具层
实现 Prompt 版本管理、模板系统、渲染功能
"""
import json
import re
import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 数据模型 ──

@dataclass
class PromptVersion:
    """Prompt 版本"""
    id: str
    novel_id: Optional[str]
    agent_type: str
    depth_level: int
    prompt_type: str  # system | user
    title: str
    content: str
    quality_score: int  # 0-100
    usage_count: int
    is_active: bool
    meta_info: Dict[str, Any]
    created_at: float
    updated_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "agent_type": self.agent_type,
            "depth_level": self.depth_level,
            "prompt_type": self.prompt_type,
            "title": self.title,
            "content": self.content,
            "quality_score": self.quality_score,
            "usage_count": self.usage_count,
            "is_active": self.is_active,
            "meta_info": self.meta_info,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PromptVersion":
        return cls(
            id=data["id"],
            novel_id=data.get("novel_id"),
            agent_type=data["agent_type"],
            depth_level=data.get("depth_level", 0),
            prompt_type=data.get("prompt_type", "system"),
            title=data.get("title", ""),
            content=data["content"],
            quality_score=data.get("quality_score", 0),
            usage_count=data.get("usage_count", 0),
            is_active=bool(data.get("is_active", 0)),
            meta_info=data.get("meta_info", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


@dataclass
class PromptTemplate:
    """Prompt 模板"""
    template_id: str
    category: str
    name: str
    description: str
    template_str: str  # 含 {placeholder} 的模板字符串
    variables: List[str]  # 变量列表
    default_content: str  # 未替换变量的默认内容
    created_at: float
    updated_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "template_str": self.template_str,
            "variables": self.variables,
            "default_content": self.default_content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PromptTemplate":
        return cls(
            template_id=data["template_id"],
            category=data.get("category", "general"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            template_str=data.get("template_str", ""),
            variables=data.get("variables", []),
            default_content=data.get("default_content", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


# ── PromptManager ──

class PromptManager:
    """
    Prompt 版本管理和模板系统（L3 工具层）
    
    功能:
    - Prompt 版本管理（创建、更新、删除、列出）
    - 模板系统（变量替换、渲染）
    - 活跃版本管理
    - 持久化到 JSON 文件
    """

    # 内置模板
    DEFAULT_TEMPLATES = [
        {
            "template_id": "outline_system",
            "category": "outline",
            "name": "故事架构师系统提示",
            "description": "用于生成章节大纲的系统提示模板",
            "template_str": """你是一个专业的小说故事架构师。
你的任务是为本小说创建详细、吸引人的章节大纲。

小说类型: {genre}
目标平台: {platform}
章节数量: {chapter_count}
当前章节: {current_chapter}

请根据以下要求创建第 {current_chapter} 章的大纲：
{outline_requirements}

大纲应包含:
1. 章节主题
2. 关键情节
3. 角色互动
4. 冲突和高潮
5. 悬念设置""",
            "variables": ["genre", "platform", "chapter_count", "current_chapter", "outline_requirements"],
            "default_content": "",
            "created_at": time.time(),
            "updated_at": time.time(),
        },
        {
            "template_id": "draft_user",
            "category": "draft",
            "name": "专业写手用户提示",
            "description": "用于生成章节内容的用户提示模板",
            "template_str": """请根据以下大纲创作第 {chapter_number} 章的完整内容。

章节标题: {chapter_title}
章节大纲:
{chapter_outline}

角色设定:
{character_settings}

世界观设定:
{world_settings}

前情提要:
{previous_chapter_summary}

风格约束:
{style_constraints}

创作要求:
1. 字数: {target_word_count} 字以上
2. 保持角色性格一致
3. 描写要生动具体
4. 对话要自然流畅
5. 适当使用感官描写""",
            "variables": [
                "chapter_number", "chapter_title", "chapter_outline",
                "character_settings", "world_settings", "previous_chapter_summary",
                "style_constraints", "target_word_count",
            ],
            "default_content": "",
            "created_at": time.time(),
            "updated_at": time.time(),
        },
    ]

    def __init__(self, persist_dir: str = "./prompt_data"):
        """
        初始化 Prompt 管理器
        
        Args:
            persist_dir: 数据持久化目录
        """
        import os
        from pathlib import Path
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # 内存存储
        self.prompts: Dict[str, PromptVersion] = {}
        self.templates: Dict[str, PromptTemplate] = {}
        self._active_prompts: Dict[str, PromptVersion] = {}  # {key: PromptVersion}

        # 初始化内置模板
        self._init_default_templates()

        # 加载持久化数据
        self._load_from_disk()

        logger.info(
            "[PromptManager] 初始化完成: %d 个 prompt, %d 个模板",
            len(self.prompts), len(self.templates),
        )

    # ── Prompt 管理接口 ──

    async def get_prompt(
        self,
        prompt_id: str,
        version: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        获取 Prompt（指定 ID 和版本）
        
        Args:
            prompt_id: Prompt ID
            version: 版本号（None=获取最新版本）
        """
        prompt = self.prompts.get(prompt_id)
        if not prompt:
            return None

        return prompt.to_dict()

    async def get_active_prompt(
        self,
        agent_type: str,
        depth_level: int = 1,
        novel_id: Optional[str] = None,
    ) -> Optional[PromptVersion]:
        """
        获取活跃 Prompt
        
        Args:
            agent_type: Agent 类型
            depth_level: 深度级别
            novel_id: 小说 ID
        """
        key = f"{agent_type}_{depth_level}_{novel_id or 'default'}"
        return self._active_prompts.get(key)

    async def list_prompts(
        self,
        category: Optional[str] = None,
        agent_type: Optional[str] = None,
        novel_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列出所有 Prompt
        
        Args:
            category: 分类过滤
            agent_type: Agent 类型过滤
            novel_id: 小说 ID 过滤
        """
        results = []
        for prompt in self.prompts.values():
            if category and prompt.meta_info.get("category") != category:
                continue
            if agent_type and prompt.agent_type != agent_type:
                continue
            if novel_id and prompt.novel_id != novel_id:
                continue
            results.append(prompt.to_dict())

        # 按更新时间排序
        results.sort(key=lambda x: -x["updated_at"])
        return results

    async def create_prompt(
        self,
        prompt_data: Dict[str, Any],
    ) -> str:
        """
        创建新 Prompt
        
        Args:
            prompt_data: Prompt 数据
            
        Returns:
            新 Prompt 的 ID
        """
        import uuid

        prompt_id = str(uuid.uuid4())[:8]
        now = time.time()

        prompt = PromptVersion(
            id=prompt_id,
            novel_id=prompt_data.get("novel_id"),
            agent_type=prompt_data.get("agent_type", "general"),
            depth_level=prompt_data.get("depth_level", 0),
            prompt_type=prompt_data.get("prompt_type", "system"),
            title=prompt_data.get("title", "未命名 Prompt"),
            content=prompt_data.get("content", ""),
            quality_score=prompt_data.get("quality_score", 0),
            usage_count=0,
            is_active=bool(prompt_data.get("is_active", 0)),
            meta_info=prompt_data.get("meta_info", {}),
            created_at=now,
            updated_at=now,
        )

        self.prompts[prompt_id] = prompt

        # 如果是活跃版本，更新活跃映射
        if prompt.is_active:
            key = f"{prompt.agent_type}_{prompt.depth_level}_{prompt.novel_id or 'default'}"
            self._active_prompts[key] = prompt

        # 持久化
        self._save_to_disk(prompt_id)

        logger.info(
            "[PromptManager] 创建 Prompt: %s (%s, depth=%d)",
            prompt_id, prompt.agent_type, prompt.depth_level,
        )

        return prompt_id

    async def update_prompt(
        self,
        prompt_id: str,
        prompt_data: Dict[str, Any],
    ) -> Optional[str]:
        """
        更新 Prompt（版本号+1）
        
        Args:
            prompt_id: Prompt ID
            prompt_data: 更新数据
            
        Returns:
            新版本 Prompt 的 ID（创建新版本）或原 ID（原地更新）
        """
        prompt = self.prompts.get(prompt_id)
        if not prompt:
            return None

        # 更新字段
        update_fields = [
            "title", "content", "quality_score", "meta_info",
        ]
        for field in update_fields:
            if field in prompt_data:
                setattr(prompt, field, prompt_data[field])

        prompt.updated_at = time.time()

        # 如果更新了 is_active，更新活跃映射
        if "is_active" in prompt_data:
            key = f"{prompt.agent_type}_{prompt.depth_level}_{prompt.novel_id or 'default'}"
            if prompt_data["is_active"]:
                self._active_prompts[key] = prompt
            else:
                self._active_prompts.pop(key, None)

        # 持久化
        self._save_to_disk(prompt_id)

        logger.info(
            "[PromptManager] 更新 Prompt: %s",
            prompt_id,
        )

        return prompt_id

    async def delete_prompt(self, prompt_id: str) -> bool:
        """
        删除 Prompt
        
        Args:
            prompt_id: Prompt ID
        """
        prompt = self.prompts.get(prompt_id)
        if not prompt:
            return False

        # 从活跃映射中移除
        key = f"{prompt.agent_type}_{prompt.depth_level}_{prompt.novel_id or 'default'}"
        self._active_prompts.pop(key, None)

        # 删除文件
        file_path = self.persist_dir / f"{prompt_id}.json"
        if file_path.exists():
            file_path.unlink()

        # 从内存中移除
        del self.prompts[prompt_id]

        logger.info("[PromptManager] 删除 Prompt: %s", prompt_id)
        return True

    # ── 模板管理接口 ──

    async def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """获取模板"""
        return self.templates.get(template_id)

    async def list_templates(self, category: Optional[str] = None) -> List[PromptTemplate]:
        """列出所有模板"""
        if category:
            return [t for t in self.templates.values() if t.category == category]
        return list(self.templates.values())

    async def create_template(
        self,
        template_data: Dict[str, Any],
    ) -> str:
        """
        创建新模板
        
        Args:
            template_data: 模板数据
            
        Returns:
            模板 ID
        """
        import uuid

        template_id = template_data.get("template_id") or str(uuid.uuid4())[:8]
        now = time.time()

        template = PromptTemplate(
            template_id=template_id,
            category=template_data.get("category", "general"),
            name=template_data.get("name", "未命名模板"),
            description=template_data.get("description", ""),
            template_str=template_data.get("template_str", ""),
            variables=template_data.get("variables", []),
            default_content=template_data.get("default_content", ""),
            created_at=now,
            updated_at=now,
        )

        self.templates[template_id] = template
        self._save_template_to_disk(template_id)

        logger.info("[PromptManager] 创建模板: %s", template_id)
        return template_id

    # ── 模板渲染 ──

    async def render_template(
        self,
        template_id: str,
        variables: Dict[str, Any],
    ) -> Optional[str]:
        """
        渲染 Prompt 模板
        
        Args:
            template_id: 模板 ID
            variables: 变量映射
            
        Returns:
            渲染后的字符串
        """
        template = self.templates.get(template_id)
        if not template:
            logger.warning("[PromptManager] 模板不存在: %s", template_id)
            return None

        try:
            # 变量替换
            result = template.template_str
            for var_name, var_value in variables.items():
                placeholder = "{" + var_name + "}"
                result = result.replace(placeholder, str(var_value))

            # 替换未提供的变量为默认值
            for var_name in template.variables:
                if "{" + var_name + "}" in result:
                    # 查找默认值
                    default_value = variables.get(var_name, "[未提供]")
                    placeholder = "{" + var_name + "}"
                    result = result.replace(placeholder, str(default_value))

            logger.debug(
                "[PromptManager] 渲染模板: %s, 变量数=%d",
                template_id, len(variables),
            )

            return result

        except Exception as e:
            logger.error("[PromptManager] 渲染模板失败: %s", e)
            return None

    async def render_prompt(
        self,
        prompt_content: str,
        variables: Dict[str, Any],
    ) -> str:
        """
        直接渲染 Prompt 内容（不含模板 ID）
        
        Args:
            prompt_content: Prompt 模板字符串
            variables: 变量映射
            
        Returns:
            渲染后的字符串
        """
        try:
            result = prompt_content
            for var_name, var_value in variables.items():
                placeholder = "{" + var_name + "}"
                result = result.replace(placeholder, str(var_value))
            return result
        except Exception as e:
            logger.error("[PromptManager] 渲染 Prompt 失败: %s", e)
            return prompt_content

    # ── 内部方法 ──

    def _init_default_templates(self) -> None:
        """初始化内置模板"""
        for template_data in self.DEFAULT_TEMPLATES:
            template = PromptTemplate.from_dict(template_data)
            self.templates[template.template_id] = template

        logger.info("[PromptManager] 加载 %d 个内置模板", len(self.DEFAULT_TEMPLATES))

    def _load_from_disk(self) -> None:
        """从磁盘加载 Prompt"""
        for file_path in self.persist_dir.glob("prompt_*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    prompt = PromptVersion.from_dict(data)
                    self.prompts[prompt.id] = prompt

                    # 更新活跃映射
                    if prompt.is_active:
                        key = f"{prompt.agent_type}_{prompt.depth_level}_{prompt.novel_id or 'default'}"
                        self._active_prompts[key] = prompt

                logger.debug("[PromptManager] 加载 Prompt: %s", prompt.id)
            except Exception as e:
                logger.warning("[PromptManager] 加载 Prompt 失败 %s: %s", file_path, e)

    def _save_to_disk(self, prompt_id: str) -> None:
        """保存 Prompt 到磁盘"""
        prompt = self.prompts.get(prompt_id)
        if not prompt:
            return

        file_path = self.persist_dir / f"prompt_{prompt_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(prompt.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("[PromptManager] 保存 Prompt 失败 %s: %s", prompt_id, e)

    def _save_template_to_disk(self, template_id: str) -> None:
        """保存模板到磁盘"""
        template = self.templates.get(template_id)
        if not template:
            return

        file_path = self.persist_dir / f"template_{template_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(template.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("[PromptManager] 保存模板失败 %s: %s", template_id, e)

    # ── 统计接口 ──

    async def get_statistics(self) -> Dict[str, Any]:
        """获取 Prompt 统计"""
        total_prompts = len(self.prompts)
        active_prompts = sum(1 for p in self.prompts.values() if p.is_active)
        total_templates = len(self.templates)

        # 按类型统计
        by_type = {}
        for prompt in self.prompts.values():
            agent_type = prompt.agent_type
            if agent_type not in by_type:
                by_type[agent_type] = {
                    "total": 0,
                    "active": 0,
                    "total_usage": 0,
                }
            by_type[agent_type]["total"] += 1
            if prompt.is_active:
                by_type[agent_type]["active"] += 1
            by_type[agent_type]["total_usage"] += prompt.usage_count

        return {
            "total_prompts": total_prompts,
            "active_prompts": active_prompts,
            "total_templates": total_templates,
            "by_agent_type": by_type,
        }

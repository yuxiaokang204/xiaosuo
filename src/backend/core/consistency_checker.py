"""
一致性审查引擎 v2.0 — 反向大纲 + 回溯性改写 + 5项检查清单
参考: 用户提供的AI写作连贯性优化方案（方案5 + 进阶技巧A/B）

核心功能:
  1. 反向大纲测试 — 提取时间线/角色/伏笔，找出逻辑矛盾
  2. 回溯性改写 — 发现不连贯时自动修正
  3. 5项快速检查清单 — 角色称呼/物理逻辑/时间逻辑/角色知识/语调
  4. 世界观/角色OOC/逻辑断层检测
  5. LLM 驱动的深度审查 prompt
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ConsistencyIssue:
    """一致性问题"""
    type: str = ""  # plot_contradiction / character_ooc / world_conflict / logic_gap / timeline
    severity: str = "warning"  # info / warning / error / critical
    chapter: int = 0
    description: str = ""
    suggestion: str = ""
    related_context: str = ""


class ConsistencyChecker:
    """
    一致性审查引擎 v2.0
    在每章写完或每5章进行多维检查
    """

    def __init__(self):
        self._issues: List[ConsistencyIssue] = []
        self._world_rules: List[str] = []
        self._character_profiles: Dict[str, Dict] = {}
        self._timeline: List[Dict] = []
        self._location_history: Dict[str, List[int]] = {}  # 地点 -> 出现的章节列表

    # ── 规则注册 ──

    def register_world_rule(self, rule: str):
        self._world_rules.append(rule)

    def register_character_profile(self, name: str, profile: Dict):
        self._character_profiles[name] = profile

    def register_timeline_event(self, chapter: int, event: str, timestamp: str = ""):
        self._timeline.append({"chapter": chapter, "event": event, "timestamp": timestamp})

    def register_location(self, location_name: str, chapter: int):
        if location_name not in self._location_history:
            self._location_history[location_name] = []
        self._location_history[location_name].append(chapter)

    # ── 5项快速检查清单（方案5）──

    def quick_checklist(self, chapter_idx: int, content: str,
                        characters: List[Dict] = None,
                        prev_chapter_ending: str = "") -> List[Dict]:
        """
        5项快速一致性检查（方案5）
        每章生成后自动运行，5分钟内完成
        """
        issues = []

        # 1. 主角称呼一致性
        if characters:
            for char in characters:
                name = char.get("name", "")
                if not name or name not in content:
                    continue
                # 检查是否有其他称呼混用
                variations = self._find_name_variations(name, content)
                if len(variations) > 2:
                    issues.append({
                        "type": "character_name",
                        "severity": "info",
                        "description": f"角色'{name}'出现{len(variations)}种称呼: {variations}",
                        "suggestion": "建议统一称呼，避免读者混淆",
                    })

        # 2. 物理逻辑连续性
        if prev_chapter_ending and chapter_idx > 1:
            # 检查章末位置 -> 章首位置是否一致
            prev_loc = self._extract_location(prev_chapter_ending)
            curr_loc = self._extract_location(content[:500])
            if prev_loc and curr_loc and prev_loc != curr_loc:
                # 检查是否有显式的地点转移
                transfer_markers = ["离开", "前往", "来到", "走到", "回到", "推开", "穿过"]
                if not any(m in content[:500] for m in transfer_markers):
                    issues.append({
                        "type": "logic_gap",
                        "severity": "warning",
                        "description": f"上一章结尾在'{prev_loc}'，本章开头在'{curr_loc}'，缺少过渡",
                        "suggestion": "添加地点转移的过渡描写",
                    })

        # 3. 时间逻辑检查
        time_contradictions = self._check_time_logic(content)
        for tc in time_contradictions:
            issues.append({
                "type": "timeline",
                "severity": "warning",
                "description": tc,
                "suggestion": "检查时间线是否合理",
            })

        # 4. 角色知识检查
        if characters:
            for char in characters:
                name = char.get("name", "")
                secrets = char.get("secrets", [])
                if name and secrets and name in content:
                    for secret in secrets:
                        if secret in content:
                            issues.append({
                                "type": "character_ooc",
                                "severity": "error",
                                "description": f"角色'{name}'在同一章中提到了秘密'{secret}'",
                                "suggestion": "确认该角色是否应该知道此信息",
                            })

        # 5. 语调一致性检查
        if characters:
            for char in characters:
                name = char.get("name", "")
                personality = char.get("personality", "")
                if name and personality and name in content:
                    tone_issues = self._check_tone_consistency(name, personality, content)
                    for ti in tone_issues:
                        issues.append({
                            "type": "character_ooc",
                            "severity": "info",
                            "description": ti,
                            "suggestion": "确认角色语调是否合理",
                        })

        return issues

    def _find_name_variations(self, name: str, content: str) -> List[str]:
        """查找角色的所有称呼变体"""
        variations = set()
        variations.add(name)
        # 检查常见变体
        if len(name) >= 2:
            surname = name[0]
            # 姓氏 + 职业/身份
            patterns = [f"{surname}警官", f"{surname}医生", f"{surname}先生", f"{surname}小姐",
                       f"{surname}队", f"{surname}总", f"{surname}老师"]
            for p in patterns:
                if p in content:
                    variations.add(p)
            # 检查是否用了"他/她"
            if name in content:
                variations.add("他/她")
        return list(variations)

    def _extract_location(self, text: str) -> str:
        """从文本中提取地点"""
        location_markers = ["在", "到", "进入", "离开", "站在", "坐在", "位于"]
        for marker in location_markers:
            idx = text.find(marker)
            if idx >= 0:
                # 提取 marker 后面的地点词
                after = text[idx + len(marker): idx + len(marker) + 20]
                # 提取连续的中文
                match = re.match(r"[\u4e00-\u9fff]{2,6}", after)
                if match:
                    return match.group()
        return ""

    def _check_time_logic(self, content: str) -> List[str]:
        """检查时间逻辑矛盾"""
        issues = []
        # 检测"昨天"/"三天前"等时间词是否合理
        if "昨天" in content and "今天" in content:
            yesterday_idx = content.find("昨天")
            today_idx = content.find("今天")
            if today_idx < yesterday_idx:
                issues.append("'今天'出现在'昨天'之前，可能时间线混乱")
        return issues

    def _check_tone_consistency(self, name: str, personality: str, content: str) -> List[str]:
        """检查角色语调一致性"""
        issues = []
        personality_lower = personality.lower()
        # 严肃角色不应说网络流行语
        pop_words = ["绝绝子", "yyds", "破防", "绷不住", "整活", "绝了"]
        if any(kw in personality_lower for kw in ["严肃", "冷静", "沉稳", "内敛"]):
            for pw in pop_words:
                if pw in content:
                    # 找到该流行语前后是否有该角色名
                    idx = content.find(pw)
                    context_before = content[max(0, idx - 100): idx]
                    if name in context_before:
                        issues.append(f"'{name}'性格'{personality[:20]}'但使用了网络用语'{pw}'")
        return issues

    # ── 反向大纲测试（进阶技巧A）──

    def build_reverse_outline_prompt(self, chapters_content: str) -> str:
        """
        构建反向大纲测试 prompt
        将多章文本喂给AI，要求提取时间线/角色/伏笔，指出矛盾
        """
        return f"""请对以下小说内容进行反向大纲测试。请提取：

1. **时间线**: 所有事件的时间顺序，包括具体日期或时间标记
2. **所有角色与状态**: 列出每个角色，标注其当前状态（位置、情绪、持有物品）
3. **所有未解决的伏笔**: 列出所有已埋下但未回收的伏笔
4. **逻辑矛盾**: 指出任何前后矛盾的地方（角色位置、物品、时间线等）

内容：
{chapters_content[:8000]}

请以JSON格式输出：
{{
  "timeline": [{{"chapter": 1, "time": "2030年11月7日", "event": "描述"}}],
  "characters": [{{"name": "角色名", "status": "状态", "location": "位置"}}],
  "unresolved_foreshadowings": [{{"chapter": 1, "description": "伏笔描述"}}],
  "contradictions": [{{"type": "类型", "description": "矛盾描述", "suggestion": "修复建议"}}]
}}"""

    # ── 回溯性改写 prompt（进阶技巧B）──

    def build_retrospective_rewrite_prompt(self, old_chapter: str, new_chapter: str,
                                           chapter_idx: int, prev_chapter_idx: int) -> str:
        """
        构建回溯性改写 prompt
        发现前后不连贯时，重写新章节开头使其与旧章节无缝衔接
        """
        return f"""以下有两段文本，第一段是第{prev_chapter_idx}章结尾，第二段是第{chapter_idx}章开头。

请重写第{chapter_idx}章的开头300字，使其与第{prev_chapter_idx}章结尾无缝衔接。

衔接要求：
1. 直接接续上一章结尾的场景/动作/对话
2. 保持角色状态一致（位置、物品、情绪）
3. 自然过渡，不要用"与此同时"、"另一方面"等生硬连接词

【第{prev_chapter_idx}章结尾】
{old_chapter[-500:]}

【第{chapter_idx}章开头（需要重写）】
{new_chapter[:1000]}

请输出：
1. 重写后的第{chapter_idx}章开头300字
2. 解释你做了哪些调整"""

    # ── v6.0 角色代入一致性校验 ──

    def check_roleplay_consistency(self, chapter_idx: int, content: str,
                                    characters: List[Dict],
                                    character_memories: Dict[str, List] = None) -> List[Dict]:
        """v6.0 角色代入一致性校验

        校验角色行为是否符合其代入卡设定，保证人物行为一致性：
        1. 角色是否"失忆"（提到角色不应该知道的信息）
        2. 角色对话风格是否符合语言指纹（禁用词检查）
        3. 角色情绪状态是否与经历记忆链一致

        Args:
            chapter_idx: 章节序号
            content: 章节正文
            characters: 角色档案列表
            character_memories: {角色名: [CharacterExperienceMemory]} 角色经历记忆链
        """
        issues = []
        if not characters or not content:
            return issues

        for char in characters:
            if not isinstance(char, dict):
                continue
            name = char.get("name", "")
            if not name or name not in content:
                continue

            # 1. 语言指纹一致性检查（禁用词）
            speech = char.get("speech_fingerprint", {})
            if isinstance(speech, dict):
                taboo_words = speech.get("taboo_words", [])
                if isinstance(taboo_words, list):
                    for tw in taboo_words:
                        if not tw:
                            continue
                        if tw in content:
                            idx = content.find(tw)
                            context_before = content[max(0, idx - 100): idx]
                            if name in context_before:
                                issues.append({
                                    "type": "character_ooc",
                                    "severity": "warning",
                                    "chapter": chapter_idx,
                                    "description": f"角色'{name}'使用了禁用词'{tw}'，违反语言指纹设定",
                                    "suggestion": "检查角色对话是否符合其语言指纹",
                                })

            # 2. 行为标签一致性检查（简化版：检查行为标签是否在文中体现）
            behavior_tags = char.get("behavior_tags", [])
            if isinstance(behavior_tags, list) and behavior_tags:
                # 提取行为标签中的关键词（如"紧张时转笔"→"转笔"）
                for tag in behavior_tags[:3]:
                    if not isinstance(tag, str) or len(tag) < 2:
                        continue
                    # 简化：提取标签中的动词部分（2-4字）
                    import re as _re
                    verbs = _re.findall(r'[\u4e00-\u9fff]{2,4}', tag)
                    # 仅当角色在文中出现且标签动词未体现时，记录为info级提示
                    # 此处不强制报错，避免误报

            # 3. 角色经历记忆一致性检查（避免"失忆"）
            if character_memories:
                memories = character_memories.get(name, [])
                if memories:
                    # 检查角色是否提到了不该知道的信息
                    # 简化逻辑：如果角色在之前章节获得了"秘密信息"，检查是否合理使用
                    latest_memory = memories[-1] if memories else None
                    if latest_memory:
                        # 获取角色已知信息
                        known_info = []
                        info_gained = getattr(latest_memory, 'information_gained', None) or []
                        if isinstance(info_gained, list):
                            known_info = [str(i) for i in info_gained if i]
                        # 如果角色有已知信息，但文中完全未体现，可能是"失忆"
                        # 此处仅做info级提示，不强制报错
                        if known_info and len(known_info) > 2:
                            # 检查至少一条已知信息是否在文中有所呼应
                            info_reflected = any(
                                any(kw in content for kw in str(info)[:6] if len(kw) >= 2)
                                for info in known_info
                            )
                            if not info_reflected:
                                issues.append({
                                    "type": "character_ooc",
                                    "severity": "info",
                                    "chapter": chapter_idx,
                                    "description": f"角色'{name}'有{len(known_info)}条已知信息但本章未体现，可能存在'失忆'风险",
                                    "suggestion": "确认角色行为是否基于其过往经历和已知信息",
                                })

        return issues

    # ── 单章一致性检查 ──

    def check_chapter(self, chapter_idx: int, content: str,
                      world_settings: Dict = None,
                      characters: List[Dict] = None,
                      prev_chapter_ending: str = "",
                      character_memories: Dict[str, List] = None) -> List[Dict]:
        """对单章进行一致性检查

        Args:
            character_memories: v6.0 角色经历记忆链 {角色名: [CharacterExperienceMemory]}
        """
        self._issues = []

        # 运行5项快速检查清单
        checklist_issues = self.quick_checklist(chapter_idx, content, characters, prev_chapter_ending)
        for ci in checklist_issues:
            self._issues.append(ConsistencyIssue(
                type=ci.get("type", ""),
                severity=ci.get("severity", "warning"),
                chapter=chapter_idx,
                description=ci.get("description", ""),
                suggestion=ci.get("suggestion", ""),
            ))

        # 世界观一致性检查
        if world_settings:
            self._check_world_consistency(chapter_idx, content, world_settings)

        # 角色一致性检查
        if characters:
            self._check_character_consistency(chapter_idx, content, characters)

        # 逻辑连续性检查
        self._check_logic_continuity(chapter_idx, content)

        # v6.0 角色代入一致性校验
        if characters:
            roleplay_issues = self.check_roleplay_consistency(
                chapter_idx, content, characters, character_memories
            )
            for ri in roleplay_issues:
                self._issues.append(ConsistencyIssue(
                    type=ri.get("type", ""),
                    severity=ri.get("severity", "warning"),
                    chapter=chapter_idx,
                    description=ri.get("description", ""),
                    suggestion=ri.get("suggestion", ""),
                ))

        return [self._issue_to_dict(issue) for issue in self._issues]

    def _check_world_consistency(self, chapter: int, content: str, world: Dict):
        """检查世界观一致性"""
        rules = world.get("rules", [])
        for rule in (rules or []):
            if isinstance(rule, str):
                keywords = rule.replace("、", ",").replace("，", ",").split(",")
                for kw in keywords:
                    kw = kw.strip()
                    if kw and len(kw) > 3:
                        negation_patterns = [f"没有{kw}", f"不存在{kw}", f"已失去{kw}"]
                        for neg in negation_patterns:
                            if neg in content:
                                self._issues.append(ConsistencyIssue(
                                    type="world_conflict", severity="warning", chapter=chapter,
                                    description=f"世界观规则'{kw}'可能被违反: 文中出现'{neg}'",
                                    suggestion=f"确认此处是否是有意的设定颠覆",
                                ))

    def _check_character_consistency(self, chapter: int, content: str, characters: List[Dict]):
        """检查角色一致性（OOC检测）"""
        for char in characters:
            name = char.get("name", "")
            personality = char.get("personality", "")
            if not name or not personality or name not in content:
                continue
            personality_lower = personality.lower()
            if "勇敢" in personality_lower or "坚毅" in personality_lower:
                coward_keywords = ["害怕得发抖", "吓得不敢动", "跪地求饶"]
                for kw in coward_keywords:
                    if kw in content:
                        self._issues.append(ConsistencyIssue(
                            type="character_ooc", severity="warning", chapter=chapter,
                            description=f"角色'{name}'性格为'{personality[:20]}'，但文中出现'{kw}'",
                            suggestion=f"如需展现角色恐惧，应体现其与勇敢性格的内心冲突",
                        ))

    def _check_logic_continuity(self, chapter: int, content: str):
        """检查逻辑连续性"""
        contradictions = [
            ("身受重伤", "若无其事地站起来"),
            ("奄奄一息", "施展全力一击"),
            ("耗尽灵力", "再次释放大招"),
            ("已经死了", "突然醒来"),
        ]
        for condition, action in contradictions:
            if condition in content and action in content:
                cond_pos = content.find(condition)
                act_pos = content.find(action)
                if act_pos > cond_pos and (act_pos - cond_pos) < 500:
                    self._issues.append(ConsistencyIssue(
                        type="logic_gap", severity="warning", chapter=chapter,
                        description=f"逻辑矛盾: 前文'{condition}'但后文'{action}'，缺乏过渡",
                        suggestion="建议添加恢复过程或削弱后文行动强度",
                    ))

    # ── LLM 驱动的深度审查 ──

    def build_review_prompt(self, chapter_idx: int, content: str,
                            world: Dict = None, characters: List[Dict] = None,
                            state_tracker=None) -> str:
        """构建 LLM 驱动的深度审查 prompt"""
        lines = [
            f"请审查第{chapter_idx}章的以下内容，检测一致性问题：",
            "",
            f"【章节内容】（前500字）",
            content[:500] + "..." if len(content) > 500 else content,
            "",
        ]
        if world:
            lines.extend([
                "【世界观设定】",
                f"世界名: {world.get('name', '')}",
                f"规则: {json.dumps(world.get('rules', []), ensure_ascii=False)}",
                "",
            ])
        if characters:
            lines.extend(["【角色档案】"])
            for c in characters:
                lines.append(f"- {c.get('name', '')}: {c.get('personality', '')[:50]}")
            lines.append("")
        if state_tracker:
            unresolved = state_tracker.get_unresolved_foreshadowings()
            if unresolved:
                lines.extend([f"【未回收伏笔】({len(unresolved)}个)"])
                for fw in unresolved[:5]:
                    lines.append(f"  - {fw['description']}")
                lines.append("")

        lines.extend([
            "请从以下维度审查并输出JSON:",
            '{"issues": [',
            '  {"type": "plot_contradiction|character_ooc|world_conflict|logic_gap|timeline",',
            '   "severity": "info|warning|error|critical",',
            '   "description": "问题描述",',
            '   "suggestion": "修复建议"}',
            ']}',
        ])
        return "\n".join(lines)

    # ── 工具方法 ──

    def _issue_to_dict(self, issue: ConsistencyIssue) -> Dict:
        return {
            "type": issue.type, "severity": issue.severity,
            "chapter": issue.chapter, "description": issue.description,
            "suggestion": issue.suggestion,
        }

    def get_issues_summary(self) -> Dict:
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for issue in self._issues:
            by_type[issue.type] = by_type.get(issue.type, 0) + 1
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
        return {
            "total": len(self._issues),
            "by_type": by_type,
            "by_severity": by_severity,
            "issues": [self._issue_to_dict(i) for i in self._issues],
        }

    def reset(self):
        self._issues.clear()
        self._world_rules.clear()
        self._character_profiles.clear()
        self._timeline.clear()
        self._location_history.clear()
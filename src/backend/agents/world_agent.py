"""
世界观构建Agent v2.0 — 映射到世界观构建师Skill

v2.0 改进：
- 继承新的 BaseAgent，使用 LLMGateway + Memory + EventBus
- 统一 execute() 接口
- 通过 EventBus 发布执行事件
- 保留所有原有功能和 mock fallback
"""
import re
from typing import Any, Dict

from .base import BaseAgent
from .prompts import WORLD_SYSTEM_PROMPT, build_world_user_prompt


class WorldAgent(BaseAgent):
    """世界观Agent - 设计世界规则、地理、历史、魔法体系"""

    AGENT_ID = "world"
    AGENT_NAME = "世界观构建师"
    CAPABILITIES = ["world_building", "setting"]
    EXPECTS_JSON = True
    DEFAULT_TEMPERATURE = 0.7

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成世界观设定

        Args:
            context: 包含 theme, existing_world, title, platform, depth_level 等字段

        Returns:
            包含 success, name, category, description, rules, locations, factions 的结果
        """
        # 发布执行开始事件
        execution_id = await self._publish_execute_start(context)

        try:
            # 提取上下文参数
            theme = str(context.get("theme", ""))
            existing = str(context.get("existing_world", ""))
            title = str(context.get("title", ""))
            genre = str(context.get("genre", ""))
            tone = str(context.get("tone", ""))
            platform = str(context.get("platform", "番茄"))
            depth_level = int(context.get("depth_level", 1))
            title_analysis = context.get("title_analysis") or {}

            # 构建用户提示词（综合 title + genre + tone）
            user_prompt = build_world_user_prompt(
                theme, existing, depth_level,
                title=title, genre=genre, tone=tone,
                title_analysis=title_analysis if title_analysis else None,
            )

            # 调用LLM
            result = await self._call_llm(
                WORLD_SYSTEM_PROMPT,
                user_prompt,
                expects_json=True,
                max_tokens=8000,
            )

            # 规范输出结构
            data = result.get("data") or {}

            # 写入长期记忆：世界观设定
            if data:
                self.memory.store_world_settings([
                    {
                        "id": f"world_{data.get('name', 'unknown')}",
                        "name": data.get("name", ""),
                        "description": data.get("description", ""),
                        "rules": data.get("rules", []),
                    }
                ])

            # 发布执行完成事件
            await self._publish_execute_done(execution_id, result)

            return {
                "success": True,
                "fallback": result.get("fallback", False),
                "name": data.get("name", ""),
                "category": data.get("category", "other"),
                "description": data.get("description", ""),
                "rules": data.get("rules", []),
                "locations": data.get("key_locations", []),
                "factions": data.get("factions", []),
                "history": data.get("history", []),
                "unique_appeal": data.get("unique_appeal", ""),
                "provider": result.get("provider"),
                "latency_ms": result.get("latency_ms"),
            }

        except Exception as e:
            import traceback
            print(f"[Agent {self.AGENT_ID}] ❌ 执行异常: {e}\n{traceback.format_exc()}")
            await self._publish_execute_done(execution_id, {
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "error": str(e),
                "name": "",
                "category": "other",
                "description": "",
                "rules": [],
                "locations": [],
                "factions": [],
            }

    def _mock_fallback(self, user_prompt: str) -> Dict:
        """生成切题的 mock 世界观数据"""
        prompt_lower = user_prompt.lower()
        if "修真" in prompt_lower or "修仙" in prompt_lower or "仙侠" in prompt_lower:
            return {
                "name": "修真界",
                "category": "fantasy_cultivation",
                "description": "一个灵气充沛的修真世界，宗门林立，修士以修炼境界划分实力，追求长生之道。",
                "rules": ["灵气浓度决定修炼速度", "修士分九境，每境三转", "天劫是晋升必经历练"],
                "key_locations": [
                    {"name": "青云宗", "sensory": "松涛声+檀香味+青石触感+晨光微亮", "function": "主角修炼圣地"},
                    {"name": "天堑山脉", "sensory": "寒风呼啸+冰雪触感+银白光感", "function": "试炼挑战之地"},
                ],
                "factions": [
                    {"name": "正道联盟", "goal": "维护修真界秩序", "conflict_with": "魔教"},
                    {"name": "魔教", "goal": "颠覆正统，追求力量", "conflict_with": "正道联盟"},
                ],
                "history": ["上古仙魔大战", "灵气复苏纪元", "宗门鼎立时代"],
                "unique_appeal": "九境修炼体系+天劫考验",
            }
        elif "科幻" in prompt_lower or "赛博" in prompt_lower or "未来" in prompt_lower:
            return {
                "name": "新纪元都市",
                "category": "sci_fi",
                "description": "末日战争后的未来世界，科技与人性交织，企业在废墟上建立新秩序。",
                "rules": ["科技高度发达但资源极度匮乏", "义体改造有排斥风险", "AI受严格伦理协议约束"],
                "key_locations": [
                    {"name": "新纪元大厦", "sensory": "电子嗡鸣+金属气味+冰冷触感+霓虹光感", "function": "企业权力中心"},
                    {"name": "下城区", "sensory": "潮湿闷热+机械噪音+锈迹触感+昏暗光感", "function": "反抗者据点"},
                ],
                "factions": [
                    {"name": "企业联盟", "goal": "垄断资源与技术", "conflict_with": "改造者互助会"},
                    {"name": "自由黑客", "goal": "打破信息垄断", "conflict_with": "企业联盟"},
                ],
                "history": ["末日战争", "企业崛起", "AI伦理法案"],
                "unique_appeal": "义体改造+企业垄断+黑客反抗",
            }
        elif "都市" in prompt_lower or "现代" in prompt_lower or "校园" in prompt_lower:
            return {
                "name": "现代都市",
                "category": "urban",
                "description": "表面平静的现代都市，暗流涌动，各色人物在都市丛林中追寻自己的命运。",
                "rules": ["遵循现实物理法则", "社会阶层分化明显", "信息即力量"],
                "key_locations": [
                    {"name": "市中心", "sensory": "车水马龙+咖啡香+柏油触感+霓虹光感", "function": "商业活动核心"},
                    {"name": "旧城区", "sensory": "老旧气息+巷弄回音+斑驳触感+黄昏光感", "function": "秘密交易场所"},
                ],
                "factions": [
                    {"name": "商业精英", "goal": "扩张商业版图", "conflict_with": "民间组织"},
                    {"name": "民间组织", "goal": "维护社区利益", "conflict_with": "商业精英"},
                ],
                "history": ["城市改造运动", "经济危机", "互联网革命"],
                "unique_appeal": "阶层碰撞+信息博弈",
            }
        elif "悬疑" in prompt_lower or "推理" in prompt_lower or "侦探" in prompt_lower:
            return {
                "name": "迷雾之城",
                "category": "urban",
                "description": "笼罩在迷雾中的城市，每一条街巷都藏着秘密，真相往往比表象更复杂。",
                "rules": ["每个案件都有关键线索", "嫌疑人至少3人", "动机必须合理"],
                "key_locations": [
                    {"name": "警局", "sensory": "咖啡味+打印机声音+纸张触感+荧光灯", "function": "案件处理中心"},
                    {"name": "案发现场", "sensory": "血腥味+雨声+湿冷触感+手电筒光", "function": "线索发现地"},
                ],
                "factions": [
                    {"name": "警方", "goal": "破案维权", "conflict_with": "神秘组织"},
                    {"name": "媒体", "goal": "挖掘真相", "conflict_with": "警方"},
                ],
                "history": ["连环悬案", "警界丑闻", "媒体革命"],
                "unique_appeal": "迷雾氛围+多层反转",
            }
        elif "末日" in prompt_lower or "废土" in prompt_lower or "丧尸" in prompt_lower:
            return {
                "name": "荒原",
                "category": "sci_fi",
                "description": "大灾难后的废土世界，幸存者在废墟中挣扎求生，资源争夺是永恒的主题。",
                "rules": ["资源极度匮乏", "变异生物遍布", "辐射带有致命风险"],
                "key_locations": [
                    {"name": "幸存者营地", "sensory": "篝火味+风声+木板触感+火光", "function": "安全据点"},
                    {"name": "旧城市废墟", "sensory": "尘土味+寂静+碎石触感+阴冷", "function": "资源搜寻地"},
                ],
                "factions": [
                    {"name": "幸存者联盟", "goal": "建立新秩序", "conflict_with": "掠夺者"},
                    {"name": "掠夺者", "goal": "抢夺资源", "conflict_with": "幸存者联盟"},
                ],
                "history": ["大灾难爆发", "文明崩溃", "新秩序萌芽"],
                "unique_appeal": "废土美学+资源博弈",
            }
        else:
            return {
                "name": "新世界",
                "category": "other",
                "description": "一个充满未知与可能的世界，等待探索者揭开它的面纱。",
                "rules": ["世界有其内在规律", "探索是发现真相的唯一途径", "每种选择都有代价"],
                "key_locations": [
                    {"name": "起点之村", "sensory": "泥土气息+鸟鸣+温暖触感+晨光", "function": "冒险起点"},
                    {"name": "迷雾森林", "sensory": "潮湿苔藓+落叶声+湿滑触感+微弱光", "function": "试炼与挑战"},
                ],
                "factions": [
                    {"name": "探索者", "goal": "发现世界真相", "conflict_with": "守护者"},
                    {"name": "守护者", "goal": "保护世界秘密", "conflict_with": "探索者"},
                ],
                "history": ["创世传说", "大分裂时代", "新纪元开始"],
                "unique_appeal": "未知探索+自由选择",
            }

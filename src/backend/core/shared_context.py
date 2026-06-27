from typing import Dict, Any, List, Optional
from datetime import datetime


class Inconsistency:
    """不一致项"""
    def __init__(self, type: str, entity_id: str, description: str):
        self.type = type
        self.entity_id = entity_id
        self.description = description


class SharedContextBus:
    """
    共享上下文总线
    确保所有Agent看到一致的信息
    """
    
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._locks: Dict[str, bool] = {}
        self._history: List[Dict] = []
        self._character_states: Dict[str, Dict] = {}
        self._world_rules: List[str] = []
        self._style_guide: Optional[Dict] = None
    
    def write(self, key: str, value: Any, agent: str):
        """Agent写入共享数据"""
        old_value = self._store.get(key)
        self._store[key] = value
        
        self._history.append({
            "timestamp": datetime.now(),
            "agent": agent,
            "key": key,
            "action": "write",
            "old": old_value,
            "new": value
        })
        
        # 分类存储
        if key.startswith("character_"):
            char_id = key.split("_")[1]
            self._character_states[char_id] = value
        elif key == "world_rules":
            self._world_rules = value if isinstance(value, list) else []
        elif key == "style_guide":
            self._style_guide = value
    
    def read(self, key: str, agent: str) -> Any:
        """Agent读取共享数据"""
        value = self._store.get(key)
        
        self._history.append({
            "timestamp": datetime.now(),
            "agent": agent,
            "key": key,
            "action": "read",
            "value": value
        })
        
        return value
    
    def get_context_for_agent(self, agent_type: str) -> Dict[str, Any]:
        """为特定Agent获取上下文"""
        context = {
            "character_states": self._character_states,
            "world_rules": self._world_rules,
            "style_guide": self._style_guide
        }
        
        # 根据Agent类型添加特定上下文
        if agent_type == "draft":
            context["recent_events"] = self._get_recent_events()
        elif agent_type == "edit":
            context["anti_patterns"] = self._get_anti_patterns()
        
        return context
    
    def _get_recent_events(self) -> List[Dict]:
        """获取最近的事件"""
        return [h for h in self._history[-10:] if h["action"] == "write"]
    
    def _get_anti_patterns(self) -> List[str]:
        """获取反模式"""
        if self._style_guide:
            return self._style_guide.get("anti_patterns", [])
        return []
    
    def check_consistency(self) -> List[Inconsistency]:
        """检查数据一致性"""
        issues: List[Inconsistency] = []
        
        # 检查角色一致性
        for char_id, state in self._character_states.items():
            if self._has_contradictory_traits(state):
                issues.append(Inconsistency(
                    type="character",
                    entity_id=char_id,
                    description=f"角色 {char_id} 存在矛盾的性格描述"
                ))
        
        # 检查世界观一致性
        issues.extend(self._check_world_consistency())
        
        return issues
    
    def _has_contradictory_traits(self, state: Dict) -> bool:
        """检查角色是否有矛盾的性格"""
        # 简单的一致性检查逻辑
        traits = state.get("traits", []) if isinstance(state, dict) else []
        # 这里可以添加更复杂的逻辑来检查矛盾的性格
        return False
    
    def _check_world_consistency(self) -> List[Inconsistency]:
        """检查世界观一致性"""
        # 简单的世界观一致性检查
        return []
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取历史记录"""
        return self._history[-limit:]
    
    def clear(self):
        """清空上下文"""
        self._store.clear()
        self._character_states.clear()
        self._world_rules.clear()
        self._style_guide = None

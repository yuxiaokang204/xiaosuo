from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json

class AgentType(Enum):
    WORKFLOW = "workflow"
    SPECIALIST = "specialist"

@dataclass
class AgentRegistration:
    id: str
    name: str
    agent_type: AgentType
    capabilities: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    is_enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)

class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentRegistration] = {}
        self._capability_index: Dict[str, List[str]] = {}

    def register(self, agent: AgentRegistration) -> None:
        self._agents[agent.id] = agent
        for capability in agent.capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = []
            if agent.id not in self._capability_index[capability]:
                self._capability_index[capability].append(agent.id)

    def unregister(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        agent = self._agents.pop(agent_id)
        for capability in agent.capabilities:
            if capability in self._capability_index:
                if agent_id in self._capability_index[capability]:
                    self._capability_index[capability].remove(agent_id)
                if not self._capability_index[capability]:
                    del self._capability_index[capability]
        return True

    def get(self, agent_id: str) -> Optional[AgentRegistration]:
        return self._agents.get(agent_id)

    def get_by_capability(self, capability: str) -> List[AgentRegistration]:
        agent_ids = self._capability_index.get(capability, [])
        return [self._agents[aid] for aid in agent_ids if self._agents[aid].is_enabled]

    def list_all(self) -> List[AgentRegistration]:
        return [agent for agent in self._agents.values() if agent.is_enabled]

    def enable(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            self._agents[agent_id].is_enabled = True
            return True
        return False

    def disable(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            self._agents[agent_id].is_enabled = False
            return True
        return False

    def update_config(self, agent_id: str, config: Dict[str, Any]) -> bool:
        if agent_id in self._agents:
            self._agents[agent_id].config.update(config)
            return True
        return False

    def find_best_agent(self, required_capability: str) -> Optional[AgentRegistration]:
        candidates = self.get_by_capability(required_capability)
        if not candidates:
            return None
        candidates.sort(key=lambda x: x.capabilities.count(required_capability), reverse=True)
        return candidates[0]

    def to_dict(self) -> Dict[str, Any]:
        return {
            aid: {
                "id": a.id,
                "name": a.name,
                "agent_type": a.agent_type.value,
                "capabilities": a.capabilities,
                "version": a.version,
                "is_enabled": a.is_enabled
            } for aid, a in self._agents.items()
        }

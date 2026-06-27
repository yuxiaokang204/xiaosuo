"""
事件总线 (EventBus) — Agent 间通信的发布/订阅机制

功能:
- 异步事件发布/订阅
- 支持多回调
- 支持事件过滤

使用示例:
    bus = EventBus()
    bus.subscribe("chapter.done", lambda data: print(data))
    await bus.publish("chapter.done", {"index": 1, "title": "第一章"})
"""
import asyncio
import inspect
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    """事件类型枚举"""
    AGENT_EXECUTE_START = "agent.execute_start"
    AGENT_EXECUTE_DONE = "agent.execute_done"
    AGENT_LLM_CALL = "agent.llm_call"
    AGENT_LLM_SUCCESS = "agent.llm_success"
    AGENT_LLM_ERROR = "agent.llm_error"
    AGENT_LLM_EXCEPTION = "agent.llm_exception"
    AGENT_JSON_PARSE_FAILED = "agent.json_parse_failed"
    CHAPTER_OUTLINED = "chapter.outlined"
    CHAPTER_DRAFTED = "chapter.drafted"
    CHAPTER_EDITED = "chapter.edited"
    CHAPTER_REVIEWED = "chapter.reviewed"
    LOOP_START = "loop.start"
    LOOP_END = "loop.end"
    PLAN_CREATED = "plan.created"


@dataclass
class Event:
    """事件包装类"""
    event_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class EventBus:
    """
    异步事件总线 — 用于 Agent 间通信
    
    支持的操作:
    - subscribe(event_type, callback) - 订阅事件
    - unsubscribe(event_type, callback_id) - 取消订阅
    - publish(event_type, data) - 发布事件
    - clear() - 清空所有订阅
    """

    def __init__(self, max_history: int = 100):
        """
        Args:
            max_history: 保留的最大历史事件数
        """
        self._subscribers: Dict[str, List[Dict[str, Any]]] = {}
        self._history: List[Event] = []
        self._max_history = max_history
        self._listener_tasks: Dict[str, asyncio.Task] = {}

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Dict[str, Any]], Any],
        listener_id: Optional[str] = None,
    ) -> str:
        """
        订阅事件

        Args:
            event_type: 事件类型，如 "chapter.done", "loop.start"
            callback: 回调函数，可同步或异步
            listener_id: 可选的监听器标识，用于取消订阅

        Returns:
            监听器 ID
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        lid = listener_id or uuid.uuid4().hex[:8]

        # 检查是否已存在相同 ID 的监听器
        existing = [s for s in self._subscribers[event_type] if s["id"] == lid]
        if existing:
            self._subscribers[event_type].remove(existing[0])

        self._subscribers[event_type].append({
            "id": lid,
            "callback": callback,
        })

        return lid

    def unsubscribe(self, event_type: str, listener_id: str) -> bool:
        """
        取消订阅

        Args:
            event_type: 事件类型
            listener_id: 监听器 ID

        Returns:
            是否成功取消订阅
        """
        if event_type not in self._subscribers:
            return False

        original_len = len(self._subscribers[event_type])
        self._subscribers[event_type] = [
            s for s in self._subscribers[event_type] if s["id"] != listener_id
        ]
        return len(self._subscribers[event_type]) < original_len

    async def publish(self, event_type: str, data: Dict[str, Any]) -> List[Any]:
        """
        发布事件，同步调用所有订阅的回调

        Args:
            event_type: 事件类型
            data: 事件数据

        Returns:
            所有回调的返回值列表
        """
        event = Event(event_type=event_type, data=data)

        # 维护历史
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        results = []
        subscribers = self._subscribers.get(event_type, [])

        if subscribers:
            for sub in subscribers:
                callback = sub["callback"]
                try:
                    if asyncio.iscoroutinefunction(callback) or inspect.isasyncgenfunction(callback):
                        result = await callback(event.data)
                        results.append(result)
                    else:
                        result = callback(event.data)
                        results.append(result)
                except Exception as e:
                    print(f"[EventBus] 回调执行失败 ({event_type}): {e}")
                    results.append(None)

        return results

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        获取事件历史

        Args:
            event_type: 可选的事件类型过滤
            limit: 返回的最大事件数

        Returns:
            事件历史列表
        """
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return [e.to_dict() for e in events[-limit:]]

    def clear(self, event_type: Optional[str] = None):
        """
        清空订阅或特定事件类型的订阅

        Args:
            event_type: 可选，只清空该事件类型的订阅
        """
        if event_type:
            self._subscribers.pop(event_type, None)
        else:
            self._subscribers.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取事件总线统计信息"""
        return {
            "total_event_types": len(self._subscribers),
            "total_subscribers": sum(len(v) for v in self._subscribers.values()),
            "history_size": len(self._history),
            "event_types": list(self._subscribers.keys()),
        }


# 全局事件总线单例
_event_bus_instance: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线单例"""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance

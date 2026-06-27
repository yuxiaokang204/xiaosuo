"""
服务模块 - 共享业务服务（L3 工具层）
"""
from .memory_service import MemoryService
from .learning_service import LearningService
from .consistency_checker import ConsistencyChecker
from .prompt_manager import PromptManager

# 向后兼容：LearningEngine 可直接从 core.learning_engine 导入
# __all__ = [
#     "MemoryService",
#     "LearningService",
#     "ConsistencyChecker",
#     "PromptManager",
# ]

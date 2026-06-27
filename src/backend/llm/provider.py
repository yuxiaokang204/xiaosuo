"""
LLM Provider 基类
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from .gateway import LLMProvider, LLMMessage, LLMResponse

__all__ = ["LLMProvider", "LLMMessage", "LLMResponse"]

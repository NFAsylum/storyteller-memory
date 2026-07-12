"""Reflection package: consolidate recent turns into structured world_state.

Public API is unchanged from the former single-module `reflection.py`:

    from core.memory.reflection import Reflection, FakeReflection, LlmReflection, ReflectionResult
"""

from core.memory.reflection.fake import FakeReflection
from core.memory.reflection.llm import LlmReflection
from core.memory.reflection.protocol import Reflection, ReflectionResult

__all__ = ["FakeReflection", "LlmReflection", "Reflection", "ReflectionResult"]

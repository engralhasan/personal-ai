"""
Memory Module Root Entry & Exporter.
Allows direct imports via `import memory` or `from memory import memory`.
"""
from core.memory import (
    ShortTermMemory,
    LongTermRelationalMemory,
    SemanticVectorMemory,
    MemoryManager,
    memory
)

__all__ = [
    "ShortTermMemory",
    "LongTermRelationalMemory",
    "SemanticVectorMemory",
    "MemoryManager",
    "memory"
]

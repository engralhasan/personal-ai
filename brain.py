"""
Brain & Reasoning Engine Root Entry & Exporter.
Allows direct imports via `import brain` or `from brain import brain`.
"""
from core.brain import (
    JarvisBrain,
    brain,
    SYSTEM_PERSONA_PROMPT
)

__all__ = [
    "JarvisBrain",
    "brain",
    "SYSTEM_PERSONA_PROMPT"
]

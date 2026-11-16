"""
Voice Engine Root Entry & Exporter.
Allows direct imports via `import voice_engine` or `from voice_engine import voice_engine`.
"""
from core.voice_engine import (
    SpeechToTextEngine,
    TextToSpeechEngine,
    VoiceEngine,
    voice_engine
)

__all__ = [
    "SpeechToTextEngine",
    "TextToSpeechEngine",
    "VoiceEngine",
    "voice_engine"
]

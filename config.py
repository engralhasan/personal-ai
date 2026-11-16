"""
Configuration Management Module for J.A.R.V.I.S. Desktop Assistant.
Handles environment variables, default settings, path initialization, and security policies.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


class RiskLevel(str, Enum):
    """Classification of action security risks for the Human-in-the-Loop Confirmation Gate."""
    READ_ONLY = "READ_ONLY"                   # e.g., read file, search web, check volume
    SAFE_EXECUTION = "SAFE_EXECUTION"         # e.g., open calculator, type text, set volume
    HIGH_RISK_DESTRUCTIVE = "HIGH_RISK"       # e.g., delete file, format disk, restart/shutdown, raw terminal commands


@dataclass
class AudioConfig:
    wake_word: str = os.getenv("WAKE_WORD", "hey jarvis").lower()
    wake_word_sensitivity: float = float(os.getenv("WAKE_WORD_SENSITIVITY", "0.6"))
    picovoice_access_key: str = os.getenv("PICOVOICE_ACCESS_KEY", "")

    # STT Settings
    stt_model_size: str = os.getenv("STT_MODEL_SIZE", "base")
    stt_device: str = os.getenv("STT_DEVICE", "cpu")
    stt_compute_type: str = os.getenv("STT_COMPUTE_TYPE", "int8")
    stt_language: str = os.getenv("STT_LANGUAGE", "auto")

    # Audio Capture Stream
    sample_rate: int = 16000
    chunk_size: int = 1024
    silence_threshold_energy: int = 300
    silence_duration_seconds: float = 1.2

    # TTS Settings
    tts_voice_en: str = os.getenv("TTS_VOICE_EN", "en-US-JennyNeural")
    tts_voice_bn: str = os.getenv("TTS_VOICE_BN", "bn-BD-NabanitaNeural")
    tts_rate: str = os.getenv("TTS_RATE", "+5%")
    tts_pitch: str = os.getenv("TTS_PITCH", "+0Hz")
    tts_fallback_offline: bool = os.getenv("TTS_FALLBACK_OFFLINE", "true").lower() == "true"


@dataclass
class LLMConfig:
    provider: str = os.getenv("LLM_PROVIDER", "gemini").lower()
    model: str = os.getenv("LLM_MODEL", "gemini-3-flash-preview")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    ollama_api_base: str = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
    temperature: float = 0.4
    max_tokens: int = 2048


@dataclass
class SecurityConfig:
    require_confirmation_for_destructive: bool = (
        os.getenv("REQUIRE_CONFIRMATION_FOR_DESTRUCTIVE", "true").lower() == "true"
    )
    confirmation_timeout_seconds: int = int(os.getenv("CONFIRMATION_TIMEOUT_SECONDS", "15"))

    # Explicit destructive keywords in commands
    destructive_command_keywords: List[str] = field(default_factory=lambda: [
        "rmdir", "del ", "rm ", "drop ", "format", "shutdown", "reboot",
        "taskkill /f", "kill -9", "sfc /scannow", "diskpart", "mkfs"
    ])


@dataclass
class StorageConfig:
    app_data_dir: Path = BASE_DIR / os.getenv("APP_DATA_DIR", "data")
    chroma_dir: Path = BASE_DIR / os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
    sqlite_db_path: Path = BASE_DIR / os.getenv("SQLITE_DB_PATH", "data/jarvis_memory.db")
    screenshots_dir: Path = BASE_DIR / os.getenv("SCREENSHOTS_DIR", "data/screenshots")
    temp_audio_dir: Path = BASE_DIR / "data/audio_temp"

    def initialize_directories(self) -> None:
        """Create required directories on disk if they don't exist."""
        for path in [self.app_data_dir, self.chroma_dir, self.screenshots_dir, self.temp_audio_dir]:
            path.mkdir(parents=True, exist_ok=True)


@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


# Global Singleton Configuration Instance
config = AppConfig()
config.storage.initialize_directories()

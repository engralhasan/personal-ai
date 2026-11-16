"""
J.A.R.V.I.S. Personal AI Desktop Assistant
Main Orchestrator & Application Entry Point.
Coordinates Voice Engine, LLM Brain, System Tools, Confirmation Gate, and PyQt6 HUD.
"""

from __future__ import annotations
import sys
import os
import logging
import threading
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QObject, pyqtSignal
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    QApplication = None

# Core & Tools Imports
from config import config
from core.security import security_gate
from core.voice_engine import voice_engine
from core.brain import brain
from ui.ui import JarvisHUDWidget, SystemTrayManager, UISignals

# Configure Logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.storage.app_data_dir / "jarvis.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("JARVIS.Main")


class JarvisOrchestrator:
    """
    Central controller orchestrating asynchronous threads between
    Voice Capture, LLM Brain execution, and PyQt6 UI events.
    """

    def __init__(self, app: QApplication):
        self.app = app
        self.signals = UISignals()

        # Initialize HUD & System Tray with Voice Mic Trigger
        self.hud = JarvisHUDWidget(
            on_user_submit_callback=self.handle_query,
            on_mic_click_callback=lambda: voice_engine.trigger_voice_input(self.handle_query)
        )
        self.tray = SystemTrayManager(
            hud_widget=self.hud,
            on_toggle_mute=voice_engine.toggle_mute
        )

        self._wire_signals()
        self._wire_security_gate()
        self._wire_voice_engine()

    def _wire_signals(self) -> None:
        """Connects Qt signals to HUD UI update slots."""
        self.signals.state_changed.connect(self.hud.set_state)
        self.signals.transcription_received.connect(self.hud.append_transcript)
        self.signals.response_ready.connect(self.hud.append_response)
        self.signals.audio_level_updated.connect(self.hud.waveform.set_audio_level)
        self.signals.request_confirmation.connect(self.hud.confirm_dialog.show_prompt)

    def _wire_security_gate(self) -> None:
        """Registers UI confirmation callback with the Security Gate."""
        def ui_confirmation_handler(prompt_text: str, timeout_seconds: int):
            # Emit thread-safe signal to show dialog in Qt GUI thread
            self.signals.request_confirmation.emit(prompt_text, timeout_seconds)

        security_gate.register_ui_handler(ui_confirmation_handler)

    def _wire_voice_engine(self) -> None:
        """Hooks VoiceEngine callbacks to Qt Signals."""
        voice_engine.on_state_change = lambda st: self.signals.state_changed.emit(st)
        voice_engine.on_transcription = lambda txt, lang: self.signals.transcription_received.emit(txt, lang)
        voice_engine.on_audio_level = lambda lvl: self.signals.audio_level_updated.emit(lvl)

    def handle_query(self, user_query: str) -> None:
        """
        Dispatches user query to LLM Brain on a background worker thread
        to maintain a 60 FPS non-blocking UI.
        """
        logger.info(f"Processing query: '{user_query}'")
        worker_thread = threading.Thread(
            target=self._process_query_worker,
            args=(user_query,),
            daemon=True
        )
        worker_thread.start()

    def _process_query_worker(self, user_query: str) -> None:
        """Background thread worker for Brain reasoning and speech synthesis."""
        try:
            self.signals.state_changed.emit("Thinking")

            # Execute LLM and any required tool calls
            response_text = brain.process_query(
                user_text=user_query,
                on_status_update=lambda st: self.signals.state_changed.emit(st)
            )

            # Display response in HUD
            self.signals.response_ready.emit(response_text)

            # Speak response aloud
            self.signals.state_changed.emit("Speaking")
            voice_engine.tts.speak(
                text=response_text,
                on_start=lambda: self.signals.state_changed.emit("Speaking"),
                on_finish=lambda: self.signals.state_changed.emit("Idle")
            )

        except Exception as e:
            logger.exception(f"Unhandled error in query processing worker: {e}")
            self.signals.response_ready.emit(f"Apologies sir, an internal error occurred: {str(e)}")
            self.signals.state_changed.emit("Idle")

    def start(self) -> None:
        """Starts background voice engine and launches desktop UI."""
        logger.info("Initializing J.A.R.V.I.S. Desktop Assistant...")
        self.hud.show()
        self.hud.set_state("Idle")

        # Start continuous audio listening thread
        voice_engine.start_listening_loop(on_user_query_callback=self.handle_query)

        # Initial greeting without honorifics or names
        welcome_msg = "All systems operational. How may I assist you?"
        self.signals.response_ready.emit(welcome_msg)
        threading.Thread(
            target=lambda: voice_engine.tts.speak(welcome_msg),
            daemon=True
        ).start()


def main():
    """Application entry point."""
    if not PYQT_AVAILABLE:
        print("\n[ERROR] PyQt6 is not installed.")
        print("Please activate your virtual environment and install dependencies:")
        print("    pip install -r requirements.txt\n")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS-Personal-AI")
    app.setQuitOnLastWindowClosed(False) # Keep running in system tray

    orchestrator = JarvisOrchestrator(app)
    orchestrator.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""
PyQt6 Modern Desktop Floating HUD & System Tray Widget for J.A.R.V.I.S.
Features:
- Frameless, translucent, always-on-top draggable HUD widget with Iron Man aesthetic.
- Dynamic audio waveform & pulsing state visualizer (Idle, Listening, Thinking, Speaking).
- Real-time conversation transcripts & interactive command input.
- Embedded Human-in-the-Loop Confirmation Gate dialog with countdown timer.
- System Tray integration.
"""

from __future__ import annotations
import math
import sys
import logging
from typing import Optional, Callable
try:
    from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QObject
    from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QIcon, QLinearGradient
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QLineEdit, QPushButton, QFrame, QTextEdit, QSystemTrayIcon,
        QMenu, QGraphicsDropShadowEffect
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    # Mock base classes for headless or pre-install environments
    class QObject:
        pass
    class QWidget:
        pass
    class QFrame:
        pass
    def pyqtSignal(*args, **kwargs):
        class DummySignal:
            def connect(self, fn): pass
            def emit(self, *a, **k): pass
        return DummySignal()
from core.security import security_gate

logger = logging.getLogger("JARVIS.UI")


class UISignals(QObject):
    """Thread-safe signals bridging background worker threads with Qt GUI."""
    state_changed = pyqtSignal(str)              # 'Idle', 'Listening', 'Thinking', 'Speaking', 'Muted'
    transcription_received = pyqtSignal(str, str) # text, lang
    response_ready = pyqtSignal(str)             # response text
    audio_level_updated = pyqtSignal(float)      # 0.0 to 1.0
    request_confirmation = pyqtSignal(str, int)  # prompt, timeout_seconds


class WaveformVisualizer(QWidget):
    """Dynamic pulsing neon waveform widget reflecting audio levels and assistant states."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.phase = 0.0
        self.amplitude = 0.2
        self.target_amplitude = 0.2
        self.state = "Idle"

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._update_animation)
        self.anim_timer.start(30) # ~33 FPS

    def set_state(self, state: str) -> None:
        self.state = state
        if state == "Idle":
            self.target_amplitude = 0.15
        elif state == "Listening":
            self.target_amplitude = 0.6
        elif state == "Thinking":
            self.target_amplitude = 0.4
        elif state == "Speaking":
            self.target_amplitude = 0.85
        elif state == "Muted":
            self.target_amplitude = 0.02
        self.update()

    def set_audio_level(self, level: float) -> None:
        """Called when mic or speech audio level changes."""
        self.target_amplitude = max(0.1, min(1.0, level * 1.5))

    def _update_animation(self) -> None:
        self.phase += 0.15
        # Smooth lerp interpolation
        self.amplitude += (self.target_amplitude - self.amplitude) * 0.2
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        mid_y = h / 2

        # State color selection
        if self.state == "Listening":
            glow_color = QColor(0, 230, 255) # Cyan
        elif self.state == "Thinking":
            glow_color = QColor(255, 170, 0) # Amber
        elif self.state == "Speaking":
            glow_color = QColor(0, 255, 170) # Emerald cyan
        elif self.state == "Muted":
            glow_color = QColor(255, 50, 50) # Red
        else:
            glow_color = QColor(64, 150, 255) # Deep Blue Idle

        pen = QPen(glow_color, 2)
        painter.setPen(pen)

        # Draw dynamic multi-frequency wave
        points = []
        num_points = 80
        for i in range(num_points):
            x = (i / (num_points - 1)) * w
            # Combine two sine frequencies with Gaussian envelope at edges
            env = math.sin((i / (num_points - 1)) * math.pi)
            y_offset = (
                math.sin(self.phase + (i * 0.2)) * 0.7 +
                math.sin(self.phase * 1.5 + (i * 0.4)) * 0.3
            ) * (h * 0.45 * self.amplitude) * env
            points.append(QPoint(int(x), int(mid_y + y_offset)))

        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])


class ConfirmationDialogWidget(QFrame):
    """Embedded interactive confirmation overlay for high-risk operations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 10, 10, 240);
                border: 2px solid #ff3344;
                border-radius: 10px;
                padding: 10px;
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
            }
            QPushButton#btnApprove {
                background-color: #00aa55;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 6px 14px;
            }
            QPushButton#btnApprove:hover {
                background-color: #00dd66;
            }
            QPushButton#btnDeny {
                background-color: #cc2233;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 6px 14px;
            }
            QPushButton#btnDeny:hover {
                background-color: #ff3344;
            }
        """)

        layout = QVBoxLayout(self)
        self.title_label = QLabel("⚠️ SECURITY CONFIRMATION REQUIRED")
        self.title_label.setStyleSheet("color: #ff4455; font-weight: bold; font-size: 13px;")
        layout.addWidget(self.title_label)

        self.prompt_label = QLabel("")
        self.prompt_label.setWordWrap(True)
        layout.addWidget(self.prompt_label)

        self.timer_label = QLabel("Auto-reject in: 15s")
        self.timer_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        layout.addWidget(self.timer_label)

        btn_layout = QHBoxLayout()
        self.btn_approve = QPushButton("AUTHORIZE")
        self.btn_approve.setObjectName("btnApprove")
        self.btn_approve.clicked.connect(self._on_approve)

        self.btn_deny = QPushButton("DENY")
        self.btn_deny.setObjectName("btnDeny")
        self.btn_deny.clicked.connect(self._on_deny)

        btn_layout.addWidget(self.btn_deny)
        btn_layout.addWidget(self.btn_approve)
        layout.addLayout(btn_layout)

        self.remaining_seconds = 15
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._tick)
        self.hide()

    def show_prompt(self, prompt: str, timeout_sec: int) -> None:
        self.prompt_label.setText(prompt)
        self.remaining_seconds = timeout_sec
        self.timer_label.setText(f"Auto-reject in: {self.remaining_seconds}s")
        self.show()
        self.countdown_timer.start(1000)

    def _tick(self) -> None:
        self.remaining_seconds -= 1
        self.timer_label.setText(f"Auto-reject in: {self.remaining_seconds}s")
        if self.remaining_seconds <= 0:
            self.countdown_timer.stop()
            self._on_deny()

    def _on_approve(self) -> None:
        self.countdown_timer.stop()
        self.hide()
        security_gate.submit_decision(True)

    def _on_deny(self) -> None:
        self.countdown_timer.stop()
        self.hide()
        security_gate.submit_decision(False)


class JarvisHUDWidget(QWidget):
    """
    Main Floating Desktop HUD Interface.
    Always-on-top, frameless, translucent, futuristic UI with state indicators and audio wave.
    """

    def __init__(self, on_user_submit_callback: Optional[Callable[[str], None]] = None, on_mic_click_callback: Optional[Callable[[], None]] = None):
        super().__init__()
        self.on_user_submit = on_user_submit_callback
        self.on_mic_click = on_mic_click_callback
        self.current_lang = "bn"
        self.drag_position = QPoint()

        self._setup_window_flags()
        self._init_ui()
        self._center_on_screen()

    def _setup_window_flags(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(420, 520)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Outer Container Panel with Dark Glassmorphism Styling
        self.panel = QFrame(self)
        self.panel.setObjectName("MainPanel")
        self.panel.setStyleSheet("""
            QFrame#MainPanel {
                background-color: rgba(12, 16, 28, 235);
                border: 1.5px solid rgba(0, 180, 255, 120);
                border-radius: 16px;
            }
            QLabel {
                color: #e0f0ff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit {
                background-color: rgba(20, 28, 48, 200);
                border: 1px solid rgba(0, 180, 255, 80);
                border-radius: 8px;
                color: #ffffff;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1.5px solid #00e5ff;
            }
            QPushButton {
                background-color: rgba(0, 140, 255, 160);
                border: none;
                border-radius: 8px;
                color: white;
                font-weight: bold;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: rgba(0, 180, 255, 220);
            }
            QTextEdit {
                background-color: rgba(8, 12, 22, 180);
                border: 1px solid rgba(0, 180, 255, 40);
                border-radius: 8px;
                color: #cce5ff;
                font-size: 12px;
                line-height: 1.4;
            }
        """)

        # Drop shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 180, 255, 90))
        shadow.setOffset(0, 4)
        self.panel.setGraphicsEffect(shadow)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(10)

        # Header Bar: Title, Arc Reactor Icon, Language Toggle, Status Pill & Controls
        header_layout = QHBoxLayout()

        self.title_label = QLabel("J.A.R.V.I.S.")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 16px; letter-spacing: 2px; color: #00e5ff;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Language Toggle Button (বাংলা / EN)
        self.btn_lang = QPushButton("বাংলা")
        self.btn_lang.setToolTip("Click to toggle language (বাংলা / EN)")
        self.btn_lang.setStyleSheet("""
            background-color: rgba(0, 180, 255, 30);
            border: 1px solid rgba(0, 180, 255, 80);
            border-radius: 8px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: bold;
            color: #00e5ff;
        """)
        self.btn_lang.clicked.connect(self._toggle_language)
        header_layout.addWidget(self.btn_lang)

        self.status_pill = QLabel("IDLE")
        self.status_pill.setStyleSheet("""
            background-color: rgba(0, 180, 255, 40);
            border: 1px solid #00b4ff;
            border-radius: 10px;
            padding: 3px 10px;
            font-size: 10px;
            font-weight: bold;
            color: #00e5ff;
        """)
        header_layout.addWidget(self.status_pill)

        self.btn_minimize = QPushButton("–")
        self.btn_minimize.setFixedSize(26, 26)
        self.btn_minimize.setStyleSheet("background-color: transparent; color: #88aacc; font-size: 14px;")
        self.btn_minimize.clicked.connect(self.hide)
        header_layout.addWidget(self.btn_minimize)

        panel_layout.addLayout(header_layout)

        # Dynamic Audio Waveform
        self.waveform = WaveformVisualizer(self)
        panel_layout.addWidget(self.waveform)

        # Conversation Activity & Log Box
        self.log_display = QTextEdit(self)
        self.log_display.setReadOnly(True)
        self.log_display.setPlaceholderText("Awaiting voice command or query...")
        panel_layout.addWidget(self.log_display)

        # Embedded Security Gate Confirmation Dialog
        self.confirm_dialog = ConfirmationDialogWidget(self)
        panel_layout.addWidget(self.confirm_dialog)

        # Bottom Input Area with Dedicated Voice Mic Button
        input_layout = QHBoxLayout()

        self.btn_mic = QPushButton("🎙️")
        self.btn_mic.setFixedSize(36, 36)
        self.btn_mic.setToolTip("Click to speak (Bangla or English)")
        self.btn_mic.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 180, 255, 70);
                border: 1.5px solid #00e5ff;
                border-radius: 18px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(0, 230, 255, 140);
            }
        """)
        self.btn_mic.clicked.connect(self._handle_mic_click)
        input_layout.addWidget(self.btn_mic)

        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Type in Bangla/English, or click 🎙️ to talk...")
        self.input_field.returnPressed.connect(self._handle_manual_submit)
        input_layout.addWidget(self.input_field)

        self.btn_send = QPushButton("⚡")
        self.btn_send.setFixedSize(36, 36)
        self.btn_send.clicked.connect(self._handle_manual_submit)
        input_layout.addWidget(self.btn_send)

        panel_layout.addLayout(input_layout)
        main_layout.addWidget(self.panel)

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 30
        y = screen.height() - self.height() - 60
        self.move(x, y)

    # --- Mouse Event Handlers for Dragging Frameless Window ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    # --- UI Update Slots ---
    def set_state(self, state: str) -> None:
        self.status_pill.setText(state.upper())
        self.waveform.set_state(state)

        color_map = {
            "IDLE": ("rgba(0, 180, 255, 40)", "#00b4ff"),
            "LISTENING": ("rgba(0, 230, 255, 80)", "#00e5ff"),
            "THINKING": ("rgba(255, 170, 0, 80)", "#ffaa00"),
            "SPEAKING": ("rgba(0, 255, 170, 80)", "#00ffaa"),
            "MUTED": ("rgba(255, 50, 50, 80)", "#ff3344"),
        }
        bg, border = color_map.get(state.upper(), ("rgba(0, 180, 255, 40)", "#00b4ff"))
        self.status_pill.setStyleSheet(f"""
            background-color: {bg};
            border: 1px solid {border};
            border-radius: 10px;
            padding: 3px 10px;
            font-size: 10px;
            font-weight: bold;
            color: {border};
        """)

    def append_transcript(self, user_text: str, lang: str = "en") -> None:
        flag = "🇧🇩" if lang == "bn" else "🌐"
        self.log_display.append(f"<b style='color:#00e5ff;'>User {flag}:</b> {user_text}")

    def append_response(self, response_text: str) -> None:
        self.log_display.append(f"<b style='color:#00ffaa;'>J.A.R.V.I.S.:</b> {response_text}<br>")

    def _handle_mic_click(self) -> None:
        if self.on_mic_click:
            self.on_mic_click()

    def _toggle_language(self) -> None:
        from core.voice_engine import voice_engine
        if self.current_lang == "bn":
            self.current_lang = "en"
            self.btn_lang.setText("EN")
            voice_engine.set_preferred_language("en")
        else:
            self.current_lang = "bn"
            self.btn_lang.setText("বাংলা")
            voice_engine.set_preferred_language("bn")

    def _handle_manual_submit(self) -> None:
        text = self.input_field.text().strip()
        if text:
            self.input_field.clear()
            self.append_transcript(text)
            if self.on_user_submit:
                self.on_user_submit(text)


class SystemTrayManager:
    """Manages system tray icon, notifications, and context menu."""

    def __init__(self, hud_widget: JarvisHUDWidget, on_toggle_mute: Callable[[], bool]):
        self.hud = hud_widget
        self.on_toggle_mute = on_toggle_mute
        self.tray = QSystemTrayIcon(hud_widget)
        self._setup_tray()

    def _setup_tray(self) -> None:
        # Create standard icon
        icon = QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_ComputerIcon)
        self.tray.setIcon(icon)
        self.tray.setToolTip("J.A.R.V.I.S. Desktop Assistant")

        # Context Menu
        menu = QMenu()
        action_toggle_hud = menu.addAction("Show/Hide HUD")
        action_toggle_hud.triggered.connect(self._toggle_hud)

        action_mute = menu.addAction("Mute/Unmute Voice")
        action_mute.triggered.connect(self._handle_mute)

        menu.addSeparator()
        action_exit = menu.addAction("Exit Assistant")
        action_exit.triggered.connect(QApplication.quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _toggle_hud(self) -> None:
        if self.hud.isVisible():
            self.hud.hide()
        else:
            self.hud.show()
            self.hud.raise_()

    def _handle_mute(self) -> None:
        is_muted = self.on_toggle_mute()
        state = "Muted" if is_muted else "Idle"
        self.hud.set_state(state)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_hud()

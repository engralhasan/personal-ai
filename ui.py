"""
UI Module Root Entry & Exporter.
Allows direct imports via `import ui` or `from ui import JarvisHUDWidget`.
"""
from ui.ui import (
    UISignals,
    WaveformVisualizer,
    ConfirmationDialogWidget,
    JarvisHUDWidget,
    SystemTrayManager
)

__all__ = [
    "UISignals",
    "WaveformVisualizer",
    "ConfirmationDialogWidget",
    "JarvisHUDWidget",
    "SystemTrayManager"
]

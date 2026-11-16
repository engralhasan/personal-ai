"""
GUI & Screen Automation Tools.
Supports mouse/keyboard automation, window manipulation, full-screen capture,
and visual OCR screen reading.
"""

from __future__ import annotations
import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import config, RiskLevel

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.2
except ImportError:
    pyautogui = None

try:
    from PIL import Image
except ImportError:
    Image = None


def take_screenshot(filename: Optional[str] = None) -> str:
    """
    Captures a full screenshot of the desktop and saves it to disk.
    """
    if not pyautogui:
        return "pyautogui is not installed. Run: pip install pyautogui Pillow"
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_name = filename or f"screenshot_{ts}.png"
        if not target_name.endswith(".png"):
            target_name += ".png"
        filepath = config.storage.screenshots_dir / target_name
        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        return f"Screenshot successfully saved to: {filepath.resolve()}"
    except Exception as e:
        logger.error(f"Failed to capture screenshot: {e}")
        return f"Error taking screenshot: {str(e)}"


def click_mouse(x: int, y: int, button: str = "left", double_click: bool = False) -> str:
    """
    Moves mouse to coordinates (x, y) and performs a click.
    """
    if not pyautogui:
        return "pyautogui is not installed. Run: pip install pyautogui"
    try:
        screen_w, screen_h = pyautogui.size()
        if not (0 <= x <= screen_w and 0 <= y <= screen_h):
            return f"Coordinates ({x}, {y}) out of screen bounds ({screen_w}x{screen_h})."

        pyautogui.moveTo(x, y, duration=0.3)
        if double_click:
            pyautogui.doubleClick(x, y, button=button)
            return f"Double-clicked {button} button at ({x}, {y})."
        else:
            pyautogui.click(x, y, button=button)
            return f"Clicked {button} button at ({x}, {y})."
    except Exception as e:
        return f"Failed to perform mouse click: {str(e)}"


def type_text(text: str, press_enter: bool = False) -> str:
    """
    Types text into the currently active window/input field.
    """
    if not pyautogui:
        return "pyautogui is not installed. Run: pip install pyautogui"
    try:
        pyautogui.write(text, interval=0.02)
        if press_enter:
            pyautogui.press('enter')
        return f"Successfully typed text ({len(text)} characters)."
    except Exception as e:
        return f"Failed to type text: {str(e)}"


def press_hotkey(keys: str) -> str:
    """
    Presses a key combination (e.g., 'ctrl+c', 'ctrl+v', 'alt+tab', 'win+d', 'ctrl+shift+esc').
    """
    if not pyautogui:
        return "pyautogui is not installed. Run: pip install pyautogui"
    try:
        key_list = [k.strip().lower() for k in keys.split("+")]
        pyautogui.hotkey(*key_list)
        return f"Pressed hotkey combination: {keys}"
    except Exception as e:
        return f"Error executing hotkey '{keys}': {str(e)}"


def get_active_windows() -> str:
    """
    Lists titles of currently visible and active desktop application windows.
    """
    try:
        import pygetwindow as gw
        windows = gw.getAllTitles()
        clean_windows = [w.strip() for w in windows if w.strip()]
        if not clean_windows:
            return "No named windows currently detected."
        return "Active Windows:\n" + "\n".join(f"- {w}" for w in clean_windows[:15])
    except Exception as e:
        return f"Error retrieving window list: {str(e)}"


def focus_window(title_keyword: str) -> str:
    """
    Brings the first window matching title_keyword to the foreground.
    """
    try:
        import pygetwindow as gw
        matches = gw.getWindowsWithTitle(title_keyword)
        if not matches:
            return f"No open window matching '{title_keyword}' was found."
        target_win = matches[0]
        if target_win.isMinimized:
            target_win.restore()
        target_win.activate()
        return f"Brought window '{target_win.title}' to foreground."
    except Exception as e:
        return f"Failed to focus window: {str(e)}"


def read_screen_text() -> str:
    """
    Extracts text visible on the current screen using OCR (Tesseract).
    """
    try:
        import pytesseract
        screenshot = pyautogui.screenshot()
        text = pytesseract.image_to_string(screenshot)
        clean_text = text.strip()
        if not clean_text:
            return "OCR completed: No readable text found on current screen."
        # Truncate if excessively long
        preview = clean_text[:1500]
        return f"Screen OCR Result:\n{preview}..."
    except ImportError:
        return "pytesseract library not available. Please install 'pytesseract' and the Tesseract-OCR binary."
    except Exception as e:
        return f"Failed to OCR screen: {str(e)}"


# Register with Tool Registry
from tools import registry

registry.register("take_screenshot", "Captures desktop screenshot and returns file path.", RiskLevel.SAFE_EXECUTION)(take_screenshot)
registry.register("click_mouse", "Moves mouse to (x, y) and clicks.", RiskLevel.SAFE_EXECUTION)(click_mouse)
registry.register("type_text", "Types text into the active focused window.", RiskLevel.SAFE_EXECUTION)(type_text)
registry.register("press_hotkey", "Executes keyboard hotkey combination (e.g., 'alt+tab', 'ctrl+s').", RiskLevel.SAFE_EXECUTION)(press_hotkey)
registry.register("get_active_windows", "Lists titles of all currently visible application windows.", RiskLevel.READ_ONLY)(get_active_windows)
registry.register("focus_window", "Brings a window matching keyword to the foreground.", RiskLevel.SAFE_EXECUTION)(focus_window)
registry.register("read_screen_text", "Performs optical character recognition (OCR) on screen.", RiskLevel.READ_ONLY)(read_screen_text)

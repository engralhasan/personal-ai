"""
Tools Package Root Entry & Exporter.
Allows direct imports via `import tools` or `from tools import registry`.
"""
from tools import (
    ToolDefinition,
    ToolRegistry,
    registry
)
from tools.system_tools import *
from tools.gui_tools import *
from tools.file_tools import *
from tools.web_tools import *
from tools.terminal_tools import *

__all__ = [
    "ToolDefinition",
    "ToolRegistry",
    "registry",
    "open_application",
    "close_application",
    "set_volume",
    "get_volume",
    "set_brightness",
    "get_system_status",
    "lock_workstation",
    "system_power_control",
    "take_screenshot",
    "click_mouse",
    "type_text",
    "press_hotkey",
    "get_active_windows",
    "focus_window",
    "read_screen_text",
    "search_files",
    "read_file_content",
    "write_file_content",
    "delete_file",
    "organize_directory",
    "web_search",
    "open_browser_url",
    "scrape_webpage",
    "execute_terminal_command"
]

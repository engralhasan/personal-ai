"""
System & OS Automation Tools.
Enables application launching/closing, volume/brightness control,
system telemetry inspection, and power management (shutdown, restart, lock).
"""

from __future__ import annotations
import os
import sys
import subprocess
import ctypes
import logging
from typing import Dict, Any, List
try:
    import psutil
except ImportError:
    psutil = None
from config import RiskLevel
from core.security import RiskLevel

logger = logging.getLogger("JARVIS.Tools.System")


def open_application(app_name: str) -> str:
    """
    Launches a desktop application by name or common alias (e.g., 'notepad', 'calculator', 'chrome', 'spotify', 'code').
    """
    app_lower = app_name.lower().strip()
    alias_map = {
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "notepad": "notepad.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "powershell": "powershell.exe",
        "explorer": "explorer.exe",
        "files": "explorer.exe",
        "task manager": "taskmgr.exe",
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "firefox": "firefox.exe",
        "code": "code.cmd",
        "vscode": "code.cmd",
        "spotify": "spotify.exe"
    }

    target = alias_map.get(app_lower, app_name)
    try:
        if sys.platform == "win32":
            # Attempt direct execution or start command
            subprocess.Popen(f"start {target}", shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", target])
        else:
            subprocess.Popen([target])
        return f"Successfully launched '{app_name}' ({target})."
    except Exception as e:
        logger.error(f"Failed to launch application '{app_name}': {e}")
        return f"Failed to launch '{app_name}': {str(e)}"


def close_application(process_name: str) -> str:
    """
    Terminates running processes matching the specified name or common application aliases.
    """
    if not psutil:
        return "psutil library is required for process management. Please run: pip install psutil"

    raw_target = process_name.lower().replace(".exe", "").strip()

    alias_map = {
        "calculator": ["calculatorapp", "calculator", "calc"],
        "calc": ["calculatorapp", "calculator", "calc"],
        "ক্যালকুলেটর": ["calculatorapp", "calculator", "calc"],
        "notepad": ["notepad"],
        "নোটপ্যাড": ["notepad"],
        "chrome": ["chrome"],
        "ক্রোম": ["chrome"],
        "edge": ["msedge"],
        "browser": ["chrome", "msedge", "firefox"],
        "ব্রাউজার": ["chrome", "msedge", "firefox"],
        "spotify": ["spotify"],
        "code": ["code"],
        "vscode": ["code"],
        "word": ["winword"],
        "excel": ["excel"],
        "task manager": ["taskmgr"],
        "taskmgr": ["taskmgr"]
    }

    targets = alias_map.get(raw_target, [raw_target])
    killed = 0

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            p_name = proc.info['name'].lower().replace(".exe", "")
            for t in targets:
                if t in p_name:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.5)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed += 1
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Fallback via Windows taskkill if psutil encountered access boundaries on UWP apps
    if killed == 0 and sys.platform == "win32":
        for t in targets:
            res = subprocess.run(["taskkill", "/F", "/IM", f"{t}.exe"], capture_output=True, text=True)
            if res.returncode == 0:
                killed += 1

    if killed > 0:
        return f"Successfully closed {killed} instance(s) matching '{process_name}'."
    return f"No active process found matching '{process_name}'."


def set_volume(level: int) -> str:
    """
    Adjusts the master audio volume level (0 to 100).
    """
    level = max(0, min(100, level))
    try:
        if sys.platform == "win32":
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                # Scalar volume is between 0.0 and 1.0
                volume.SetMasterVolumeLevelScalar(level / 100.0, None)
                return f"System volume set to {level}%."
            except Exception:
                # Fallback to PowerShell script
                ps_cmd = f"$obj = New-Object -ComObject WScript.Shell; 1..50 | % {{ $obj.SendKeys([char]174) }}; 1..{level // 2} | % {{ $obj.SendKeys([char]175) }}"
                subprocess.run(["powershell", "-Command", ps_cmd], check=False)
                return f"Adjusted volume to approx {level}% via script."
        return f"Volume control not implemented for platform {sys.platform}."
    except Exception as e:
        return f"Error setting volume: {str(e)}"


def get_volume() -> str:
    """
    Gets the current master volume percentage.
    """
    try:
        if sys.platform == "win32":
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            current = int(round(volume.GetMasterVolumeLevelScalar() * 100))
            is_muted = volume.GetMute() == 1
            return f"Current volume: {current}%{' (Muted)' if is_muted else ''}."
        return "Volume detection is only supported on Windows in this build."
    except Exception as e:
        return f"Could not determine current volume: {str(e)}"


def set_brightness(level: int) -> str:
    """
    Sets the display brightness level (0 to 100).
    """
    level = max(0, min(100, level))
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
        return f"Display brightness set to {level}%."
    except Exception as e:
        # Fallback to WMI PowerShell on Windows
        if sys.platform == "win32":
            ps_cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
            res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True)
            if res.returncode == 0:
                return f"Display brightness set to {level}% via WMI."
        return f"Failed to set brightness: {str(e)}"


def get_system_status() -> str:
    """
    Retrieves real-time system performance telemetry: CPU, RAM, battery, and disk stats.
    """
    if not psutil:
        return "psutil is not installed. System performance metrics require: pip install psutil"

    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    battery_info = "Desktop / No battery"
    if hasattr(psutil, "sensors_battery"):
        bat = psutil.sensors_battery()
        if bat:
            plugged = "Plugged in" if bat.power_plugged else "On battery"
            battery_info = f"{bat.percent}% ({plugged})"

    return (
        f"🖥️ System Health Metrics:\n"
        f"- CPU Usage: {cpu_percent}%\n"
        f"- RAM Usage: {mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)\n"
        f"- Disk Space: {disk.percent}% used ({disk.free // (1024**3)}GB free)\n"
        f"- Battery: {battery_info}"
    )


def lock_workstation() -> str:
    """
    Instantly locks the Windows computer workstation.
    """
    if sys.platform == "win32":
        ctypes.windll.user32.LockWorkStation()
        return "Workstation locked successfully."
    return "Locking workstation is only supported on Windows."


def system_power_control(action: str) -> str:
    """
    Controls computer power states: 'shutdown', 'restart', 'sleep'.
    Requires explicit Human-in-the-Loop confirmation.
    """
    action_clean = action.lower().strip()
    if action_clean == "shutdown":
        if sys.platform == "win32":
            subprocess.run(["shutdown", "/s", "/t", "10"], check=False)
            return "Shutdown sequence initiated (10 second timer)."
        subprocess.run(["shutdown", "-h", "now"], check=False)
        return "System shutdown initiated."

    elif action_clean == "restart":
        if sys.platform == "win32":
            subprocess.run(["shutdown", "/r", "/t", "10"], check=False)
            return "Restart sequence initiated (10 second timer)."
        subprocess.run(["reboot"], check=False)
        return "System reboot initiated."

    elif action_clean == "sleep":
        if sys.platform == "win32":
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)
            return "Putting computer to sleep."
        return "Sleep action not configured for this OS."

    return f"Unrecognized power action '{action}'. Options: shutdown, restart, sleep."


# Register with Tool Registry
from tools import registry

registry.register("open_application", "Opens a desktop application by name or alias.", RiskLevel.SAFE_EXECUTION)(open_application)
registry.register("close_application", "Closes a running desktop application or process.", RiskLevel.SAFE_EXECUTION)(close_application)
registry.register("set_volume", "Sets the system audio volume from 0 to 100.", RiskLevel.SAFE_EXECUTION)(set_volume)
registry.register("get_volume", "Reads current system volume level and mute status.", RiskLevel.READ_ONLY)(get_volume)
registry.register("set_brightness", "Sets the screen brightness from 0 to 100.", RiskLevel.SAFE_EXECUTION)(set_brightness)
registry.register("get_system_status", "Returns CPU, RAM, disk, and battery telemetry.", RiskLevel.READ_ONLY)(get_system_status)
registry.register("lock_workstation", "Locks the desktop workstation immediately.", RiskLevel.SAFE_EXECUTION)(lock_workstation)
registry.register(
    "system_power_control",
    "Triggers shutdown, restart, or sleep. HIGH RISK: Requires user confirmation.",
    RiskLevel.HIGH_RISK_DESTRUCTIVE,
    requires_confirmation=True
)(system_power_control)

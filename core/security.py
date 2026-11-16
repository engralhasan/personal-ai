"""
Security, Guardrails & Human-in-the-Loop Confirmation Gate.
Ensures destructive, high-risk, or system-altering actions require explicit user approval.
"""

from __future__ import annotations
import logging
import threading
import time
from typing import Callable, Optional, Dict, Any, Tuple
from config import config, RiskLevel

logger = logging.getLogger("JARVIS.Security")


class SecurityViolationError(PermissionError):
    """Raised when an operation violates security policies."""
    pass


class ActionRejectedError(Exception):
    """Raised when the user denies confirmation for a high-risk action."""
    pass


class ConfirmationGate:
    """
    Thread-safe Human-in-the-Loop approval gate.
    Coordinates approval requests across the GUI and voice interfaces.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._pending_event = threading.Event()
        self._approval_status: Optional[bool] = None
        self._current_prompt: Optional[str] = None
        self._ui_callback: Optional[Callable[[str, int], None]] = None
        self._voice_callback: Optional[Callable[[str], bool]] = None

    def register_ui_handler(self, callback: Callable[[str, int], None]) -> None:
        """Register the UI dialog handler: fn(prompt_text, timeout_sec)."""
        self._ui_callback = callback

    def register_voice_handler(self, callback: Callable[[str], bool]) -> None:
        """Register the Voice prompt handler: fn(prompt_text) -> bool."""
        self._voice_callback = callback

    def request_approval(self, action_name: str, details: Dict[str, Any], risk_reason: str) -> bool:
        """
        Pauses the caller thread and requests explicit user approval.
        Returns True if approved, False if denied or timed out.
        """
        with self._lock:
            self._pending_event.clear()
            self._approval_status = None
            prompt = (
                f"⚠️ SECURITY GATE: High-Risk Action Detected!\n"
                f"Action: {action_name}\n"
                f"Details: {details}\n"
                f"Reason: {risk_reason}\n"
                f"Do you authorize this operation?"
            )
            self._current_prompt = prompt
            logger.warning(f"Requesting confirmation for '{action_name}': {risk_reason}")

            # Notify UI if available
            if self._ui_callback:
                try:
                    self._ui_callback(prompt, config.security.confirmation_timeout_seconds)
                except Exception as e:
                    logger.error(f"Failed to trigger UI confirmation callback: {e}")

            # Try voice prompt if handler registered
            if self._voice_callback and not self._ui_callback:
                try:
                    voice_approved = self._voice_callback(
                        f"Security confirmation required. Do you authorize executing {action_name}?"
                    )
                    self.submit_decision(voice_approved)
                except Exception as e:
                    logger.error(f"Failed to trigger Voice confirmation callback: {e}")

            # Wait for decision or timeout
            timed_out = not self._pending_event.wait(timeout=config.security.confirmation_timeout_seconds)

            if timed_out:
                logger.warning(f"Confirmation timed out after {config.security.confirmation_timeout_seconds}s. Action rejected.")
                self._approval_status = False

            return bool(self._approval_status)

    def submit_decision(self, approved: bool) -> None:
        """Called by UI or voice recognizer when user approves/denies."""
        self._approval_status = approved
        self._pending_event.set()


class SecurityValidator:
    """
    Validates tool calls, checks for destructive command sequences,
    and determines risk classification.
    """

    @staticmethod
    def inspect_command(command_str: str) -> Tuple[RiskLevel, str]:
        """Examines shell command string against safety blacklist."""
        cmd_lower = command_str.lower().strip()

        # Check explicit high-risk keywords
        for keyword in config.security.destructive_command_keywords:
            if keyword in cmd_lower:
                return (
                    RiskLevel.HIGH_RISK_DESTRUCTIVE,
                    f"Command contains dangerous pattern '{keyword}'"
                )

        # Dangerous system modifications
        if any(term in cmd_lower for term in [":(){ :|:& };:", "del /f", "rm -rf", "reg delete"]):
            return (
                RiskLevel.HIGH_RISK_DESTRUCTIVE,
                "Command attempts catastrophic system/registry file deletion"
            )

        return RiskLevel.SAFE_EXECUTION, "Standard terminal command"

    @staticmethod
    def inspect_file_action(action: str, file_path: str) -> Tuple[RiskLevel, str]:
        """Examines file system operations for destructive potential."""
        action_lower = action.lower()
        if "delete" in action_lower or "remove" in action_lower:
            return (
                RiskLevel.HIGH_RISK_DESTRUCTIVE,
                f"Permanent deletion requested for '{file_path}'"
            )
        if "overwrite" in action_lower:
            return (
                RiskLevel.HIGH_RISK_DESTRUCTIVE,
                f"Overwriting content of '{file_path}'"
            )
        return RiskLevel.SAFE_EXECUTION, "Safe file read or write"


# Global security gate singleton
security_gate = ConfirmationGate()
security_validator = SecurityValidator()

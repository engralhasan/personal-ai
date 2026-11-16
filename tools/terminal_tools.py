"""
Terminal & Shell Execution Tools.
Safely executes shell/terminal commands with timeouts, output capture,
and security validation against destructive commands.
"""

from __future__ import annotations
import subprocess
import sys
import logging
from typing import Optional
from config import RiskLevel, config
from core.security import security_gate, security_validator, RiskLevel

logger = logging.getLogger("JARVIS.Tools.Terminal")


def execute_terminal_command(command: str, timeout: int = 30) -> str:
    """
    Executes a shell or terminal command and captures the output.
    HIGH RISK: If destructive or altering command patterns are detected, requires explicit confirmation.
    """
    cmd_clean = command.strip()
    if not cmd_clean:
        return "Error: Empty command provided."

    # Inspect command risk level
    risk, reason = security_validator.inspect_command(cmd_clean)
    if risk == RiskLevel.HIGH_RISK_DESTRUCTIVE or config.security.require_confirmation_for_destructive:
        if risk == RiskLevel.HIGH_RISK_DESTRUCTIVE:
            approved = security_gate.request_approval(
                action_name="execute_terminal_command",
                details={"command": cmd_clean},
                risk_reason=reason
            )
            if not approved:
                return f"ACTION_DENIED: Execution of command '{cmd_clean}' was rejected by user."

    logger.info(f"Executing terminal command: {cmd_clean}")
    try:
        shell_executable = "powershell.exe" if sys.platform == "win32" else "/bin/bash"

        result = subprocess.run(
            cmd_clean,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            executable=shell_executable if sys.platform == "win32" else None
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        output_parts = []
        if stdout:
            output_parts.append(f"[STDOUT]\n{stdout}")
        if stderr:
            output_parts.append(f"[STDERR]\n{stderr}")

        exit_code = result.returncode
        status_line = f"Process exited with code {exit_code}."

        if not output_parts:
            return f"Command executed successfully with no output. {status_line}"

        return f"{status_line}\n" + "\n\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing terminal command: {str(e)}"


# Register with Tool Registry
from tools import registry

registry.register(
    "execute_terminal_command",
    "Executes a CLI terminal command. HIGH RISK if modifying/deleting system files.",
    RiskLevel.HIGH_RISK_DESTRUCTIVE,
    requires_confirmation=False # Handled dynamically inside inspect_command
)(execute_terminal_command)

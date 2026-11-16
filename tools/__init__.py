"""
Tools Registry and Orchestrator.
Exposes standard OpenAI/LiteLLM function calling schemas and routes tool execution
through the Human-in-the-Loop Confirmation Gate.
"""

from __future__ import annotations
import inspect
import json
import logging
from typing import Callable, Dict, Any, List, Optional
from config import RiskLevel
from core.security import security_gate, RiskLevel

logger = logging.getLogger("JARVIS.Tools")


class ToolDefinition:
    """Encapsulates a callable tool function, its metadata, and schema."""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        risk_level: RiskLevel = RiskLevel.SAFE_EXECUTION,
        requires_confirmation: bool = False
    ):
        self.name = name
        self.description = description
        self.func = func
        self.risk_level = risk_level
        self.requires_confirmation = requires_confirmation
        self.schema = self._generate_openai_schema()

    def _generate_openai_schema(self) -> Dict[str, Any]:
        """Auto-generates OpenAI-compliant function call JSON schema from function signature and docstrings."""
        sig = inspect.signature(self.func)
        properties = {}
        required = []

        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }

        for param_name, param in sig.parameters.items():
            if param_name in ["self", "cls"]:
                continue

            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                param_type = type_mapping.get(param.annotation, "string")

            prop_def: Dict[str, Any] = {
                "type": param_type,
                "description": f"Parameter: {param_name}"
            }

            if param.default == inspect.Parameter.empty:
                required.append(param_name)
            else:
                prop_def["default"] = param.default

            properties[param_name] = prop_def

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


class ToolRegistry:
    """Central catalog of callable system tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        risk_level: RiskLevel = RiskLevel.SAFE_EXECUTION,
        requires_confirmation: bool = False
    ):
        """Decorator to register functions as executable tools."""
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_desc = description or (func.__doc__ or "No description provided").strip()
            definition = ToolDefinition(
                name=tool_name,
                description=tool_desc,
                func=func,
                risk_level=risk_level,
                requires_confirmation=requires_confirmation
            )
            self._tools[tool_name] = definition
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def get_openai_schemas(self) -> List[Dict[str, Any]]:
        """Returns the list of all registered tool schemas formatted for LiteLLM/OpenAI."""
        return [tool.schema for tool in self._tools.values()]

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Executes tool with parameter parsing, safety gate checks, and error wrapping.
        """
        tool = self.get_tool(name)
        if not tool:
            return f"Error: Tool '{name}' is not recognized in J.A.R.V.I.S. tool registry."

        logger.info(f"Invoking tool '{name}' with arguments: {arguments}")

        # Human-in-the-Loop Confirmation Gate verification
        if tool.requires_confirmation or tool.risk_level == RiskLevel.HIGH_RISK_DESTRUCTIVE:
            approved = security_gate.request_approval(
                action_name=name,
                details=arguments,
                risk_reason="This action is classified as potentially destructive or high-risk."
            )
            if not approved:
                logger.warning(f"Execution of '{name}' aborted: User rejected confirmation.")
                return f"ACTION_DENIED: The user denied authorization to execute '{name}'."

        try:
            result = tool.func(**arguments)
            # Serialize result to JSON string if it's a dict or list
            if isinstance(result, (dict, list)):
                return json.dumps(result, indent=2, ensure_ascii=False)
            return str(result)
        except Exception as e:
            logger.exception(f"Exception during execution of tool '{name}': {e}")
            return f"Error executing tool '{name}': {str(e)}"


# Global tools registry singleton
registry = ToolRegistry()

# Import tool modules to trigger registration decorators
from tools.system_tools import *
from tools.gui_tools import *
from tools.file_tools import *
from tools.web_tools import *
from tools.terminal_tools import *

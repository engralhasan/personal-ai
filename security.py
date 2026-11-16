"""
Security & Guardrails Root Entry & Exporter.
Allows direct imports via `import security` or `from security import security_gate`.
"""
from core.security import (
    ConfirmationGate,
    SecurityValidator,
    SecurityViolationError,
    ActionRejectedError,
    security_gate,
    security_validator,
    RiskLevel
)

__all__ = [
    "ConfirmationGate",
    "SecurityValidator",
    "SecurityViolationError",
    "ActionRejectedError",
    "security_gate",
    "security_validator",
    "RiskLevel"
]

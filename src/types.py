"""Shared type definitions for the Context Register."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional


@dataclass(frozen=True)
class RegisterState:
    """Immutable snapshot of the register's current state at a point in time."""

    active_domain: Optional[str] = None
    active_device: Optional[str] = None
    last_action: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    turn_counter: int = 0
    timestamp: Optional[float] = None


@dataclass
class RoutingResult:
    """Output from the router or the LLM's response."""

    action_name: str
    domain: Optional[str] = None
    device: Optional[str] = None
    confidence: float = 0.0
    parameters: Optional[Dict[str, Any]] = None
    source: Literal["router", "llm"] = "router"


@dataclass
class EnrichedInput:
    """Result of the enrichment step with context metadata."""

    original_utterance: str
    enriched_utterance: str
    context_applied: bool
    register_state: RegisterState = field(default_factory=RegisterState)


class ExpiryReason(enum.Enum):
    """Reason why the register was cleared."""

    TURN_LIMIT = "turn_limit"
    DOMAIN_CHANGE = "domain_change"
    TIME_ELAPSED = "time_elapsed"
    MANUAL = "manual"

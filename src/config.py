"""Configuration dataclass for the Context Register."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RegisterConfig:
    """All configurable parameters with sensible defaults.

    A developer can instantiate with zero arguments and have it work correctly.
    """

    max_turns: int = 3
    max_elapsed_seconds: float = 120.0
    enable_duckling: bool = True
    duckling_url: str = "http://localhost:8000"
    duckling_timeout_ms: float = 50.0
    duckling_dimensions: List[str] = field(
        default_factory=lambda: [
            "temperature",
            "time",
            "duration",
            "number",
            "quantity",
        ]
    )
    context_prefix_format: str = "[context: {slots}]"
    slot_separator: str = ", "
    enable_persistence: bool = False
    persistence_path: Optional[str] = None

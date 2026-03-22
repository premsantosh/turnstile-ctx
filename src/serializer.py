"""Optional state persistence for the Context Register."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from src.config import RegisterConfig
from src.types import RegisterState

logger = logging.getLogger(__name__)


class StateSerializer:
    """Serializes and deserializes RegisterState to/from JSON files."""

    def __init__(self, config: RegisterConfig) -> None:
        self._config = config

    def save(self, state: RegisterState, path: str) -> bool:
        """Serialize RegisterState to JSON. Returns True on success, False on failure. Never raises."""
        try:
            data: Dict[str, Any] = {
                "active_domain": state.active_domain,
                "active_device": state.active_device,
                "last_action": state.last_action,
                "parameters": state.parameters,
                "turn_counter": state.turn_counter,
                "timestamp": state.timestamp,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            logger.warning("Failed to save register state to %s", path)
            return False

    def load(
        self, path: str, max_elapsed_seconds: float = 120.0
    ) -> Optional[RegisterState]:
        """Load RegisterState from JSON. Returns None on any failure or if state is stale. Never raises."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)

            state = RegisterState(
                active_domain=data.get("active_domain"),
                active_device=data.get("active_device"),
                last_action=data.get("last_action"),
                parameters=data.get("parameters"),
                turn_counter=data.get("turn_counter", 0),
                timestamp=data.get("timestamp"),
            )

            # Check time-based staleness
            if state.timestamp is not None:
                if (time.time() - state.timestamp) > max_elapsed_seconds:
                    logger.info("Loaded state is stale; discarding")
                    return None

            return state
        except FileNotFoundError:
            return None
        except Exception:
            logger.warning("Failed to load register state from %s", path)
            return None

"""Expiry condition evaluation for the Context Register."""

from __future__ import annotations

import time
from typing import Optional

from src.config import RegisterConfig
from src.types import ExpiryReason, RegisterState


class ExpiryEvaluator:
    """Evaluates whether the register should be cleared before a new turn."""

    def check(
        self,
        state: RegisterState,
        config: RegisterConfig,
        new_domain: Optional[str] = None,
    ) -> Optional[ExpiryReason]:
        """Evaluate all expiry conditions in priority order.

        Returns the first triggered condition, or None if the register should be kept.
        Evaluation order: time-based -> turn-based -> domain change.
        """
        if _is_empty(state):
            return None

        if (
            state.timestamp is not None
            and (time.time() - state.timestamp) > config.max_elapsed_seconds
        ):
            return ExpiryReason.TIME_ELAPSED

        if state.turn_counter >= config.max_turns:
            return ExpiryReason.TURN_LIMIT

        if (
            new_domain is not None
            and state.active_domain is not None
            and new_domain != state.active_domain
        ):
            return ExpiryReason.DOMAIN_CHANGE

        return None


def _is_empty(state: RegisterState) -> bool:
    """Check if all content slots are None."""
    return (
        state.active_domain is None
        and state.active_device is None
        and state.last_action is None
        and state.parameters is None
    )

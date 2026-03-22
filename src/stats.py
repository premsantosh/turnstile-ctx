"""Observability / metrics for the Context Register."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.types import ExpiryReason


class Stats:
    """Tracks usage metrics for debugging and research evaluation."""

    def __init__(self) -> None:
        self.total_enrich_calls: int = 0
        self.context_applied_count: int = 0
        self.context_empty_count: int = 0
        self.total_update_calls: int = 0
        self.expiry_count_by_reason: Dict[ExpiryReason, int] = {
            reason: 0 for reason in ExpiryReason
        }
        self.duckling_success_count: int = 0
        self.duckling_failure_count: int = 0
        self.duckling_skip_count: int = 0

    def record_enrich(self, context_applied: bool) -> None:
        self.total_enrich_calls += 1
        if context_applied:
            self.context_applied_count += 1
        else:
            self.context_empty_count += 1

    def record_update(self) -> None:
        self.total_update_calls += 1

    def record_expiry(self, reason: ExpiryReason) -> None:
        self.expiry_count_by_reason[reason] += 1

    def record_duckling_success(self) -> None:
        self.duckling_success_count += 1

    def record_duckling_failure(self) -> None:
        self.duckling_failure_count += 1

    def record_duckling_skip(self) -> None:
        self.duckling_skip_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Return all metrics as a flat dictionary with computed fields."""
        context_hit_rate: float = 0.0
        if self.total_enrich_calls > 0:
            context_hit_rate = self.context_applied_count / self.total_enrich_calls

        duckling_total = self.duckling_success_count + self.duckling_failure_count
        duckling_success_rate: Optional[float] = None
        if duckling_total > 0:
            duckling_success_rate = self.duckling_success_count / duckling_total

        return {
            "total_enrich_calls": self.total_enrich_calls,
            "context_applied_count": self.context_applied_count,
            "context_empty_count": self.context_empty_count,
            "total_update_calls": self.total_update_calls,
            "expiry_count_by_reason": {
                reason.value: count
                for reason, count in self.expiry_count_by_reason.items()
            },
            "duckling_success_count": self.duckling_success_count,
            "duckling_failure_count": self.duckling_failure_count,
            "duckling_skip_count": self.duckling_skip_count,
            "context_hit_rate": context_hit_rate,
            "duckling_success_rate": duckling_success_rate,
        }

    def reset(self) -> None:
        """Reset all counters to zero."""
        self.total_enrich_calls = 0
        self.context_applied_count = 0
        self.context_empty_count = 0
        self.total_update_calls = 0
        self.expiry_count_by_reason = {reason: 0 for reason in ExpiryReason}
        self.duckling_success_count = 0
        self.duckling_failure_count = 0
        self.duckling_skip_count = 0

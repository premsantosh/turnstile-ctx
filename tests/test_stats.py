"""Tests for observability / stats module."""

from src.stats import Stats
from src.types import ExpiryReason


class TestStats:
    def setup_method(self) -> None:
        self.stats = Stats()

    def test_initial_stats_zero(self) -> None:
        d = self.stats.to_dict()
        assert d["total_enrich_calls"] == 0
        assert d["context_applied_count"] == 0
        assert d["context_empty_count"] == 0
        assert d["total_update_calls"] == 0
        assert d["duckling_success_count"] == 0
        assert d["duckling_failure_count"] == 0
        assert d["duckling_skip_count"] == 0
        assert d["context_hit_rate"] == 0.0
        assert d["duckling_success_rate"] is None

    def test_context_applied_increments(self) -> None:
        self.stats.record_enrich(context_applied=True)
        assert self.stats.context_applied_count == 1
        assert self.stats.total_enrich_calls == 1

    def test_context_empty_increments(self) -> None:
        self.stats.record_enrich(context_applied=False)
        assert self.stats.context_empty_count == 1
        assert self.stats.total_enrich_calls == 1

    def test_expiry_counts_by_reason(self) -> None:
        self.stats.record_expiry(ExpiryReason.TURN_LIMIT)
        self.stats.record_expiry(ExpiryReason.TIME_ELAPSED)
        self.stats.record_expiry(ExpiryReason.TIME_ELAPSED)
        d = self.stats.to_dict()
        assert d["expiry_count_by_reason"]["turn_limit"] == 1
        assert d["expiry_count_by_reason"]["time_elapsed"] == 2

    def test_hit_rate_computation(self) -> None:
        self.stats.record_enrich(context_applied=True)
        self.stats.record_enrich(context_applied=True)
        self.stats.record_enrich(context_applied=False)
        d = self.stats.to_dict()
        assert abs(d["context_hit_rate"] - 2.0 / 3.0) < 1e-9

    def test_duckling_success_rate(self) -> None:
        self.stats.record_duckling_success()
        self.stats.record_duckling_success()
        self.stats.record_duckling_failure()
        d = self.stats.to_dict()
        assert abs(d["duckling_success_rate"] - 2.0 / 3.0) < 1e-9

    def test_reset_clears_all(self) -> None:
        self.stats.record_enrich(context_applied=True)
        self.stats.record_update()
        self.stats.record_expiry(ExpiryReason.MANUAL)
        self.stats.record_duckling_success()
        self.stats.reset()
        d = self.stats.to_dict()
        assert d["total_enrich_calls"] == 0
        assert d["total_update_calls"] == 0
        assert d["duckling_success_count"] == 0
        assert all(v == 0 for v in d["expiry_count_by_reason"].values())

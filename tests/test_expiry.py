"""Tests for expiry logic."""

import time

from src.config import RegisterConfig
from src.expiry import ExpiryEvaluator
from src.types import ExpiryReason, RegisterState


def _make_state(**kwargs: object) -> RegisterState:
    return RegisterState(**kwargs)  # type: ignore[arg-type]


class TestExpiryEvaluator:
    def setup_method(self) -> None:
        self.evaluator = ExpiryEvaluator()
        self.config = RegisterConfig()

    def test_empty_state_no_expiry(self) -> None:
        state = RegisterState()
        assert self.evaluator.check(state, self.config) is None

    def test_turn_limit_reached(self) -> None:
        state = _make_state(
            active_domain="HVAC", turn_counter=3, timestamp=time.time()
        )
        assert self.evaluator.check(state, self.config) == ExpiryReason.TURN_LIMIT

    def test_turn_limit_not_reached(self) -> None:
        state = _make_state(
            active_domain="HVAC", turn_counter=2, timestamp=time.time()
        )
        assert self.evaluator.check(state, self.config) is None

    def test_time_elapsed(self) -> None:
        state = _make_state(
            active_domain="HVAC", timestamp=time.time() - 200
        )
        assert self.evaluator.check(state, self.config) == ExpiryReason.TIME_ELAPSED

    def test_time_not_elapsed(self) -> None:
        state = _make_state(
            active_domain="HVAC", timestamp=time.time() - 10
        )
        assert self.evaluator.check(state, self.config) is None

    def test_domain_change(self) -> None:
        state = _make_state(
            active_domain="HVAC", timestamp=time.time()
        )
        result = self.evaluator.check(state, self.config, new_domain="wine_cellar")
        assert result == ExpiryReason.DOMAIN_CHANGE

    def test_same_domain(self) -> None:
        state = _make_state(
            active_domain="HVAC", timestamp=time.time()
        )
        assert self.evaluator.check(state, self.config, new_domain="HVAC") is None

    def test_priority_order(self) -> None:
        """When multiple conditions are true, time-based is returned first."""
        state = _make_state(
            active_domain="HVAC",
            turn_counter=5,
            timestamp=time.time() - 200,
        )
        result = self.evaluator.check(state, self.config, new_domain="wine_cellar")
        assert result == ExpiryReason.TIME_ELAPSED

    def test_none_timestamp_skips_time_check(self) -> None:
        state = _make_state(
            active_domain="HVAC", turn_counter=1, timestamp=None
        )
        assert self.evaluator.check(state, self.config) is None

    def test_none_new_domain_skips_domain_check(self) -> None:
        state = _make_state(
            active_domain="HVAC", timestamp=time.time()
        )
        assert self.evaluator.check(state, self.config, new_domain=None) is None

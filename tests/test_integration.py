"""Multi-turn conversation integration tests."""

import time
from unittest.mock import patch

from src.config import RegisterConfig
from src.register import ContextRegister
from src.types import RoutingResult


def _no_duckling_config(**overrides: object) -> RegisterConfig:
    return RegisterConfig(enable_duckling=False, **overrides)  # type: ignore[arg-type]


class TestIntegrationBasicFollowUp:
    """Scenario 1: Basic follow-up across two turns."""

    def test_two_turn_hvac_followup(self) -> None:
        reg = ContextRegister(_no_duckling_config())

        # Turn 1: first utterance — register is empty
        enriched1 = reg.enrich("I'm feeling hot")
        assert enriched1.context_applied is False
        assert enriched1.enriched_utterance == "I'm feeling hot"

        # Route to HVAC/living_room_ac/power_on
        reg.update(
            RoutingResult(
                action_name="power_on",
                domain="HVAC",
                device="living_room_ac",
                confidence=0.95,
                source="router",
            ),
            "I'm feeling hot",
        )

        # Turn 2: follow-up — register has HVAC context
        enriched2 = reg.enrich("set it to 65 degrees")
        assert enriched2.context_applied is True
        assert "domain=HVAC" in enriched2.enriched_utterance
        assert "device=living_room_ac" in enriched2.enriched_utterance
        assert "action=power_on" in enriched2.enriched_utterance
        assert enriched2.enriched_utterance.endswith("set it to 65 degrees")

        # Update with new action
        reg.update(
            RoutingResult(
                action_name="temperature_set",
                domain="HVAC",
                device="living_room_ac",
                confidence=0.92,
                parameters={"temperature": 65},
                source="router",
            ),
            "set it to 65 degrees",
        )

        # Turn counter resets after update
        assert reg.get_state().turn_counter == 0


class TestIntegrationTurnBasedExpiry:
    """Scenario 2: Register expires after max_turns of no updates."""

    def test_turn_limit_expiry(self) -> None:
        reg = ContextRegister(_no_duckling_config(max_turns=3))

        # Turn 1: route to HVAC
        reg.update(
            RoutingResult(
                action_name="power_on", domain="HVAC", confidence=0.9, source="router"
            ),
            "turn on AC",
        )

        # Turns 2-4: three enrich calls without update (unrelated queries)
        reg.enrich("what's the weather")
        reg.enrich("tell me a joke")
        reg.enrich("what time is it")

        # Turn 5: expiry should have triggered (turn_counter=3 >= max_turns=3)
        enriched = reg.enrich("set temperature")
        assert enriched.context_applied is False
        assert enriched.enriched_utterance == "set temperature"


class TestIntegrationDomainChange:
    """Scenario 3: Domain change clears and repopulates register."""

    def test_domain_change_clears_register(self) -> None:
        reg = ContextRegister(_no_duckling_config())

        # Turn 1: HVAC
        reg.update(
            RoutingResult(
                action_name="power_on", domain="HVAC", confidence=0.9, source="router"
            ),
            "turn on the AC",
        )
        assert reg.get_state().active_domain == "HVAC"

        # Turn 2: wine_cellar — domain change triggers clear then repopulate
        reg.update(
            RoutingResult(
                action_name="temperature_query",
                domain="wine_cellar",
                confidence=0.88,
                source="router",
            ),
            "check the wine cellar temperature",
        )
        assert reg.get_state().active_domain == "wine_cellar"
        assert reg.get_state().last_action == "temperature_query"


class TestIntegrationTimeBasedExpiry:
    """Scenario 4: Register expires after max_elapsed_seconds."""

    def test_time_expiry(self) -> None:
        reg = ContextRegister(_no_duckling_config())

        # Turn 1: populate register
        reg.update(
            RoutingResult(
                action_name="power_on", domain="HVAC", confidence=0.9, source="router"
            ),
            "turn on AC",
        )

        # Simulate 121 seconds passing
        with patch("src.expiry.time.time", return_value=time.time() + 121):
            enriched = reg.enrich("set temperature")

        assert enriched.context_applied is False
        assert enriched.enriched_utterance == "set temperature"


class TestIntegrationDucklingFailure:
    """Scenario 5: Graceful degradation when Duckling fails."""

    def test_duckling_failure_still_populates_state(self) -> None:
        # Duckling disabled — simulates unavailable
        reg = ContextRegister(_no_duckling_config())

        reg.update(
            RoutingResult(
                action_name="temperature_set",
                domain="HVAC",
                device="living_room_ac",
                confidence=0.92,
                source="router",
            ),
            "set it to 65 degrees",
        )

        state = reg.get_state()
        assert state.active_domain == "HVAC"
        assert state.active_device == "living_room_ac"
        assert state.last_action == "temperature_set"
        # No Duckling, so no extracted params beyond what RoutingResult provides
        assert reg.is_empty is False


class TestIntegrationEmptyPassthrough:
    """Scenario 6: Empty register passthrough."""

    def test_empty_register_passthrough(self) -> None:
        reg = ContextRegister(_no_duckling_config())
        enriched = reg.enrich("turn on the lights")
        assert enriched.enriched_utterance == "turn on the lights"
        assert enriched.context_applied is False
        assert enriched.original_utterance == "turn on the lights"

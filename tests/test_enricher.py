"""Tests for input enrichment."""

from src.config import RegisterConfig
from src.enricher import Enricher
from src.types import RegisterState


class TestEnricher:
    def setup_method(self) -> None:
        self.enricher = Enricher()
        self.config = RegisterConfig()

    def test_empty_state_no_prefix(self) -> None:
        state = RegisterState()
        result = self.enricher.enrich(state, "turn on the lights", self.config)
        assert result.enriched_utterance == "turn on the lights"
        assert result.context_applied is False

    def test_full_state_all_slots(self) -> None:
        state = RegisterState(
            active_domain="HVAC",
            active_device="living_room_ac",
            last_action="power_on",
            parameters={"temperature": 65},
        )
        result = self.enricher.enrich(state, "set it to 65 degrees", self.config)
        assert "domain=HVAC" in result.enriched_utterance
        assert "device=living_room_ac" in result.enriched_utterance
        assert "action=power_on" in result.enriched_utterance
        assert "params=" in result.enriched_utterance
        assert result.enriched_utterance.endswith("set it to 65 degrees")
        assert result.context_applied is True

    def test_partial_state_only_domain(self) -> None:
        state = RegisterState(active_domain="HVAC")
        result = self.enricher.enrich(state, "what's the temperature", self.config)
        assert result.enriched_utterance == "[context: domain=HVAC] what's the temperature"
        assert result.context_applied is True

    def test_partial_state_domain_and_params(self) -> None:
        state = RegisterState(
            active_domain="wine_cellar",
            parameters={"temperature": 55},
        )
        result = self.enricher.enrich(state, "what about humidity", self.config)
        assert "domain=wine_cellar" in result.enriched_utterance
        assert "params=" in result.enriched_utterance
        assert "device=" not in result.enriched_utterance
        assert "action=" not in result.enriched_utterance

    def test_context_applied_flag(self) -> None:
        empty = RegisterState()
        populated = RegisterState(active_domain="HVAC")

        r1 = self.enricher.enrich(empty, "hello", self.config)
        r2 = self.enricher.enrich(populated, "hello", self.config)

        assert r1.context_applied is False
        assert r2.context_applied is True

    def test_special_characters_in_utterance(self) -> None:
        state = RegisterState(active_domain="HVAC")
        utterance = 'set it to "max" — 100% power! 🔥'
        result = self.enricher.enrich(state, utterance, self.config)
        assert result.enriched_utterance.endswith(utterance)
        assert result.context_applied is True

    def test_custom_format_template(self) -> None:
        config = RegisterConfig(context_prefix_format="<ctx:{slots}>")
        state = RegisterState(active_domain="security")
        result = self.enricher.enrich(state, "lock it", config)
        assert result.enriched_utterance == "<ctx:domain=security> lock it"

    def test_custom_separator(self) -> None:
        config = RegisterConfig(slot_separator=" | ")
        state = RegisterState(active_domain="HVAC", active_device="thermostat")
        result = self.enricher.enrich(state, "set temp", config)
        assert "domain=HVAC | device=thermostat" in result.enriched_utterance

    def test_register_state_snapshot_attached(self) -> None:
        state = RegisterState(active_domain="HVAC")
        result = self.enricher.enrich(state, "hello", self.config)
        assert result.register_state is state

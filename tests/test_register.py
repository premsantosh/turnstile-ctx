"""Tests for the core ContextRegister class."""

import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

from src.config import RegisterConfig
from src.register import ContextRegister
from src.types import RegisterState, RoutingResult


class TestContextRegister:
    def test_init_default_config(self) -> None:
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        state = reg.get_state()
        assert state.active_domain is None
        assert state.turn_counter == 0

    def test_init_custom_config(self) -> None:
        config = RegisterConfig(max_turns=10, enable_duckling=False)
        reg = ContextRegister(config)
        assert reg._config.max_turns == 10

    def test_is_empty_on_init(self) -> None:
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        assert reg.is_empty is True

    def test_update_populates_state(self) -> None:
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        reg.update(
            RoutingResult(
                action_name="power_on",
                domain="HVAC",
                device="living_room_ac",
                confidence=0.95,
                source="router",
            ),
            "turn on the AC",
        )
        state = reg.get_state()
        assert state.active_domain == "HVAC"
        assert state.active_device == "living_room_ac"
        assert state.last_action == "power_on"

    def test_is_empty_after_update(self) -> None:
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        reg.update(
            RoutingResult(action_name="power_on", domain="HVAC", confidence=0.9, source="router"),
            "turn on the AC",
        )
        assert reg.is_empty is False

    def test_clear_resets_state(self) -> None:
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        reg.update(
            RoutingResult(action_name="power_on", domain="HVAC", confidence=0.9, source="router"),
            "turn on the AC",
        )
        reg.clear()
        assert reg.is_empty is True
        state = reg.get_state()
        assert state.active_domain is None

    def test_get_state_returns_frozen(self) -> None:
        """RegisterState is frozen, so it cannot be mutated."""
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        reg.update(
            RoutingResult(action_name="power_on", domain="HVAC", confidence=0.9, source="router"),
            "test",
        )
        state = reg.get_state()
        try:
            state.active_domain = "hacked"  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass
        assert reg.get_state().active_domain == "HVAC"

    def test_enrich_never_raises(self) -> None:
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        with patch.object(reg._enricher, "enrich", side_effect=RuntimeError("boom")):
            result = reg.enrich("hello")
        assert result.enriched_utterance == "hello"
        assert result.context_applied is False

    def test_update_never_raises(self) -> None:
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        with patch.object(reg, "_extract_parameters", side_effect=RuntimeError("boom")):
            reg.update(
                RoutingResult(action_name="test", confidence=0.5, source="router"),
                "test utterance",
            )
        # Should not raise — state may be stale but no exception propagated

    def test_enrich_increments_turn_counter(self) -> None:
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        reg.update(
            RoutingResult(action_name="power_on", domain="HVAC", confidence=0.9, source="router"),
            "turn on AC",
        )
        assert reg.get_state().turn_counter == 0
        reg.enrich("next utterance")
        assert reg.get_state().turn_counter == 1
        reg.enrich("another")
        assert reg.get_state().turn_counter == 2

    def test_get_stats(self) -> None:
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        reg.enrich("hello")
        stats = reg.get_stats()
        assert stats["total_enrich_calls"] == 1
        assert stats["context_empty_count"] == 1

    def test_persistence_save_and_load(self) -> None:
        """Register with persistence enabled saves state and loads on init."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            config = RegisterConfig(
                enable_duckling=False,
                enable_persistence=True,
                persistence_path=path,
            )
            reg = ContextRegister(config)
            reg.update(
                RoutingResult(
                    action_name="power_on", domain="HVAC", confidence=0.9, source="router"
                ),
                "turn on AC",
            )
            # State should be persisted to disk
            assert os.path.exists(path)
            with open(path) as f:
                data = json.load(f)
            assert data["active_domain"] == "HVAC"

            # New register loads persisted state
            reg2 = ContextRegister(config)
            assert reg2.get_state().active_domain == "HVAC"
        finally:
            os.unlink(path)

    def test_persistence_save_failure_does_not_raise(self) -> None:
        config = RegisterConfig(
            enable_duckling=False,
            enable_persistence=True,
            persistence_path="/nonexistent_dir/state.json",
        )
        reg = ContextRegister(config)
        # update should not raise even if persistence fails
        reg.update(
            RoutingResult(action_name="test", confidence=0.5, source="router"),
            "test",
        )

    def test_extractor_init_failure(self) -> None:
        """If extractor init fails, register continues without it."""
        with patch("src.extractor.ParameterExtractor.__init__", side_effect=RuntimeError("no duckling")):
            config = RegisterConfig(enable_duckling=True)
            reg = ContextRegister(config)
            assert reg._extractor is None

    def test_extractor_returns_params(self) -> None:
        """When extractor returns parameters, they are merged into state."""
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        mock_ext = MagicMock()
        mock_ext.extract.return_value = {"temperature": 72, "unit": "fahrenheit"}
        reg._extractor = mock_ext

        reg.update(
            RoutingResult(
                action_name="temp_set",
                domain="HVAC",
                confidence=0.9,
                parameters={"mode": "cool"},
                source="router",
            ),
            "set it to 72 degrees",
        )
        state = reg.get_state()
        assert state.parameters is not None
        assert state.parameters["temperature"] == 72
        assert state.parameters["mode"] == "cool"

    def test_extractor_failure_still_populates_state(self) -> None:
        """When extractor raises, state is still populated without params."""
        reg = ContextRegister(RegisterConfig(enable_duckling=False))
        mock_ext = MagicMock()
        mock_ext.extract.side_effect = RuntimeError("duckling down")
        reg._extractor = mock_ext

        reg.update(
            RoutingResult(
                action_name="temp_set", domain="HVAC", confidence=0.9, source="router"
            ),
            "set it to 72 degrees",
        )
        state = reg.get_state()
        assert state.active_domain == "HVAC"
        stats = reg.get_stats()
        assert stats["duckling_failure_count"] == 1

    def test_serializer_init_failure(self) -> None:
        """If serializer init fails, register continues without persistence."""
        with patch("src.serializer.StateSerializer.__init__", side_effect=RuntimeError("disk error")):
            config = RegisterConfig(
                enable_duckling=False,
                enable_persistence=True,
                persistence_path="/tmp/test_state.json",
            )
            reg = ContextRegister(config)
            assert reg._serializer is None

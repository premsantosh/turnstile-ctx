"""Tests for state persistence."""

import json
import os
import tempfile
import time
from unittest.mock import patch

from src.config import RegisterConfig
from src.serializer import StateSerializer
from src.types import RegisterState


class TestStateSerializer:
    def setup_method(self) -> None:
        self.config = RegisterConfig()
        self.serializer = StateSerializer(self.config)

    def test_save_and_load_roundtrip(self) -> None:
        state = RegisterState(
            active_domain="HVAC",
            active_device="living_room_ac",
            last_action="power_on",
            parameters={"temperature": 65},
            turn_counter=1,
            timestamp=time.time(),
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            assert self.serializer.save(state, path) is True
            loaded = self.serializer.load(path)
            assert loaded is not None
            assert loaded.active_domain == "HVAC"
            assert loaded.active_device == "living_room_ac"
            assert loaded.last_action == "power_on"
            assert loaded.parameters == {"temperature": 65}
            assert loaded.turn_counter == 1
        finally:
            os.unlink(path)

    def test_load_nonexistent_file(self) -> None:
        assert self.serializer.load("/nonexistent/path.json") is None

    def test_load_corrupt_file(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("not valid json {{{")
            path = f.name
        try:
            assert self.serializer.load(path) is None
        finally:
            os.unlink(path)

    def test_load_stale_state(self) -> None:
        state = RegisterState(
            active_domain="HVAC",
            timestamp=time.time() - 300,
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.serializer.save(state, path)
            loaded = self.serializer.load(path, max_elapsed_seconds=120.0)
            assert loaded is None
        finally:
            os.unlink(path)

    def test_save_failure(self) -> None:
        state = RegisterState(active_domain="HVAC", timestamp=time.time())
        result = self.serializer.save(state, "/nonexistent_dir/state.json")
        assert result is False

    def test_load_empty_state(self) -> None:
        """State with no timestamp should load fine (no staleness check)."""
        data = {
            "active_domain": "security",
            "active_device": None,
            "last_action": None,
            "parameters": None,
            "turn_counter": 0,
            "timestamp": None,
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name
        try:
            loaded = self.serializer.load(path)
            assert loaded is not None
            assert loaded.active_domain == "security"
        finally:
            os.unlink(path)

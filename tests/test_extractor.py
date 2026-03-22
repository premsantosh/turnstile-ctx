"""Tests for parameter extraction (Duckling wrapper)."""

import json
from unittest.mock import MagicMock, patch

from src.config import RegisterConfig
from src.extractor import ParameterExtractor, _map_duckling_response


class TestParameterExtractor:
    def test_duckling_disabled(self) -> None:
        config = RegisterConfig(enable_duckling=False)
        ext = ParameterExtractor(config)
        assert ext.extract("65 degrees fahrenheit") is None

    @patch("src.extractor.urllib.request.urlopen")
    def test_duckling_unavailable(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = ConnectionError("refused")
        config = RegisterConfig(enable_duckling=True)
        ext = ParameterExtractor(config)
        assert ext._duckling_available is False
        assert ext.extract("65 degrees") is None

    @patch("src.extractor.urllib.request.urlopen")
    def test_duckling_timeout(self, mock_urlopen: MagicMock) -> None:
        """First call succeeds (health check), second times out."""
        health_resp = MagicMock()
        health_resp.__enter__ = MagicMock(return_value=health_resp)
        health_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [health_resp, TimeoutError("timed out")]
        config = RegisterConfig(enable_duckling=True)
        ext = ParameterExtractor(config)
        assert ext._duckling_available is True
        assert ext.extract("65 degrees") is None

    def test_extract_temperature(self) -> None:
        entities = [
            {
                "dim": "temperature",
                "value": {"value": 65, "unit": "fahrenheit"},
            }
        ]
        result = _map_duckling_response(entities)
        assert result == {"temperature": 65, "unit": "fahrenheit"}

    def test_extract_time(self) -> None:
        entities = [
            {
                "dim": "time",
                "value": {"value": "2026-03-21T07:00:00.000-07:00"},
            }
        ]
        result = _map_duckling_response(entities)
        assert result is not None
        assert "time" in result
        assert "2026" in result["time"]

    def test_extract_duration(self) -> None:
        entities = [
            {
                "dim": "duration",
                "value": {"normalized": {"value": 1200}},
            }
        ]
        result = _map_duckling_response(entities)
        assert result == {"duration_seconds": 1200}

    def test_extract_multiple(self) -> None:
        entities = [
            {
                "dim": "temperature",
                "value": {"value": 72, "unit": "fahrenheit"},
            },
            {
                "dim": "duration",
                "value": {"normalized": {"value": 600}},
            },
        ]
        result = _map_duckling_response(entities)
        assert result is not None
        assert result["temperature"] == 72
        assert result["duration_seconds"] == 600

    def test_extract_nothing(self) -> None:
        assert _map_duckling_response([]) is None

    def test_extract_number(self) -> None:
        entities = [
            {"dim": "number", "value": {"value": 50}}
        ]
        result = _map_duckling_response(entities)
        assert result == {"number": 50}

    def test_extract_quantity(self) -> None:
        entities = [
            {"dim": "quantity", "value": {"value": 3, "unit": "cup"}}
        ]
        result = _map_duckling_response(entities)
        assert result == {"quantity": 3, "quantity_unit": "cup"}

    @patch("src.extractor.urllib.request.urlopen")
    def test_extract_with_live_duckling_mock(self, mock_urlopen: MagicMock) -> None:
        """Simulate a full round-trip with mocked HTTP."""
        # Health check succeeds
        health_resp = MagicMock()
        health_resp.__enter__ = MagicMock(return_value=health_resp)
        health_resp.__exit__ = MagicMock(return_value=False)

        # Parse response
        parse_resp = MagicMock()
        parse_resp.read.return_value = json.dumps([
            {"dim": "temperature", "value": {"value": 65, "unit": "fahrenheit"}}
        ]).encode()
        parse_resp.__enter__ = MagicMock(return_value=parse_resp)
        parse_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [health_resp, parse_resp]

        config = RegisterConfig(enable_duckling=True)
        ext = ParameterExtractor(config)
        result = ext.extract("65 degrees fahrenheit")
        assert result == {"temperature": 65, "unit": "fahrenheit"}

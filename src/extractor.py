"""Parameter extraction via Duckling (optional dependency)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from src.config import RegisterConfig

logger = logging.getLogger(__name__)


class ParameterExtractor:
    """Wraps Duckling to extract structured parameters from user utterances.

    Duckling is a standalone HTTP server (Haskell binary with REST API).
    This extractor is fully isolated. 
    If Duckling is unavailable or disabled,
    no other module is affected.
    """

    def __init__(self, config: RegisterConfig) -> None:
        self._config = config
        self._duckling_available = False

        if not config.enable_duckling:
            return

        try:
            req = urllib.request.Request(config.duckling_url, method="GET")
            urllib.request.urlopen(req, timeout=config.duckling_timeout_ms / 1000.0)
            self._duckling_available = True
            logger.info("Duckling server available at %s", config.duckling_url)
        except Exception:
            logger.warning(
                "Duckling server not available at %s; extraction disabled",
                config.duckling_url,
            )

    def extract(self, utterance: str) -> Optional[Dict[str, Any]]:
        """Extract structured parameters from an utterance.

        Returns a dict of extracted parameters, or None if nothing was extracted
        or Duckling is unavailable. Never raises.
        """
        if not self._duckling_available:
            return None

        try:
            dims_json = json.dumps(self._config.duckling_dimensions)
            form_data = urllib.parse.urlencode({
                "locale": "en_US",
                "text": utterance,
                "dims": dims_json,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self._config.duckling_url}/parse",
                data=form_data,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            timeout_s = self._config.duckling_timeout_ms / 1000.0
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw: List[Dict[str, Any]] = json.loads(resp.read().decode("utf-8"))

            return _map_duckling_response(raw)

        except Exception:
            logger.warning("Duckling extraction failed for: %s", utterance)
            return None


def _map_duckling_response(entities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Map Duckling response entities to a flat parameter dict."""
    if not entities:
        return None

    result: Dict[str, Any] = {}

    for entity in entities:
        dim = entity.get("dim", "")
        value_block = entity.get("value", {})

        if dim == "temperature":
            result["temperature"] = value_block.get("value")
            unit = value_block.get("unit")
            if unit:
                result["unit"] = unit
        elif dim == "time":
            result["time"] = value_block.get("value")
        elif dim == "duration":
            normalized = value_block.get("normalized", {})
            result["duration_seconds"] = normalized.get("value")
        elif dim == "number":
            result["number"] = value_block.get("value")
        elif dim == "quantity":
            result["quantity"] = value_block.get("value")
            unit = value_block.get("unit")
            if unit:
                result["quantity_unit"] = unit

    return result if result else None

"""Core ContextRegister class — the central orchestrator."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import replace
from typing import Any, Dict, Optional

from src.config import RegisterConfig
from src.enricher import Enricher
from src.expiry import ExpiryEvaluator
from src.stats import Stats
from src.types import EnrichedInput, ExpiryReason, RegisterState, RoutingResult

logger = logging.getLogger(__name__)


class ContextRegister:
    """Manages the lifecycle of the register state.

    This is the only class that external code interacts with directly.
    """

    def __init__(self, config: Optional[RegisterConfig] = None) -> None:
        self._config = config or RegisterConfig()
        self._state = RegisterState()
        self._enricher = Enricher()
        self._expiry = ExpiryEvaluator()
        self._stats = Stats()
        self._lock = asyncio.Lock()

        # Extractor and serializer are wired in lazily
        self._extractor: Optional[Any] = None
        self._serializer: Optional[Any] = None

        self._init_extractor()
        self._init_serializer()

    def _init_extractor(self) -> None:
        if not self._config.enable_duckling:
            return
        try:
            from src.extractor import ParameterExtractor
            self._extractor = ParameterExtractor(self._config)
        except Exception:
            logger.warning("Failed to initialize ParameterExtractor; continuing without Duckling")

    def _init_serializer(self) -> None:
        if not self._config.enable_persistence:
            return
        try:
            from src.serializer import StateSerializer
            self._serializer = StateSerializer(self._config)
            loaded = self._serializer.load(
                self._config.persistence_path or "",
                self._config.max_elapsed_seconds,
            )
            if loaded is not None:
                self._state = loaded
        except Exception:
            logger.warning("Failed to initialize serializer; continuing without persistence")

    def enrich(self, utterance: str) -> EnrichedInput:
        """Enrich an utterance with register context. Never raises."""
        try:
            # Check expiry
            reason = self._expiry.check(self._state, self._config)
            if reason is not None:
                logger.info("Register expired: %s", reason.value)
                self.clear(reason)

            # Increment turn counter
            self._state = replace(
                self._state, turn_counter=self._state.turn_counter + 1
            )

            # Enrich
            result = self._enricher.enrich(self._state, utterance, self._config)

            # Update stats
            self._stats.record_enrich(result.context_applied)

            return result
        except Exception:
            logger.exception("enrich() caught unexpected error; returning original utterance")
            return EnrichedInput(
                original_utterance=utterance,
                enriched_utterance=utterance,
                context_applied=False,
                register_state=self._state,
            )

    def update(self, result: RoutingResult, utterance: str) -> None:
        """Update the register after a successful routing. Never raises."""
        try:
            # Check domain change
            if (
                result.domain is not None
                and self._state.active_domain is not None
                and result.domain != self._state.active_domain
            ):
                logger.info("Domain change: %s -> %s", self._state.active_domain, result.domain)
                self.clear(ExpiryReason.DOMAIN_CHANGE)

            # Extract parameters
            merged_params = dict(result.parameters) if result.parameters else {}
            extracted = self._extract_parameters(utterance)
            if extracted:
                merged_params.update(extracted)

            self._state = RegisterState(
                active_domain=result.domain,
                active_device=result.device,
                last_action=result.action_name,
                parameters=merged_params if merged_params else None,
                turn_counter=0,
                timestamp=time.time(),
            )

            # Persist if enabled
            if self._serializer is not None and self._config.persistence_path:
                try:
                    self._serializer.save(self._state, self._config.persistence_path)
                except Exception:
                    logger.warning("Failed to persist register state")

            self._stats.record_update()
        except Exception:
            logger.exception("update() caught unexpected error; state may be stale")

    def _extract_parameters(self, utterance: str) -> Optional[Dict[str, Any]]:
        """Attempt parameter extraction via Duckling. Returns None on any failure."""
        if self._extractor is None:
            self._stats.record_duckling_skip()
            return None
        try:
            params = self._extractor.extract(utterance)
            if params is not None:
                self._stats.record_duckling_success()
            else:
                self._stats.record_duckling_skip()
            return params
        except Exception:
            self._stats.record_duckling_failure()
            logger.warning("Parameter extraction failed; skipping")
            return None

    def clear(self, reason: ExpiryReason = ExpiryReason.MANUAL) -> None:
        """Reset the register to empty state."""
        logger.info("Clearing register: %s", reason.value)
        self._state = RegisterState()
        self._stats.record_expiry(reason)

    def get_state(self) -> RegisterState:
        """Return the current RegisterState without modifying it."""
        return self._state

    def get_stats(self) -> Dict[str, Any]:
        """Return current observability metrics."""
        return self._stats.to_dict()

    @property
    def is_empty(self) -> bool:
        """True if all content slots are None."""
        return (
            self._state.active_domain is None
            and self._state.active_device is None
            and self._state.last_action is None
            and self._state.parameters is None
        )

    async def enrich_async(self, utterance: str) -> EnrichedInput:
        """Async-safe version of enrich()."""
        async with self._lock:
            return self.enrich(utterance)

    async def update_async(self, result: RoutingResult, utterance: str) -> None:
        """Async-safe version of update()."""
        async with self._lock:
            self.update(result, utterance)

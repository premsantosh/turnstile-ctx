"""Async safety tests for the Context Register."""

import asyncio

import pytest

from src.config import RegisterConfig
from src.register import ContextRegister
from src.types import RoutingResult


@pytest.mark.asyncio
async def test_concurrent_enrich_calls() -> None:
    """Run 100 concurrent enrich() calls — verify no state corruption."""
    reg = ContextRegister(RegisterConfig(enable_duckling=False, max_turns=200))
    reg.update(
        RoutingResult(
            action_name="power_on", domain="HVAC", device="ac", confidence=0.9, source="router"
        ),
        "turn on AC",
    )

    async def do_enrich(i: int) -> None:
        result = await reg.enrich_async(f"utterance {i}")
        assert result.enriched_utterance.endswith(f"utterance {i}")

    await asyncio.gather(*[do_enrich(i) for i in range(100)])

    state = reg.get_state()
    # State should still be valid (not corrupted)
    assert state.active_domain == "HVAC"


@pytest.mark.asyncio
async def test_concurrent_enrich_and_update() -> None:
    """Interleave enrich() and update() calls concurrently."""
    reg = ContextRegister(RegisterConfig(enable_duckling=False))

    async def do_enrich(i: int) -> None:
        await reg.enrich_async(f"enrich {i}")

    async def do_update(i: int) -> None:
        await reg.update_async(
            RoutingResult(
                action_name=f"action_{i}",
                domain="HVAC",
                confidence=0.9,
                source="router",
            ),
            f"update {i}",
        )

    tasks = []
    for i in range(50):
        tasks.append(do_enrich(i))
        tasks.append(do_update(i))

    await asyncio.gather(*tasks)

    # State should be consistent — some valid state exists
    state = reg.get_state()
    assert state.active_domain == "HVAC"
    assert state.last_action is not None
    assert state.last_action.startswith("action_")

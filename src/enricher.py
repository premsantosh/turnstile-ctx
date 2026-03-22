"""Input enrichment logic for the Context Register."""

from __future__ import annotations

from src.config import RegisterConfig
from src.types import EnrichedInput, RegisterState


class Enricher:
    """Stateless utility that prepends register context to raw utterances."""

    def enrich(
        self,
        state: RegisterState,
        utterance: str,
        config: RegisterConfig,
    ) -> EnrichedInput:
        """Produce an EnrichedInput from a RegisterState and raw utterance.

        If the state is empty, returns the utterance unchanged.
        Otherwise, prepends a structured context prefix.
        """
        if _is_empty(state):
            return EnrichedInput(
                original_utterance=utterance,
                enriched_utterance=utterance,
                context_applied=False,
                register_state=state,
            )

        slots: list[str] = []
        if state.active_domain is not None:
            slots.append(f"domain={state.active_domain}")
        if state.active_device is not None:
            slots.append(f"device={state.active_device}")
        if state.last_action is not None:
            slots.append(f"action={state.last_action}")
        if state.parameters is not None:
            slots.append(f"params={state.parameters}")

        slot_string = config.slot_separator.join(slots)
        prefix = config.context_prefix_format.format(slots=slot_string)
        enriched = f"{prefix} {utterance}"

        return EnrichedInput(
            original_utterance=utterance,
            enriched_utterance=enriched,
            context_applied=True,
            register_state=state,
        )


def _is_empty(state: RegisterState) -> bool:
    """Check if all content slots are None."""
    return (
        state.active_domain is None
        and state.active_device is None
        and state.last_action is None
        and state.parameters is None
    )

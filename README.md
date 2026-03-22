# Turnstile Context Register

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-68%20passed-brightgreen.svg)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-99%25-brightgreen.svg)](#testing)

A lightweight, structured state module that carries resolved conversational context across turns in an intent routing pipeline.

**Python 3.10+ | Zero Required Dependencies | Duckling Optional**

---

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Enrichment Format](#enrichment-format)
- [Expiry Conditions](#expiry-conditions)
- [Duckling (Optional)](#duckling-optional)
- [Architecture](#architecture)
- [Development](#development)
- [Testing](#testing)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [License](#license)

---

## Overview

### What It Does

The Context Register sits between the user and the sentence encoder. After each successfully routed action, it captures the resolved **domain**, **device**, **action**, and **parameters** into a small structured state. Before the next utterance is encoded, it prepends this state as a structured prefix — giving the router the context needed to route follow-up utterances like *"set it to 65 degrees"* or *"turn that off too."*

### What It Is NOT

It is **not** a dialogue state tracker, not a conversation history store, not a memory module. It is a minimal, ephemeral, structured bridge between consecutive turns. It holds at most one turn's worth of resolved context and expires automatically.

### Design Principles

- **Zero required dependencies** — only Python standard library for core functionality
- **Failure isolation** — `enrich()` and `update()` never raise exceptions
- **Immutable state** — `RegisterState` is a frozen dataclass; new instances are created on each update
- **Async-safe** — uses `asyncio.Lock` for concurrent access protection
- **Optional Duckling** — parameter extraction via Duckling is entirely opt-in

---

## Installation

### From source

```bash
git clone https://github.com/your-org/turnstile-ctx.git
cd turnstile-ctx
pip install -e .
```

### With development dependencies

```bash
pip install -e ".[dev]"
```

### Requirements

- Python 3.10 or higher
- No external packages required for core functionality
- [Duckling](https://github.com/facebook/duckling) (optional) — for structured parameter extraction

---

## Quickstart

```python
from src import ContextRegister, RegisterConfig, RoutingResult

# Initialize with defaults (Duckling enabled, 3-turn expiry, 120s timeout)
register = ContextRegister()

# Or with custom config
register = ContextRegister(RegisterConfig(
    max_turns=5,
    max_elapsed_seconds=180.0,
    enable_duckling=False,  # Skip Duckling, parameters slot stays None
))

# ── In your routing loop ──

# Step 1: Enrich the utterance before encoding
enriched = register.enrich("set it to 65 degrees")
# enriched.enriched_utterance might be:
#   "[context: domain=HVAC, device=living_room_ac] set it to 65 degrees"
# enriched.context_applied == True

# Step 2: Feed enriched utterance to your encoder
# embedding = encoder.encode(enriched.enriched_utterance)
# result = router.forward(embedding)

# Step 3: After successful routing, update the register
register.update(
    result=RoutingResult(
        action_name="temperature_set",
        domain="HVAC",
        device="living_room_ac",
        confidence=0.92,
        parameters={"temperature": 65},
        source="router",
    ),
    utterance="set it to 65 degrees",
)

# Step 4: Check stats
print(register.get_stats())
# {"total_enrich_calls": 1, "context_applied_count": 1, ...}
```

### Async Usage

```python
import asyncio
from src import ContextRegister, RegisterConfig, RoutingResult

register = ContextRegister(RegisterConfig(enable_duckling=False))

async def handle_turn(utterance: str) -> str:
    enriched = await register.enrich_async(utterance)
    # ... route the enriched utterance ...
    await register.update_async(
        RoutingResult(action_name="power_on", domain="HVAC", confidence=0.9, source="router"),
        utterance,
    )
    return enriched.enriched_utterance
```

---

## API Reference

### `ContextRegister(config: RegisterConfig = None)`

The main class. Instantiate with optional config; defaults work out of the box.

#### Methods

| Method | Signature | Description |
|---|---|---|
| `enrich()` | `enrich(utterance: str) -> EnrichedInput` | Prepend register context to an utterance before encoding. **Never raises.** |
| `update()` | `update(result: RoutingResult, utterance: str) -> None` | Update the register after a successful routing. **Never raises.** |
| `clear()` | `clear(reason: ExpiryReason = MANUAL) -> None` | Reset the register to empty state. |
| `get_state()` | `get_state() -> RegisterState` | Return the current state without modification. |
| `get_stats()` | `get_stats() -> Dict[str, Any]` | Return observability metrics. |
| `is_empty` | `@property -> bool` | `True` if all content slots are `None`. |
| `enrich_async()` | `async enrich_async(utterance: str) -> EnrichedInput` | Async-safe version of `enrich()`. |
| `update_async()` | `async update_async(result, utterance) -> None` | Async-safe version of `update()`. |

### `RegisterState` (frozen dataclass)

| Field | Type | Default | Description |
|---|---|---|---|
| `active_domain` | `Optional[str]` | `None` | Current domain (e.g., `"HVAC"`, `"wine_cellar"`) |
| `active_device` | `Optional[str]` | `None` | Specific device (e.g., `"living_room_ac"`) |
| `last_action` | `Optional[str]` | `None` | Most recent action (e.g., `"power_on"`) |
| `parameters` | `Optional[Dict]` | `None` | Resolved parameters |
| `turn_counter` | `int` | `0` | Turns since last update |
| `timestamp` | `Optional[float]` | `None` | Unix epoch of last update |

### `RoutingResult`

| Field | Type | Description |
|---|---|---|
| `action_name` | `str` | Resolved action name |
| `domain` | `Optional[str]` | Domain this action belongs to |
| `device` | `Optional[str]` | Specific device targeted |
| `confidence` | `float` | Confidence score (0.0–1.0) |
| `parameters` | `Optional[Dict]` | Extracted parameters |
| `source` | `Literal["router", "llm"]` | Whether the router or LLM produced this |

### `EnrichedInput`

| Field | Type | Description |
|---|---|---|
| `original_utterance` | `str` | Raw user utterance |
| `enriched_utterance` | `str` | Utterance with context prefix (or unchanged) |
| `context_applied` | `bool` | Whether context was prepended |
| `register_state` | `RegisterState` | Snapshot of state used for enrichment |

### `ExpiryReason` (enum)

| Value | Description |
|---|---|
| `TURN_LIMIT` | Turn counter exceeded threshold |
| `DOMAIN_CHANGE` | New routing has a different domain |
| `TIME_ELAPSED` | Time since last update exceeded threshold |
| `MANUAL` | Explicitly cleared by calling code |

---

## Configuration

All parameters have sensible defaults. Zero-argument instantiation works correctly.

```python
RegisterConfig(
    max_turns=3,              # Turns before auto-expiry
    max_elapsed_seconds=120.0, # Seconds before time-based expiry
    enable_duckling=True,      # Enable Duckling parameter extraction
    duckling_url="http://localhost:8000",
    duckling_timeout_ms=50.0,
    duckling_dimensions=["temperature", "time", "duration", "number", "quantity"],
    context_prefix_format="[context: {slots}]",
    slot_separator=", ",
    enable_persistence=False,  # Serialize state to disk
    persistence_path=None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `max_turns` | `int` | `3` | Turns with no contextual reference before the register clears |
| `max_elapsed_seconds` | `float` | `120.0` | Seconds since last update before time-based expiry |
| `enable_duckling` | `bool` | `True` | Whether to attempt Duckling extraction |
| `duckling_url` | `str` | `"http://localhost:8000"` | Duckling server URL |
| `duckling_timeout_ms` | `float` | `50.0` | Max wait time for Duckling response |
| `duckling_dimensions` | `List[str]` | `["temperature", "time", ...]` | Which Duckling dimensions to extract |
| `context_prefix_format` | `str` | `"[context: {slots}]"` | Template for the enrichment prefix |
| `slot_separator` | `str` | `", "` | Separator between slots in the prefix |
| `enable_persistence` | `bool` | `False` | Whether to serialize register state to disk |
| `persistence_path` | `Optional[str]` | `None` | File path for state serialization (JSON) |

---

## Enrichment Format

| Register State | Raw Utterance | Enriched Output |
|---|---|---|
| *(empty)* | `turn on the lights` | `turn on the lights` |
| domain=HVAC, device=living_room_ac, action=power_on | `set it to 65 degrees` | `[context: domain=HVAC, device=living_room_ac, action=power_on] set it to 65 degrees` |
| domain=wine_cellar, action=temperature_query | `what about humidity` | `[context: domain=wine_cellar, action=temperature_query] what about humidity` |

The format is deliberately simple and readable. The sentence encoder (MiniLM) was trained on natural text, not XML or JSON. A bracketed prefix with `key=value` pairs is close enough to natural language that the encoder handles it well, while being structured enough for the MLP to learn meaningful associations.

---

## Expiry Conditions

The register auto-clears when any condition triggers (checked in this priority order):

1. **Time-based** — elapsed time since last update exceeds `max_elapsed_seconds`
2. **Turn-based** — `turn_counter` reaches `max_turns` with no new `update()` call
3. **Domain change** — new routing result has a different domain than `active_domain`

Edge cases handled:
- Empty register is never expired (short-circuits all checks)
- `timestamp=None` (never populated) skips time-based check
- `new_domain=None` (not yet known) skips domain change check

---

## Duckling (Optional)

[Duckling](https://github.com/facebook/duckling) is a standalone HTTP server for structured parameter extraction. It is **not required** — set `enable_duckling=False` to skip it entirely. All core functionality (enrichment, expiry, persistence) works without it.

### Setup

```bash
# Via Docker (recommended)
docker run -p 8000:8000 rasa/duckling

# Or build from source (requires Haskell stack)
# See https://github.com/facebook/duckling
```

### Supported Dimensions

| Dimension | Output Key | Example Input | Example Output |
|---|---|---|---|
| `temperature` | `temperature` + `unit` | `"65 degrees fahrenheit"` | `{"temperature": 65, "unit": "fahrenheit"}` |
| `time` | `time` | `"7am tomorrow"` | `{"time": "2026-03-21T07:00:00.000-07:00"}` |
| `duration` | `duration_seconds` | `"twenty minutes"` | `{"duration_seconds": 1200}` |
| `number` | `number` | `"fifty percent"` | `{"number": 50}` |
| `quantity` | `quantity` + `quantity_unit` | `"3 cups"` | `{"quantity": 3, "quantity_unit": "cup"}` |

---

## Architecture

```
src/
├── __init__.py          # Public API exports
├── register.py          # Core ContextRegister class (orchestrator)
├── config.py            # RegisterConfig dataclass
├── enricher.py          # Input enrichment logic (stateless)
├── extractor.py         # Parameter extraction (Duckling wrapper, isolated)
├── expiry.py            # Expiry condition evaluation (pure logic)
├── serializer.py        # Optional state persistence (JSON)
├── stats.py             # Observability / metrics
└── types.py             # Shared type definitions (RegisterState, RoutingResult, etc.)
tests/
├── test_register.py     # Core register unit tests
├── test_enricher.py     # Input enrichment tests
├── test_extractor.py    # Parameter extraction tests
├── test_expiry.py       # Expiry logic tests
├── test_serializer.py   # Persistence tests
├── test_stats.py        # Observability tests
├── test_integration.py  # Multi-turn conversation tests (6 scenarios)
└── test_thread_safety.py # Async concurrency tests
```

### Data Flow

```
User utterance
    │
    ▼
┌──────────────┐     ┌────────────────┐
│  enrich()    │────▶│  ExpiryEvaluator│──▶ clear if expired
│              │     └────────────────┘
│              │     ┌────────────────┐
│              │────▶│    Enricher     │──▶ prepend context prefix
│              │     └────────────────┘
└──────┬───────┘
       │ EnrichedInput
       ▼
   Encoder ──▶ Routing
       │
       ▼ RoutingResult
┌──────────────┐     ┌────────────────┐
│  update()    │────▶│ ParameterExtract│──▶ Duckling (optional)
│              │     └────────────────┘
│              │────▶ new RegisterState
│              │────▶ persist (optional)
└──────────────┘
```

---

## Development

### Prerequisites

- Python 3.10+
- (Optional) Docker for running Duckling

### Setup

```bash
# Clone the repository
git clone https://github.com/your-org/turnstile-ctx.git
cd turnstile-ctx

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Code Style

- All modules use type hints throughout
- Frozen dataclasses for immutable state
- Logging via Python's standard `logging` module (no print statements)
- Public methods that interact with external systems never raise exceptions

---

## Testing

The test suite covers unit tests, integration scenarios, and async concurrency.

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run a specific test file
python -m pytest tests/test_register.py -v

# Run with coverage report
python -m pytest --cov=src --cov-report=term-missing

# Run only integration tests
python -m pytest tests/test_integration.py -v

# Run thread safety tests
python -m pytest tests/test_thread_safety.py -v
```

### Test Structure

| File | Tests | What It Covers |
|---|---|---|
| `test_register.py` | 17 | Core register lifecycle, failure isolation, persistence |
| `test_enricher.py` | 9 | Context prefix formatting, edge cases |
| `test_extractor.py` | 11 | Duckling mapping, timeouts, unavailability |
| `test_expiry.py` | 10 | Turn/time/domain expiry, priority order |
| `test_serializer.py` | 6 | JSON roundtrip, corrupt files, stale state |
| `test_stats.py` | 7 | Metric counters, computed rates, reset |
| `test_integration.py` | 6 | Multi-turn conversation scenarios |
| `test_thread_safety.py` | 2 | Concurrent async access (100+ coroutines) |

### Type Checking

```bash
mypy src/ --strict
```

---

## Contributing

Contributions are welcome! Here's how to get started:

### Reporting Bugs

- Open an issue with a clear title and description
- Include steps to reproduce, expected vs. actual behavior
- Include your Python version and OS

### Suggesting Features

- Open an issue describing the use case and proposed solution
- Explain how it fits with the project's design principles (minimal, ephemeral, zero-dependency)

### Submitting Changes

1. **Fork** the repository and create a branch from `main`
2. **Install** dev dependencies: `pip install -e ".[dev]"`
3. **Make** your changes, following the existing code style
4. **Add tests** for any new functionality — target 95%+ coverage
5. **Run the full test suite** and ensure all tests pass:
   ```bash
   python -m pytest --cov=src --cov-report=term-missing
   ```
6. **Run type checking**:
   ```bash
   mypy src/ --strict
   ```
7. **Commit** with a clear message describing *what* and *why*
8. **Open a pull request** against `main`

### Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Include tests for new code paths
- Ensure `enrich()` and `update()` continue to never raise (failure isolation is a core invariant)
- Do not add required external dependencies — the core must remain stdlib-only
- Update the README if adding new public API or configuration options

### Code of Conduct

Be respectful and constructive. We're here to build something useful together.

---

## Changelog

### 0.1.0 (2026-03-21)

- Initial release
- Core `ContextRegister` with `enrich()` / `update()` / `clear()` lifecycle
- Configurable turn-based, time-based, and domain-change expiry
- Stateless `Enricher` with customizable prefix format
- Optional Duckling integration for parameter extraction
- Optional JSON state persistence
- Full async support with `asyncio.Lock`
- Observability via `Stats` module with hit rates and expiry counters
- 68 tests, 99% code coverage

---

## License

This project is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE) file for details.

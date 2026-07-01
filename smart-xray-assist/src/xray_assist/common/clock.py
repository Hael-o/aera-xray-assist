"""Time sources. api-schema.md: timestamp_ms = wall clock (audit/display),
monotonic_ms = latency/ordering. Both milliseconds, never nanoseconds."""

from __future__ import annotations

import time


def timestamp_ms() -> int:
    """Wall-clock epoch milliseconds. May jump (NTP). Use for display/audit only."""
    return int(time.time() * 1000)


def monotonic_ms() -> int:
    """Monotonic milliseconds. Never goes backward. Use for latency/ordering."""
    return int(time.monotonic() * 1000)

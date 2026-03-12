"""Shared agent invocation schemas."""

from __future__ import annotations

from enum import Enum


class TravelTomAgentMode(str, Enum):
    """Supported route-facing invocation modes for the TravelTom agent."""

    CHAT = "chat"
    DIRECT_RECOMMENDATION = "direct_recommendation"

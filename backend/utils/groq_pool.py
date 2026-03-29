"""
Shared Groq client with automatic API key rotation on rate limit (429).
All agents import get_groq_client() instead of creating their own AsyncGroq.
"""

import os
import logging
from groq import AsyncGroq  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Pool of API keys for rotation
_GROQ_KEYS = [
    k for k in [
        os.getenv("GROQ_API_KEY", ""),
        os.getenv("GROQ_API_KEY_2", ""),
    ] if k
]

_current_key_index = 0
_clients: dict[int, AsyncGroq] = {}


def get_groq_client() -> AsyncGroq:
    """Return the current Groq client. Call rotate_groq_key() on 429."""
    global _current_key_index
    if _current_key_index not in _clients:
        key = _GROQ_KEYS[_current_key_index % len(_GROQ_KEYS)] if _GROQ_KEYS else ""
        _clients[_current_key_index] = AsyncGroq(api_key=key)
    return _clients[_current_key_index]


def rotate_groq_key() -> AsyncGroq:
    """Switch to next API key and return new client. Call this on 429 errors."""
    global _current_key_index
    if len(_GROQ_KEYS) <= 1:
        logger.warning("Only 1 Groq API key available — cannot rotate")
        return get_groq_client()
    
    old_idx = _current_key_index
    _current_key_index = (_current_key_index + 1) % len(_GROQ_KEYS)
    logger.info(f"Groq key rotated: slot {old_idx} → {_current_key_index}")
    
    if _current_key_index not in _clients:
        key = _GROQ_KEYS[_current_key_index]
        _clients[_current_key_index] = AsyncGroq(api_key=key)
    
    return _clients[_current_key_index]


def get_all_groq_keys_count() -> int:
    """Return how many Groq keys are configured."""
    return len(_GROQ_KEYS)

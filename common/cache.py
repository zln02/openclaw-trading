"""Unified TTL cache for all OpenClaw modules.

Usage:
    from common.cache import ttl_cache, get_cached, set_cached, clear_cache

    # Decorator style
    @ttl_cache(ttl=300)
    def get_market_data():
        ...

    # Manual style
    val = get_cached("btc_funding")
    if val is None:
        val = fetch_funding()
        set_cached("btc_funding", val, ttl=300)
"""
from __future__ import annotations

import time
import functools
import threading
from typing import Any, Callable, Optional

_lock = threading.Lock()
_store: dict[str, tuple[float, float, Any]] = {}  # key -> (created_at, ttl, value)


def get_cached(key: str) -> Optional[Any]:
    """Get a value from cache. Returns None if expired or missing."""
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        created_at, ttl, value = entry
        if time.time() - created_at > ttl:
            del _store[key]
            return None
        return value


def set_cached(key: str, value: Any, ttl: float = 300) -> None:
    """Store a value in cache with TTL (seconds)."""
    with _lock:
        _store[key] = (time.time(), ttl, value)


def invalidate(key: str) -> None:
    """Remove a specific key from cache."""
    with _lock:
        _store.pop(key, None)


def clear_cache() -> None:
    """Clear all cached entries."""
    with _lock:
        _store.clear()


def cache_stats() -> dict:
    """Return cache statistics."""
    with _lock:
        now = time.time()
        total = len(_store)
        alive = sum(1 for (created, ttl, _) in _store.values() if now - created <= ttl)
        return {"total_keys": total, "alive_keys": alive, "expired_keys": total - alive}


def ttl_cache(ttl: float = 300, key_prefix: str = ""):
    """Decorator: cache function results with TTL.

    Cache key is derived from function name + args.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build cache key from function name and arguments
            parts = [key_prefix or func.__qualname__]
            if args:
                parts.extend(str(a) for a in args)
            if kwargs:
                parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(parts)

            cached = get_cached(cache_key)
            if cached is not None:
                return cached

            result = func(*args, **kwargs)
            set_cached(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator

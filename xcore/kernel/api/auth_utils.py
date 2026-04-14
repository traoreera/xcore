"""
Shared authentication and utility functions for XCore API adapters.
"""

import hashlib
import hmac
import asyncio
from typing import Optional, Any, Coroutine


def hash_key(
    key: Optional[str | bytes],
    server_key: Optional[str | bytes],
    server_key_iterations: int = 100000,
) -> bytes:
    """
    Hash a key using PBKDF2 with a server-side salt.
    Used for IPC authentication.
    """
    if key is None:
        key_bytes = b""
    elif isinstance(key, bytes):
        key_bytes = key
    else:
        key_bytes = key.encode("utf-8")

    if server_key is None:
        raise ValueError("server_key cannot be None")

    if isinstance(server_key, str):
        server_key = server_key.encode("utf-8")

    return hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=key_bytes,
        salt=server_key,
        iterations=server_key_iterations,
    )


def verify_api_key(
    api_key: Optional[str],
    stored_hash: bytes,
    server_key: bytes,
    server_key_iterations: int = 100000,
) -> bool:
    """
    Verify an incoming API key against a stored hash.
    """
    if api_key is None:
        return False

    incoming_hash = hash_key(api_key, server_key, server_key_iterations)
    return hmac.compare_digest(incoming_hash, stored_hash)


def run_sync(coro: Coroutine) -> Any:
    """
    Helper to run an async coroutine in a synchronous context.
    Attempts to get the current event loop, or creates a new one if none exists.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we are in an environment like gevent or a running loop,
            # we might need a more complex solution, but for standard Flask/Django:
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        # No loop in this thread
        return asyncio.run(coro)

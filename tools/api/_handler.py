"""
tools/api/_handler.py

Base class for all tools/api/*.py clients.
Subclass sets CACHE_PREFIX.
All methods call self.call() not cache directly.
Credentials loaded once via _get_client().
"""

from typing import Callable


class BaseAPIHandler:
    """
    Base class for all API client handlers.

    Subclass sets CACHE_PREFIX.
    All methods call self.call() not cache directly.
    Credentials loaded once via _get_client().
    """

    CACHE_PREFIX: str = ""  # set per subclass

    def _get_client(self):
        """Override to return authenticated client."""
        raise NotImplementedError

    def cache_key(self, suffix: str) -> str:
        """Namespaced cache key for this handler."""
        return f"{self.CACHE_PREFIX}_{suffix}"

    def call(
        self, suffix: str, params_hash: str, live_fn: Callable, stale_ok: bool = True
    ) -> dict:
        """
        All API calls go through here.
        Delegates to CacheManager.
        Subclasses never call cache directly.
        """
        from core.cache import cache

        return cache.call(self.cache_key(suffix), params_hash, live_fn, stale_ok=stale_ok)

    def hash(self, *args, **kwargs) -> str:
        """Convenience — delegates to cache.hash()."""
        from core.cache import cache

        return cache.hash(*args, **kwargs)

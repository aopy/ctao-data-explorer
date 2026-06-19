from __future__ import annotations

import time
from typing import Any


class FakeRedis:
    """Small async in-memory Redis used in tests.

    Supports the minimal Redis API needed by the API and auth_service tests:
    get, set, setex, expire, delete, and aclose. TTL is enforced lazily.
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.expiry: dict[str, float] = {}

    def _expired(self, key: str) -> bool:
        t = self.expiry.get(key)
        return t is not None and t <= time.time()

    async def get(self, key: str) -> str | None:
        if self._expired(key):
            self.store.pop(key, None)
            self.expiry.pop(key, None)
            return None
        return self.store.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: float | int | None = None,
        px: float | int | None = None,
        keepttl: bool = False,
        nx: bool = False,
        xx: bool = False,
        get: bool = False,
        **_: Any,
    ) -> str | bool | None:
        if self._expired(key):
            self.store.pop(key, None)
            self.expiry.pop(key, None)

        old = self.store.get(key)

        if nx and old is not None:
            return old if get else False

        if xx and old is None:
            return old if get else False

        self.store[key] = value

        if ex is not None:
            self.expiry[key] = time.time() + float(ex)
        elif px is not None:
            self.expiry[key] = time.time() + (float(px) / 1000.0)
        elif not keepttl:
            self.expiry.pop(key, None)

        return old if get else True

    async def setex(self, key: str, ttl_seconds: int | float, value: str) -> bool:
        self.store[key] = value
        self.expiry[key] = time.time() + float(ttl_seconds)
        return True

    async def expire(self, key: str, ttl_seconds: int | float) -> bool:
        if key not in self.store:
            return False

        self.expiry[key] = time.time() + float(ttl_seconds)
        return True

    async def delete(self, *keys: str) -> int:
        count = 0

        for key in keys:
            if key in self.store:
                self.store.pop(key, None)
                self.expiry.pop(key, None)
                count += 1

        return count

    async def aclose(self) -> None:
        return None

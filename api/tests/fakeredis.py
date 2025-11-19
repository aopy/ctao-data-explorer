import time


class FakeRedis:
    """Small async in-memory Redis used in tests.
    - Supports get/set with ex/px/nx/xx/keepttl/get (minimal semantics).
    - setex, expire, delete, aclose.
    - TTL is enforced lazily on get()/expire().
    """

    def __init__(self):
        self.store: dict[str, str] = {}
        self.expiry: dict[str, float] = {}  # key -> epoch seconds

    def _expired(self, key: str) -> bool:
        t = self.expiry.get(key)
        return t is not None and t <= time.time()

    async def get(self, key: str):
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
        ex: float | int | None = None,  # seconds
        px: float | int | None = None,  # milliseconds
        keepttl: bool = False,
        nx: bool = False,  # only set if not exists
        xx: bool = False,  # only set if exists
        get: bool = False,  # return old value if True
        # (exat/pxat not needed for tests)
        **kwargs,
    ):
        if self._expired(key):
            # simulate eviction if expired
            self.store.pop(key, None)
            self.expiry.pop(key, None)

        old = self.store.get(key)

        if nx and old is not None:
            return old if get else False
        if xx and old is None:
            return old if get else False

        self.store[key] = value

        # TTL handling
        if ex is not None:
            self.expiry[key] = time.time() + float(ex)
        elif px is not None:
            self.expiry[key] = time.time() + (float(px) / 1000.0)
        elif not keepttl:
            self.expiry.pop(key, None)

        return old if get else True

    async def setex(self, key: str, ttl_seconds: int | float, value: str):
        self.store[key] = value
        self.expiry[key] = time.time() + float(ttl_seconds)
        return True

    async def expire(self, key: str, ttl_seconds: int | float):
        if key not in self.store:
            return False
        self.expiry[key] = time.time() + float(ttl_seconds)
        return True

    async def delete(self, *keys: str):
        count = 0
        for k in keys:
            if k in self.store:
                self.store.pop(k, None)
                self.expiry.pop(k, None)
                count += 1
        return count

    async def aclose(self):
        return None

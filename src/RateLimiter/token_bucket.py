# src/RateLimiter/token_bucket.py
import time
from .base import BaseRateLimiter

class TokenBucketLimiter(BaseRateLimiter):
    def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        self._store = {} if backend == "memory" else None

    def _get_data(self, key):
        if self.backend == "redis":
            return self.redis_client.hgetall(key)
        return self._store.get(key, {})

    def _set_data(self, key, mapping):
        if self.backend == "redis":
            self.redis_client.hset(key, mapping=mapping)
        else:
            self._store[key] = mapping

    def allow_request(self, identifier=None):
        key = self._get_key(identifier)
        data = self._get_data(key)
        now = time.time()

        if not data:
            self._set_data(key, {"tokens_remaining": self.capacity - 1, "last_fill_time": now})
            return True

        tokens = float(data.get("tokens_remaining", 0))
        last_fill = float(data.get("last_fill_time", now))
        elapsed = now - last_fill
        tokens = min(self.capacity, tokens + elapsed * self.fill_rate)

        if tokens >= 1:
            tokens -= 1
            allowed = True
        else:
            allowed = False

        self._set_data(key, {"tokens_remaining": tokens, "last_fill_time": now})
        return allowed

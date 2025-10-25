import time
from .base import BaseRateLimiter


class QueueLimiter(BaseRateLimiter):
    def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        self._store = {} if backend == "memory" else None

    def _get_data(self, key):
        if self.backend == "redis":
            return self.redis_client.hgetall(key)
        return self._store.get(key, {"queue": [], "last_check": time.time()})

    def _set_data(self, key, mapping):
        if self.backend == "redis":
            self.redis_client.hset(key, mapping=mapping)
        else:
            self._store[key] = mapping

    def allow_request(self, identifier=None):
        key = self._get_key(identifier)
        data = self._get_data(key)
        now = time.time()

        queue = data.get("queue", [])
        last_check = float(data.get("last_check", now))

        if queue.size() < self.capacity:
            queue.append(key)
            self._set_data(key, {"queue": queue, "last_check": now})
        else:
            # Remove expired requests
            while queue and now - last_check > (1 / self.fill_rate):
                queue.pop(0)
                last_check += (1 / self.fill_rate)

            if len(queue) < self.capacity:
                queue.append(key)
                self._set_data(key, {"queue": queue, "last_check": now})
            else:
                self._set_data(key, {"queue": queue, "last_check": last_check})
                return False    
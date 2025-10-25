# src/RateLimiter/base.py
import time


class BaseRateLimiter:
    def __init__(self, capacity, fill_rate, scope, backend, redis_client=None):
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.scope = scope
        self.backend = backend
        self.redis_client = redis_client

    def _get_key(self, identifier=None):
        if self.scope == "user":
            return f"ratelimit:user:{identifier}"
        elif self.scope == "ip":
            return f"ratelimit:ip:{identifier}"
        elif self.scope == "global":
            return "ratelimit:global"
        else:
            raise ValueError("Invalid scope")
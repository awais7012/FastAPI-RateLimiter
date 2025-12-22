# src/RateLimiter/base.py
import time
import threading
from abc import ABC, abstractmethod

class BaseRateLimiter(ABC):
    """Base class for all rate limiters with backend support"""
    
    def __init__(self, capacity, fill_rate, scope, backend, redis_client=None):
        """
        Initialize base rate limiter.
        
        Args:
            capacity: Maximum capacity (tokens or requests)
            fill_rate: Refill/leak rate
            scope: "user", "ip", or "global"
            backend: "memory" or "redis"
            redis_client: Redis client instance (required if backend="redis")
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        if fill_rate <= 0:
            raise ValueError("Fill rate must be positive")
        if scope not in ["user", "ip", "global"]:
            raise ValueError("Scope must be 'user', 'ip', or 'global'")
        if backend not in ["memory", "redis"]:
            raise ValueError("Backend must be 'memory' or 'redis'")
        if backend == "redis" and redis_client is None:
            raise ValueError("redis_client is required when backend='redis'")
        
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.scope = scope
        self.backend = backend
        self.redis_client = redis_client
        
        # Memory backend storage
        self._memory_storage = {}
        self._lock = threading.Lock()
    
    def _get_key(self, identifier=None):
        """Generate storage key based on scope and identifier"""
        if self.scope == "user":
            if identifier is None:
                raise ValueError("identifier is required for 'user' scope")
            return f"ratelimit:user:{identifier}"
        elif self.scope == "ip":
            if identifier is None:
                raise ValueError("identifier is required for 'ip' scope")
            return f"ratelimit:ip:{identifier}"
        elif self.scope == "global":
            return "ratelimit:global"
        else:
            raise ValueError("Invalid scope")
    
    def _get_from_backend(self, key):
        """Get data from backend (memory or Redis)"""
        if self.backend == "memory":
            with self._lock:
                return self._memory_storage.get(key)
        else:  # redis
            data = self.redis_client.get(key)
            if data:
                import json
                return json.loads(data)
            return None
    
    def _set_to_backend(self, key, value, ttl=None):
        """Set data to backend (memory or Redis)"""
        if self.backend == "memory":
            with self._lock:
                self._memory_storage[key] = value
        else:  # redis
            import json
            self.redis_client.set(key, json.dumps(value))
            if ttl:
                self.redis_client.expire(key, int(ttl))
    
    def _delete_from_backend(self, key):
        """Delete data from backend"""
        if self.backend == "memory":
            with self._lock:
                self._memory_storage.pop(key, None)
        else:  # redis
            self.redis_client.delete(key)
    
    @abstractmethod
    def allow_request(self, identifier=None):
        """Check if request should be allowed"""
        pass
    
    @abstractmethod
    def reset(self, identifier=None):
        """Reset rate limit for identifier"""
        pass
    
    def get_config(self):
        """Get rate limiter configuration"""
        return {
            "capacity": self.capacity,
            "fill_rate": self.fill_rate,
            "scope": self.scope,
            "backend": self.backend
        }
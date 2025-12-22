
import redis
from .token_bucket import TokenBucketLimiter


class fastapi_advanced_rate_limiter:
   
    
    def __init__(self, fill_rate, capacity, scope="user", backend="memory", redis_url=None):
        """
        Initialize rate limiter with automatic Redis connection handling.
        
        Args:
            fill_rate: Tokens added per second
            capacity: Maximum burst capacity
            scope: "user", "ip", or "global"
            backend: "memory" or "redis"
            redis_url: Redis connection URL (e.g., "redis://localhost:6379")
        """
        self.fill_rate = fill_rate
        self.capacity = capacity
        self.scope = scope
        self.backend = backend
        self.redis_url = redis_url
        
        # Create Redis client if needed
        redis_client = None
        if backend == "redis":
            if redis_url is None:
                raise ValueError("redis_url is required when backend='redis'")
            redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        
        # Create the underlying limiter
        self._limiter = TokenBucketLimiter(
            capacity=capacity,
            fill_rate=fill_rate,
            scope=scope,
            backend=backend,
            redis_client=redis_client
        )
    
    def allow_request(self, identifier=None):
        """
        Check if a request should be allowed.
        
        Args:
            identifier: User ID, IP address, or None for global scope
            
        Returns:
            bool: True if request is allowed, False otherwise
        """
        return self._limiter.allow_request(identifier)
    
    def reset(self, identifier=None):
        """Reset rate limit state for an identifier"""
        return self._limiter.reset(identifier)
    
    def get_config(self):
        """Get configuration details"""
        return self._limiter.get_config()
    
    def __repr__(self):
        return (f"RateLimiter("
                f"fill_rate={self.fill_rate}, "
                f"capacity={self.capacity}, "
                f"scope='{self.scope}', "
                f"backend='{self.backend}')")
# src/RateLimiter/token_bucket.py
import time
from .base import BaseRateLimiter


class TokenBucketLimiter(BaseRateLimiter):
    """
    Token Bucket rate limiter implementation.
    
    Tokens are added to the bucket at a constant rate (fill_rate per second).
    Each request consumes 1 token. Request is denied if bucket is empty.
    Allows bursts up to capacity.
    """
    
    def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        
        # TTL for automatic cleanup
        self._ttl = int((capacity / fill_rate) * 2) + 60

    def allow_request(self, identifier=None):
        """
        Check if request should be allowed based on token bucket algorithm.
        
        Args:
            identifier: User ID, IP address, or None for global scope
            
        Returns:
            bool: True if request is allowed, False otherwise
        """
        key = self._get_key(identifier)
        now = time.time()
        
        # Get current bucket state
        data = self._get_from_backend(key)
        
        if data is None:
            # First request - initialize bucket with (capacity - 1) tokens
            new_data = {
                "tokens_remaining": self.capacity - 1,
                "last_fill_time": now
            }
            self._set_to_backend(key, new_data, ttl=self._ttl)
            return True
        
        tokens = float(data.get("tokens_remaining", 0))
        last_fill = float(data.get("last_fill_time", now))
        
        # Calculate tokens added since last check
        elapsed = now - last_fill
        tokens_to_add = elapsed * self.fill_rate
        tokens = min(self.capacity, tokens + tokens_to_add)
        
        # Check if we have at least 1 token
        if tokens >= 1:
            tokens -= 1
            allowed = True
        else:
            allowed = False
        
        # Update bucket state
        new_data = {
            "tokens_remaining": tokens,
            "last_fill_time": now
        }
        self._set_to_backend(key, new_data, ttl=self._ttl)
        
        return allowed

    def reset(self, identifier=None):
        """
        Reset rate limit by refilling the bucket.
        
        Args:
            identifier: User ID, IP address, or None for global scope
        """
        key = self._get_key(identifier)
        self._delete_from_backend(key)
    
    def get_wait_time(self, identifier=None):
        """
        Calculate time (in seconds) until next request would be allowed.
        
        Args:
            identifier: User ID, IP address, or None for global scope
            
        Returns:
            float: Seconds to wait (0 if request would be allowed now)
        """
        key = self._get_key(identifier)
        now = time.time()
        
        data = self._get_from_backend(key)
        if data is None:
            return 0.0
        
        tokens = float(data.get("tokens_remaining", 0))
        last_fill = float(data.get("last_fill_time", now))
        
        # Calculate current tokens after refill
        elapsed = now - last_fill
        tokens_to_add = elapsed * self.fill_rate
        current_tokens = min(self.capacity, tokens + tokens_to_add)
        
        # If we have at least 1 token, no wait needed
        if current_tokens >= 1:
            return 0.0
        
        # Calculate time needed to get 1 token
        tokens_needed = 1 - current_tokens
        wait_time = tokens_needed / self.fill_rate
        
        return max(0.0, wait_time)
    
    def get_status(self, identifier=None):
        """
        Get current bucket status for debugging/monitoring.
        
        Args:
            identifier: User ID, IP address, or None for global scope
            
        Returns:
            dict: Current bucket state including tokens and capacity
        """
        key = self._get_key(identifier)
        now = time.time()
        
        data = self._get_from_backend(key)
        if data is None:
            return {
                "tokens_remaining": self.capacity,
                "capacity": self.capacity,
                "fill_rate": self.fill_rate,
                "utilization_pct": 0.0
            }
        
        tokens = float(data.get("tokens_remaining", 0))
        last_fill = float(data.get("last_fill_time", now))
        
        # Calculate current tokens after refill
        elapsed = now - last_fill
        tokens_to_add = elapsed * self.fill_rate
        current_tokens = min(self.capacity, tokens + tokens_to_add)
        
        return {
            "tokens_remaining": round(current_tokens, 2),
            "capacity": self.capacity,
            "fill_rate": self.fill_rate,
            "utilization_pct": round((1 - current_tokens / self.capacity) * 100, 1),
            "last_fill_time": last_fill
        }
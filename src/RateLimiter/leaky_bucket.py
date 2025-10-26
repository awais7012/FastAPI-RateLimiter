"""
    Leaky Bucket rate limiter implementation.
    
    Water leaks out at a constant rate (fill_rate per second).
    Each request adds 1 unit of water. Request is denied if bucket overflows.
    """
    
import time
import json
from .base import BaseRateLimiter


class LeakyBucketLimiter(BaseRateLimiter):
    
    def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        
        
        self._ttl = int((capacity / fill_rate) * 2) + 60

    def allow_request(self, identifier=None):
        """
        Check if request should be allowed based on leaky bucket algorithm.
        
        Args:
            identifier: User ID, IP address, or None for global scope
            
        Returns:
            bool: True if request is allowed, False otherwise
        """
        key = self._get_key(identifier)
        now = time.time()
        
    
        data = self._get_from_backend(key)
        
        if data is None:
           
            new_data = {
                "water_level": 1.0,
                "last_check": now
            }
            self._set_to_backend(key, new_data, ttl=self._ttl)
            return True
        
        water_level = float(data.get("water_level", 0))
        last_check = float(data.get("last_check", now))
        
        # Calculate water leaked since last check
        elapsed = now - last_check
        leaked = elapsed * self.fill_rate
        water_level = max(0.0, water_level - leaked)
        
        # Check if new request can fit in bucket
        if water_level + 1 <= self.capacity:
            # Accept request - add water to bucket
            water_level += 1
            allowed = True
        else:
            # Reject request - bucket is full
            allowed = False
        
        # Update bucket state
        new_data = {
            "water_level": water_level,
            "last_check": now
        }
        self._set_to_backend(key, new_data, ttl=self._ttl)
        
        return allowed

    def reset(self, identifier=None):
        """
        Reset rate limit by emptying the bucket.
        
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
        
        water_level = float(data.get("water_level", 0))
        last_check = float(data.get("last_check", now))
        
        # Calculate current water level after leakage
        elapsed = now - last_check
        leaked = elapsed * self.fill_rate
        current_level = max(0.0, water_level - leaked)
        
        # If bucket has room, no wait needed
        if current_level + 1 <= self.capacity:
            return 0.0
        
        # Calculate how much needs to leak for next request
        excess = (current_level + 1) - self.capacity
        wait_time = excess / self.fill_rate
        
        return max(0.0, wait_time)
    
    def get_status(self, identifier=None):
        """
        Get current bucket status for debugging/monitoring.
        
        Args:
            identifier: User ID, IP address, or None for global scope
            
        Returns:
            dict: Current bucket state including water level and capacity
        """
        key = self._get_key(identifier)
        now = time.time()
        
        data = self._get_from_backend(key)
        if data is None:
            return {
                "water_level": 0.0,
                "capacity": self.capacity,
                "fill_rate": self.fill_rate,
                "available": self.capacity,
                "utilization_pct": 0.0
            }
        
        water_level = float(data.get("water_level", 0))
        last_check = float(data.get("last_check", now))
        
        # Calculate current level after leakage
        elapsed = now - last_check
        leaked = elapsed * self.fill_rate
        current_level = max(0.0, water_level - leaked)
        
        return {
            "water_level": round(current_level, 2),
            "capacity": self.capacity,
            "fill_rate": self.fill_rate,
            "available": round(max(0, self.capacity - current_level), 2),
            "utilization_pct": round((current_level / self.capacity) * 100, 1),
            "last_check": last_check
        }
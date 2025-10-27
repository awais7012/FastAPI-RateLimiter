import time
import threading
from collections import deque
from .base import BaseRateLimiter


class FixedWindowRateLimiter(BaseRateLimiter):
    """
    Fixed Window Rate Limiter - divides time into fixed windows.
    
    Pros: Simple, memory efficient
    Cons: Burst traffic at window boundaries (can get 2x capacity in short time)
    """
    
    def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        
        # TTL should be at least 2 windows to handle edge cases
        window_size = 1 / fill_rate
        self._ttl = int(window_size * 2) + 60
        
        # Per-key locks for memory backend
        self._key_locks = {}
        self._key_locks_lock = threading.Lock()

    def _get_key_lock(self, key):
        """Get or create a lock for a specific key"""
        with self._key_locks_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def allow_request(self, identifier=None):
        """
        Check if request should be allowed based on fixed window algorithm.
        
        Args:
            identifier: User ID, IP address, or None for global scope
            
        Returns:
            bool: True if request is allowed, False otherwise
        """
        key = self._get_key(identifier)
        
        # Use Redis atomic operations if available
        if self.backend == "redis":
            return self._allow_request_redis_atomic(key)
        
        # Use per-key locking for memory backend
        return self._allow_request_memory(key)
    
    def _allow_request_redis_atomic(self, key):
        """Atomic implementation using Redis INCR"""
        now = time.time()
        window_size = 1 / self.fill_rate
        current_window = int(now / window_size)
        
        # Use window-specific key for atomic operations
        window_key = f"{key}:window:{current_window}"
        
        try:
            # INCR is atomic in Redis
            count = self.redis_client.incr(window_key)
            
            # Set TTL on first increment
            if count == 1:
                self.redis_client.expire(window_key, self._ttl)
            
            return count <= self.capacity
        except Exception as e:
            print(f"Redis operation failed: {e}, falling back to non-atomic")
            return self._allow_request_memory(key)
    
    def _allow_request_memory(self, key):
        """Thread-safe implementation for memory backend"""
        now = time.time()
        window_size = 1 / self.fill_rate
        current_window = int(now / window_size)
        
        # Use per-key lock to prevent race conditions
        lock = self._get_key_lock(key)
        with lock:
            data = self._get_from_backend(key)
            
            if data is None:
                new_data = {
                    "count": 1,
                    "window_start": current_window
                }
                self._set_to_backend(key, new_data, ttl=self._ttl)
                return True
            
            count = int(data.get("count", 0))
            window_start = int(data.get("window_start", current_window))
            
            if window_start < current_window:
                # New window - reset count
                count = 1
                window_start = current_window
                allowed = True
            else:
                # Same window - check capacity
                if count < self.capacity:
                    count += 1
                    allowed = True
                else:
                    allowed = False
            
            new_data = {
                "count": count,
                "window_start": window_start
            }
            self._set_to_backend(key, new_data, ttl=self._ttl)
            
            return allowed

    def reset(self, identifier=None):
        """Reset rate limit state"""
        key = self._get_key(identifier)
        self._delete_from_backend(key)
    
    def get_status(self, identifier=None):
        """Get current window status"""
        key = self._get_key(identifier)
        now = time.time()
        window_size = 1 / self.fill_rate
        current_window = int(now / window_size)
        
        data = self._get_from_backend(key)
        if data is None:
            return {
                "count": 0,
                "capacity": self.capacity,
                "available": self.capacity,
                "window": current_window,
                "window_size": window_size
            }
        
        count = int(data.get("count", 0))
        window_start = int(data.get("window_start", current_window))
        
        # If old window, count is effectively 0
        if window_start < current_window:
            count = 0
        
        return {
            "count": count,
            "capacity": self.capacity,
            "available": max(0, self.capacity - count),
            "window": current_window,
            "window_size": window_size
        }




  
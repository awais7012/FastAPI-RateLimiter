import time
import json
from .base import BaseRateLimiter


class QueueLimiter(BaseRateLimiter):
    """
    Queue-based rate limiter (similar to Sliding Window).
    
    Maintains a queue of timestamps. Requests expire after (capacity / fill_rate) seconds.
    Request is allowed if queue has fewer than capacity items.
    """
    
    def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        
        # TTL for automatic cleanup (time for queue to fully expire + buffer)
        self._ttl = int((capacity / fill_rate) * 2) + 60
        
        # Time window for request expiration
        self._window = capacity / fill_rate

    def _cleanup_queue(self, queue, current_time):
        """
        Remove expired timestamps from queue.
        
        Args:
            queue: List of timestamps
            current_time: Current time
            
        Returns:
            list: Cleaned queue with only valid timestamps
        """
        cutoff_time = current_time - self._window
        # Remove timestamps older than the window
        return [ts for ts in queue if ts > cutoff_time]

    def allow_request(self, identifier=None):
        """
        Check if request should be allowed based on queue size.
        
        Args:
            identifier: User ID, IP address, or None for global scope
            
        Returns:
            bool: True if request is allowed, False otherwise
        """
        key = self._get_key(identifier)
        now = time.time()
        
        # Get current queue state
        data = self._get_from_backend(key)
        
        if data is None:
            # First request - initialize queue
            new_data = {
                "queue": [now],
                "last_update": now
            }
            self._set_to_backend(key, new_data, ttl=self._ttl)
            return True
        
        queue = data.get("queue", [])
        
        # Remove expired requests
        queue = self._cleanup_queue(queue, now)
        
        # Check if we have capacity for a new request
        if len(queue) < self.capacity:
            queue.append(now)
            allowed = True
        else:
            allowed = False
        
        # Update storage
        new_data = {
            "queue": queue,
            "last_update": now
        }
        self._set_to_backend(key, new_data, ttl=self._ttl)
        
        return allowed

    def reset(self, identifier=None):
        """
        Reset rate limit by clearing the queue.
        
        Args:
            identifier: User ID, IP address, or None for global scope
        """
        key = self._get_key(identifier)
        self._delete_from_backend(key)

    def get_retry_after(self, identifier=None):
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
        
        queue = data.get("queue", [])
        
        # Remove expired requests
        queue = self._cleanup_queue(queue, now)
        
        # If queue is not full, request can be made immediately
        if len(queue) < self.capacity:
            return 0.0
        
        # Find the oldest request in the queue
        if not queue:
            return 0.0
        
        oldest_timestamp = min(queue)
        cutoff_time = now - self._window
        
        # Calculate when the oldest request will expire
        time_until_expiry = oldest_timestamp - cutoff_time
        
        return max(0.0, time_until_expiry)

    def get_current_usage(self, identifier=None):
        """
        Get current queue usage statistics.
        
        Args:
            identifier: User ID, IP address, or None for global scope
            
        Returns:
            dict: Current usage statistics
        """
        key = self._get_key(identifier)
        now = time.time()
        
        data = self._get_from_backend(key)
        if data is None:
            return {
                "current_requests": 0,
                "capacity": self.capacity,
                "available_slots": self.capacity,
                "fill_rate": self.fill_rate,
                "window_seconds": self._window,
                "utilization_pct": 0.0
            }
        
        queue = data.get("queue", [])
        
        # Remove expired requests
        queue = self._cleanup_queue(queue, now)
        
        current_count = len(queue)
        
        return {
            "current_requests": current_count,
            "capacity": self.capacity,
            "available_slots": self.capacity - current_count,
            "fill_rate": self.fill_rate,
            "window_seconds": round(self._window, 2),
            "utilization_pct": round((current_count / self.capacity) * 100, 1),
            "oldest_request_age": round(now - min(queue), 2) if queue else 0.0
        }

    def get_status(self, identifier=None):
        """
        Alias for get_current_usage for consistency with other limiters.
        """
        return self.get_current_usage(identifier)
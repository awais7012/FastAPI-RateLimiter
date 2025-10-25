import time
import json
from .base import BaseRateLimiter


class QueueLimiter(BaseRateLimiter):
   
    
    def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        self._store = {} if backend == "memory" else None

    def _get_data(self, key):
       
        if self.backend == "redis":
            data = self.redis_client.hgetall(key)
            if data:
                # Handle both bytes and string keys from Redis
                queue_key = b"queue" if b"queue" in data else "queue"
                last_check_key = b"last_check" if b"last_check" in data else "last_check"
                
                queue_str = data.get(queue_key, b"[]" if isinstance(queue_key, bytes) else "[]")
                if isinstance(queue_str, bytes):
                    queue_str = queue_str.decode()
                
                last_check_str = data.get(last_check_key, b"0" if isinstance(last_check_key, bytes) else "0")
                if isinstance(last_check_str, bytes):
                    last_check_str = last_check_str.decode()
                
                return {
                    "queue": json.loads(queue_str),
                    "last_check": float(last_check_str)
                }
            return {"queue": [], "last_check": time.time()}
        
        return self._store.get(key, {"queue": [], "last_check": time.time()})

    def _set_data(self, key, mapping):
        """Store queue data to storage backend"""
        if self.backend == "redis":
            redis_mapping = {
                "queue": json.dumps(mapping["queue"]),
                "last_check": str(mapping["last_check"])
            }
            self.redis_client.hset(key, mapping=redis_mapping)
        else:
            self._store[key] = mapping

    def allow_request(self, identifier=None):
       
        key = self._get_key(identifier)
        data = self._get_data(key)
        now = time.time()

        queue = data.get("queue", [])
        last_check = float(data.get("last_check", now))

        # Calculate how many requests should have expired
        time_elapsed = now - last_check
        requests_to_remove = int(time_elapsed * self.fill_rate)
        
        # Remove expired requests from the front of the queue
        if requests_to_remove > 0:
            queue = queue[requests_to_remove:]
            last_check = now

        # Check if we have capacity for a new request
        if len(queue) < self.capacity:
            queue.append(now)
            self._set_data(key, {"queue": queue, "last_check": last_check})
            return True
        else:
            # Update storage even for blocked requests
            self._set_data(key, {"queue": queue, "last_check": last_check})
            return False

    def get_retry_after(self, identifier=None):
       
        key = self._get_key(identifier)
        data = self._get_data(key)
        now = time.time()

        queue = data.get("queue", [])
        last_check = float(data.get("last_check", now))

        # If queue is not full, request can be made immediately
        if len(queue) < self.capacity:
            return 0
        
        # Calculate when the next slot will become available
        time_elapsed = now - last_check
        requests_to_remove = int(time_elapsed * self.fill_rate)
        
        if requests_to_remove > 0:
            return 0
        
        # Time until one slot becomes available (1 token / fill_rate)
        time_until_next_token = (1.0 / self.fill_rate) - time_elapsed
        return max(0, time_until_next_token)

    def get_current_usage(self, identifier=None):
        """Get current queue usage statistics"""
        key = self._get_key(identifier)
        data = self._get_data(key)
        now = time.time()

        queue = data.get("queue", [])
        last_check = float(data.get("last_check", now))

        # Calculate current valid requests
        time_elapsed = now - last_check
        requests_to_remove = int(time_elapsed * self.fill_rate)
        
        if requests_to_remove > 0:
            queue = queue[requests_to_remove:]

        return {
            "current_requests": len(queue),
            "capacity": self.capacity,
            "available_slots": self.capacity - len(queue),
            "fill_rate": self.fill_rate
        }
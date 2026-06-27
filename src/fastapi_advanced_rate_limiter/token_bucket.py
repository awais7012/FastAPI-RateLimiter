# src/RateLimiter/token_bucket.py
import time
import threading
from .base import BaseRateLimiter


class TokenBucketLimiter(BaseRateLimiter):
    def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        self._ttl = int((capacity / fill_rate) * 2) + 60
        
        
        self._key_locks = {}
        self._key_locks_lock = threading.Lock()

    def _get_key_lock(self, key):
        """Get or create a lock for a specific key"""
        with self._key_locks_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def allow_request(self, identifier=None):
        key = self._get_key(identifier)

        # Use Redis atomic operations (safe across multiple replicas)
        if self.backend == "redis":
            return self._allow_request_redis_atomic(key)

        # Use per-key locking for memory backend (single process only)
        return self._allow_request_memory(key)

    def _allow_request_redis_atomic(self, key):
        """
        Atomic implementation using a Redis Lua script.

        The entire refill-check-decrement-store sequence runs inside Redis as a
        single atomic operation, so concurrent requests from multiple API
        replicas (or worker processes) cannot lose updates.
        """
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local fill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local ttl = tonumber(ARGV[4])

        local data = redis.call('GET', key)
        local tokens, last_fill
        if data then
            local state = cjson.decode(data)
            tokens = tonumber(state.tokens_remaining)
            last_fill = tonumber(state.last_fill_time)
        else
            tokens = capacity
            last_fill = now
        end

        -- Refill based on elapsed time
        local elapsed = now - last_fill
        tokens = math.min(capacity, tokens + elapsed * fill_rate)

        local allowed = 0
        if tokens >= 1 then
            tokens = tokens - 1
            allowed = 1
        end

        local new_data = cjson.encode({
            tokens_remaining = tokens,
            last_fill_time = now
        })
        redis.call('SETEX', key, ttl, new_data)

        return {allowed, tostring(tokens)}
        """

        now = time.time()
        try:
            result = self.redis_client.eval(
                lua_script,
                1,  # number of keys
                key,
                self.capacity,
                self.fill_rate,
                now,
                self._ttl
            )
            return bool(result[0])
        except Exception as e:
            print(f"Redis Lua script failed: {e}, falling back to non-atomic")
            return self._allow_request_memory(key)

    def _allow_request_memory(self, key):
        """Thread-safe implementation for memory backend"""
        now = time.time()

        # Use per-key lock for thread safety
        lock = self._get_key_lock(key)
        with lock:
            data = self._get_from_backend(key)

            if data is None:
                new_data = {
                    "tokens_remaining": self.capacity - 1,
                    "last_fill_time": now
                }
                self._set_to_backend(key, new_data, ttl=self._ttl)
                return True

            tokens = float(data.get("tokens_remaining", 0))
            last_fill = float(data.get("last_fill_time", now))

            elapsed = now - last_fill
            tokens_to_add = elapsed * self.fill_rate
            tokens = min(self.capacity, tokens + tokens_to_add)

            if tokens >= 1:
                tokens -= 1
                allowed = True
            else:
                allowed = False

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
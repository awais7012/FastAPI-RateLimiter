import time
import threading
from .base import BaseRateLimiter


class SlidingWindowRateLimiter(BaseRateLimiter):
    """Sliding Window Rate Limiter - uses weighted count from previous window"""
    
    def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        window_size = 1 / fill_rate
        self._ttl = int(window_size * 3) + 60
        self._key_locks = {}
        self._key_locks_lock = threading.Lock()

    def _get_key_lock(self, key):
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

        The weighted-count read-modify-write runs as a single atomic operation
        inside Redis, so concurrent requests from multiple API replicas cannot
        over-admit by racing on the same window state.
        """
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local fill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local ttl = tonumber(ARGV[4])

        local window_size = 1 / fill_rate
        local current_window = math.floor(now / window_size)

        local data = redis.call('GET', key)
        local stored_window, current_count, previous_count
        if data then
            local state = cjson.decode(data)
            stored_window = tonumber(state.current_window)
            current_count = tonumber(state.current_count)
            previous_count = tonumber(state.previous_count)
        else
            stored_window = current_window
            current_count = 0
            previous_count = 0
        end

        if stored_window < current_window then
            if stored_window == current_window - 1 then
                previous_count = current_count
            else
                previous_count = 0
            end
            current_count = 0
            stored_window = current_window
        end

        local elapsed_in_window = (now % window_size) / window_size
        local weighted_count = current_count + (1 - elapsed_in_window) * previous_count

        local allowed = 0
        if weighted_count < capacity then
            current_count = current_count + 1
            allowed = 1
        end

        local new_data = cjson.encode({
            current_window = stored_window,
            current_count = current_count,
            previous_count = previous_count
        })
        redis.call('SETEX', key, ttl, new_data)

        return {allowed}
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
        window_size = 1 / self.fill_rate
        current_window = int(now / window_size)

        lock = self._get_key_lock(key)
        with lock:
            data = self._get_from_backend(key)
            
            if data is None:
                new_data = {
                    "current_window": current_window,
                    "current_count": 1,
                    "previous_count": 0
                }
                self._set_to_backend(key, new_data, ttl=self._ttl)
                return True
            
            stored_window = int(data.get("current_window", current_window))
            current_count = int(data.get("current_count", 0))
            previous_count = int(data.get("previous_count", 0))
            
            if stored_window < current_window:
                if stored_window == current_window - 1:
                    previous_count = current_count
                else:
                    previous_count = 0
                current_count = 0
                stored_window = current_window
            
            elapsed_in_window = (now % window_size) / window_size
            weighted_count = current_count + (1 - elapsed_in_window) * previous_count
            
            if weighted_count < self.capacity:
                current_count += 1
                allowed = True
            else:
                allowed = False
            
            new_data = {
                "current_window": stored_window,
                "current_count": current_count,
                "previous_count": previous_count
            }
            self._set_to_backend(key, new_data, ttl=self._ttl)
            return allowed

    def reset(self, identifier=None):
        key = self._get_key(identifier)
        self._delete_from_backend(key)

import time
import json
import threading
from .base import BaseRateLimiter


class LeakyBucketLimiter(BaseRateLimiter):
    
    def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        
        self._ttl = int((capacity / fill_rate) * 2) + 60
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
        Check if request should be allowed based on leaky bucket algorithm.
        
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
        """
        Atomic implementation using Redis Lua script.
        This eliminates race conditions entirely.
        """
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local fill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local ttl = tonumber(ARGV[4])
        
        -- Get current state
        local data = redis.call('GET', key)
        local water_level, last_check
        
        if data then
            local state = cjson.decode(data)
            water_level = tonumber(state.water_level)
            last_check = tonumber(state.last_check)
        else
            water_level = 0
            last_check = now
        end
        
        -- Calculate leakage
        local elapsed = now - last_check
        local leaked = elapsed * fill_rate
        water_level = math.max(0, water_level - leaked)
        
        -- Check if request can be accepted
        local allowed = 0
        if water_level + 1 <= capacity then
            water_level = water_level + 1
            allowed = 1
        end
        
        -- Save state
        local new_data = cjson.encode({
            water_level = water_level,
            last_check = now
        })
        redis.call('SETEX', key, ttl, new_data)
        
        return {allowed, water_level}
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
            # Fallback to non-atomic if Lua script fails
            print(f"Redis Lua script failed: {e}, falling back to non-atomic")
            return self._allow_request_memory(key)
    
    def _allow_request_memory(self, key):
        """Thread-safe implementation for memory backend"""
        now = time.time()
        
        # Use per-key lock to prevent race conditions
        lock = self._get_key_lock(key)
        with lock:
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
                water_level += 1
                allowed = True
            else:
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
        
        # For memory backend, use lock to get consistent state
        if self.backend == "memory":
            lock = self._get_key_lock(key)
            with lock:
                return self._calculate_wait_time(key, now)
        else:
            return self._calculate_wait_time(key, now)
    
    def _calculate_wait_time(self, key, now):
        """Helper to calculate wait time"""
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
        
        # For memory backend, use lock for consistent state
        if self.backend == "memory":
            lock = self._get_key_lock(key)
            with lock:
                return self._get_status_snapshot(key, now)
        else:
            return self._get_status_snapshot(key, now)
    
    def _get_status_snapshot(self, key, now):
        """Helper to get status snapshot"""
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
            "last_check": last_check,
            "elapsed_since_check": round(elapsed, 2)
        }
class SlidingWindowLogRateLimiter(BaseRateLimiter):
      """
    Sliding Window Log - keeps timestamp of each request.
    
    Pros: Most accurate, no boundary issues
    Cons: Memory intensive (stores all timestamps), O(n) time complexity
    
    Use this when you need perfect accuracy and request volume is moderate.
    """
    
def __init__(self, capacity, fill_rate, scope="user", backend="memory", redis_client=None):
        super().__init__(capacity, fill_rate, scope, backend, redis_client)
        
        self._window_size = 1 / fill_rate
        self._ttl = int(self._window_size * 2) + 60
        
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
        Check if request should be allowed based on sliding window log.
        
        Args:
            identifier: User ID, IP address, or None for global scope
            
        Returns:
            bool: True if request is allowed, False otherwise
        """
        key = self._get_key(identifier)
        
        # Redis implementation using sorted sets
        if self.backend == "redis":
            return self._allow_request_redis(key)
        
        # Memory implementation
        return self._allow_request_memory(key)
    
def _allow_request_redis(self, key):
        """Redis implementation using sorted sets (ZSET)"""
        now = time.time()
        window_start = now - self._window_size
        
        try:
            # Remove old timestamps (atomic)
            self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Count requests in current window
            count = self.redis_client.zcard(key)
            
            if count < self.capacity:
                # Add current timestamp with score = timestamp
                self.redis_client.zadd(key, {str(now): now})
                self.redis_client.expire(key, self._ttl)
                return True
            else:
                return False
        except Exception as e:
            print(f"Redis operation failed: {e}")
            return False
    
def _allow_request_memory(self, key):
        """Memory implementation using list of timestamps"""
        now = time.time()
        window_start = now - self._window_size
        
        lock = self._get_key_lock(key)
        with lock:
            data = self._get_from_backend(key)
            
            # Get existing timestamps
            if data is None:
                timestamps = []
            else:
                timestamps = data.get("timestamps", [])
            
            # Remove expired timestamps
            timestamps = [ts for ts in timestamps if ts > window_start]
            
            # Check if we can accept the request
            if len(timestamps) < self.capacity:
                timestamps.append(now)
                self._set_to_backend(key, {"timestamps": timestamps}, ttl=self._ttl)
                return True
            else:
                # Still save the cleaned list
                self._set_to_backend(key, {"timestamps": timestamps}, ttl=self._ttl)
                return False

def reset(self, identifier=None):
        """Reset rate limit state"""
        key = self._get_key(identifier)
        self._delete_from_backend(key)
    
def get_status(self, identifier=None):
        """Get current status"""
        key = self._get_key(identifier)
        now = time.time()
        window_start = now - self._window_size
        
        if self.backend == "redis":
            try:
                count = self.redis_client.zcount(key, window_start, now)
            except:
                count = 0
        else:
            data = self._get_from_backend(key)
            if data is None:
                count = 0
            else:
                timestamps = data.get("timestamps", [])
                count = sum(1 for ts in timestamps if ts > window_start)
        
        return {
            "count": count,
            "capacity": self.capacity,
            "available": max(0, self.capacity - count),
            "window_size": self._window_size
        }
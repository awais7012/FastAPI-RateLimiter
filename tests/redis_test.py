# test_redis_backend.py
"""
Comprehensive Redis backend test for all rate limiters
Tests: Token Bucket, Leaky Bucket, Queue Limiter with Redis backend
"""
import threading
import time
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from RateLimiter.token_bucket import TokenBucketLimiter
from RateLimiter.leaky_bucket import LeakyBucketLimiter
from RateLimiter.queue_limiter import QueueLimiter

# Redis import
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("❌ Redis not installed. Install with: pip install redis")
    sys.exit(1)

# === CONFIG ===
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

TEST_DURATION = 8  # seconds
CAPACITY = 10
FILL_RATE = 2.0

# Test users
USERS = [
    ("alice", 0.3),    # 3.3 req/sec
    ("bob", 0.5),      # 2 req/sec
    ("charlie", 0.15), # 6.6 req/sec
]


class ThreadSafeCounter:
    """Thread-safe counter for tracking results"""
    def __init__(self):
        self.lock = threading.Lock()
        self.data = defaultdict(lambda: {"allowed": 0, "blocked": 0})
    
    def increment(self, user_id, allowed):
        with self.lock:
            if allowed:
                self.data[user_id]["allowed"] += 1
            else:
                self.data[user_id]["blocked"] += 1
    
    def get_snapshot(self):
        with self.lock:
            return dict(self.data)


def get_redis_client():
    """Create and test Redis connection"""
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=False
        )
        client.ping()
        return client
    except redis.ConnectionError as e:
        print(f"❌ Redis connection failed: {e}")
        print(f"   Make sure Redis is running on {REDIS_HOST}:{REDIS_PORT}")
        print(f"\n   Start Redis:")
        print(f"   - Windows: redis-server.exe")
        print(f"   - Linux/Mac: redis-server")
        print(f"   - Docker: docker run -p 6379:6379 redis")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def cleanup_redis(redis_client):
    """Clean up all rate limit keys from Redis"""
    try:
        keys = redis_client.keys("ratelimit:*")
        if keys:
            redis_client.delete(*keys)
            print(f"🧹 Cleaned up {len(keys)} Redis keys")
        else:
            print("🧹 No keys to clean up")
    except Exception as e:
        print(f"⚠️  Cleanup failed: {e}")


def worker(user_id, interval, counter, stop, limiter):
    """Worker thread simulating user requests"""
    while not stop.is_set():
        try:
            allowed = limiter.allow_request(user_id)
            counter.increment(user_id, allowed)
            time.sleep(interval)
        except Exception as e:
            print(f"\n⚠️  Error in {user_id}: {e}")
            break


def test_single_scope(limiter_class, name, scope, redis_client):
    """Test a single limiter with specific scope"""
    print(f"\n{'─'*70}")
    print(f"Testing {name} - {scope.upper()} scope")
    print(f"{'─'*70}")
    
    try:
        limiter = limiter_class(
            capacity=CAPACITY,
            fill_rate=FILL_RATE,
            scope=scope,
            backend="redis",
            redis_client=redis_client
        )
    except Exception as e:
        print(f"❌ Failed to create limiter: {e}")
        return None
    
    counter = ThreadSafeCounter()
    stop = threading.Event()
    threads = []
    
    # Determine identifier based on scope
    if scope == "user":
        identifiers = {user_id: user_id for user_id, _ in USERS}
    elif scope == "ip":
        identifiers = {user_id: f"10.0.0.{i+1}" for i, (user_id, _) in enumerate(USERS)}
    else:  # global
        identifiers = {user_id: None for user_id, _ in USERS}
    
    # Create worker with appropriate identifier
    def scoped_worker(user_id, interval):
        identifier = identifiers[user_id]
        while not stop.is_set():
            try:
                allowed = limiter.allow_request(identifier)
                counter.increment(user_id, allowed)
                time.sleep(interval)
            except Exception as e:
                print(f"\n⚠️  Error in {user_id}: {e}")
                break
    
    # Start workers
    for user_id, interval in USERS:
        t = threading.Thread(
            target=scoped_worker,
            args=(user_id, interval),
            daemon=True
        )
        t.start()
        threads.append(t)
    
    # Run test
    start = time.time()
    time.sleep(TEST_DURATION)
    stop.set()
    
    for t in threads:
        t.join(timeout=2.0)
    
    elapsed = time.time() - start
    snapshot = counter.get_snapshot()
    
    # Print results
    total_allowed = sum(d["allowed"] for d in snapshot.values())
    total_blocked = sum(d["blocked"] for d in snapshot.values())
    
    for user_id, _ in USERS:
        data = snapshot.get(user_id, {"allowed": 0, "blocked": 0})
        rate = data["allowed"] / elapsed
        print(f"  {user_id:10s}: allowed={data['allowed']:3d} blocked={data['blocked']:3d} rate={rate:.2f}/s")
    
    success_rate = (total_allowed / (total_allowed + total_blocked) * 100) if total_allowed + total_blocked > 0 else 0
    print(f"  {'TOTAL':10s}: allowed={total_allowed:3d} blocked={total_blocked:3d} success={success_rate:.1f}%")
    
    return {
        "limiter": name,
        "scope": scope,
        "allowed": total_allowed,
        "blocked": total_blocked,
        "rate": total_allowed / elapsed,
        "success": success_rate
    }


def verify_redis_persistence(redis_client):
    """Verify that data persists in Redis between requests"""
    print(f"\n{'='*70}")
    print("REDIS PERSISTENCE TEST")
    print(f"{'='*70}")
    
    limiter = TokenBucketLimiter(
        capacity=5,
        fill_rate=1.0,
        scope="user",
        backend="redis",
        redis_client=redis_client
    )
    
    user_id = "persistence_test_user"
    
    print("\n1️⃣  Making 3 requests...")
    for i in range(3):
        result = "✅" if limiter.allow_request(user_id) else "❌"
        print(f"   Request {i+1}: {result}")
    
    # Check Redis directly
    key = f"ratelimit:user:{user_id}"
    redis_data = redis_client.get(key)
    print(f"\n2️⃣  Redis key '{key}' exists: {redis_data is not None}")
    
    if redis_data:
        import json
        data = json.loads(redis_data)
        print(f"   Stored data: {data}")
    
    print("\n3️⃣  Creating NEW limiter instance (simulating app restart)...")
    limiter2 = TokenBucketLimiter(
        capacity=5,
        fill_rate=1.0,
        scope="user",
        backend="redis",
        redis_client=redis_client
    )
    
    print("\n4️⃣  Making 3 more requests with new instance...")
    for i in range(3):
        result = "✅" if limiter2.allow_request(user_id) else "❌"
        print(f"   Request {i+1}: {result}")
    
    status = limiter2.get_status(user_id)
    if 'tokens_remaining' in status:
        print(f"\n5️⃣  Final token count: {status['tokens_remaining']:.2f}/5")
        expected = 5 - 6  # Made 6 requests total
        if abs(status['tokens_remaining'] - max(0, expected)) < 0.1:
            print("   ✅ Persistence verified! State survived across instances")
        else:
            print("   ⚠️  Unexpected token count")


def test_concurrent_access(redis_client):
    """Test thread safety with Redis backend"""
    print(f"\n{'='*70}")
    print("CONCURRENT ACCESS TEST (Thread Safety)")
    print(f"{'='*70}")
    
    limiter = TokenBucketLimiter(
        capacity=100,
        fill_rate=10.0,
        scope="global",
        backend="redis",
        redis_client=redis_client
    )
    
    allowed_count = [0]
    lock = threading.Lock()
    
    def hammer():
        """Make 50 rapid requests"""
        for _ in range(50):
            if limiter.allow_request(None):
                with lock:
                    allowed_count[0] += 1
    
    # Start 10 threads making requests simultaneously
    print("\n🔨 Starting 10 threads, each making 50 requests (500 total)...")
    threads = []
    start = time.time()
    
    for i in range(10):
        t = threading.Thread(target=hammer)
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()
    
    elapsed = time.time() - start
    
    print(f"\n📊 Results:")
    print(f"   Total requests: 500")
    print(f"   Allowed: {allowed_count[0]}")
    print(f"   Blocked: {500 - allowed_count[0]}")
    print(f"   Time: {elapsed:.2f}s")
    
    # Expected: capacity=100, so should allow ~100 requests
    if 90 <= allowed_count[0] <= 110:
        print(f"   ✅ Thread safety verified! (~100 expected, got {allowed_count[0]})")
    else:
        print(f"   ⚠️  Unexpected count (expected ~100)")


def main():
    print("="*70)
    print("REDIS BACKEND COMPREHENSIVE TEST")
    print("="*70)
    
    # Connect to Redis
    print(f"\n🔌 Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    redis_client = get_redis_client()
    
    if not redis_client:
        print("\n❌ Cannot proceed without Redis connection")
        return
    
    print("✅ Redis connection successful!")
    
    # Clean up old data
    print("\n🧹 Cleaning up old test data...")
    cleanup_redis(redis_client)
    
    # Test settings
    print(f"\n⚙️  Test Configuration:")
    print(f"   Duration: {TEST_DURATION}s per test")
    print(f"   Capacity: {CAPACITY}")
    print(f"   Fill rate: {FILL_RATE}/s")
    print(f"   Users: {len(USERS)} concurrent")
    
    # Run tests for all combinations
    limiters = [
        (TokenBucketLimiter, "Token Bucket"),
        (LeakyBucketLimiter, "Leaky Bucket"),
        (QueueLimiter, "Queue Limiter"),
    ]
    
    scopes = ["user", "ip", "global"]
    results = []
    
    print(f"\n{'='*70}")
    print("RATE LIMITER TESTS")
    print(f"{'='*70}")
    
    for limiter_class, name in limiters:
        print(f"\n{'═'*70}")
        print(f"  {name}")
        print(f"{'═'*70}")
        
        for scope in scopes:
            result = test_single_scope(limiter_class, name, scope, redis_client)
            if result:
                results.append(result)
            
            # Clean up between tests
            cleanup_redis(redis_client)
            time.sleep(0.5)
    
    # Comparison table
    if results:
        print(f"\n{'='*70}")
        print("COMPARISON SUMMARY")
        print(f"{'='*70}")
        print(f"{'Limiter':<20} {'Scope':<8} {'Allowed':>8} {'Blocked':>8} {'Rate/s':>8} {'Success%':>9}")
        print("─"*70)
        
        for r in results:
            print(f"{r['limiter']:<20} {r['scope']:<8} {r['allowed']:>8} {r['blocked']:>8} "
                  f"{r['rate']:>7.2f} {r['success']:>8.1f}%")
    
    # Additional tests
    print(f"\n{'='*70}")
    print("ADDITIONAL REDIS TESTS")
    print(f"{'='*70}")
    
    cleanup_redis(redis_client)
    verify_redis_persistence(redis_client)
    
    cleanup_redis(redis_client)
    test_concurrent_access(redis_client)
    
    # Final cleanup
    print(f"\n{'='*70}")
    cleanup_redis(redis_client)
    
    # Close connection
    redis_client.close()
    print("\n✅ All Redis tests completed!")
    print("="*70)


if __name__ == "__main__":
    if not REDIS_AVAILABLE:
        print("❌ Redis module not available")
        print("   Install with: pip install redis")
    else:
        try:
            main()
        except KeyboardInterrupt:
            print("\n\n⚠️  Tests interrupted by user")
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
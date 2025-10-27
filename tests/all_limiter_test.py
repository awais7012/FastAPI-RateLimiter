# test_all_limiters_comprehensive.py
import threading
import time
import sys
import os
from collections import defaultdict
from typing import Optional

# Add src/ to path - TWO methods to ensure it works
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Also add parent directory
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_path not in sys.path:
    sys.path.insert(0, parent_path)

# Try importing from both paths
try:
    from RateLimiter.token_bucket import TokenBucketLimiter
    from RateLimiter.leaky_bucket import LeakyBucketLimiter
    from RateLimiter.queue_limiter import QueueLimiter
except ImportError:
    from src.RateLimiter.token_bucket import TokenBucketLimiter
    from src.RateLimiter.leaky_bucket import LeakyBucketLimiter
    from src.RateLimiter.queue_limiter import QueueLimiter

# Import window-based limiters
FixedWindowRateLimiter = None
SlidingWindowRateLimiter = None
SlidingWindowLogRateLimiter = None

try:
    from RateLimiter.fixed_window import FixedWindowRateLimiter
except ImportError:
    try:
        from src.RateLimiter.fixed_window import FixedWindowRateLimiter
    except ImportError:
        print("⚠️  FixedWindowRateLimiter not found, will skip")

try:
    from RateLimiter.sliding_window import SlidingWindowRateLimiter
except ImportError:
    try:
        from src.RateLimiter.sliding_window import SlidingWindowRateLimiter
    except ImportError:
        print("⚠️  SlidingWindowRateLimiter not found, will skip")

try:
    from RateLimiter.sliding_window_log import SlidingWindowLogRateLimiter
except ImportError:
    try:
        from src.RateLimiter.sliding_window_log import SlidingWindowLogRateLimiter
    except ImportError:
        print("⚠️  SlidingWindowLogRateLimiter not found, will skip")

# Optional Redis support
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️  Redis not installed. Install with: pip install redis")

# === CONFIG ===
TEST_DURATION = 10  # seconds per test
PRINT_EVERY = 2    # seconds

# Rate limiter settings for different scopes
LIMITERS_CONFIG = {
    "user": {"capacity": 5, "fill_rate": 1.0},    # 5 requests, refill 1/sec
    "ip": {"capacity": 10, "fill_rate": 2.0},     # 10 requests, refill 2/sec
    "global": {"capacity": 20, "fill_rate": 5.0}, # 20 requests, refill 5/sec
}

# User simulation patterns (user_id, request_interval_seconds)
USERS = [
    ("user_normal", 0.5),    # 2 req/sec
    ("user_bursty", 0.05),   # 20 req/sec (very aggressive)
    ("user_light", 1.5),     # 0.67 req/sec
    ("user_medium", 0.3),    # 3.33 req/sec
    ("user_heavy", 0.2),     # 5 req/sec
]

# Redis connection (if available)
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "decode_responses": True  # Important for consistent behavior
}


class Stats:
    """Thread-safe statistics collector"""
    def __init__(self):
        self.lock = threading.Lock()
        self.data = defaultdict(lambda: {
            "allowed": 0,
            "blocked": 0,
            "blocked_by_user": 0,
            "blocked_by_ip": 0,
            "blocked_by_global": 0,
        })
    
    def record(self, user_id: str, allowed: bool, blocked_by: Optional[str] = None):
        with self.lock:
            if allowed:
                self.data[user_id]["allowed"] += 1
            else:
                self.data[user_id]["blocked"] += 1
                if blocked_by:
                    self.data[user_id][f"blocked_by_{blocked_by}"] += 1
    
    def get_snapshot(self):
        with self.lock:
            return dict(self.data)
    
    def reset(self):
        with self.lock:
            self.data.clear()


def user_worker(user_id: str, sleep_interval: float, stats: Stats, 
                stop_event: threading.Event, user_rl, ip_rl, global_rl):
    """Simulate a user making requests through cascading rate limiters"""
    # Assign IP based on user (some users share IPs)
    ip_mapping = {
        "user_normal": "192.0.2.1",
        "user_bursty": "192.0.2.1",  # Same IP as normal
        "user_light": "192.0.2.2",
        "user_medium": "192.0.2.2",   # Same IP as light
        "user_heavy": "192.0.2.3",
    }
    ip = ip_mapping.get(user_id, "192.0.2.255")
    
    while not stop_event.is_set():
        try:
            # Check rate limiters in order: global -> IP -> user
            
            # 1. Global limiter (all users share this)
            if global_rl and not global_rl.allow_request(None):
                stats.record(user_id, allowed=False, blocked_by="global")
                time.sleep(sleep_interval)
                continue
            
            # 2. IP limiter (users sharing IP share this limit)
            if ip_rl and not ip_rl.allow_request(ip):
                stats.record(user_id, allowed=False, blocked_by="ip")
                time.sleep(sleep_interval)
                continue
            
            # 3. Per-user limiter
            if user_rl.allow_request(user_id):
                stats.record(user_id, allowed=True)
            else:
                stats.record(user_id, allowed=False, blocked_by="user")
            
            time.sleep(sleep_interval)
        
        except Exception as e:
            print(f"Error in worker {user_id}: {e}")
            break


def print_progress(stats: Stats, elapsed: float, limiter_name: str, backend: str):
    """Print formatted progress update"""
    snapshot = stats.get_snapshot()
    
    print(f"\n{'='*90}")
    print(f"  {limiter_name} | {backend.upper()} Backend | Elapsed: {elapsed:.1f}s")
    print(f"{'='*90}")
    print(f"{'User':<15} {'Allowed':>8} {'Blocked':>8} {'By User':>8} "
          f"{'By IP':>8} {'By Global':>8} {'Rate/s':>8}")
    print(f"{'-'*90}")
    
    total_allowed = 0
    total_blocked = 0
    
    for user_id, _ in USERS:
        data = snapshot.get(user_id, {})
        allowed = data.get("allowed", 0)
        blocked = data.get("blocked", 0)
        blocked_user = data.get("blocked_by_user", 0)
        blocked_ip = data.get("blocked_by_ip", 0)
        blocked_global = data.get("blocked_by_global", 0)
        
        rate = allowed / elapsed if elapsed > 0 else 0
        
        print(f"{user_id:<15} {allowed:>8} {blocked:>8} {blocked_user:>8} "
              f"{blocked_ip:>8} {blocked_global:>8} {rate:>7.2f}")
        
        total_allowed += allowed
        total_blocked += blocked
    
    print(f"{'-'*90}")
    total_rate = total_allowed / elapsed if elapsed > 0 else 0
    success_rate = (total_allowed / (total_allowed + total_blocked) * 100) if (total_allowed + total_blocked) > 0 else 0
    
    print(f"{'TOTAL':<15} {total_allowed:>8} {total_blocked:>8} "
          f"{'':>8} {'':>8} {'':>8} {total_rate:>7.2f}")
    print(f"Success Rate: {success_rate:.1f}%")


def run_single_test(limiter_class, limiter_name: str, backend: str, redis_client=None):
    """Run a single test configuration"""
    print(f"\n{'#'*90}")
    print(f"# Testing: {limiter_name} with {backend.upper()} backend")
    print(f"{'#'*90}")
    
    # Create rate limiters for each scope
    user_config = LIMITERS_CONFIG["user"]
    ip_config = LIMITERS_CONFIG["ip"]
    global_config = LIMITERS_CONFIG["global"]
    
    try:
        user_rl = limiter_class(
            capacity=user_config["capacity"],
            fill_rate=user_config["fill_rate"],
            scope="user",
            backend=backend,
            redis_client=redis_client
        )
        
        ip_rl = limiter_class(
            capacity=ip_config["capacity"],
            fill_rate=ip_config["fill_rate"],
            scope="ip",
            backend=backend,
            redis_client=redis_client
        )
        
        global_rl = limiter_class(
            capacity=global_config["capacity"],
            fill_rate=global_config["fill_rate"],
            scope="global",
            backend=backend,
            redis_client=redis_client
        )
        
        print(f"✅ Created limiters successfully")
        
    except Exception as e:
        print(f"❌ Failed to create limiters: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    stats = Stats()
    stop_event = threading.Event()
    threads = []
    
    # Start worker threads
    for user_id, interval in USERS:
        t = threading.Thread(
            target=user_worker,
            args=(user_id, interval, stats, stop_event, user_rl, ip_rl, global_rl),
            daemon=True
        )
        t.start()
        threads.append(t)
    
    start_time = time.time()
    last_print = start_time
    
    try:
        while time.time() - start_time < TEST_DURATION:
            time.sleep(0.1)
            current_time = time.time()
            
            if current_time - last_print >= PRINT_EVERY:
                elapsed = current_time - start_time
                print_progress(stats, elapsed, limiter_name, backend)
                last_print = current_time
    
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        stop_event.set()
        return None
    
    finally:
        stop_event.set()
        for t in threads:
            t.join(timeout=2.0)
    
    # Final report
    elapsed = time.time() - start_time
    print_progress(stats, elapsed, limiter_name, backend)
    
    # Return summary for comparison
    snapshot = stats.get_snapshot()
    total_allowed = sum(d.get("allowed", 0) for d in snapshot.values())
    total_blocked = sum(d.get("blocked", 0) for d in snapshot.values())
    
    return {
        "limiter": limiter_name,
        "backend": backend,
        "duration": elapsed,
        "total_allowed": total_allowed,
        "total_blocked": total_blocked,
        "rate": total_allowed / elapsed if elapsed > 0 else 0,
        "success_rate": (total_allowed / (total_allowed + total_blocked) * 100) if (total_allowed + total_blocked) > 0 else 0
    }


def get_redis_client():
    """Create Redis client if available"""
    if not REDIS_AVAILABLE:
        return None
    
    try:
        client = redis.Redis(**REDIS_CONFIG)
        client.ping()
        print("✅ Redis connection successful")
        return client
    except Exception as e:
        print(f"⚠️  Redis connection failed: {e}")
        print(f"   Make sure Redis is running: docker run -d -p 6379:6379 redis")
        return None


def cleanup_redis(redis_client):
    """Clean up Redis test data"""
    if redis_client:
        try:
            # Delete all rate limit keys
            keys = redis_client.keys("ratelimit:*")
            if keys:
                redis_client.delete(*keys)
                print(f"🧹 Cleaned up {len(keys)} Redis keys")
        except Exception as e:
            print(f"⚠️  Redis cleanup failed: {e}")


def test_basic_functionality():
    """Quick sanity test before running full suite"""
    print("\n" + "="*90)
    print("  BASIC FUNCTIONALITY TEST")
    print("="*90)
    
    limiters_to_test = [
        (TokenBucketLimiter, "Token Bucket"),
        (LeakyBucketLimiter, "Leaky Bucket"),
        (QueueLimiter, "Queue Limiter"),
    ]
    
    # Add window-based limiters if available
    if FixedWindowRateLimiter:
        limiters_to_test.append((FixedWindowRateLimiter, "Fixed Window"))
    if SlidingWindowRateLimiter:
        limiters_to_test.append((SlidingWindowRateLimiter, "Sliding Window"))
    if SlidingWindowLogRateLimiter:
        limiters_to_test.append((SlidingWindowLogRateLimiter, "Sliding Window Log"))
    
    print("\nTesting each limiter with basic operations...")
    
    all_passed = True
    
    for limiter_class, limiter_name in limiters_to_test:
        try:
            # Test with memory backend
            limiter = limiter_class(
                capacity=5,
                fill_rate=1.0,
                scope="user",
                backend="memory"
            )
            
            # Test basic allow/deny
            allowed_count = 0
            for i in range(10):
                if limiter.allow_request("test_user"):
                    allowed_count += 1
            
            if allowed_count == 5:  # Should allow exactly capacity
                print(f"  ✅ {limiter_name:<25} - PASSED (allowed {allowed_count}/10)")
            else:
                print(f"  ⚠️  {limiter_name:<25} - UNEXPECTED (allowed {allowed_count}/10, expected 5)")
                all_passed = False
                
        except Exception as e:
            print(f"  ❌ {limiter_name:<25} - FAILED: {e}")
            all_passed = False
    
    if all_passed:
        print("\n✅ All basic tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check implementation.")
    
    return all_passed


def main():
    """Run comprehensive stress tests"""
    print("="*90)
    print("  COMPREHENSIVE RATE LIMITER STRESS TEST SUITE")
    print("="*90)
    print(f"\nTest Configuration:")
    print(f"  Duration per test: {TEST_DURATION}s")
    print(f"  Concurrent users: {len(USERS)}")
    print(f"  Rate limiters: 6 algorithms (Token, Leaky, Queue, Fixed Window, Sliding Window, Sliding Log)")
    print(f"  Backends: Memory" + (" + Redis" if REDIS_AVAILABLE else ""))
    print(f"\nLimiter Settings:")
    for scope, config in LIMITERS_CONFIG.items():
        print(f"  {scope.capitalize()}: capacity={config['capacity']}, "
              f"fill_rate={config['fill_rate']}/s")
    
    print(f"\nUser Patterns:")
    for user_id, interval in USERS:
        rate = 1.0 / interval
        print(f"  {user_id}: {rate:.2f} req/s")
    
    # Run basic functionality test first
    if not test_basic_functionality():
        print("\n❌ Basic tests failed. Fix issues before running stress tests.")
        response = input("\nContinue with stress tests anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Define test matrix - ALL 6 ALGORITHMS
    limiter_classes = [
        (TokenBucketLimiter, "Token Bucket"),
        (LeakyBucketLimiter, "Leaky Bucket"),
        (QueueLimiter, "Queue Limiter"),
    ]
    
    # Add window-based limiters if available
    if FixedWindowRateLimiter:
        limiter_classes.append((FixedWindowRateLimiter, "Fixed Window"))
    if SlidingWindowRateLimiter:
        limiter_classes.append((SlidingWindowRateLimiter, "Sliding Window"))
    if SlidingWindowLogRateLimiter:
        limiter_classes.append((SlidingWindowLogRateLimiter, "Sliding Window Log"))
    
    backends = ["memory"]
    redis_client = None
    
    # Check Redis availability
    if REDIS_AVAILABLE:
        redis_client = get_redis_client()
        if redis_client:
            backends.append("redis")
    
    print(f"\n📋 Test Matrix: {len(limiter_classes)} algorithms × {len(backends)} backends = {len(limiter_classes) * len(backends)} tests")
    print(f"⏱️  Total estimated time: ~{len(limiter_classes) * len(backends) * (TEST_DURATION + 2)}s")
    
    input("\nPress ENTER to start tests...")
    
    # Run all test combinations
    results = []
    test_num = 0
    total_tests = len(limiter_classes) * len(backends)
    
    for limiter_class, limiter_name in limiter_classes:
        for backend in backends:
            test_num += 1
            print(f"\n{'='*90}")
            print(f"  TEST {test_num}/{total_tests}: {limiter_name} ({backend.upper()})")
            print(f"{'='*90}")
            
            result = run_single_test(
                limiter_class,
                limiter_name,
                backend,
                redis_client if backend == "redis" else None
            )
            
            if result:
                results.append(result)
            else:
                print(f"⚠️  Test skipped or failed")
            
            # Clean up Redis between tests
            if backend == "redis" and redis_client:
                cleanup_redis(redis_client)
            
            # Pause between tests
            if test_num < total_tests:
                print(f"\n⏸️  Pausing 2s before next test...")
                time.sleep(2)
    
    # Print comparison summary
    print("\n" + "="*90)
    print("  FINAL COMPARISON SUMMARY")
    print("="*90)
    print(f"{'Limiter':<25} {'Backend':<10} {'Allowed':>10} {'Blocked':>10} "
          f"{'Rate/s':>10} {'Success%':>10}")
    print("-"*90)
    
    for r in results:
        print(f"{r['limiter']:<25} {r['backend']:<10} {r['total_allowed']:>10} "
              f"{r['total_blocked']:>10} {r['rate']:>9.2f} {r['success_rate']:>9.1f}%")
    
    # Analyze results
    print("\n" + "="*90)
    print("  ANALYSIS")
    print("="*90)
    
    if results:
        # Group by backend
        memory_results = [r for r in results if r['backend'] == 'memory']
        redis_results = [r for r in results if r['backend'] == 'redis']
        
        if memory_results:
            avg_memory_rate = sum(r['rate'] for r in memory_results) / len(memory_results)
            print(f"\nMemory Backend:")
            print(f"  Average rate: {avg_memory_rate:.2f} req/s")
            print(f"  Tests run: {len(memory_results)}")
        
        if redis_results:
            avg_redis_rate = sum(r['rate'] for r in redis_results) / len(redis_results)
            print(f"\nRedis Backend:")
            print(f"  Average rate: {avg_redis_rate:.2f} req/s")
            print(f"  Tests run: {len(redis_results)}")
        
        # Find best performing
        best = max(results, key=lambda x: x['rate'])
        print(f"\n🏆 Best Performance:")
        print(f"   {best['limiter']} ({best['backend']}): {best['rate']:.2f} req/s")
        
        # Find most restrictive
        most_restrictive = min(results, key=lambda x: x['success_rate'])
        print(f"\n🔒 Most Restrictive:")
        print(f"   {most_restrictive['limiter']} ({most_restrictive['backend']}): {most_restrictive['success_rate']:.1f}% success")
    
    # Close Redis connection
    if redis_client:
        redis_client.close()
    
    print("\n✅ All tests completed!")
    print("="*90)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test suite interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
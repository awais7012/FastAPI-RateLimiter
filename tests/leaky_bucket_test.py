# stress_test_limiters.py
import threading
import time
import sys
import os

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from RateLimiter.token_bucket import TokenBucketLimiter
from RateLimiter.queue_limiter import QueueLimiter
from RateLimiter.leaky_bucket import LeakyBucketLimiter
import redis

# === CONFIG ===
USE_REDIS = False  # Change to True to test Redis backend
REDIS_URL = "redis://localhost:6379"
TEST_DURATION = 10  # seconds
REQUESTS_PER_SECOND = 5  # average request rate per user

CAPACITY = 10
FILL_RATE = 2.0  # tokens or leak rate per second

# Test scenarios
test_users = [
    ("user_steady", 1.0 / REQUESTS_PER_SECOND),
    ("user_burst", 0.05),
    ("user_slow", 1.0),
]

test_ips = [
    ("ip_steady", 1.0 / REQUESTS_PER_SECOND),
    ("ip_burst", 0.05),
]

global_scope_identifier = None  # used for global limiter

# Helper to flush Redis if needed
def flush_redis(redis_client):
    try:
        redis_client.flushall()
        print("[Redis] FLUSHALL done")
    except Exception as e:
        print(f"[Redis] flush failed: {e}")


# Worker thread for a user/IP/global
def worker(limiter, identifier, sleep_interval, results, limiter_name):
    allowed = 0
    blocked = 0
    end_time = time.time() + TEST_DURATION
    while time.time() < end_time:
        if limiter.allow_request(identifier):
            allowed += 1
        else:
            blocked += 1
        time.sleep(sleep_interval)
    results[f"{identifier}_{limiter_name}"] = {"allowed": allowed, "blocked": blocked}


def run_test(limiter_class, scope, backend, redis_client):
    limiter_name = limiter_class.__name__
    print(f"\nRunning {limiter_name} test (scope={scope}, backend={backend})")
    
    # Create limiter
    limiter = limiter_class(
        capacity=CAPACITY,
        fill_rate=FILL_RATE,
        scope=scope,
        backend=backend,
        redis_client=redis_client,
    )
    
    threads = []
    results = {}

    if scope == "user":
        for user_id, interval in test_users:
            t = threading.Thread(target=worker, args=(limiter, user_id, interval, results, limiter_name))
            t.start()
            threads.append(t)
    elif scope == "ip":
        for ip_id, interval in test_ips:
            t = threading.Thread(target=worker, args=(limiter, ip_id, interval, results, limiter_name))
            t.start()
            threads.append(t)
    elif scope == "global":
        # Single global limiter, all users hit same bucket
        for user_id, interval in test_users:
            t = threading.Thread(target=worker, args=(limiter, global_scope_identifier, interval, results, limiter_name))
            t.start()
            threads.append(t)
    
    # Wait for threads to finish
    for t in threads:
        t.join()
    
    return results


def print_results(results):
    print("\n" + "="*60)
    print(f"{'IDENTIFIER':<20} | {'ALLOWED':>7} | {'BLOCKED':>7}")
    print("="*60)
    total_allowed = 0
    total_blocked = 0
    for identifier, stats in results.items():
        total_allowed += stats["allowed"]
        total_blocked += stats["blocked"]
        print(f"{identifier:<20} | {stats['allowed']:>7} | {stats['blocked']:>7}")
    print("="*60)
    print(f"{'TOTAL':<20} | {total_allowed:>7} | {total_blocked:>7}")
    print("="*60)


def main():
    if USE_REDIS:
        r_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        flush_redis(r_client)
        backend = "redis"
    else:
        r_client = None
        backend = "memory"

    # Run tests for all 3 limiters and all scopes
    for limiter_class in [TokenBucketLimiter, QueueLimiter, LeakyBucketLimiter]:
        for scope in ["user", "ip", "global"]:
            if USE_REDIS:
                flush_redis(r_client)
            results = run_test(limiter_class, scope, backend, r_client)
            print_results(results)


if __name__ == "__main__":
    main()

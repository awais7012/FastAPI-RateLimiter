# compare_algorithms.py
"""
Compare Token Bucket vs Queue-based rate limiters side-by-side
Save this to: E:\coding\fastApi\compare_algorithms.py
"""
import threading
import time
import sys
import os

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from RateLimiter.token_bucket import TokenBucketLimiter
from RateLimiter.queue_limiter import QueueLimiter
import redis

# === CONFIG ===
USE_REDIS = False          # set True to use Redis
REDIS_URL = "redis://localhost:6379"
TEST_DURATION = 10         # seconds
REQUESTS_PER_SECOND = 3    # target request rate per user

# Rate limiter settings (same for both)
CAPACITY = 5
FILL_RATE = 1.0  # 1 token/request per second

# Test scenarios
test_users = [
    ("steady_user", 1.0/REQUESTS_PER_SECOND),    # exactly at limit
    ("bursty_user", 0.1),                         # burst then wait
    ("slow_user", 2.0),                           # well below limit
]


def flush_redis():
    try:
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        r.flushall()
        print("[redis] FLUSHALL done\n")
    except Exception as e:
        print(f"[redis] flush failed: {e}\n")


def user_worker(user_id, sleep_interval, results, stop_event, limiter, limiter_type):
    """Worker thread for a single user"""
    allowed = 0
    blocked = 0
    
    while not stop_event.is_set():
        ok = limiter.allow_request(user_id)
        if ok:
            allowed += 1
        else:
            blocked += 1
        
        time.sleep(sleep_interval)
    
    results[f"{user_id}_{limiter_type}"] = {
        "allowed": allowed,
        "blocked": blocked
    }


def run_limiter_test(limiter_class, limiter_name, backend, redis_client):
    """Run test for a specific limiter type"""
    limiter = limiter_class(
        capacity=CAPACITY,
        fill_rate=FILL_RATE,
        scope="user",
        backend=backend,
        redis_client=redis_client
    )
    
    stop_event = threading.Event()
    results = {}
    threads = []
    
    # Start worker threads
    for user_id, interval in test_users:
        t = threading.Thread(
            target=user_worker,
            args=(user_id, interval, results, stop_event, limiter, limiter_name)
        )
        t.start()
        threads.append(t)
    
    # Run test
    start_time = time.time()
    time.sleep(TEST_DURATION)
    
    # Stop workers
    stop_event.set()
    for t in threads:
        t.join(timeout=2)
    
    elapsed = time.time() - start_time
    return results, elapsed


def print_comparison(tb_results, queue_results, elapsed):
    """Print side-by-side comparison"""
    print("\n" + "="*80)
    print(f"{'USER':<20} | {'TOKEN BUCKET':<25} | {'QUEUE LIMITER':<25}")
    print("="*80)
    
    tb_total_allowed = 0
    tb_total_blocked = 0
    queue_total_allowed = 0
    queue_total_blocked = 0
    
    for user_id, _ in test_users:
        tb_key = f"{user_id}_token_bucket"
        queue_key = f"{user_id}_queue"
        
        tb_stats = tb_results.get(tb_key, {"allowed": 0, "blocked": 0})
        queue_stats = queue_results.get(queue_key, {"allowed": 0, "blocked": 0})
        
        tb_total_allowed += tb_stats["allowed"]
        tb_total_blocked += tb_stats["blocked"]
        queue_total_allowed += queue_stats["allowed"]
        queue_total_blocked += queue_stats["blocked"]
        
        tb_rate = tb_stats["allowed"] / elapsed
        queue_rate = queue_stats["allowed"] / elapsed
        
        print(f"{user_id:<20} | "
              f"✓{tb_stats['allowed']:>4} ✗{tb_stats['blocked']:>4} ({tb_rate:>4.1f}/s) | "
              f"✓{queue_stats['allowed']:>4} ✗{queue_stats['blocked']:>4} ({queue_rate:>4.1f}/s)")
    
    print("="*80)
    print(f"{'TOTAL':<20} | "
          f"✓{tb_total_allowed:>4} ✗{tb_total_blocked:>4} ({tb_total_allowed/elapsed:>4.1f}/s) | "
          f"✓{queue_total_allowed:>4} ✗{queue_total_blocked:>4} ({queue_total_allowed/elapsed:>4.1f}/s)")
    print("="*80)
    
    # Analysis
    print("\n📊 ANALYSIS:")
    print(f"Token Bucket:")
    print(f"  • Smoother rate: {tb_total_allowed/elapsed:.2f} req/s")
    print(f"  • Block rate: {tb_total_blocked/(tb_total_allowed+tb_total_blocked)*100:.1f}%")
    
    print(f"\nQueue Limiter:")
    print(f"  • Stricter enforcement: {queue_total_allowed/elapsed:.2f} req/s")
    print(f"  • Block rate: {queue_total_blocked/(queue_total_allowed+queue_total_blocked)*100:.1f}%")
    
    diff = tb_total_allowed - queue_total_allowed
    if queue_total_allowed > 0:
        print(f"\n🔍 Difference: Token Bucket allowed {diff:+d} more requests ({diff/queue_total_allowed*100:+.1f}%)")
    else:
        print(f"\n🔍 Difference: Token Bucket allowed {diff:+d} more requests")
    
    if diff > 0:
        print("   → Token Bucket is more permissive (allows burst recovery)")
    elif diff < 0:
        print("   → Queue Limiter is more permissive")
    else:
        print("   → Both algorithms performed identically")


def main():
    print("="*80)
    print("RATE LIMITER ALGORITHM COMPARISON")
    print("="*80)
    print(f"Duration: {TEST_DURATION}s")
    print(f"Capacity: {CAPACITY} requests")
    print(f"Fill Rate: {FILL_RATE} tokens/sec")
    print(f"Backend: {'Redis' if USE_REDIS else 'Memory'}")
    print("="*80)
    
    if USE_REDIS:
        flush_redis()
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    else:
        redis_client = None
    
    backend = "redis" if USE_REDIS else "memory"
    
    # Run Token Bucket test
    print("\n🪣 Running Token Bucket test...")
    tb_results, tb_elapsed = run_limiter_test(
        TokenBucketLimiter, "token_bucket", backend, redis_client
    )
    
    # Small delay between tests
    time.sleep(1)
    
    if USE_REDIS:
        flush_redis()
    
    # Run Queue Limiter test
    print("📋 Running Queue Limiter test...")
    queue_results, queue_elapsed = run_limiter_test(
        QueueLimiter, "queue", backend, redis_client
    )
    
    # Print comparison
    print_comparison(tb_results, queue_results, TEST_DURATION)
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()
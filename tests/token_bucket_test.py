# test_token_bucket_stress.py
import threading
import time
import sys
import os

# Add src/ to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from RateLimiter.token_bucket import TokenBucketLimiter
from RateLimiter.queue_limiter import QueueLimiter

# === CONFIG ===
TEST_DURATION = 12  # seconds
PRINT_EVERY = 1  # seconds

# Rate limiter settings
PER_USER_FILL = 1.0
PER_USER_CAP = 5

IP_FILL = 0.5
IP_CAP = 3

GLOBAL_FILL = 2.0
GLOBAL_CAP = 10

users = [
    ("user_normal", 0.5),
    ("user_bursty", 0.05),
    ("user_light", 1.5),
    ("user_medium", 0.3),
]


# === Worker thread for simulation ===
def user_worker(user_id, sleep_interval, results, stop_event,
                per_user_rl, ip_rl, global_rl):
    allowed = 0
    blocked = 0
    ip = f"192.0.2.{hash(user_id) % 255}"

    while not stop_event.is_set():
        # Global limiter (scope="global", identifier=None)
        if global_rl and not global_rl.allow_request(None):
            blocked += 1
            time.sleep(sleep_interval)
            continue

        # IP limiter (scope="ip", identifier=ip_address)
        if ip_rl and not ip_rl.allow_request(ip):
            blocked += 1
            time.sleep(sleep_interval)
            continue

        # Per-user limiter (scope="user", identifier=user_id)
        if per_user_rl.allow_request(user_id):
            allowed += 1
        else:
            blocked += 1

        time.sleep(sleep_interval)

    results[user_id] = {"allowed": allowed, "blocked": blocked}


def run_test():
    # Create limiters with CORRECT scopes
    per_user_rl = TokenBucketLimiter(
        capacity=PER_USER_CAP,
        fill_rate=PER_USER_FILL,
        scope="user"  # ✅ Per-user limiting
    )
    ip_rl = TokenBucketLimiter(
        capacity=IP_CAP,
        fill_rate=IP_FILL,
        scope="ip"  # ✅ Per-IP limiting
    )
    global_rl = TokenBucketLimiter(
        capacity=GLOBAL_CAP,
        fill_rate=GLOBAL_FILL,
        scope="global"  # ✅ Global limiting (this was the missing piece!)
    )

    stop_event = threading.Event()
    results = {}
    threads = []

    # Start user threads
    for user_id, interval in users:
        t = threading.Thread(target=user_worker,
                             args=(user_id, interval, results, stop_event,
                                   per_user_rl, ip_rl, global_rl))
        t.start()
        threads.append(t)

    start = time.time()
    try:
        while time.time() - start < TEST_DURATION:
            time.sleep(PRINT_EVERY)
            elapsed = int(time.time() - start)
            print(f"\n-- elapsed: {elapsed}s --")
            for u in users:
                uid = u[0]
                summary = results.get(uid, {"allowed": 0, "blocked": 0})
                rate = summary['allowed'] / elapsed if elapsed > 0 else 0
                print(f"  {uid:15s}: allowed={summary['allowed']:3d} "
                      f"blocked={summary['blocked']:3d} rate={rate:.2f}/s")
    finally:
        stop_event.set()
        for t in threads:
            t.join()

    print("\n" + "="*60)
    print("=== FINAL REPORT ===")
    print("="*60)
    total_allowed = sum(results[u]["allowed"] for u in results)
    total_blocked = sum(results[u]["blocked"] for u in results)
    
    for u in results:
        print(f"{u:15s}: allowed={results[u]['allowed']:3d} "
              f"blocked={results[u]['blocked']:3d}")
    
    print("-"*60)
    print(f"{'TOTAL':15s}: allowed={total_allowed:3d} blocked={total_blocked:3d}")
    print(f"Average rate: {total_allowed / TEST_DURATION:.2f} requests/sec")
    print(f"Success rate: {total_allowed/(total_allowed+total_blocked)*100:.1f}%")


if __name__ == "__main__":
    print("Starting TokenBucketLimiter stress test")
    print(f"Duration: {TEST_DURATION}s")
    print(f"Limiters: Per-user={PER_USER_CAP}@{PER_USER_FILL}/s, "
          f"IP={IP_CAP}@{IP_FILL}/s, Global={GLOBAL_CAP}@{GLOBAL_FILL}/s\n")
    run_test()
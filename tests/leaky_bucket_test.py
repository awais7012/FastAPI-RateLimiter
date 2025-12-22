
import threading
import time
import sys
import os
from collections import defaultdict


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from RateLimiter.leaky_bucket import LeakyBucketLimiter

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


# === Worker thread for simulation ===
def user_worker(user_id, sleep_interval, counter, stop_event,
                per_user_rl, ip_rl, global_rl):
    ip = f"192.0.2.{hash(user_id) % 255}"

    while not stop_event.is_set():
        allowed = False
        
        try:
            # Global limiter (scope="global", identifier=None)
            if global_rl and not global_rl.allow_request(None):
                counter.increment(user_id, False)
                time.sleep(sleep_interval)
                continue

            # IP limiter (scope="ip", identifier=ip_address)
            if ip_rl and not ip_rl.allow_request(ip):
                counter.increment(user_id, False)
                time.sleep(sleep_interval)
                continue

            # Per-user limiter (scope="user", identifier=user_id)
            if per_user_rl.allow_request(user_id):
                allowed = True
            
            counter.increment(user_id, allowed)
            time.sleep(sleep_interval)
            
        except Exception as e:
            print(f"\n⚠️  Error in {user_id}: {e}")
            break


def run_test():
    print("="*60)
    print("Starting LeakyBucketLimiter stress test")
    print("="*60)
    print(f"Duration: {TEST_DURATION}s")
    print(f"Limiters:")
    print(f"  Per-user: capacity={PER_USER_CAP}, fill_rate={PER_USER_FILL}/s")
    print(f"  IP:       capacity={IP_CAP}, fill_rate={IP_FILL}/s")
    print(f"  Global:   capacity={GLOBAL_CAP}, fill_rate={GLOBAL_FILL}/s")
    print(f"Users: {len(users)} concurrent users")
    print("="*60 + "\n")
    
    # Create limiters with CORRECT scopes
    try:
        per_user_rl = LeakyBucketLimiter(
            capacity=PER_USER_CAP,
            fill_rate=PER_USER_FILL,
            scope="user"
        )
        ip_rl = LeakyBucketLimiter(
            capacity=IP_CAP,
            fill_rate=IP_FILL,
            scope="ip"
        )
        global_rl = LeakyBucketLimiter(
            capacity=GLOBAL_CAP,
            fill_rate=GLOBAL_FILL,
            scope="global"
        )
    except Exception as e:
        print(f"❌ Failed to create limiters: {e}")
        import traceback
        traceback.print_exc()
        return

    counter = ThreadSafeCounter()
    stop_event = threading.Event()
    threads = []

    # Start user threads
    for user_id, interval in users:
        t = threading.Thread(target=user_worker,
                             args=(user_id, interval, counter, stop_event,
                                   per_user_rl, ip_rl, global_rl),
                             daemon=True)
        t.start()
        threads.append(t)

    start = time.time()
    try:
        while time.time() - start < TEST_DURATION:
            time.sleep(PRINT_EVERY)
            elapsed = time.time() - start
            
            # Get current snapshot
            snapshot = counter.get_snapshot()
            
            print(f"\n-- elapsed: {int(elapsed)}s --")
            for user_id, _ in users:
                data = snapshot.get(user_id, {"allowed": 0, "blocked": 0})
                allowed = data["allowed"]
                blocked = data["blocked"]
                rate = allowed / elapsed if elapsed > 0 else 0
                print(f"  {user_id:15s}: allowed={allowed:3d} "
                      f"blocked={blocked:3d} rate={rate:.2f}/s")
    
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
    
    finally:
        stop_event.set()
        for t in threads:
            t.join(timeout=2.0)

    # Final report
    elapsed = time.time() - start
    snapshot = counter.get_snapshot()
    
    print("\n" + "="*60)
    print("=== FINAL REPORT ===")
    print("="*60)
    
    total_allowed = 0
    total_blocked = 0
    
    for user_id, _ in users:
        data = snapshot.get(user_id, {"allowed": 0, "blocked": 0})
        allowed = data["allowed"]
        blocked = data["blocked"]
        print(f"{user_id:15s}: allowed={allowed:3d} blocked={blocked:3d}")
        total_allowed += allowed
        total_blocked += blocked
    
    print("-"*60)
    print(f"{'TOTAL':15s}: allowed={total_allowed:3d} blocked={total_blocked:3d}")
    print(f"Average rate: {total_allowed / elapsed:.2f} requests/sec")
    
    if total_allowed + total_blocked > 0:
        success_rate = (total_allowed / (total_allowed + total_blocked)) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    # Show limiter status for debugging
    print("\n" + "="*60)
    print("=== LIMITER STATUS ===")
    print("="*60)
    try:
        for user_id, _ in users:
            status = per_user_rl.get_status(user_id)
            print(f"{user_id:15s}: water_level={status.get('water_level', 0):.2f}/{PER_USER_CAP}")
    except AttributeError:
        print("⚠️  get_status() method not available")


if __name__ == "__main__":
    run_test()
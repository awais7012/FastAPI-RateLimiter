# stress_test.py
"""
Stress test for RateLimiter with multi-layer rate limiting
Save this to: E:\coding\fastApi\stress_test.py
"""
import threading
import time
import sys
import os

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from RateLimiter import RateLimiter
import redis

# === CONFIG ===
USE_REDIS = False          # set False to use in-memory mode
REDIS_URL = "redis://localhost:6379"
TEST_DURATION = 12         # seconds to run the test
PRINT_EVERY = 1            # seconds between status prints

# Rate limiter settings
PER_USER_FILL = 1.0   # tokens/sec
PER_USER_CAP = 5      # burst capacity

IP_FILL = 0.5
IP_CAP = 3

GLOBAL_FILL = 2.0
GLOBAL_CAP = 10

# Users to simulate: (user_id, sleep_between_requests)
users = [
    ("user_normal", 0.5),   # normal user: one request every 0.5s
    ("user_bursty", 0.05),  # bursty/spammer: many requests quickly
    ("user_light", 1.5),    # light user: one request every 1.5s
    ("user_medium", 0.3),   # moderate user
]


# === OPTIONAL: flush redis for a clean run ===
def flush_redis():
    try:
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        r.flushall()
        print("[redis] FLUSHALL done")
    except Exception as e:
        print("[redis] flush failed:", e)


# === Worker thread that simulates a single user ===
def user_worker(user_id, sleep_interval, results, stop_event,
                per_user_rl, ip_rl, global_rl, use_ip_as_id=False):
    """
    results: dict to store counts: results[user_id] = {"allowed": n, "blocked": m}
    stop_event: threading.Event to stop the loop
    """
    allowed = 0
    blocked = 0
    ip = "192.0.2.{}".format(hash(user_id) % 255)

    while not stop_event.is_set():
        # check global first (if provided)
        if global_rl:
            ok_global = global_rl.allow_request(None)
            if not ok_global:
                blocked += 1
                # small sleep to avoid pure spin if globally blocked
                time.sleep(sleep_interval)
                continue

        # check IP limiter
        if ip_rl:
            ok_ip = ip_rl.allow_request(ip)
            if not ok_ip:
                blocked += 1
                time.sleep(sleep_interval)
                continue

        # check per-user limiter
        identifier = user_id if not use_ip_as_id else ip
        ok_user = per_user_rl.allow_request(identifier)
        if ok_user:
            allowed += 1
        else:
            blocked += 1

        time.sleep(sleep_interval)

    results[user_id] = {"allowed": allowed, "blocked": blocked}


def run_test(use_redis=USE_REDIS):
    if use_redis:
        # clean redis keys to start fresh
        flush_redis()

    backend = "redis" if use_redis else "memory"
    
    print(f"\nCreating rate limiters (backend={backend})...")
    
    per_user_rl = RateLimiter(
        fill_rate=PER_USER_FILL,
        capacity=PER_USER_CAP,
        scope="user",
        backend=backend,
        redis_url=REDIS_URL if use_redis else None
    )
    
    ip_rl = RateLimiter(
        fill_rate=IP_FILL,
        capacity=IP_CAP,
        scope="ip",
        backend=backend,
        redis_url=REDIS_URL if use_redis else None
    )
    
    global_rl = RateLimiter(
        fill_rate=GLOBAL_FILL,
        capacity=GLOBAL_CAP,
        scope="global",
        backend=backend,
        redis_url=REDIS_URL if use_redis else None
    )
    
    print("✓ Rate limiters created\n")

    stop_event = threading.Event()
    results = {}
    threads = []

    # create a thread per user
    print(f"Starting {len(users)} user threads...\n")
    for user_id, interval in users:
        t = threading.Thread(
            target=user_worker,
            args=(user_id, interval, results, stop_event, per_user_rl, ip_rl, global_rl)
        )
        t.start()
        threads.append(t)

    # status loop
    start = time.time()
    try:
        while time.time() - start < TEST_DURATION:
            time.sleep(PRINT_EVERY)
            elapsed = int(time.time() - start)
            print(f"-- elapsed: {elapsed}s --")
            for u in users:
                uid = u[0]
                summary = results.get(uid, {"allowed": 0, "blocked": 0})
                print(f"  {uid}: allowed={summary['allowed']} blocked={summary['blocked']}")
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        # stop workers
        stop_event.set()
        for t in threads:
            t.join(timeout=2)

    # final report
    print("\n" + "="*60)
    print("=== FINAL REPORT ===")
    print("="*60)
    total_allowed = 0
    total_blocked = 0
    for uid in [u[0] for u in users]:
        r = results.get(uid, {"allowed": 0, "blocked": 0})
        print(f"{uid}: allowed={r['allowed']} blocked={r['blocked']}")
        total_allowed += r['allowed']
        total_blocked += r['blocked']

    print(f"\nTotal allowed={total_allowed} blocked={total_blocked}")
    print(f"Average rate: {total_allowed/TEST_DURATION:.2f} requests/sec")
    print("="*60)


if __name__ == "__main__":
    print("="*60)
    print("Starting stress test (per-user + per-ip + global layers)")
    print("="*60)
    run_test(use_redis=USE_REDIS)
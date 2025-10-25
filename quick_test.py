# stress_test_queue.py
"""
Stress test for QueueLimiter with multiple users and request patterns
Save this in your project root, e.g., E:\coding\fastApi\tests\stress_test_queue.py
"""

import threading
import time
import sys
import os

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '..', 'src')
sys.path.insert(0, src_dir)

from RateLimiter.queue_limiter import QueueLimiter

# === CONFIG ===
TEST_DURATION = 12        # seconds to run the test
PRINT_EVERY = 1           # seconds between status prints

# QueueLimiter settings
QUEUE_CAPACITY = 5         # max requests in queue
QUEUE_INTERVAL = 1.0       # interval in seconds between dequeuing

# Users to simulate: (user_id, sleep_between_requests)
users = [
    ("user_normal", 0.5),   # normal user: one request every 0.5s
    ("user_bursty", 0.05),  # bursty/spammer: many requests quickly
    ("user_light", 1.5),    # light user: slow requests
    ("user_medium", 0.3),   # moderate user
]

# === Worker thread to simulate a single user ===
def user_worker(user_id, sleep_interval, results, stop_event, limiter):
    allowed = 0
    blocked = 0

    while not stop_event.is_set():
        ok = limiter.allow_request(user_id)
        if ok:
            allowed += 1
        else:
            blocked += 1
        time.sleep(sleep_interval)

    results[user_id] = {"allowed": allowed, "blocked": blocked}

def run_test():
    print("="*60)
    print("Starting QueueLimiter stress test")
    print("="*60)

    # Create the limiter
    limiter = QueueLimiter(capacity=QUEUE_CAPACITY, interval=QUEUE_INTERVAL)
    print("✓ QueueLimiter created\n")

    stop_event = threading.Event()
    results = {}
    threads = []

    # Create a thread per user
    for user_id, interval in users:
        t = threading.Thread(
            target=user_worker,
            args=(user_id, interval, results, stop_event, limiter)
        )
        t.start()
        threads.append(t)

    # Monitor loop
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
        stop_event.set()
        for t in threads:
            t.join(timeout=2)

    # Final report
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
    run_test()

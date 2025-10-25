# test_queue_limiter.py
import sys
import os
import threading
import time

# Add src/ to Python path **before any imports from RateLimiter**
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "src"))
sys.path.insert(0, src_dir)

from RateLimiter.queue_limiter import QueueLimiter

# === CONFIG ===
TEST_DURATION = 10  # seconds
PRINT_EVERY = 1

QUEUE_CAPACITY = 5
FILL_RATE = 1.0  # tokens/sec

# Simulated users: (user_id, sleep_between_requests)
users = [
    ("user_normal", 0.5),
    ("user_bursty", 0.05),
    ("user_light", 1.5),
    ("user_medium", 0.3),
]

def user_worker(user_id, sleep_interval, limiter, results, stop_event):
    allowed = 0
    blocked = 0
    while not stop_event.is_set():
        if limiter.allow_request(user_id):
            allowed += 1
        else:
            blocked += 1
        time.sleep(sleep_interval)
    results[user_id] = {"allowed": allowed, "blocked": blocked}

def run_test():
    limiter = QueueLimiter(capacity=QUEUE_CAPACITY, fill_rate=FILL_RATE)

    stop_event = threading.Event()
    results = {}
    threads = []

    # start threads
    for user_id, interval in users:
        t = threading.Thread(target=user_worker, args=(user_id, interval, limiter, results, stop_event))
        t.start()
        threads.append(t)

    start = time.time()
    try:
        while time.time() - start < TEST_DURATION:
            time.sleep(PRINT_EVERY)
            print(f"-- elapsed: {int(time.time()-start)}s --")
            for u in users:
                uid = u[0]
                summary = results.get(uid, {"allowed": 0, "blocked": 0})
                print(f"  {uid}: allowed={summary['allowed']} blocked={summary['blocked']}")
    finally:
        stop_event.set()
        for t in threads:
            t.join()

    print("\n=== FINAL REPORT ===")
    total_allowed = sum(results[u]["allowed"] for u in results)
    total_blocked = sum(results[u]["blocked"] for u in results)
    for u in results:
        print(f"{u}: allowed={results[u]['allowed']} blocked={results[u]['blocked']}")
    print(f"Total allowed={total_allowed} blocked={total_blocked}")
    print(f"Average rate: {total_allowed/TEST_DURATION:.2f} requests/sec")

if __name__ == "__main__":
    print("Starting QueueLimiter stress test (multi-user)")
    run_test()

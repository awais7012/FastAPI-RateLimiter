Got it 👍 You just want me to take **that full README draft** and make it look like a *fully polished GitHub markdown file* — with proper emojis, heading hierarchy, badges, spacing, and visual polish (like how FastAPI, Redis, or Celery repos do it).

Here’s your **final, ready-to-publish `README.md`** version, styled professionally while keeping your original content intact:

````{"id":"92381","variant":"standard","title":"README.md — FastAPI Rate Limiter"}
# ⚡️ FastAPI RateLimiter

> **High-Performance, Multi-Algorithm Rate Limiting for FastAPI**

A compact, battle-tested library of rate limiting algorithms ready to plug into FastAPI apps.  
Supports **Token Bucket**, **Leaky Bucket**, **Queue-based**, **Fixed Window**, **Sliding Window**, and **Sliding Log** limiters — each available with **in-memory** and **Redis** backends, and usable at **global**, **per-user**, or **per-IP** scope.

---

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-Compatible-brightgreen?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/Backend-Redis-red?style=for-the-badge&logo=redis" />
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/github/license/awais7012/FastAPI-RateLimiter?style=for-the-badge" />
</p>

---

## 📚 Table of Contents
- [💡 Why use rate limiting?](#-why-use-rate-limiting)
- [✨ Key features](#-key-features)
- [🧮 Algorithms (what & when to use)](#-algorithms-what--when-to-use)
  - [Token Bucket](#token-bucket)
  - [Leaky Bucket](#leaky-bucket)
  - [Queue-based Limiter](#queue-based-limiter)
  - [Fixed Window](#fixed-window)
  - [Sliding Window (weighted)](#sliding-window-weighted)
  - [Sliding Window Log](#sliding-window-log)
- [⚙️ Installation](#️-installation)
- [🚀 Quick start (examples)](#-quick-start-examples)
  - [Memory backend — per-user token bucket](#memory-backend--per-user-token-bucket)
  - [Redis backend — per-ip leaky bucket](#redis-backend--per-ip-leaky-bucket)
  - [Global queue limiter example](#global-queue-limiter-example)
  - [FastAPI middleware integration](#fastapi-middleware-integration)
- [🧱 Redis vs In-memory tradeoffs](#-redis-vs-in-memory-tradeoffs)
- [🧪 Testing & stress harnesses](#-testing--stress-harnesses)
- [🎛️ How to tune limits](#️-how-to-tune-limits)
- [🧰 Development & contribution](#-development--contribution)
- [📜 License](#-license)

---

## 💡 Why use rate limiting?

Rate limiting protects your service from **overload**, **DDoS**, **abusive clients**, and **accidental traffic spikes**. It:

- prevents one user from consuming all capacity  
- smooths bursts to preserve downstream resources  
- enforces fair usage (per-user / per-IP / global)  
- ensures predictable performance and reliability  

---

## ✨ Key features

✅ Multiple algorithms for different behaviors (burstiness vs strict pacing)  
✅ Two backends: in-memory (zero-deps) and Redis (cluster-friendly, cross-instance)  
✅ Scopes: `user`, `ip`, `global`  
✅ Helpers: `get_status()`, `get_retry_after()`, `get_wait_time()`  
✅ Includes stress test harness simulating thousands of concurrent requests  

---

## 🧮 Algorithms — What they do, pros/cons, when to use

### 🪙 Token Bucket
**Concept:** Tokens are added steadily (`fill_rate`) up to `capacity`. Each request consumes a token.  
**Pros:** Allows short bursts, maintains steady average rate.  
**Cons:** Slightly permissive for bursts.  
**When to use:** APIs where occasional bursts are fine — e.g., file uploads, user-triggered events.  
**Analogy:** A wallet of tokens you spend to make requests.

---

### 💧 Leaky Bucket
**Concept:** Requests fill a bucket that leaks at a fixed rate. Overflowed requests are dropped.  
**Pros:** Enforces smooth, consistent rate.  
**Cons:** Less tolerant of bursts than Token Bucket.  
**When to use:** When steady pacing is critical (e.g., dispatching jobs, calling external APIs).

---

### 📦 Queue-based Limiter
**Concept:** Keeps a queue of recent timestamps (like a rolling window). Allows only `capacity` within `window = capacity / fill_rate`.  
**Pros:** Predictable, easy to compute wait times.  
**Cons:** Slightly more strict, stores timestamps.  
**When to use:** When you need fairness or ordered request flow.

---

### ⏱️ Fixed Window
**Concept:** Counts all requests within a discrete time window. Resets each interval.  
**Pros:** Simple, very fast, Redis `INCR` friendly.  
**Cons:** Boundary bursts possible.  
**When to use:** Coarse limits (minute/hour/day based quotas).

---

### 🪟 Sliding Window (Weighted)
**Concept:** Combines current + previous windows proportionally for smoother transitions.  
**Pros:** Removes boundary spikes, lightweight.  
**Cons:** Approximation-based.  
**When to use:** For smoother, low-latency APIs.

---

### 📜 Sliding Log
**Concept:** Logs timestamps and prunes anything outside the window.  
**Pros:** Fully accurate; no burst gaps.  
**Cons:** Memory + CPU heavy; not ideal for huge scale.  
**When to use:** When exact enforcement is essential (auth endpoints, payment APIs).

---

## ⚙️ Installation

```bash
git clone https://github.com/awais7012/FastAPI-RateLimiter.git
cd FastAPI-RateLimiter

python -m venv venv
# Activate
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
pip install redis  # optional: Redis backend
```

---

## 🚀 Quick start (examples)

### 🧠 Memory backend — per-user Token Bucket

```python
from RateLimiter.token_bucket import TokenBucketLimiter

# 5-token burst, refill 1 token/sec
limiter = TokenBucketLimiter(capacity=5, fill_rate=1.0, scope="user", backend="memory")

user_id = "alice"
if limiter.allow_request(user_id):
    print("Allowed")
else:
    print("429 Too Many Requests")
```

---

### 🌐 Redis backend — per-IP Leaky Bucket

```python
import redis
from RateLimiter.leaky_bucket import LeakyBucketLimiter

r = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
ip_limiter = LeakyBucketLimiter(capacity=3, fill_rate=0.5, scope="ip", backend="redis", redis_client=r)

if ip_limiter.allow_request("198.51.100.7"):
    print("Processed")
else:
    print("Too many requests; retry after:", ip_limiter.get_wait_time("198.51.100.7"))
```

---

### 🌍 Global Queue Limiter Example

```python
from RateLimiter.queue_limiter import QueueLimiter

global_limiter = QueueLimiter(capacity=100, fill_rate=10.0, scope="global", backend="memory")

if not global_limiter.allow_request(None):
    print("Global limit reached")
```

---

### ⚡ FastAPI Middleware Integration

```python
from fastapi import FastAPI, Request, HTTPException
from RateLimiter.token_bucket import TokenBucketLimiter

app = FastAPI()
limiter = TokenBucketLimiter(capacity=5, fill_rate=1.0, scope="user", backend="memory")

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    user = request.headers.get("x-user-id") or request.client.host
    if not limiter.allow_request(user):
        raise HTTPException(status_code=429, detail="Too many requests")
    return await call_next(request)
```

---

## 🧱 Redis vs In-memory — Tradeoffs

| Backend | Pros | Cons | Use case |
|----------|------|------|-----------|
| **In-memory** | ⚡ Super fast, no setup | ❌ Not shared across app instances | Local dev, single-instance apps |
| **Redis** | 🌍 Shared, atomic, scalable | 🧱 Requires Redis service | Distributed apps / production |

**Run Redis via Docker:**

```bash
docker run -d --name redis -p 6379:6379 redis
```

---

## 🧪 Testing & Stress Harnesses

Prebuilt tests in `/tests`:

- `test_token_bucket.py`, `test_user_scope.py`, etc.  
- `all_limiter_test.py` → runs all limiters, scopes, and backends.

```bash
python -m tests.all_limiter_test
```

✅ Simulates:
- Multi-user concurrency  
- IP-based vs global limits  
- Redis + memory backend comparison  

---

## 🎛️ How to Tune Limits

1. **Scope wisely:**  
   - `global`: total requests allowed across all users  
   - `user`: per-user fairness  
   - `ip`: ideal for unauthenticated clients  

2. **Pick algorithm:**  
   - Burst-friendly → Token Bucket  
   - Strict pacing → Leaky Bucket  
   - Exact precision → Sliding Log  

3. **Set parameters:**  
   ```python
   capacity = 10  # burst size
   fill_rate = 2.0  # steady rate (req/sec)
   ```

4. **Monitor status:**  
   ```python
   limiter.get_status(user_id)
   limiter.get_wait_time(user_id)
   ```

---

## 🧰 Development & Contribution

- Fork → Branch → PR flow  
- Follow PEP8 + consistent docstrings  
- Tests live in `/tests`  
- Use `pytest` or direct `python -m tests.<module>`  

For Redis-based work, ensure local Redis or container is running.

---

## 📜 License

```text
MIT License
Copyright (c) 2025
```

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/awais7012">Ahmed Awais</a><br/>
  Designed for developers who love clean, scalable FastAPI tooling.
</p>
````

Would you like me to now make the **`USAGE.md`** — where each algorithm (Token, Leaky, Queue, Fixed, Sliding Window, Sliding Log) has its own **FastAPI route + decorator example** and Redis/memory switch usage?

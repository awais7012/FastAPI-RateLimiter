

````{"variant":"standard","title":"FastAPI Rate Limiter – README","id":"58219"}
# ⚡ FastAPI Rate Limiter

A lightweight, production-ready library providing modern rate limiting algorithms for **FastAPI** and **Python applications**.

---

## 🚀 Overview

Rate limiting is one of the most critical components for any API or backend system. It helps:
- Protect your app and server from excessive requests.
- Reduce infrastructure costs.
- Prevent DoS attacks and brute-force exploits.
- Maintain a consistent and stable user experience.

This library implements **five of the most common and battle-tested rate limiting algorithms**, supporting both **in-memory** and **Redis** backends.

---

## 🧠 Supported Algorithms

| Algorithm | Description |
|------------|--------------|
| **Token Bucket** | Allows bursts of traffic up to a fixed capacity, then refills over time. Ideal for APIs that need short bursts. |
| **Leaky Bucket** | Smoothens request rates by leaking tokens at a fixed rate. Prevents traffic spikes. |
| **Sliding Window** | Tracks requests in a rolling time window for more accurate enforcement. |
| **Fixed Window** | Divides time into fixed blocks (e.g., per minute/hour) and counts requests within each block. |
| **Queue Limiter** | Queues incoming requests up to a limit instead of rejecting them immediately. |

---

## 🧩 Scopes of Limiting

You can apply rate limits on three levels:

| Scope | Description |
|--------|--------------|
| **Global** | Limit applies across all users and IPs. Useful for backend-wide throttling. |
| **Per User** | Each authenticated user has their own limiter. |
| **IP-Based** | Requests are grouped by IP, useful for login/signup or unauthenticated routes. |

You can mix and match these — for example:
```python
# Apply per-user, per-IP, and global rate limits simultaneously
if not global_limiter.allow_request():
    return "Global limit exceeded"
elif not ip_limiter.allow_request(ip):
    return "IP limit exceeded"
elif not user_limiter.allow_request(user_id):
    return "User limit exceeded"
```

---

## 🛠️ Backends

### 🔹 In-Memory (default)
- Simple and fast.
- Best for single-instance apps or testing environments.
- No external dependencies.

### 🔹 Redis
- Recommended for **distributed systems** or apps running on multiple servers.
- Keeps consistent limits across all instances.
- Requires Redis installed locally or via Docker.

Example Redis setup:
```bash
docker run -d -p 6379:6379 redis
```

Update your limiter to use Redis:
```python
from RateLimiter.token_bucket import TokenBucketLimiter
import redis

r = redis.Redis(host="localhost", port=6379, db=0)
limiter = TokenBucketLimiter(capacity=10, fill_rate=2, backend="redis", redis_client=r)
```

---

## 🧪 Testing All Limiters

You can run a full-scale stress test using:
```bash
python tests/test_all_limiters_comprehensive.py
```

This test script:
- Simulates multiple users with different traffic patterns.
- Tests **all 5 algorithms**.
- Tests both **memory** and **Redis** backends.
- Shows performance, allowed/blocked requests, and success rates.

Example output:
```
============================================================
  Token Bucket | REDIS Backend | Elapsed: 8.2s
============================================================
User           Allowed  Blocked  By User  By IP  By Global  Rate/s
-----------------------------------------------------------------
user_normal         42       13       5       0        8     5.12
...
Success Rate: 86.5%
```

---

## 🧩 Example: FastAPI Middleware Integration

Here’s how you might use the library inside a FastAPI app:

```python
from fastapi import FastAPI, Request, HTTPException
from RateLimiter.token_bucket import TokenBucketLimiter

limiter = TokenBucketLimiter(capacity=10, fill_rate=1, scope="user", backend="memory")

app = FastAPI()

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    user_id = request.headers.get("X-User-ID", "guest")
    if not limiter.allow_request(user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return await call_next(request)
```

---

## 📊 Algorithms Explained

### 🪣 Token Bucket
- Each request consumes one token.
- Tokens refill at a steady rate.
- If no tokens are available → request is rejected.

### 💧 Leaky Bucket
- Requests enter a bucket that leaks at a constant rate.
- Ensures a steady output even if requests arrive in bursts.

### 🪟 Fixed Window
- Time is divided into fixed intervals (e.g., 1 minute).
- If requests exceed capacity within that window → blocked.

### 🪟 Sliding Window
- Similar to fixed, but window slides continuously over time.
- More precise for high-frequency APIs.

### 🧾 Queue Limiter
- Instead of dropping requests, it queues them until processed or timeout.

---

## 🧰 Features Summary

✅ 5 Limiter Algorithms  
✅ Redis or Memory Backend  
✅ Global / IP / User Scope  
✅ Thread-Safe Implementation  
✅ Built-in Stress Testing Script  
✅ Easy FastAPI Integration  

---

## 📦 Installation

```bash
pip install fastapi-rate-limiter
```

or directly from source:
```bash
git clone https://github.com/yourname/fastapi-rate-limiter
cd fastapi-rate-limiter
pip install -r requirements.txt
```

---

## 👨‍💻 Example Test Script

Check out [`test_all_limiters_comprehensive.py`](tests/test_all_limiters_comprehensive.py)  
This script simulates real-world usage with multiple users and concurrent threads.

---

## 🧩 Upcoming Improvements
- Async-compatible limiters
- Rate limit headers for HTTP responses
- Built-in FastAPI dependency injection system
- Visualization dashboard for Redis stats

---

## 📄 License

MIT License © 2025 [Ahmad Awais(Romeo)]
````


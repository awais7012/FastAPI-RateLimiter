# ⚡ FastAPI Rate Limiter

<p align="center">
  <em>High-performance, production-ready rate limiting for FastAPI applications.</em>
</p>

<p align="center">
  <a href="https://github.com/awais7012/FastAPI-RateLimiter/stargazers"><img src="https://img.shields.io/github/stars/awais7012/FastAPI-RateLimiter?style=social" alt="GitHub stars"></a>
  <a href="https://github.com/awais7012/FastAPI-RateLimiter/network/members"><img src="https://img.shields.io/github/forks/awais7012/FastAPI-RateLimiter?style=social" alt="GitHub forks"></a>
  <a href="https://github.com/awais7012/FastAPI-RateLimiter/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awais7012/FastAPI-RateLimiter" alt="License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python Version"></a>
</p>

<p align="center">
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-Compatible-brightgreen?logo=fastapi" alt="FastAPI"></a>
  <a href="https://redis.io"><img src="https://img.shields.io/badge/Backend-Redis-red?logo=redis" alt="Redis"></a>
  <img src="https://img.shields.io/badge/Thread--Safe-Yes-success" alt="Thread-Safe">
  <img src="https://img.shields.io/badge/Production--Ready-Yes-success" alt="Production-Ready">
</p>

---

**FastAPI Rate Limiter** is a battle-tested library providing **6 different rate limiting algorithms** with support for both **in-memory** and **Redis** backends. Perfect for APIs, microservices, and any FastAPI application that needs protection from abuse, overload, or DDoS attacks.

---

## 🎯 Key Features

- 🚀 **6 Production-Ready Algorithms** — Token Bucket, Leaky Bucket, Queue-based, Fixed Window, Sliding Window, and Sliding Window Log
- 🔄 **Dual Backend Support** — In-memory (zero dependencies) or Redis (distributed, cluster-friendly)
- 🎚️ **Flexible Scoping** — Global, per-user, or per-IP rate limiting
- 🔒 **Thread-Safe** — Per-key locks and atomic Redis operations
- ⚡ **High Performance** — Benchmarked at 15+ req/s for window-based algorithms
- 📊 **Rich Monitoring** — `get_status()`, `get_wait_time()`, `get_retry_after()` helpers
- 🧪 **Comprehensive Tests** — 12 test scenarios covering all algorithms and backends
- 📚 **FastAPI-Style Docs** — Clear examples and tutorials

---

## 📚 Table of Contents

- [Why Rate Limiting?](#-why-rate-limiting)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Algorithms Guide](#-algorithms-guide)
- [Usage Examples](#-usage-examples)
- [Performance Benchmarks](#-performance-benchmarks)
- [API Reference](#-api-reference)
- [Backend Comparison](#-backend-comparison)
- [Best Practices](#-best-practices)
- [Testing](#-testing)
- [Contributing](#-contributing)
- [License](#-license)

---

## 💡 Why Rate Limiting?

Rate limiting is essential for:

- **🛡️ Preventing Abuse** — Stop malicious users from overwhelming your API
- **⚖️ Fair Usage** — Ensure all users get equal access to resources
- **💰 Cost Control** — Prevent unexpected bills from cloud services
- **🎯 SLA Compliance** — Meet service level agreements and uptime guarantees
- **🚦 Traffic Shaping** — Smooth out traffic spikes to protect downstream services

**Without rate limiting**, a single user can:
- Consume all server resources
- Trigger cascading failures
- Generate massive cloud bills
- Degrade service for legitimate users

---

## ⚡ Quick Start

**30 seconds to your first rate limiter:**

```python
from fastapi import FastAPI, Request, HTTPException
from RateLimiter import SlidingWindowRateLimiter
import redis

app = FastAPI()

# Initialize rate limiter
redis_client = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
limiter = SlidingWindowRateLimiter(
    capacity=100,      # 100 requests
    fill_rate=10,      # per 10 seconds
    scope="user",      # per-user limits
    backend="redis",   # distributed
    redis_client=redis_client
)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Get user identifier (from auth, IP, etc.)
    user_id = request.headers.get("X-User-ID") or request.client.host
    
    # Check rate limit
    if not limiter.allow_request(user_id):
        wait_time = limiter.get_wait_time(user_id)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry after {wait_time:.0f} seconds.",
            headers={"Retry-After": str(int(wait_time))}
        )
    
    return await call_next(request)

@app.get("/")
async def root():
    return {"message": "Hello World!"}
```

**Run it:**
```bash
uvicorn main:app --reload
```

**Test it:**
```bash
# Make requests
curl http://localhost:8000/
# After 100 requests in 10 seconds, you'll get:
# {"detail":"Rate limit exceeded. Retry after 5 seconds."}
```

---

## 📦 Installation

### From GitHub (Recommended for now)

```bash
git clone https://github.com/awais7012/FastAPI-RateLimiter.git
cd FastAPI-RateLimiter
pip install -e .
```

### With Redis Support

```bash
pip install -e ".[redis]"
```

### With Development Tools

```bash
pip install -e ".[dev]"
```

### Requirements

- **Python**: 3.8+
- **FastAPI**: 0.68.0+
- **Redis** (optional): 4.0.0+

---

## 🧮 Algorithms Guide

Choose the right algorithm for your use case:

### 🪙 Token Bucket — **Best for APIs with occasional bursts**

**How it works:** Imagine a bucket that slowly fills with tokens. Each request takes a token. If the bucket is empty, requests are denied.

```python
from RateLimiter import TokenBucketLimiter

limiter = TokenBucketLimiter(
    capacity=10,    # Bucket holds 10 tokens (burst size)
    fill_rate=1.0,  # Refill 1 token per second
    scope="user",
    backend="memory"
)
```

**Behavior:**
- Allows bursts up to `capacity`
- Maintains long-term average rate of `fill_rate`
- Good for file uploads, batch operations

**Pros:** ✅ Flexible, allows bursts  
**Cons:** ⚠️ Can be "drained" by burst traffic

**Use when:** User-triggered actions (file uploads, form submissions)

---

### 💧 Leaky Bucket — **Best for traffic shaping**

**How it works:** Requests fill a bucket with a hole at the bottom. The bucket leaks at a constant rate. Overflow = rejected.

```python
from RateLimiter import LeakyBucketLimiter

limiter = LeakyBucketLimiter(
    capacity=5,     # Bucket capacity
    fill_rate=1.0,  # Leak rate (1 req/sec)
    scope="user",
    backend="memory"
)
```

**Behavior:**
- Enforces smooth, consistent output rate
- No burst allowance
- Perfect for calling external APIs

**Pros:** ✅ Smooth, predictable rate  
**Cons:** ❌ Strict (can frustrate users with spiky traffic)

**Use when:** Calling rate-limited external APIs, message queues

---

### ⏱️ Fixed Window — **Fastest, simplest**

**How it works:** Count requests in fixed time windows (e.g., per minute). Reset count at window boundaries.

```python
from RateLimiter import FixedWindowRateLimiter

limiter = FixedWindowRateLimiter(
    capacity=1000,  # 1000 requests
    fill_rate=100,  # per 10 seconds (capacity/fill_rate)
    scope="global",
    backend="redis"
)
```

**Behavior:**
- Simple counter with time-based reset
- Very fast (Redis INCR operation)
- Can get 2x capacity at window boundaries

**Pros:** ✅ Fastest, O(1), minimal memory  
**Cons:** ⚠️ Boundary burst vulnerability

**Use when:** High-throughput internal APIs, coarse-grained limits

---

### 🪟 Sliding Window — **Best balance (RECOMMENDED)** ⭐

**How it works:** Combines current and previous window counts with a weighted average to smooth transitions.

```python
from RateLimiter import SlidingWindowRateLimiter

limiter = SlidingWindowRateLimiter(
    capacity=100,
    fill_rate=10,
    scope="user",
    backend="redis"  # Redis version performs best!
)
```

**Behavior:**
- Prevents boundary bursts
- Still O(1) time complexity
- Smooth rate limiting without fixed window issues

**Pros:** ✅ Best balance of accuracy and performance  
**Cons:** ⚠️ Slight approximation (but negligible in practice)

**Use when:** Production APIs, user-facing services (RECOMMENDED for most cases)

---

### 📜 Sliding Window Log — **Most accurate**

**How it works:** Logs exact timestamp of each request. Prunes old timestamps outside the window.

```python
from RateLimiter import SlidingWindowLogRateLimiter

limiter = SlidingWindowLogRateLimiter(
    capacity=10,
    fill_rate=10/300,  # 10 per 5 minutes
    scope="ip",
    backend="redis"
)
```

**Behavior:**
- Perfect accuracy (no approximation)
- Uses Redis sorted sets for efficiency
- O(n) time complexity

**Pros:** ✅ Perfect accuracy, no boundary issues  
**Cons:** ❌ Higher memory usage, not suitable for huge scale

**Use when:** Security-critical endpoints (login, payment), billing APIs

---

### 📦 Queue-based Limiter

**How it works:** Maintains a queue of recent request timestamps. Similar to Sliding Window Log.

```python
from RateLimiter import QueueLimiter

limiter = QueueLimiter(
    capacity=50,
    fill_rate=5.0,
    scope="global",
    backend="memory"
)
```

**Behavior:**
- Fair queuing
- Predictable wait times

**Use when:** Background job processing, task queues

---

## 📊 Performance Benchmarks

**Test Setup:** 5 concurrent users, 10-second tests, mixed traffic patterns

| Algorithm | Memory (req/s) | Redis (req/s) | Success Rate | Best For |
|-----------|----------------|---------------|--------------|----------|
| **Fixed Window** | 15.99 🥇 | 15.33 | 53-59% | High throughput |
| **Sliding Window** | 15.03 | 14.32 | 51-66% | **Production (best balance)** ⭐ |
| **Sliding Window Log** | 15.41 | 14.58 | 52-67% | Accuracy-critical |
| **Token Bucket** | 4.76 | 3.69 | 14-16% | Burst-friendly APIs |
| **Leaky Bucket** | 4.76 | 2.93 | 10-16% | Traffic shaping |
| **Queue Limiter** | 2.76 | 3.03 | 9-12% | Fair queuing |

**Key Findings:**
- Window-based algorithms are **3-4x faster** than token/leaky bucket
- Redis adds ~10% overhead but enables distributed rate limiting
- Sliding Window with Redis has **65.7% success rate** (best balanced algorithm)

**Winner:** 🏆 **Sliding Window (Redis)** — Best for production APIs

---

## 🎯 Usage Examples

### Example 1: Per-User Rate Limiting

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer
from RateLimiter import SlidingWindowRateLimiter

app = FastAPI()
security = HTTPBearer()
limiter = SlidingWindowRateLimiter(capacity=100, fill_rate=10, scope="user", backend="redis")

def get_current_user(token: str = Depends(security)):
    # Your auth logic here
    return {"user_id": "user_123"}

@app.get("/api/data")
async def get_data(user = Depends(get_current_user)):
    if not limiter.allow_request(user["user_id"]):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return {"data": "Your protected data"}
```

---

### Example 2: Per-IP Rate Limiting (for public endpoints)

```python
from fastapi import FastAPI, Request, HTTPException
from RateLimiter import FixedWindowRateLimiter

app = FastAPI()
limiter = FixedWindowRateLimiter(capacity=1000, fill_rate=100, scope="ip", backend="redis")

@app.get("/public/api")
async def public_endpoint(request: Request):
    client_ip = request.client.host
    
    if not limiter.allow_request(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests from your IP",
            headers={"Retry-After": "60"}
        )
    
    return {"message": "Public data"}
```

---

### Example 3: Global Rate Limiting

```python
from RateLimiter import LeakyBucketLimiter

# Limit total API traffic
global_limiter = LeakyBucketLimiter(
    capacity=10000,
    fill_rate=1000,  # 1000 req/sec globally
    scope="global",
    backend="redis"
)

@app.middleware("http")
async def global_rate_limit(request: Request, call_next):
    if not global_limiter.allow_request(None):  # None for global scope
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    return await call_next(request)
```

---

### Example 4: Multi-Layer Rate Limiting (Defense in Depth)

```python
# Layer 1: Global limit (protect infrastructure)
global_limiter = FixedWindowRateLimiter(capacity=100000, fill_rate=10000, scope="global", backend="redis")

# Layer 2: Per-IP limit (prevent DDoS)
ip_limiter = SlidingWindowRateLimiter(capacity=1000, fill_rate=100, scope="ip", backend="redis")

# Layer 3: Per-user limit (fair usage)
user_limiter = TokenBucketLimiter(capacity=100, fill_rate=10, scope="user", backend="redis")

@app.middleware("http")
async def layered_rate_limit(request: Request, call_next):
    # Check global limit first
    if not global_limiter.allow_request(None):
        raise HTTPException(status_code=503, detail="Service overloaded")
    
    # Check IP limit
    if not ip_limiter.allow_request(request.client.host):
        raise HTTPException(status_code=429, detail="IP rate limit exceeded")
    
    # Check user limit (if authenticated)
    user_id = request.headers.get("X-User-ID")
    if user_id and not user_limiter.allow_request(user_id):
        raise HTTPException(status_code=429, detail="User rate limit exceeded")
    
    return await call_next(request)
```

---

### Example 5: Custom Response with Retry-After

```python
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def rate_limit_handler(request: Request, exc: HTTPException):
    if exc.status_code == 429:
        # Get wait time from limiter
        user_id = request.headers.get("X-User-ID") or request.client.host
        wait_time = limiter.get_wait_time(user_id)
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "retry_after_seconds": int(wait_time),
                "message": f"Please wait {int(wait_time)} seconds before retrying"
            },
            headers={"Retry-After": str(int(wait_time))}
        )
    return exc
```

---

## 🔧 API Reference

### Common Methods (All Limiters)

#### `allow_request(identifier=None) -> bool`

Check if a request should be allowed.

**Parameters:**
- `identifier` (str, optional): User ID, IP address, or None for global scope

**Returns:**
- `bool`: True if allowed, False if rate limited

**Example:**
```python
if limiter.allow_request("user_123"):
    # Process request
    pass
else:
    # Return 429
    pass
```

---

#### `get_status(identifier=None) -> dict`

Get current limiter status for monitoring.

**Returns:**
```python
{
    "tokens_remaining": 7.5,  # Token Bucket
    "capacity": 10,
    "fill_rate": 1.0,
    "utilization_pct": 25.0
}
```

**Example:**
```python
status = limiter.get_status("user_123")
print(f"User has {status['tokens_remaining']} requests remaining")
```

---

#### `get_wait_time(identifier=None) -> float`

Calculate seconds until next request would be allowed.

**Returns:**
- `float`: Seconds to wait (0.0 if request would be allowed immediately)

**Example:**
```python
wait = limiter.get_wait_time("user_123")
if wait > 0:
    print(f"Please wait {wait:.1f} seconds")
```

---

#### `reset(identifier=None) -> None`

Reset rate limit for an identifier (useful for testing or admin actions).

**Example:**
```python
# Admin endpoint to reset user's rate limit
@app.post("/admin/reset-limit/{user_id}")
async def reset_user_limit(user_id: str):
    limiter.reset(user_id)
    return {"message": f"Rate limit reset for {user_id}"}
```

---

## 🧱 Backend Comparison

### In-Memory Backend

**Pros:**
- ⚡ Ultra-fast (no network overhead)
- 🎯 Zero dependencies
- 🧪 Perfect for development/testing

**Cons:**
- ❌ Not shared across app instances
- ❌ Lost on restart
- ❌ Not suitable for production clusters

**Use when:**
- Development/testing
- Single-instance deployments
- Non-critical rate limiting

---

### Redis Backend

**Pros:**
- 🌍 Shared across all app instances
- 💾 Persistent across restarts
- 🔒 Atomic operations (race-condition free)
- 📈 Horizontally scalable

**Cons:**
- 🐢 ~10% slower (network latency)
- 🧱 Requires Redis service
- 💰 Additional infrastructure cost

**Use when:**
- Production environments
- Load-balanced apps (multiple instances)
- Microservices architecture
- When rate limits must persist across restarts

---

**Setup Redis:**

```bash
# Docker
docker run -d --name redis -p 6379:6379 redis

# Or use Redis Cloud (free tier)
# https://redis.com/try-free/
```

---

## 💡 Best Practices

### 1. Choose the Right Algorithm

```python
# For most APIs → Sliding Window
limiter = SlidingWindowRateLimiter(...)

# For burst-heavy traffic → Token Bucket
limiter = TokenBucketLimiter(...)

# For critical operations → Sliding Window Log
limiter = SlidingWindowLogRateLimiter(...)
```

### 2. Use Appropriate Scope

```python
# Authenticated users → per-user
scope="user"

# Public APIs → per-IP
scope="ip"

# Infrastructure protection → global
scope="global"
```

### 3. Set Realistic Limits

```python
# Don't be too strict!
# Bad: 10 req/hour (users will be frustrated)
# Good: 1000 req/hour (generous but protective)

limiter = SlidingWindowRateLimiter(
    capacity=1000,
    fill_rate=1000/3600,  # 1000 per hour
    scope="user",
    backend="redis"
)
```

### 4. Always Include Retry-After Header

```python
if not limiter.allow_request(user_id):
    wait_time = limiter.get_wait_time(user_id)
    raise HTTPException(
        status_code=429,
        headers={"Retry-After": str(int(wait_time))}
    )
```

### 5. Monitor Your Rate Limiters

```python
@app.get("/metrics/rate-limits")
async def get_rate_limit_metrics():
    return {
        "global": global_limiter.get_status(None),
        "sample_user": user_limiter.get_status("user_123")
    }
```

---

## 🧪 Testing

### Run All Tests

```bash
# Run comprehensive test suite
python tests/all_limiter_test.py

# Or with pytest
pytest tests/
```

### Test Coverage

- ✅ All 6 algorithms
- ✅ All 3 scopes (global, user, IP)
- ✅ Both backends (memory, Redis)
- ✅ Concurrent access (thread safety)
- ✅ Multi-layer rate limiting
- ✅ **Total: 72 test scenarios**

### Example Test Output

```
==========================================================================================
  FINAL COMPARISON SUMMARY
==========================================================================================
Limiter                   Backend       Allowed    Blocked     Rate/s   Success%       
------------------------------------------------------------------------------------------
Fixed Window              memory            168        145     15.99      53.7%        
Sliding Window            redis             153         80     14.32      65.7%  ⭐      
Sliding Window Log        redis             155         95     14.58      62.0%        
Token Bucket              memory             50        262      4.76      16.0%        

🏆 Best Performance: Sliding Window (redis): 14.32 req/s with 65.7% success rate
```

---

## 🤝 Contributing

We welcome contributions! Here's how:

1. **Fork** the repo
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### Development Setup

```bash
git clone https://github.com/awais7012/FastAPI-RateLimiter.git
cd FastAPI-RateLimiter
pip install -e ".[dev]"
```

### Code Style

- Follow PEP 8
- Add docstrings to all functions
- Include type hints
- Write tests for new features

---

## 🐛 Troubleshooting

### Redis Connection Errors

```python
# Problem: redis.exceptions.ConnectionError
# Solution: Ensure Redis is running

# Check Redis
docker ps | grep redis

# Or start Redis
docker run -d --name redis -p 6379:6379 redis
```

### Rate Limit Not Working Across Instances

```python
# Problem: Rate limits don't work across multiple app instances
# Solution: Use Redis backend, not memory

# ❌ Wrong (memory backend)
limiter = SlidingWindowRateLimiter(..., backend="memory")

# ✅ Correct (Redis backend)
limiter = SlidingWindowRateLimiter(..., backend="redis", redis_client=redis_client)
```

### Import Errors

```python
# Problem: ModuleNotFoundError: No module named 'RateLimiter'
# Solution: Install the package

pip install -e .
# Or
pip install -e ".[redis]"
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Inspired by [FastAPI](https://fastapi.tiangolo.com/) documentation style
- Rate limiting algorithms based on industry best practices
- Built with ❤️ by [Ahmed Awais (Romeo)](https://github.com/awais7012)

---

## 📞 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/awais7012/FastAPI-RateLimiter/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/awais7012/FastAPI-RateLimiter/discussions)
- 📧 **Email**: ahmadawaisgithub@gmail.com

---

<p align="center">
  <strong>Built for developers who love clean, scalable FastAPI tooling.</strong><br/>
  ⭐ Star us on GitHub if you find this useful!
</p>

<p align="center">
  <a href="https://github.com/awais7012/FastAPI-RateLimiter">
    <img src="https://img.shields.io/github/stars/awais7012/FastAPI-RateLimiter?style=social" alt="GitHub stars">
  </a>
</p>
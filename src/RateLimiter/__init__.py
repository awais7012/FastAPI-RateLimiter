
from .base import BaseRateLimiter
from .token_bucket import TokenBucketLimiter
from .rate_limiter import RateLimiter


__all__ = ["BaseRateLimiter", "TokenBucketLimiter", "RateLimiter"]

# Leaky Bucket
try:
    from .leaky_bucket import LeakyBucketLimiter
    __all__.append("LeakyBucketLimiter")
except ImportError:
    pass

# Queue Limiter
try:
    from .queue_limiter import QueueLimiter
    __all__.append("QueueLimiter")
except ImportError:
    pass

# Fixed Window
try:
    from .fixed_window import FixedWindowRateLimiter
    __all__.append("FixedWindowRateLimiter")
except ImportError:
    pass

# Sliding Window
try:
    from .sliding_window import SlidingWindowRateLimiter
    __all__.append("SlidingWindowRateLimiter")
except ImportError:
    pass

# Sliding Window Log
try:
    from .sliding_window_log import SlidingWindowLogRateLimiter
    __all__.append("SlidingWindowLogRateLimiter")
except ImportError:
    pass

__version__ = "2.0.0"

# Convenience mapping for easy access
LIMITERS = {
    "token_bucket": TokenBucketLimiter,
}

if "LeakyBucketLimiter" in __all__:
    LIMITERS["leaky_bucket"] = LeakyBucketLimiter

if "QueueLimiter" in __all__:
    LIMITERS["queue"] = QueueLimiter

if "FixedWindowRateLimiter" in __all__:
    LIMITERS["fixed_window"] = FixedWindowRateLimiter

if "SlidingWindowRateLimiter" in __all__:
    LIMITERS["sliding_window"] = SlidingWindowRateLimiter

if "SlidingWindowLogRateLimiter" in __all__:
    LIMITERS["sliding_window_log"] = SlidingWindowLogRateLimiter
# test_detailed_state.py
"""
Detailed test showing internal state differences between Token Bucket and Leaky Bucket
"""
import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from fastapi_advanced_rate_limiter.token_bucket import TokenBucketLimiter
from fastapi_advanced_rate_limiter.leaky_bucket import LeakyBucketLimiter


def show_status(limiter, user_id, label):
    """Show current limiter status"""
    try:
        status = limiter.get_status(user_id)
        if 'tokens_remaining' in status:
            print(f"  {label}: Tokens={status['tokens_remaining']:.2f}/{status['capacity']} "
                  f"(Available: {status['tokens_remaining']:.2f})")
        elif 'water_level' in status:
            print(f"  {label}: Water={status['water_level']:.2f}/{status['capacity']} "
                  f"(Space left: {status['available']:.2f})")
    except Exception as e:
        print(f"  {label}: Error getting status - {e}")


def test_with_status(limiter_class, name):
    """Test with detailed status output"""
    print(f"\n{'='*70}")
    print(f"{name}")
    print(f"{'='*70}")
    
    limiter = limiter_class(capacity=5, fill_rate=1.0, scope="user")
    user_id = "test_user"
    
    # Initial state
    print("\n📊 Initial State:")
    show_status(limiter, user_id, "Before any requests")
    
    # Make 3 requests
    print("\n🔸 Making 3 requests rapidly...")
    for i in range(3):
        result = "✅ ALLOWED" if limiter.allow_request(user_id) else "❌ BLOCKED"
        print(f"  Request {i+1}: {result}")
    
    show_status(limiter, user_id, "After 3 requests")
    
    # Wait 2 seconds
    print("\n⏰ Waiting 2 seconds...")
    time.sleep(2)
    show_status(limiter, user_id, "After 2 second wait")
    
    # Make 5 more requests
    print("\n🔸 Making 5 more requests rapidly...")
    for i in range(5):
        result = "✅ ALLOWED" if limiter.allow_request(user_id) else "❌ BLOCKED"
        print(f"  Request {i+1}: {result}")
    
    show_status(limiter, user_id, "After 5 more requests")
    
    # Wait 5 seconds
    print("\n⏰ Waiting 5 seconds...")
    time.sleep(5)
    show_status(limiter, user_id, "After 5 second wait")
    
    # Try one more
    print("\n🔸 Making 1 final request...")
    result = "✅ ALLOWED" if limiter.allow_request(user_id) else "❌ BLOCKED"
    print(f"  Request: {result}")
    show_status(limiter, user_id, "After final request")


def conceptual_explanation():
    """Show the conceptual difference"""
    print("\n" + "="*70)
    print("CONCEPTUAL DIFFERENCE")
    print("="*70)
    
    print("\n🪣 Token Bucket (Restaurant Analogy):")
    print("  - You have a bowl with 5 tokens (money)")
    print("  - Each request costs 1 token")
    print("  - Tokens are added back at 1/second")
    print("  - Ask: 'Do I have enough tokens to spend?'")
    print("  - State: Tokens REMAINING (what you have)")
    
    print("\n💧 Leaky Bucket (Water Tank Analogy):")
    print("  - You have a tank that can hold 5 liters")
    print("  - Each request adds 1 liter of water")
    print("  - Water leaks out at 1 liter/second")
    print("  - Ask: 'Do I have space to add more water?'")
    print("  - State: Water LEVEL (what's filled)")
    
    print("\n🎯 Key Insight:")
    print("  Token Bucket: tracks what you HAVE")
    print("  Leaky Bucket: tracks what you've USED")
    print("  Both produce SAME rate limiting results!")
    
    print("\n📐 Mathematical Relationship:")
    print("  tokens_remaining + water_level = capacity")
    print("  If tokens=2, then water=3 (in a capacity=5 bucket)")
    print("  They're inverse representations of the same state!")


def verify_inverse_relationship():
    """Verify that token and water levels are inversely related"""
    print("\n" + "="*70)
    print("VERIFICATION: Inverse Relationship")
    print("="*70)
    
    token_limiter = TokenBucketLimiter(capacity=5, fill_rate=1.0, scope="user")
    leaky_limiter = LeakyBucketLimiter(capacity=5, fill_rate=1.0, scope="user")
    
    user_id = "test_user"
    
    print("\n🧪 Making 3 requests on both limiters...")
    for i in range(3):
        token_limiter.allow_request(user_id)
        leaky_limiter.allow_request(user_id)
    
    token_status = token_limiter.get_status(user_id)
    leaky_status = leaky_limiter.get_status(user_id)
    
    tokens = token_status.get('tokens_remaining', 0)
    water = leaky_status.get('water_level', 0)
    
    print(f"\nToken Bucket: {tokens:.2f} tokens remaining")
    print(f"Leaky Bucket: {water:.2f} water level")
    print(f"Sum: {tokens:.2f} + {water:.2f} = {tokens + water:.2f}")
    print(f"Capacity: 5")
    
    if abs((tokens + water) - 5.0) < 0.01:
        print("\n✅ VERIFIED: tokens + water = capacity")
        print("   They are inverse representations!")
    else:
        print("\n⚠️  Unexpected: Sum doesn't equal capacity")


def main():
    print("="*70)
    print("DETAILED STATE COMPARISON: Token Bucket vs Leaky Bucket")
    print("="*70)
    print("Settings: capacity=5, fill_rate=1.0/s")
    
    # Test Token Bucket
    test_with_status(TokenBucketLimiter, "🪙 TOKEN BUCKET")
    
    time.sleep(1)
    
    # Test Leaky Bucket
    test_with_status(LeakyBucketLimiter, "💧 LEAKY BUCKET")
    
    # Show conceptual explanation
    conceptual_explanation()
    
    # Verify inverse relationship
    verify_inverse_relationship()


if __name__ == "__main__":
    main()
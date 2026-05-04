"""
Rate Limiter — protects endpoints from abuse and brute force attacks.
Uses SlowAPI (built on top of limits library).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Create limiter instance
# Uses client IP address as the key
limiter = Limiter(key_func=get_remote_address)
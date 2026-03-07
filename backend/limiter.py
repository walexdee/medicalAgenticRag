from slowapi import Limiter
from slowapi.util import get_remote_address

# Single shared limiter instance imported by main.py and all routers.
# get_remote_address uses the client IP as the rate-limit key.
limiter = Limiter(key_func=get_remote_address)

from time import time
from typing import Dict
from fastapi import Request, HTTPException, status
from ..core.config import RATE_LIMIT_PER_MINUTE

bucket: Dict[str, list[float]] = {}

def rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time()
    window = 60.0
    arr = bucket.get(ip, [])
    arr = [t for t in arr if now - t < window]
    if len(arr) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    arr.append(now)
    bucket[ip] = arr

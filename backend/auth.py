from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

from backend.config import API_KEY

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str = Security(_api_key_header)):
    """
    FastAPI dependency that enforces API key authentication.
    If API_KEY is not configured (e.g. local dev), all requests pass through.
    If API_KEY is set, requests must include header:  X-API-Key: <value>
    """
    if API_KEY and key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

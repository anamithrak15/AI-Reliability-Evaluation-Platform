from fastapi import Request

from app.core.config import get_settings


def client_ip(request: Request) -> str:
    """Caller address for rate limiting and logs.

    With TRUSTED_PROXY_HOPS = N the last N hops are our own proxies, each appending the address it
    saw to X-Forwarded-For, so the real client is N entries from the right. Anything the caller put
    further left is ignored, which stops header spoofing from dodging rate limits.
    """
    direct = request.client.host if request.client else "unknown"
    hops = get_settings().trusted_proxy_hops
    if hops <= 0:
        return direct
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    index = len(forwarded) - hops
    return forwarded[index] if 0 <= index < len(forwarded) else direct

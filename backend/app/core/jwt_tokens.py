"""Short-lived JWT helpers for dev cookie auth (swap for refresh tokens later)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

import jwt

JWT_ALG = "HS256"


def create_access_token(
    *,
    sub: str,
    role: str,
    secret: str,
    email: Optional[str] = None,
    days: int = 7,
) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(days=days)
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if email:
        payload["email"] = email
    return jwt.encode(payload, secret, algorithm=JWT_ALG)


def decode_access_token(token: str, secret: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, secret, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None

"""JWT helpers: short-lived access + longer-lived refresh (HS256)."""

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
    fbo_id: Optional[str] = None,
    username: Optional[str] = None,
    display_name: Optional[str] = None,
    training_status: Optional[str] = None,
    registration_status: Optional[str] = None,
    training_required: Optional[bool] = None,
    ver: Optional[int] = None,
    minutes: int = 60,
) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(minutes=minutes)
    payload: dict[str, Any] = {
        "typ": "access",
        "sub": sub,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if email:
        payload["email"] = email
    if fbo_id:
        payload["fbo_id"] = fbo_id
    if username:
        payload["username"] = username
    if display_name is not None:
        payload["display_name"] = display_name
    if training_status:
        payload["training_status"] = training_status
    if registration_status:
        payload["registration_status"] = registration_status
    if training_required is not None:
        payload["training_required"] = training_required
    if ver is not None:
        payload["ver"] = ver
    return jwt.encode(payload, secret, algorithm=JWT_ALG)


def create_refresh_token(*, sub: str, secret: str, days: int = 14) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(days=days)
    payload: dict[str, Any] = {
        "typ": "refresh",
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALG)


def decode_access_token(token: str, secret: str) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") == "refresh":
        return None
    return payload


def decode_refresh_token(token: str, secret: str) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "refresh":
        return None
    return payload

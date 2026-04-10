"""Password hashing (bcrypt). Dev seed hash must match Alembic migration."""

from __future__ import annotations

import bcrypt

# Same plain password and bcrypt hash as migration `20250410_0005_dev_login_passwords`.
# Local/dev only — rotate in real deployments.
DEV_LOGIN_PASSWORD_PLAIN = "myle-dev-login"
DEV_LOGIN_BCRYPT_HASH = (
    "$2b$12$9Btds2bpJbyCRS7P2HUePeE6pJKr1DiIlPphCBt71eti7cNuViMjm"
)


def verify_password(plain: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()

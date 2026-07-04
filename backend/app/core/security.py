"""
安全模块 — JWT 令牌生成/验证 + bcrypt 密码哈希
<<<<<<< HEAD

直接使用 bcrypt，避免 passlib 与新版 bcrypt 的兼容性问题
=======
>>>>>>> main
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

<<<<<<< HEAD

# ============================================================
# 密码哈希（直接使用 bcrypt）
=======
# ============================================================
# 密码哈希（直接使用 bcrypt，避免 passlib 兼容性问题）
>>>>>>> main
# ============================================================


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希"""
<<<<<<< HEAD
    # bcrypt 要求密码不超过 72 字节
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")
=======
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
>>>>>>> main


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配"""
<<<<<<< HEAD
    pwd_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
=======
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
>>>>>>> main


# ============================================================
# JWT
# ============================================================


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    """生成访问令牌 (Access Token)"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """生成刷新令牌 (Refresh Token)"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并验证 JWT Token，返回 payload"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Token 无效或已过期: {e}")

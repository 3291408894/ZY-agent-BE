"""JWT 令牌 + 密码哈希（纯 Python 实现，零额外二进制依赖）"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """对密码进行安全哈希（HMAC-SHA256 + salt）"""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex() + ":" + key.hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希值是否匹配"""
    try:
        salt_hex, key_hex = hashed_password.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_key = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt, 100000
        )
        return hmac.compare_digest(expected_key.hex(), key_hex)
    except (ValueError, AttributeError):
        return False


def _base64url_encode(data: bytes) -> str:
    """Base64URL 编码（无 padding）"""
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(s: str) -> bytes:
    """Base64URL 解码"""
    import base64
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_access_token(user_id: str, expires_delta: int | None = None) -> str:
    """生成 JWT 访问令牌（HS256 自实现版本）"""
    import json
    if expires_delta is None:
        expires_delta = settings.ACCESS_TOKEN_EXPIRE_SECONDS
    expire = datetime.now(timezone.utc) + timedelta(seconds=expires_delta)
    header = _base64url_encode(json.dumps({"alg": ALGORITHM, "typ": "JWT"}).encode())
    payload = _base64url_encode(json.dumps({
        "sub": user_id,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }).encode())
    signature = hmac.new(
        settings.SECRET_KEY.encode(), f"{header}.{payload}".encode(), "sha256"
    ).digest()
    return f"{header}.{payload}.{_base64url_encode(signature)}"


def decode_access_token(token: str) -> dict | None:
    """解码 JWT 令牌，失败返回 None"""
    import json
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts

        # 验证签名
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode(),
            f"{header_b64}.{payload_b64}".encode(),
            "sha256",
        ).digest()
        actual_sig = _base64url_decode(signature_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(_base64url_decode(payload_b64))

        # 验证过期
        if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None

        return payload
    except Exception:
        return None

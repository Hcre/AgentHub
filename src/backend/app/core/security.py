"""安全工具：API Key 的 AES-256-GCM 加密 + JWT 签发/校验。

PRD §3.2：API Key 使用 AES-256-GCM 加密存储；WebSocket 连接需 JWT 鉴权。
"""

import base64
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_NONCE_BYTES = 12


def _load_key() -> bytes:
    """从配置加载 32 字节 AES 密钥（base64）。长度非法时抛错，避免静默降级。"""
    raw = base64.b64decode(settings.secret_key)
    if len(raw) != 32:
        raise ValueError(
            "SECRET_KEY 必须是 base64 编码的 32 字节密钥；"
            '生成：python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"'
        )
    return raw


def encrypt_secret(plaintext: str) -> str:
    """加密明文（如 Agent api_key），返回 base64(nonce + ciphertext)。"""
    key = _load_key()
    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_secret(token: str) -> str:
    """解密 encrypt_secret 的产物。"""
    key = _load_key()
    blob = base64.b64decode(token)
    nonce, ct = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    """签发 JWT。subject 通常为 user_id。"""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """校验并解析 JWT；非法/过期会抛 jwt.PyJWTError。"""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

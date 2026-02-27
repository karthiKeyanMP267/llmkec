"""Auth helpers for the ingestion API routes using the existing auth service JWT."""

import base64
import hmac
import json
import os
import time
from hashlib import sha256
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.ingestion_api.utils.logger import get_logger

logger = get_logger(__name__)


_bearer = HTTPBearer(auto_error=False)


def _b64url_decode(val: str) -> bytes:
    padding = '=' * (-len(val) % 4)
    return base64.urlsafe_b64decode(val + padding)


def _verify_hs256(token: str, secret: str) -> dict:
    try:
        header_b64, payload_b64, sig_b64 = token.split('.')
    except ValueError:
        logger.warning("Invalid token format")
        raise HTTPException(status_code=401, detail="Invalid token format")  # raise required by FastAPI

    header = json.loads(_b64url_decode(header_b64))
    if header.get("alg") != "HS256":
        logger.warning("Unsupported JWT algorithm: %s", header.get("alg"))
        raise HTTPException(status_code=401, detail="Unsupported alg")  # raise required by FastAPI

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected_sig = hmac.new(secret.encode(), signing_input, sha256).digest()
    provided_sig = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected_sig, provided_sig):
        logger.warning("Invalid JWT signature")
        raise HTTPException(status_code=401, detail="Invalid signature")  # raise required by FastAPI

    payload = json.loads(_b64url_decode(payload_b64))
    exp = payload.get("exp")
    if exp is not None and time.time() > float(exp):
        logger.warning("Token expired")
        raise HTTPException(status_code=401, detail="Token expired")  # raise required by FastAPI
    return payload


def require_admin_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    request: Request = None,
):
    if not credentials or not credentials.credentials:
        logger.warning("Missing bearer token")
        raise HTTPException(status_code=401, detail="Missing bearer token")  # raise required by FastAPI

    secret = os.getenv("AUTH_JWT_SECRET")
    allowed_roles = os.getenv("INGESTION_ALLOWED_ROLES", "ADMIN").split(',')
    allowed_roles = {r.strip().upper() for r in allowed_roles if r.strip()}

    if not secret:
        logger.error("AUTH_JWT_SECRET not configured")
        raise HTTPException(status_code=500, detail="AUTH_JWT_SECRET not configured")  # raise required by FastAPI

    payload = _verify_hs256(credentials.credentials, secret)
    role = str(payload.get("role", "")).upper()
    if role not in allowed_roles:
        logger.warning("Forbidden: role '%s' not in allowed roles", role)
        raise HTTPException(status_code=403, detail="Forbidden")  # raise required by FastAPI

    request.state.user = payload
    return payload
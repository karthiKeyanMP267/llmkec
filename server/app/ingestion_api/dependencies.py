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


_bearer = HTTPBearer(auto_error=False)


def _b64url_decode(val: str) -> bytes:
    padding = '=' * (-len(val) % 4)
    return base64.urlsafe_b64decode(val + padding)


def _verify_hs256(token: str, secret: str) -> dict:
    try:
        header_b64, payload_b64, sig_b64 = token.split('.')
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token format")

    header = json.loads(_b64url_decode(header_b64))
    if header.get("alg") != "HS256":
        raise HTTPException(status_code=401, detail="Unsupported alg")

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected_sig = hmac.new(secret.encode(), signing_input, sha256).digest()
    provided_sig = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(_b64url_decode(payload_b64))
    exp = payload.get("exp")
    if exp is not None and time.time() > float(exp):
        raise HTTPException(status_code=401, detail="Token expired")
    return payload


def require_admin_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    request: Request = None,
):
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    secret = os.getenv("AUTH_JWT_SECRET")
    allowed_roles = os.getenv("INGESTION_ALLOWED_ROLES", "ADMIN").split(',')
    allowed_roles = {r.strip().upper() for r in allowed_roles if r.strip()}

    if not secret:
        raise HTTPException(status_code=500, detail="AUTH_JWT_SECRET not configured")

    payload = _verify_hs256(credentials.credentials, secret)
    role = str(payload.get("role", "")).upper()
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Forbidden")

    request.state.user = payload
    return payload
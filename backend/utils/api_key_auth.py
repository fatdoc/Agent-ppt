"""Authentication helpers for the server-to-server public API."""
from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta

from flask import g, request

from models import ApiKey, db
from utils.auth import single_user_mode_allows, single_user_mode_maintenance_response
from utils.response import error_response


def _bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def authenticate_api_key(required_scope: str = "ppt:generate"):
    """Set ``g.current_user``/``g.current_api_key`` or return an API error."""
    token = _bearer_token()
    prefix = ApiKey.prefix_from_token(token)
    if not prefix:
        return error_response("INVALID_API_KEY", "A valid API key is required", 401)

    api_key = ApiKey.query.filter_by(key_prefix=prefix).first()
    if not api_key or not api_key.is_usable():
        return error_response("INVALID_API_KEY", "The API key is invalid, expired, or revoked", 401)
    if not hmac.compare_digest(api_key.key_hash, ApiKey.hash_token(token)):
        return error_response("INVALID_API_KEY", "The API key is invalid, expired, or revoked", 401)
    if required_scope and not api_key.has_scope(required_scope):
        return error_response("INSUFFICIENT_SCOPE", f"API key requires scope: {required_scope}", 403)
    if not api_key.user or not api_key.user.is_active:
        return error_response("INVALID_API_KEY", "The API key owner is inactive", 401)
    if not single_user_mode_allows(api_key.user):
        return single_user_mode_maintenance_response()

    now = datetime.utcnow()
    write_interval = max(0, int(os.getenv('API_KEY_LAST_USED_WRITE_INTERVAL_SECONDS', '300')))
    if not api_key.last_used_at or now - api_key.last_used_at >= timedelta(seconds=write_interval):
        api_key.last_used_at = now
        db.session.commit()
    g.current_api_key = api_key
    g.current_user = api_key.user
    return None

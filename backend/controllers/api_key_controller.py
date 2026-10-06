"""Logged-in API key management endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, request

from models import ApiKey, db
from utils import bad_request, not_found, success_response
from utils.auth import current_user


api_key_bp = Blueprint("api_keys", __name__, url_prefix="/api/api-keys")
ALLOWED_SCOPES = {"ppt:generate"}


@api_key_bp.route("", methods=["POST"])
def create_api_key():
    user = current_user()
    if not user:
        return bad_request("Login required")

    data = request.get_json() or {}
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 120:
        return bad_request("name is required and must be at most 120 characters")

    scopes = data.get("scopes") or ["ppt:generate"]
    if not isinstance(scopes, list) or not scopes or not set(scopes).issubset(ALLOWED_SCOPES):
        return bad_request("scopes may only contain ppt:generate")

    expires_at = None
    expires_in_days = data.get("expires_in_days")
    if expires_in_days is not None:
        try:
            expires_in_days = int(expires_in_days)
        except (TypeError, ValueError):
            return bad_request("expires_in_days must be an integer")
        if expires_in_days < 1 or expires_in_days > 3650:
            return bad_request("expires_in_days must be between 1 and 3650")
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    api_key, plaintext = ApiKey.issue(
        user_id=user.id,
        name=name,
        scopes=[str(scope) for scope in scopes],
        expires_at=expires_at,
    )
    db.session.add(api_key)
    db.session.commit()
    return success_response(
        {
            "api_key": api_key.to_dict(),
            "key": plaintext,
            "warning": "Store this key securely. It will not be shown again.",
        },
        status_code=201,
    )


@api_key_bp.route("", methods=["GET"])
def list_api_keys():
    user = current_user()
    if not user:
        return bad_request("Login required")
    keys = ApiKey.query.filter_by(user_id=user.id).order_by(ApiKey.created_at.desc()).all()
    return success_response({"api_keys": [item.to_dict() for item in keys]})


@api_key_bp.route("/<api_key_id>", methods=["DELETE"])
def revoke_api_key(api_key_id: str):
    user = current_user()
    if not user:
        return bad_request("Login required")
    api_key = ApiKey.query.filter_by(id=api_key_id, user_id=user.id).first()
    if not api_key:
        return not_found("ApiKey")
    api_key.revoke()
    db.session.commit()
    return success_response({"api_key": api_key.to_dict()}, message="API key revoked")

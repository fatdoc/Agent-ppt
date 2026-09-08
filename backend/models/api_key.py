"""API keys for server-to-server access to the public PPT API."""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime

from . import db


class ApiKey(db.Model):
    """A revocable, scoped credential owned by an application user."""

    __tablename__ = "api_keys"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    key_prefix = db.Column(db.String(40), nullable=False, unique=True)
    key_hash = db.Column(db.String(64), nullable=False, unique=True)
    scopes_json = db.Column(db.Text, nullable=False, default='["ppt:generate"]')
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    expires_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, *, user_id: str, name: str, scopes: list[str] | None = None, expires_at=None):
        """Create a model and return it together with the one-time plaintext token."""
        key_id = secrets.token_hex(8)
        secret = secrets.token_urlsafe(32)
        prefix = f"lt_live_{key_id}"
        token = f"{prefix}.{secret}"
        model = cls(
            user_id=user_id,
            name=name,
            key_prefix=prefix,
            key_hash=cls.hash_token(token),
            expires_at=expires_at,
        )
        model.set_scopes(scopes or ["ppt:generate"])
        return model, token

    @staticmethod
    def prefix_from_token(token: str) -> str | None:
        if not token or "." not in token:
            return None
        prefix, _secret = token.split(".", 1)
        return prefix if prefix.startswith("lt_live_") else None

    def get_scopes(self) -> list[str]:
        try:
            scopes = json.loads(self.scopes_json or "[]")
        except (TypeError, json.JSONDecodeError):
            return []
        return [str(scope) for scope in scopes] if isinstance(scopes, list) else []

    def set_scopes(self, scopes: list[str]) -> None:
        self.scopes_json = json.dumps(sorted(set(scopes)), ensure_ascii=False)

    def has_scope(self, scope: str) -> bool:
        scopes = self.get_scopes()
        return "*" in scopes or scope in scopes

    def is_usable(self, now: datetime | None = None) -> bool:
        now = now or datetime.utcnow()
        return bool(self.is_active and not self.revoked_at and (not self.expires_at or self.expires_at > now))

    def revoke(self) -> None:
        self.is_active = False
        self.revoked_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.key_prefix,
            "scopes": self.get_scopes(),
            "is_active": bool(self.is_active),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }

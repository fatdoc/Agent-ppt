"""Public API workflow state for outline-to-description-to-image jobs."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from . import db


class PublicPptGeneration(db.Model):
    """Stable public job identity over the internal description and image tasks."""

    __tablename__ = "public_ppt_generations"
    __table_args__ = (
        db.UniqueConstraint("user_id", "idempotency_key", name="uq_public_ppt_generation_idempotency"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    api_key_id = db.Column(db.String(36), db.ForeignKey("api_keys.id"), nullable=False, index=True)
    project_id = db.Column(db.String(36), db.ForeignKey("projects.id"), nullable=False, unique=True, index=True)
    description_task_id = db.Column(db.String(36), db.ForeignKey("tasks.id"), nullable=False)
    image_task_id = db.Column(db.String(36), db.ForeignKey("tasks.id"), nullable=False)
    idempotency_key = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(40), nullable=False, default="QUEUED", index=True)
    current_stage = db.Column(db.String(40), nullable=False, default="descriptions")
    request_json = db.Column(db.Text, nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    project = db.relationship("Project")
    description_task = db.relationship("Task", foreign_keys=[description_task_id])
    image_task = db.relationship("Task", foreign_keys=[image_task_id])
    api_key = db.relationship("ApiKey")

    def set_request_data(self, data: dict) -> None:
        self.request_json = json.dumps(data, ensure_ascii=False)

    def get_request_data(self) -> dict:
        try:
            data = json.loads(self.request_json or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def to_dict(self) -> dict:
        return {
            "generation_id": self.id,
            "status": self.status,
            "current_stage": self.current_stage,
            "project_id": self.project_id,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

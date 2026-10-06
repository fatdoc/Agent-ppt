"""Education content and immutable, project-owned revisions."""

import json
import uuid
from datetime import datetime

from . import db


class CompetitionDocument(db.Model):
    __tablename__ = "competition_documents"
    project_id = db.Column(
        db.String(36),
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    revision = db.Column(db.Integer, nullable=False, default=1)
    payload = db.Column(db.Text, nullable=False)
    active_task_id = db.Column(db.String(36), nullable=True)

    def content(self):
        return json.loads(self.payload)


class CompetitionRevision(db.Model):
    __tablename__ = "competition_revisions"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(
        db.String(36), db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    revision = db.Column(db.Integer, nullable=False)
    payload = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint("project_id", "revision", name="uq_competition_revision"),
    )


class CompetitionOperation(db.Model):
    __tablename__ = "competition_operations"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(
        db.String(36), db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    request_key = db.Column(db.String(80), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    task_id = db.Column(db.String(36), db.ForeignKey("tasks.id"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint(
            "project_id", "request_key", name="uq_competition_operation"
        ),
    )

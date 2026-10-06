"""Non-destructive organization metadata, isolated from shared file storage."""

from datetime import datetime
from . import db


class EducationSpaceEntry(db.Model):
    __tablename__ = "education_space_entries"
    key = db.Column(db.String(90), primary_key=True)
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category = db.Column(db.String(20), nullable=False)
    previous_category = db.Column(db.String(20))
    display_name = db.Column(db.String(500))
    deleted_at = db.Column(db.DateTime)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

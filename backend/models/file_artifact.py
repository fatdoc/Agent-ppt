"""Tenant-owned records for generated file trees such as MinerU extracts."""
import uuid
from datetime import datetime

from . import db


class FileArtifact(db.Model):
    __tablename__ = 'file_artifacts'
    __table_args__ = (
        db.UniqueConstraint('extract_id', name='uq_file_artifacts_extract_id'),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extract_id = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True, index=True)
    reference_file_id = db.Column(
        db.String(36),
        db.ForeignKey('reference_files.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    kind = db.Column(db.String(40), nullable=False, default='mineru_extract')
    root_relative_path = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'extract_id': self.extract_id,
            'project_id': self.project_id,
            'reference_file_id': self.reference_file_id,
            'kind': self.kind,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
        }

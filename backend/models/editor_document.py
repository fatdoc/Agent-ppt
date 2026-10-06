"""Additive immutable semantic revisions; existing Local Pages remain untouched."""
import uuid
from datetime import datetime
from . import db

class EditorDocument(db.Model):
    __tablename__ = 'editor_documents'
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'), primary_key=True)
    revision = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.CheckConstraint('revision > 0', name='ck_editor_document_revision_positive'),)

class EditorRevision(db.Model):
    __tablename__ = 'editor_revisions'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'), nullable=False)
    revision = db.Column(db.Integer, nullable=False)
    actor_user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    restored_from_revision = db.Column(db.Integer, nullable=True)
    payload = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('project_id','revision',name='uq_editor_project_revision'), db.CheckConstraint('revision > 0',name='ck_editor_revision_positive'))

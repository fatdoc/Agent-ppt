"""Reusable, versioned PPT outline template model."""
import json
import uuid
from datetime import datetime
from . import db


class OutlineTemplate(db.Model):
    __tablename__ = 'outline_templates'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    competition_id = db.Column(db.String(80), nullable=True, index=True)
    competition_type_id = db.Column(db.String(80), nullable=True)
    track_id = db.Column(db.String(80), nullable=True)
    theme_id = db.Column(db.String(80), nullable=True)
    support_scope = db.Column(db.String(20), nullable=False, default='PRIVATE')
    status = db.Column(db.String(20), nullable=False, default='DRAFT', index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    target_page_count = db.Column(db.Integer, nullable=True)
    style_tags = db.Column(db.Text, nullable=True)
    sections = db.Column(db.Text, nullable=False, default='[]')
    versions = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.String(100), nullable=False, default='CURRENT_USER')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def _load_json(value, fallback):
        if not value:
            return fallback
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback

    @staticmethod
    def _dump_json(value):
        return json.dumps(value, ensure_ascii=False)

    def get_sections(self):
        return self._load_json(self.sections, [])

    def set_sections(self, sections):
        self.sections = self._dump_json(sections or [])

    def get_versions(self):
        return self._load_json(self.versions, [])

    def set_versions(self, versions):
        self.versions = self._dump_json(versions or [])

    def get_style_tags(self):
        return self._load_json(self.style_tags, [])

    def set_style_tags(self, tags):
        self.style_tags = self._dump_json(tags or [])

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'competitionId': self.competition_id,
            'competitionTypeId': self.competition_type_id,
            'trackId': self.track_id,
            'themeId': self.theme_id,
            'supportScope': self.support_scope,
            'status': self.status,
            'version': self.version,
            'targetPageCount': self.target_page_count,
            'styleTags': self.get_style_tags(),
            'sections': self.get_sections(),
            'versions': self.get_versions(),
            'createdBy': self.created_by,
            'createdAt': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
        }

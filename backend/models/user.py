"""User model for application login accounts."""
import uuid
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from . import db


class User(db.Model):
    """Application user account."""

    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    email = db.Column(db.String(255), nullable=True, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    projects = db.relationship('Project', back_populates='user', lazy='select')
    settings = db.relationship('Settings', back_populates='user', lazy='select', uselist=False)
    user_templates = db.relationship('UserTemplate', back_populates='user', lazy='select')
    user_style_templates = db.relationship('UserStyleTemplate', back_populates='user', lazy='select')
    reference_files = db.relationship('ReferenceFile', back_populates='user', lazy='select')
    materials = db.relationship('Material', back_populates='user', lazy='select')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<User {self.id}: {self.username}>'

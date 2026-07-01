"""Credit account and ledger models."""
import json
import uuid
from datetime import datetime

from . import db


class CreditAccount(db.Model):
    """Per-user credit balance."""

    __tablename__ = 'credit_accounts'

    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    balance = db.Column(db.Integer, nullable=False, default=0)
    reserved_balance = db.Column(db.Integer, nullable=False, default=0)
    lifetime_credited = db.Column(db.Integer, nullable=False, default=0)
    lifetime_spent = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', back_populates='credit_account')

    @property
    def available_balance(self) -> int:
        return max(0, int(self.balance or 0) - int(self.reserved_balance or 0))

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'balance': self.balance,
            'reserved_balance': self.reserved_balance,
            'available_balance': self.available_balance,
            'lifetime_credited': self.lifetime_credited,
            'lifetime_spent': self.lifetime_spent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class CreditLedger(db.Model):
    """Immutable-ish credit movements for audit and task settlement."""

    __tablename__ = 'credit_ledger'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    task_id = db.Column(db.String(36), db.ForeignKey('tasks.id'), nullable=True, index=True)
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'), nullable=True, index=True)
    entry_type = db.Column(db.String(30), nullable=False, index=True)
    operation = db.Column(db.String(80), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    reserved_after = db.Column(db.Integer, nullable=False)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship('User', back_populates='credit_ledger')
    task = db.relationship('Task', back_populates='credit_entries')

    def get_metadata(self):
        if not self.metadata_json:
            return {}
        try:
            return json.loads(self.metadata_json)
        except json.JSONDecodeError:
            return {}

    def set_metadata(self, data) -> None:
        self.metadata_json = json.dumps(data or {}, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'task_id': self.task_id,
            'project_id': self.project_id,
            'entry_type': self.entry_type,
            'operation': self.operation,
            'amount': self.amount,
            'balance_after': self.balance_after,
            'reserved_after': self.reserved_after,
            'metadata': self.get_metadata(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

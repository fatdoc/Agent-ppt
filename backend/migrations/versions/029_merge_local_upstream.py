"""merge Local safety lineage with the fixed Upstream snapshot

Revision ID: 029_merge_local_upstream
Revises: 028_local_integrity, 78475bbce762
"""

revision = '029_merge_local_upstream'
down_revision = ('028_local_integrity', '78475bbce762')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""Registration helpers for tenant-owned generated file trees."""
from __future__ import annotations

from models import FileArtifact, db


def register_mineru_artifact(
    extract_id: str | None,
    *,
    user_id: str | None,
    project_id: str | None = None,
    reference_file_id: str | None = None,
) -> FileArtifact | None:
    if not extract_id:
        return None
    if not user_id:
        raise ValueError('MinerU artifacts require an owning user')

    existing = FileArtifact.query.filter_by(extract_id=extract_id).first()
    if existing:
        if existing.user_id != user_id:
            raise ValueError('MinerU extract id collision across tenants')
        return existing

    artifact = FileArtifact(
        extract_id=extract_id,
        user_id=user_id,
        project_id=project_id,
        reference_file_id=reference_file_id,
        kind='mineru_extract',
        root_relative_path=f'mineru_files/{extract_id}',
    )
    db.session.add(artifact)
    db.session.flush()
    return artifact

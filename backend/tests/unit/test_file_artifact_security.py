"""Security regression tests for tenant-owned MinerU file artifacts."""

import os
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from models import FileArtifact, Project, User, db
from services.file_artifact_service import register_mineru_artifact
from utils.auth import create_auth_token


@pytest.fixture
def mineru_artifact_case(client, app, tmp_path):
    with app.app_context():
        owner = User(username="artifact-owner", email="artifact-owner@example.test")
        owner.set_password("artifact-owner-password")
        intruder = User(username="artifact-intruder", email="artifact-intruder@example.test")
        intruder.set_password("artifact-intruder-password")
        db.session.add_all([owner, intruder])
        db.session.flush()

        project = Project(
            user_id=owner.id,
            project_title="Owner project",
            creation_type="idea",
            idea_prompt="owner content",
        )
        db.session.add(project)
        db.session.flush()

        extract_id = f"owner-extract-{uuid.uuid4().hex}"
        artifact = FileArtifact(
            extract_id=extract_id,
            user_id=owner.id,
            project_id=project.id,
            kind="mineru_extract",
            root_relative_path=f"mineru_files/{extract_id}",
        )
        db.session.add(artifact)
        db.session.commit()

        owner_token = create_auth_token(owner)
        intruder_token = create_auth_token(intruder)
        case = SimpleNamespace(
            artifact_id=artifact.id,
            extract_id=extract_id,
            owner_headers={"Authorization": f"Bearer {owner_token}"},
            intruder_headers={"Authorization": f"Bearer {intruder_token}"},
            owner_id=owner.id,
            intruder_id=intruder.id,
            project_id=project.id,
        )

    upload_root = Path(app.config["UPLOAD_FOLDER"])
    artifact_root = upload_root / "mineru_files" / extract_id
    artifact_root.mkdir(parents=True)
    owned_file = artifact_root / "images" / "owned.png"
    owned_file.parent.mkdir()
    owned_file.write_bytes(b"owner-only-image")

    sibling_root = upload_root / "mineru_files" / f"{extract_id}-secret"
    sibling_root.mkdir(parents=True)
    sibling_file = sibling_root / "secret.png"
    sibling_file.write_bytes(b"sibling-secret")

    outside_root = tmp_path / "outside-artifacts"
    outside_root.mkdir()
    outside_file = outside_root / "outside-secret.png"
    outside_file.write_bytes(b"outside-secret")

    case.artifact_root = artifact_root
    case.owned_file = owned_file
    case.sibling_root = sibling_root
    case.sibling_file = sibling_file
    case.outside_root = outside_root
    case.outside_file = outside_file
    return case


def _mineru_url(case, filepath: str) -> str:
    return f"/files/mineru/{case.extract_id}/{filepath}"


def test_mineru_artifact_owner_can_read_contained_file(client, mineru_artifact_case):
    response = client.get(
        _mineru_url(mineru_artifact_case, "images/owned.png"),
        headers=mineru_artifact_case.owner_headers,
    )

    assert response.status_code == 200
    assert response.data == b"owner-only-image"


def test_mineru_artifact_is_not_readable_by_another_tenant(client, mineru_artifact_case):
    response = client.get(
        _mineru_url(mineru_artifact_case, "images/owned.png"),
        headers=mineru_artifact_case.intruder_headers,
    )

    assert response.status_code == 404, response.get_json()
    assert b"owner-only-image" not in response.data


@pytest.mark.parametrize(
    "escape_path",
    [
        "../{extract_id}-secret/secret.png",
        "%2e%2e/{extract_id}-secret/secret.png",
    ],
)
def test_mineru_artifact_rejects_parent_and_sibling_prefix_escape(
    client,
    mineru_artifact_case,
    escape_path,
):
    escape_path = escape_path.format(extract_id=mineru_artifact_case.extract_id)
    response = client.get(
        _mineru_url(mineru_artifact_case, escape_path),
        headers=mineru_artifact_case.owner_headers,
    )

    assert response.status_code in {403, 404}, response.get_json()
    assert b"sibling-secret" not in response.data


def test_mineru_artifact_rejects_symlink_escape(client, mineru_artifact_case):
    link = mineru_artifact_case.artifact_root / "outside-link.png"
    try:
        os.symlink(mineru_artifact_case.outside_file, link)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    response = client.get(
        _mineru_url(mineru_artifact_case, link.name),
        headers=mineru_artifact_case.owner_headers,
    )

    assert response.status_code in {403, 404}, response.get_json()
    assert b"outside-secret" not in response.data


def test_deleted_mineru_artifact_is_not_served(client, app, mineru_artifact_case):
    with app.app_context():
        artifact = db.session.get(FileArtifact, mineru_artifact_case.artifact_id)
        artifact.deleted_at = datetime.utcnow()
        db.session.commit()

    response = client.get(
        _mineru_url(mineru_artifact_case, "images/owned.png"),
        headers=mineru_artifact_case.owner_headers,
    )

    assert response.status_code == 404, response.get_json()


def test_mineru_registration_rejects_extract_id_collision_across_tenants(
    app,
    mineru_artifact_case,
):
    with app.app_context(), pytest.raises(
        ValueError,
        match="collision across tenants",
    ):
        register_mineru_artifact(
            mineru_artifact_case.extract_id,
            user_id=mineru_artifact_case.intruder_id,
        )

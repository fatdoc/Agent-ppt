"""Tenant, credential, and idempotency guards for the public PPT API."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from models import (
    ApiKey,
    Page,
    Project,
    PublicPptGeneration,
    Task,
    User,
    UserTemplate,
    db,
)
from services.public_ppt_generation_service import create_generation, validate_request


def _payload() -> dict:
    return {
        "title": "Public API security test",
        "outline": [
            {
                "title": "Security boundary",
                "points": ["Tenant isolation", "Idempotency"],
                "part": "Security",
            }
        ],
        "visual": {"style": "clean security report", "aspect_ratio": "16:9"},
        "options": {"language": "en", "detail_level": "default"},
    }


def _api_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def public_api_security_case(client, app):
    with app.app_context():
        owner = User(username="public-owner", email="public-owner@example.test")
        owner.set_password("public-owner-password")
        intruder = User(username="public-intruder", email="public-intruder@example.test")
        intruder.set_password("public-intruder-password")
        db.session.add_all([owner, intruder])
        db.session.flush()

        owner_key, owner_token = ApiKey.issue(
            user_id=owner.id,
            name="owner-key",
            scopes=["ppt:generate"],
        )
        intruder_key, intruder_token = ApiKey.issue(
            user_id=intruder.id,
            name="intruder-key",
            scopes=["ppt:generate"],
        )
        revoked_key, revoked_token = ApiKey.issue(
            user_id=intruder.id,
            name="revoked-key",
            scopes=["ppt:generate"],
        )
        revoked_key.revoke()
        expired_key, expired_token = ApiKey.issue(
            user_id=intruder.id,
            name="expired-key",
            scopes=["ppt:generate"],
            expires_at=datetime.utcnow() - timedelta(seconds=1),
        )
        wrong_scope_key, wrong_scope_token = ApiKey.issue(
            user_id=intruder.id,
            name="wrong-scope-key",
            scopes=["templates:read"],
        )
        db.session.add_all(
            [owner_key, intruder_key, revoked_key, expired_key, wrong_scope_key]
        )
        db.session.flush()

        project = Project(
            user_id=owner.id,
            project_title="Owner public generation",
            creation_type="outline",
            outline_text="Owner outline",
            status="COMPLETED",
        )
        db.session.add(project)
        db.session.flush()

        page = Page(
            project_id=project.id,
            order_index=0,
            generated_image_path=f"{project.id}/pages/owner.png",
            status="COMPLETED",
        )
        page.set_outline_content({"title": "Owner-only title", "points": ["Owner-only point"]})
        page.set_description_content({"text": "Owner-only description"})
        db.session.add(page)

        description_task = Task(
            user_id=owner.id,
            project_id=project.id,
            task_type="PUBLIC_GENERATE_DESCRIPTIONS",
            status="COMPLETED",
        )
        description_task.set_progress({"total": 1, "completed": 1, "failed": 0})
        image_task = Task(
            user_id=owner.id,
            project_id=project.id,
            task_type="PUBLIC_GENERATE_IMAGES",
            status="COMPLETED",
        )
        image_task.set_progress({"total": 1, "completed": 1, "failed": 0})
        db.session.add_all([description_task, image_task])
        db.session.flush()

        generation = PublicPptGeneration(
            user_id=owner.id,
            api_key_id=owner_key.id,
            project_id=project.id,
            description_task_id=description_task.id,
            image_task_id=image_task.id,
            idempotency_key="existing-race-key",
            status="COMPLETED",
            current_stage="completed",
            request_json="{}",
        )
        generation.set_request_data(validate_request(_payload()))
        db.session.add(generation)

        owner_template = UserTemplate(
            user_id=owner.id,
            name="Owner-only template",
            file_path="user-templates/owner/template.png",
        )
        intruder_template = UserTemplate(
            user_id=intruder.id,
            name="Intruder template",
            file_path="user-templates/intruder/template.png",
        )
        db.session.add_all([owner_template, intruder_template])
        db.session.commit()

        case = SimpleNamespace(
            owner_id=owner.id,
            intruder_id=intruder.id,
            owner_key_id=owner_key.id,
            owner_token=owner_token,
            intruder_token=intruder_token,
            revoked_token=revoked_token,
            expired_token=expired_token,
            wrong_scope_token=wrong_scope_token,
            project_id=project.id,
            page_id=page.id,
            generation_id=generation.id,
            owner_template_id=owner_template.id,
            intruder_template_id=intruder_template.id,
        )

    image_path = (
        Path(app.config["UPLOAD_FOLDER"])
        / case.project_id
        / "pages"
        / "owner.png"
    )
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"owner-only-public-image")
    case.image_path = image_path
    return case


@pytest.mark.parametrize(
    "url_factory",
    [
        lambda case: f"/v1/ppt-generations/{case.generation_id}",
        lambda case: f"/v1/ppt-generations/{case.generation_id}/pages",
        lambda case: (
            f"/v1/ppt-generations/{case.generation_id}"
            f"/pages/{case.page_id}/image"
        ),
    ],
    ids=["generation", "pages", "image"],
)
def test_other_user_api_key_cannot_read_generation_resources(
    client,
    public_api_security_case,
    url_factory,
):
    response = client.get(
        url_factory(public_api_security_case),
        headers=_api_headers(public_api_security_case.intruder_token),
    )

    assert response.status_code == 404, response.get_json()
    assert b"Owner-only" not in response.data
    assert b"owner-only-public-image" not in response.data


def test_public_template_listing_is_tenant_scoped(client, public_api_security_case):
    response = client.get(
        "/v1/templates",
        headers=_api_headers(public_api_security_case.intruder_token),
    )

    assert response.status_code == 200, response.get_json()
    template_ids = {
        item["template_id"] for item in response.get_json()["data"]["templates"]
    }
    assert public_api_security_case.intruder_template_id in template_ids
    assert public_api_security_case.owner_template_id not in template_ids


@pytest.mark.parametrize(
    ("token_attribute", "expected_status", "expected_code"),
    [
        ("revoked_token", 401, "INVALID_API_KEY"),
        ("expired_token", 401, "INVALID_API_KEY"),
        ("wrong_scope_token", 403, "INSUFFICIENT_SCOPE"),
    ],
)
def test_public_api_rejects_unusable_or_under_scoped_keys(
    client,
    public_api_security_case,
    token_attribute,
    expected_status,
    expected_code,
):
    token = getattr(public_api_security_case, token_attribute)
    response = client.get("/v1/templates", headers=_api_headers(token))

    assert response.status_code == expected_status, response.get_json()
    assert response.get_json()["error"]["code"] == expected_code


def test_idempotency_unique_race_loser_returns_existing_generation(
    app,
    public_api_security_case,
    monkeypatch,
):
    """Deterministically emulate a concurrent insert becoming visible at commit.

    The first lookup is forced to miss. The database unique constraint then makes
    this transaction lose the insert race; the recovery lookup must return the
    already-committed generation without leaving duplicate projects or tasks.
    """
    monkeypatch.setenv("CREDIT_ENABLED", "false")

    with app.app_context():
        query_class = type(PublicPptGeneration.query)
        original_filter_by = query_class.filter_by
        first_lookup_hidden = False

        class _NoResult:
            @staticmethod
            def first():
                return None

        def racing_filter_by(query, **kwargs):
            nonlocal first_lookup_hidden
            entity = query.column_descriptions[0].get("entity")
            is_idempotency_lookup = (
                entity is PublicPptGeneration
                and kwargs
                == {
                    "user_id": public_api_security_case.owner_id,
                    "idempotency_key": "existing-race-key",
                }
            )
            if is_idempotency_lookup and not first_lookup_hidden:
                first_lookup_hidden = True
                return _NoResult()
            return original_filter_by(query, **kwargs)

        before = {
            "generations": PublicPptGeneration.query.count(),
            "projects": Project.query.count(),
            "tasks": Task.query.count(),
            "pages": Page.query.count(),
        }
        monkeypatch.setattr(query_class, "filter_by", racing_filter_by)

        generation, created = create_generation(
            user_id=public_api_security_case.owner_id,
            api_key_id=public_api_security_case.owner_key_id,
            data=_payload(),
            idempotency_key="existing-race-key",
        )

        after = {
            "generations": PublicPptGeneration.query.count(),
            "projects": Project.query.count(),
            "tasks": Task.query.count(),
            "pages": Page.query.count(),
        }
        assert first_lookup_hidden
        assert created is False
        assert generation.id == public_api_security_case.generation_id
        assert after == before

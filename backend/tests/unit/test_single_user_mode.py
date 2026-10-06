"""Temporary single-user maintenance boundary regression tests."""

from pathlib import Path

import pytest

from models import ApiKey, Project, Settings, User, db
from utils.auth import create_auth_token


MAINTENANCE_CODE = "SERVICE_MAINTENANCE"


def test_load_dotenv_false_skips_project_environment(monkeypatch, tmp_path):
    import app as app_module

    calls = []
    monkeypatch.setenv("LOAD_DOTENV", "false")
    monkeypatch.setattr(app_module, "load_dotenv", lambda **kwargs: calls.append(kwargs))

    app_module._load_project_dotenv(tmp_path / ".env")

    assert calls == []


def test_dotenv_defaults_never_override_explicit_environment(monkeypatch, tmp_path):
    import app as app_module

    calls = []
    monkeypatch.setenv("LOAD_DOTENV", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////explicit.db")
    monkeypatch.setattr(app_module, "load_dotenv", lambda **kwargs: calls.append(kwargs))

    app_module._load_project_dotenv(tmp_path / ".env")

    assert calls == [{"dotenv_path": tmp_path / ".env", "override": False}]
    assert app_module.os.environ["DATABASE_URL"] == "sqlite:////explicit.db"


def _assert_maintenance(response):
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == MAINTENANCE_CODE


def _set_web_cookies(client, token: str, csrf_token: str = "test-csrf-token"):
    client.set_cookie("banana_auth_token", token)
    client.set_cookie("banana_csrf_token", csrf_token)


@pytest.fixture
def single_user_case(client, app):
    with app.app_context():
        allowed = User(username="maintenance-allowed")
        allowed.set_password("allowed-password")
        blocked = User(username="maintenance-blocked")
        blocked.set_password("blocked-password")
        db.session.add_all([allowed, blocked])
        db.session.flush()

        db.session.add_all([
            Settings(user_id=allowed.id),
            Settings(user_id=blocked.id),
        ])
        allowed_project = Project(
            user_id=allowed.id,
            project_title="Allowed project",
            creation_type="idea",
            status="DRAFT",
        )
        blocked_project = Project(
            user_id=blocked.id,
            project_title="Blocked project",
            creation_type="idea",
            status="DRAFT",
        )
        db.session.add_all([allowed_project, blocked_project])
        db.session.flush()

        allowed_key, allowed_api_token = ApiKey.issue(
            user_id=allowed.id,
            name="allowed-api-key",
            scopes=["ppt:generate"],
        )
        blocked_key, blocked_api_token = ApiKey.issue(
            user_id=blocked.id,
            name="blocked-api-key",
            scopes=["ppt:generate"],
        )
        db.session.add_all([allowed_key, blocked_key])
        db.session.commit()

        allowed_id = allowed.id
        blocked_id = blocked.id
        allowed_project_id = allowed_project.id
        blocked_project_id = blocked_project.id
        allowed_key_id = allowed_key.id
        blocked_key_id = blocked_key.id
        allowed_cookie = create_auth_token(allowed)
        blocked_cookie = create_auth_token(blocked)

        for project_id, content in (
            (allowed_project_id, b"allowed file"),
            (blocked_project_id, b"blocked file"),
        ):
            pages_dir = Path(app.config["UPLOAD_FOLDER"]) / project_id / "pages"
            pages_dir.mkdir(parents=True, exist_ok=True)
            (pages_dir / "slide.txt").write_bytes(content)

    return {
        "allowed_id": allowed_id,
        "blocked_id": blocked_id,
        "allowed_project_id": allowed_project_id,
        "blocked_project_id": blocked_project_id,
        "allowed_cookie": allowed_cookie,
        "blocked_cookie": blocked_cookie,
        "allowed_api_token": allowed_api_token,
        "blocked_api_token": blocked_api_token,
        "allowed_key_id": allowed_key_id,
        "blocked_key_id": blocked_key_id,
    }


def test_registration_is_disabled_without_changing_existing_users(
    client, app, single_user_case, monkeypatch
):
    monkeypatch.setenv("SINGLE_USER_MODE_USER_ID", single_user_case["allowed_id"])
    with app.app_context():
        before = {user.id: user.is_active for user in User.query.all()}

    response = client.post(
        "/api/auth/register",
        json={"username": "new-user", "password": "new-password"},
    )

    _assert_maintenance(response)
    with app.app_context():
        assert {user.id: user.is_active for user in User.query.all()} == before
        assert User.query.filter_by(username="new-user").first() is None


@pytest.mark.parametrize(
    ("account", "password", "expected_status"),
    [
        ("allowed", "allowed-password", 200),
        ("blocked", "blocked-password", 503),
    ],
)
def test_login_only_issues_cookie_for_designated_user(
    client, app, single_user_case, monkeypatch, account, password, expected_status
):
    monkeypatch.setenv("SINGLE_USER_MODE_USER_ID", single_user_case["allowed_id"])
    response = client.post(
        "/api/auth/login",
        json={"username": f"maintenance-{account}", "password": password},
    )

    assert response.status_code == expected_status
    if expected_status == 200:
        assert client.get_cookie("banana_auth_token") is not None
    else:
        _assert_maintenance(response)
        assert client.get_cookie("banana_auth_token") is None

    with app.app_context():
        blocked = db.session.get(User, single_user_case["blocked_id"])
        assert blocked is not None and blocked.is_active is True


@pytest.mark.parametrize(
    ("principal", "expected_status"),
    [("allowed", 200), ("blocked", 503)],
)
def test_cookie_authenticated_web_api_obeys_single_user_boundary(
    client, single_user_case, monkeypatch, principal, expected_status
):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("SINGLE_USER_MODE_USER_ID", single_user_case["allowed_id"])
    _set_web_cookies(client, single_user_case[f"{principal}_cookie"])

    response = client.get("/api/projects")

    assert response.status_code == expected_status
    if expected_status == 503:
        _assert_maintenance(response)


def test_allowed_cookie_still_requires_csrf_and_blocked_write_never_mutates(
    client, app, single_user_case, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("SINGLE_USER_MODE_USER_ID", single_user_case["allowed_id"])
    _set_web_cookies(client, single_user_case["allowed_cookie"])

    missing_csrf = client.post(
        "/api/projects",
        json={"creation_type": "idea", "idea_prompt": "missing csrf"},
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.get_json()["error"]["code"] == "CSRF_FAILED"

    accepted = client.post(
        "/api/projects",
        json={"creation_type": "idea", "idea_prompt": "accepted"},
        headers={"X-CSRF-Token": "test-csrf-token"},
    )
    assert accepted.status_code == 201

    _set_web_cookies(client, single_user_case["blocked_cookie"])
    with app.app_context():
        count_before = Project.query.count()
    rejected = client.post(
        "/api/projects",
        json={"creation_type": "idea", "idea_prompt": "must not persist"},
        headers={"X-CSRF-Token": "test-csrf-token"},
    )
    _assert_maintenance(rejected)
    with app.app_context():
        assert Project.query.count() == count_before


@pytest.mark.parametrize(
    ("principal", "project_owner", "expected_status", "expected_body"),
    [
        ("allowed", "allowed", 200, b"allowed file"),
        ("blocked", "blocked", 503, None),
        ("blocked", "allowed", 503, None),
    ],
)
def test_file_access_requires_designated_user_even_for_owned_files(
    client,
    single_user_case,
    monkeypatch,
    principal,
    project_owner,
    expected_status,
    expected_body,
):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("SINGLE_USER_MODE_USER_ID", single_user_case["allowed_id"])
    _set_web_cookies(client, single_user_case[f"{principal}_cookie"])
    project_id = single_user_case[f"{project_owner}_project_id"]

    response = client.get(f"/files/{project_id}/pages/slide.txt")

    assert response.status_code == expected_status
    if expected_body is not None:
        assert response.data == expected_body
    else:
        _assert_maintenance(response)


@pytest.mark.parametrize(
    ("principal", "expected_status"),
    [("allowed", 200), ("blocked", 503)],
)
def test_public_api_key_owner_must_match_designated_user(
    client, app, single_user_case, monkeypatch, principal, expected_status
):
    monkeypatch.setenv("SINGLE_USER_MODE_USER_ID", single_user_case["allowed_id"])
    response = client.get(
        "/v1/templates",
        headers={"Authorization": f"Bearer {single_user_case[f'{principal}_api_token']}"},
    )

    assert response.status_code == expected_status
    if expected_status == 503:
        _assert_maintenance(response)
        with app.app_context():
            key = db.session.get(ApiKey, single_user_case["blocked_key_id"])
            assert key.last_used_at is None


def test_mode_disabled_preserves_existing_multi_user_authentication(
    client, single_user_case, monkeypatch
):
    monkeypatch.delenv("SINGLE_USER_MODE_USER_ID", raising=False)
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    _set_web_cookies(client, single_user_case["blocked_cookie"])

    assert client.get("/api/projects").status_code == 200


def test_single_user_mode_fails_closed_when_legacy_auth_is_disabled(
    client, app, single_user_case, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("SINGLE_USER_MODE_USER_ID", single_user_case["allowed_id"])

    response = client.get("/api/projects")

    _assert_maintenance(response)
    with app.app_context():
        assert User.query.filter_by(username="admin").first() is None

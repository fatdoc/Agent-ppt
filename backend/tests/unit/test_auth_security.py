from app import _validate_security_configuration


def test_login_uses_http_only_cookie_without_returning_token(client, monkeypatch):
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    response = client.post('/api/auth/register', json={
        'username': 'cookie-user',
        'password': 'safe-password',
    })

    assert response.status_code == 201
    assert 'token' not in response.get_json()['data']
    cookies = response.headers.getlist('Set-Cookie')
    auth_cookie = next(value for value in cookies if value.startswith('banana_auth_token='))
    csrf_cookie = next(value for value in cookies if value.startswith('banana_csrf_token='))
    assert 'HttpOnly' in auth_cookie
    assert 'SameSite=Lax' in auth_cookie
    assert 'HttpOnly' not in csrf_cookie


def test_cookie_authenticated_writes_require_matching_csrf(client, monkeypatch):
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    registered = client.post('/api/auth/register', json={
        'username': 'csrf-user',
        'password': 'safe-password',
    })
    assert registered.status_code == 201

    rejected = client.post('/api/projects', json={
        'creation_type': 'idea',
        'idea_prompt': 'blocked without csrf',
    })
    assert rejected.status_code == 403
    assert rejected.get_json()['error']['code'] == 'CSRF_FAILED'

    csrf_cookie = client.get_cookie('banana_csrf_token')
    accepted = client.post(
        '/api/projects',
        json={'creation_type': 'idea', 'idea_prompt': 'allowed with csrf'},
        headers={'X-CSRF-Token': csrf_cookie.value},
    )
    assert accepted.status_code == 201


def test_logout_revokes_previously_issued_token(client, app, monkeypatch):
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    registered = client.post('/api/auth/register', json={
        'username': 'logout-user',
        'password': 'safe-password',
    })
    assert registered.status_code == 201
    old_auth_cookie = client.get_cookie('banana_auth_token').value
    csrf_cookie = client.get_cookie('banana_csrf_token').value

    logged_out = client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf_cookie})
    assert logged_out.status_code == 200

    rejected = client.get('/api/auth/me', headers={'Authorization': f'Bearer {old_auth_cookie}'})
    assert rejected.status_code == 401


def test_production_rejects_default_or_short_secret(monkeypatch):
    class FakeApp:
        config = {'SECRET_KEY': 'your-secret-key-change-this'}

    monkeypatch.setenv('FLASK_ENV', 'production')
    try:
        _validate_security_configuration(FakeApp())
    except RuntimeError as exc:
        assert 'SECRET_KEY' in str(exc)
    else:
        raise AssertionError('Expected insecure production secret to be rejected')


def test_legacy_default_admin_is_blocked_until_password_reset(client, app, monkeypatch):
    from models import User, db

    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    with app.app_context():
        user = User(username='legacy-admin', password_reset_required=True)
        user.set_password('known-legacy-password')
        db.session.add(user)
        db.session.commit()

    response = client.post('/api/auth/login', json={
        'username': 'legacy-admin',
        'password': 'known-legacy-password',
    })
    assert response.status_code == 403
    assert response.get_json()['error']['code'] == 'PASSWORD_RESET_REQUIRED'

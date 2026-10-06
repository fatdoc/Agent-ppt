"""
自助大模型配置锁定（AI_CONFIG_SELF_SERVICE）行为测试。

关闭自助配置时：
- 普通用户：GET /api/settings 返回 ai_config_editable=False，PUT 拒绝大模型字段
- 管理员：可修改自己的模型配置，也可通过 admin API 管理其他用户
"""

import pytest

from models import Settings, User, db
from utils.auth import create_auth_token


@pytest.fixture
def auth_required(monkeypatch):
    """启用登录鉴权，避免测试环境自动使用默认 admin 账号。"""
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    yield


@pytest.fixture
def locked_env(monkeypatch, auth_required):
    monkeypatch.setenv('AI_CONFIG_SELF_SERVICE', 'false')
    yield


@pytest.fixture
def unlocked_env(monkeypatch, auth_required):
    monkeypatch.setenv('AI_CONFIG_SELF_SERVICE', 'true')
    yield


def _register_user(client, username='testuser', password='password123'):
    return client.post('/api/auth/register', json={
        'username': username,
        'password': password,
    })


def _auth_headers(app, user_id: str):
    with app.app_context():
        user = User.query.filter_by(id=user_id).first()
        token = create_auth_token(user)
    return {'Authorization': f'Bearer {token}'}


def _create_admin(app, username='admin', password='admin123'):
    with app.app_context():
        user = User(username=username, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        db.session.add(Settings(user_id=user.id))
        db.session.commit()
        return user.id


def _create_regular_user(app, username='regular', password='password123'):
    with app.app_context():
        user = User(username=username, is_admin=False)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        db.session.add(Settings(user_id=user.id))
        db.session.commit()
        return user.id


def test_get_settings_reports_editable_flag_when_locked(client, locked_env, app):
    user_id = _create_regular_user(app)
    response = client.get('/api/settings/', headers=_auth_headers(app, user_id))
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['ai_config_editable'] is False
    assert data['current_user_is_admin'] is False


def test_get_settings_reports_editable_flag_when_unlocked(client, unlocked_env, app):
    user_id = _create_regular_user(app)
    response = client.get('/api/settings/', headers=_auth_headers(app, user_id))
    assert response.status_code == 200
    assert response.get_json()['data']['ai_config_editable'] is True


def test_admin_get_settings_reports_editable_when_locked(client, locked_env, app):
    admin_id = _create_admin(app)
    response = client.get('/api/settings/', headers=_auth_headers(app, admin_id))
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['ai_config_editable'] is True
    assert data['current_user_is_admin'] is True


def test_update_settings_rejects_ai_fields_when_locked(client, locked_env, app):
    user_id = _create_regular_user(app)
    response = client.put(
        '/api/settings/',
        json={'api_key': 'user-supplied-key'},
        headers=_auth_headers(app, user_id),
    )
    assert response.status_code == 403
    data = response.get_json()
    assert data['error']['code'] == 'AI_CONFIG_LOCKED'


def test_update_settings_rejects_model_fields_when_locked(client, locked_env, app):
    user_id = _create_regular_user(app)
    response = client.put(
        '/api/settings/',
        json={'text_model': 'my-model', 'ai_provider_format': 'openai'},
        headers=_auth_headers(app, user_id),
    )
    assert response.status_code == 403


def test_update_settings_allows_non_ai_fields_when_locked(client, locked_env, app):
    user_id = _create_regular_user(app)
    response = client.put(
        '/api/settings/',
        json={'output_language': 'en'},
        headers=_auth_headers(app, user_id),
    )
    assert response.status_code == 200
    assert response.get_json()['data']['output_language'] == 'en'
    client.put(
        '/api/settings/',
        json={'output_language': 'zh'},
        headers=_auth_headers(app, user_id),
    )


def test_update_settings_accepts_ai_fields_when_unlocked(client, unlocked_env, app):
    user_id = _create_regular_user(app)
    response = client.put(
        '/api/settings/',
        json={'text_model': 'test-model-x'},
        headers=_auth_headers(app, user_id),
    )
    assert response.status_code == 200
    assert response.get_json()['data']['text_model'] == 'test-model-x'
    client.put(
        '/api/settings/',
        json={'text_model': ''},
        headers=_auth_headers(app, user_id),
    )


def test_admin_can_update_ai_fields_when_locked(client, locked_env, app):
    admin_id = _create_admin(app)
    response = client.put(
        '/api/settings/',
        json={'text_model': 'admin-self-model'},
        headers=_auth_headers(app, admin_id),
    )
    assert response.status_code == 200
    assert response.get_json()['data']['text_model'] == 'admin-self-model'


def test_reset_preserves_ai_config_when_locked(client, unlocked_env, app, monkeypatch):
    admin_id = _create_admin(app)
    headers = _auth_headers(app, admin_id)

    response = client.put(
        '/api/settings/',
        json={'text_model': 'admin-managed-model', 'api_key': 'admin-managed-key'},
        headers=headers,
    )
    assert response.status_code == 200

    monkeypatch.setenv('AI_CONFIG_SELF_SERVICE', 'false')
    response = client.post('/api/settings/reset', headers=headers)
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['text_model'] == 'admin-managed-model'
    assert data['api_key_length'] == len('admin-managed-key')

    monkeypatch.setenv('AI_CONFIG_SELF_SERVICE', 'true')
    response = client.post('/api/settings/reset', headers=headers)
    assert response.status_code == 200
    assert response.get_json()['data']['text_model'] != 'admin-managed-model'


def test_oauth_authorize_blocked_when_locked(client, locked_env, app):
    user_id = _create_regular_user(app)
    response = client.get('/api/settings/openai-oauth/authorize', headers=_auth_headers(app, user_id))
    assert response.status_code == 403
    assert response.get_json()['error']['code'] == 'AI_CONFIG_LOCKED'


def test_oauth_disconnect_blocked_when_locked(client, locked_env, app):
    user_id = _create_regular_user(app)
    response = client.post('/api/settings/openai-oauth/disconnect', headers=_auth_headers(app, user_id))
    assert response.status_code == 403


def test_admin_oauth_allowed_when_locked(client, locked_env, app):
    admin_id = _create_admin(app)
    response = client.get('/api/settings/openai-oauth/authorize', headers=_auth_headers(app, admin_id))
    # authorize may fail for missing OAuth config, but must not be AI_CONFIG_LOCKED
    if response.status_code == 403:
        assert response.get_json()['error']['code'] != 'AI_CONFIG_LOCKED'


def test_admin_can_list_users(client, locked_env, app):
    admin_id = _create_admin(app)
    _create_regular_user(app, username='alice')
    response = client.get('/api/settings/admin/users', headers=_auth_headers(app, admin_id))
    assert response.status_code == 200
    usernames = {user['username'] for user in response.get_json()['data']['users']}
    assert {'admin', 'alice'} <= usernames


def test_non_admin_cannot_list_users(client, locked_env, app):
    user_id = _create_regular_user(app)
    response = client.get('/api/settings/admin/users', headers=_auth_headers(app, user_id))
    assert response.status_code == 403
    assert response.get_json()['error']['code'] == 'ADMIN_REQUIRED'


def test_admin_can_update_other_user_ai_config(client, locked_env, app):
    admin_id = _create_admin(app)
    regular_id = _create_regular_user(app, username='bob')
    response = client.put(
        f'/api/settings/admin/users/{regular_id}',
        json={'text_model': 'managed-for-bob'},
        headers=_auth_headers(app, admin_id),
    )
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['text_model'] == 'managed-for-bob'
    assert data['managed_user']['username'] == 'bob'


def test_admin_update_other_user_rejects_non_ai_fields(client, locked_env, app):
    admin_id = _create_admin(app)
    regular_id = _create_regular_user(app, username='carol')
    response = client.put(
        f'/api/settings/admin/users/{regular_id}',
        json={'output_language': 'en'},
        headers=_auth_headers(app, admin_id),
    )
    assert response.status_code == 400


def test_admin_can_reset_other_user_ai_config(client, locked_env, app):
    admin_id = _create_admin(app)
    regular_id = _create_regular_user(app, username='dave')
    headers = _auth_headers(app, admin_id)

    client.put(
        f'/api/settings/admin/users/{regular_id}',
        json={'text_model': 'temp-model'},
        headers=headers,
    )
    response = client.post(
        f'/api/settings/admin/users/{regular_id}/reset-ai-config',
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()['data']['text_model'] != 'temp-model'

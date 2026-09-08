"""Authentication helpers for account-scoped API access."""
import os
import re
import secrets
from functools import wraps
from typing import Optional

from flask import current_app, g, has_request_context, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from models import Page, Project, User, db
from utils.response import error_response, not_found

TOKEN_SALT = 'banana-slides-auth'
DEFAULT_USERNAME = 'admin'
SINGLE_USER_MODE_ERROR_CODE = 'SERVICE_MAINTENANCE'
SINGLE_USER_MODE_ERROR_MESSAGE = 'Service is temporarily limited to the designated account'


def single_user_mode_user_id() -> Optional[str]:
    """Return the only account allowed during a temporary maintenance window."""
    return os.getenv('SINGLE_USER_MODE_USER_ID', '').strip() or None


def single_user_mode_allows(user_or_id) -> bool:
    """Return whether ``user_or_id`` may authenticate in single-user mode.

    An unset environment variable keeps the existing multi-user behavior.  The
    comparison intentionally uses only the immutable user id, never username or
    email aliases.
    """
    allowed_id = single_user_mode_user_id()
    if not allowed_id:
        return True
    user_id = getattr(user_or_id, 'id', user_or_id)
    return bool(user_id) and str(user_id) == allowed_id


def single_user_mode_maintenance_response():
    return error_response(
        SINGLE_USER_MODE_ERROR_CODE,
        SINGLE_USER_MODE_ERROR_MESSAGE,
        503,
    )


def auth_required_enabled() -> bool:
    """Return whether API login is required for this environment."""
    raw = os.getenv('AUTH_REQUIRED')
    if raw is not None:
        return raw.strip().lower() in {'1', 'true', 'yes', 'on'}
    if current_app.config.get('TESTING'):
        return False
    return True


def ai_config_self_service_enabled() -> bool:
    """Return whether users may edit AI model config (provider/key/model) themselves.

    When disabled, per-user model config lives only in the database and is
    maintained by the operator (e.g. via scripts/set_user_ai_config.py).
    """
    raw = os.getenv('AI_CONFIG_SELF_SERVICE')
    if raw is not None:
        return raw.strip().lower() in {'1', 'true', 'yes', 'on'}
    if current_app.config.get('TESTING'):
        return True
    if os.getenv('TESTING', '').strip().lower() in {'1', 'true', 'yes', 'on'}:
        return True
    return False


def is_admin_user(user=None) -> bool:
    """Return whether the given (or current) user is an administrator."""
    user = user or current_user()
    return bool(user and getattr(user, 'is_admin', False))


def ai_config_editable_for_user(user=None) -> bool:
    """Return whether the user may edit AI model config in the settings UI."""
    return ai_config_self_service_enabled() or is_admin_user(user)


def require_admin_user():
    """Return an error response if the current user is not an admin."""
    user = current_user()
    if not user:
        return error_response('AUTH_REQUIRED', 'Login required', 401)
    if not is_admin_user(user):
        return error_response('ADMIN_REQUIRED', 'Administrator access required', 403)
    return None


def token_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=TOKEN_SALT)


def create_auth_token(user: User) -> str:
    return token_serializer().dumps({
        'user_id': user.id,
        'auth_version': int(user.auth_version or 0),
    })


def load_user_from_token(token: str) -> Optional[User]:
    if not token:
        return None
    max_age = int(os.getenv('AUTH_TOKEN_MAX_AGE_SECONDS', str(30 * 24 * 60 * 60)))
    try:
        payload = token_serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    user_id = payload.get('user_id')
    if not user_id:
        return None
    user = User.query.filter_by(id=user_id, is_active=True).first()
    if not user:
        return None
    if int(payload.get('auth_version') or 0) != int(user.auth_version or 0):
        return None
    return user


def _legacy_bearer_enabled() -> bool:
    # Browser sessions are cookie-only. Operators may temporarily opt in to
    # legacy bearer tokens during a controlled rollout, but they are not a
    # secure default because browser JavaScript used to persist them.
    raw = os.getenv('AUTH_ALLOW_LEGACY_BEARER', 'false')
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def get_bearer_token() -> str:
    header = request.headers.get('Authorization', '')
    if _legacy_bearer_enabled() and header.lower().startswith('bearer '):
        return header[7:].strip()
    return ''


def get_or_create_default_user() -> User:
    user = User.query.filter_by(username=DEFAULT_USERNAME).first()
    if user:
        if (
            not current_app.config.get('TESTING')
            and user.check_password('admin123')
        ):
            raise RuntimeError(
                'The legacy admin/admin123 credential must be rotated before authentication is disabled'
            )
        if not user.is_admin:
            user.is_admin = True
        return user
    password = os.getenv('DEFAULT_USER_PASSWORD')
    if not password:
        if current_app.config.get('TESTING') or os.getenv('TESTING', '').lower() == 'true':
            password = secrets.token_urlsafe(32)
        else:
            raise RuntimeError(
                'DEFAULT_USER_PASSWORD is required when authentication is disabled'
            )
    user = User(username=DEFAULT_USERNAME, email=None, is_admin=True)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def current_user() -> Optional[User]:
    if not has_request_context():
        return None
    return getattr(g, 'current_user', None)


def current_user_id() -> Optional[str]:
    user = current_user()
    return user.id if user else None


def authenticate_request():
    """Populate g.current_user or return an auth error response."""
    bearer_token = get_bearer_token()
    cookie_token = request.cookies.get('banana_auth_token', '')
    token = bearer_token or cookie_token
    user = load_user_from_token(token) if token else None

    if user:
        if not single_user_mode_allows(user):
            g.current_user = None
            g.auth_transport = None
            return single_user_mode_maintenance_response()
        g.current_user = user
        g.auth_transport = 'bearer' if bearer_token else 'cookie'
        return None

    if not auth_required_enabled():
        # Never map an unauthenticated request to the legacy default account
        # while the operator has explicitly narrowed access to another id.
        if single_user_mode_user_id():
            g.current_user = None
            g.auth_transport = None
            return single_user_mode_maintenance_response()
        user = get_or_create_default_user()
        db.session.commit()
        g.current_user = user
        g.auth_transport = 'disabled'
        return None

    g.current_user = None
    return error_response('AUTH_REQUIRED', 'Login required', 401)


def validate_csrf_request():
    """Require a double-submit token for state changes authenticated by cookie."""
    if request.method in {'GET', 'HEAD', 'OPTIONS', 'TRACE'}:
        return None
    if getattr(g, 'auth_transport', None) != 'cookie':
        return None
    cookie_token = request.cookies.get('banana_csrf_token', '')
    header_token = request.headers.get('X-CSRF-Token', '')
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        return error_response('CSRF_FAILED', 'CSRF token is missing or invalid', 403)
    return None


def owned_project_or_404(project_id: str) -> Optional[Project]:
    user_id = current_user_id()
    if not user_id:
        return None
    return Project.query.filter(
        Project.id == project_id,
        Project.user_id == user_id,
    ).first()


def owned_page_or_404(project_id: str, page_id: str) -> Optional[Page]:
    """Resolve a page only when its complete parent chain belongs to the user."""
    user_id = current_user_id()
    if not user_id:
        return None
    return (
        Page.query
        .join(Project, Page.project_id == Project.id)
        .filter(
            Page.id == page_id,
            Page.project_id == project_id,
            Project.user_id == user_id,
        )
        .first()
    )


def require_owned_project(project_id: str):
    project = owned_project_or_404(project_id)
    if not project:
        return None, not_found('Project')
    return project, None


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return error_response('AUTH_REQUIRED', 'Login required', 401)
        return fn(*args, **kwargs)
    return wrapper


def validate_username(username: str) -> bool:
    return bool(re.fullmatch(r'[A-Za-z0-9_.-]{3,80}', username or ''))

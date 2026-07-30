"""Authentication helpers for account-scoped API access."""
import os
import re
from functools import wraps
from typing import Optional

from flask import current_app, g, has_request_context, request
from sqlalchemy import or_
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from models import Project, User, db
from utils.response import error_response, not_found

TOKEN_SALT = 'banana-slides-auth'
DEFAULT_USERNAME = os.getenv('DEFAULT_USERNAME', 'default')


def auth_required_enabled() -> bool:
    """Account login is disabled in the vocational education build."""
    return False


def token_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=TOKEN_SALT)


def create_auth_token(user: User) -> str:
    return token_serializer().dumps({'user_id': user.id})


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
    return User.query.filter_by(id=user_id, is_active=True).first()


def get_bearer_token() -> str:
    header = request.headers.get('Authorization', '')
    if header.lower().startswith('bearer '):
        return header[7:].strip()
    return request.cookies.get('banana_auth_token', '')


def get_or_create_default_user() -> User:
    user = User.query.filter_by(username=DEFAULT_USERNAME).first()
    if user:
        return user
    user = User(username=DEFAULT_USERNAME, email=None)
    user.set_password(os.getenv('DEFAULT_USER_PASSWORD', 'banana-slides-default'))
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
    if not auth_required_enabled():
        user = get_or_create_default_user()
        db.session.commit()
        g.current_user = user
        return None

    token = get_bearer_token()
    user = load_user_from_token(token) if token else None

    if user:
        g.current_user = user
        return None

    g.current_user = None
    return error_response('AUTH_REQUIRED', 'Login required', 401)


def owned_project_or_404(project_id: str) -> Optional[Project]:
    user_id = current_user_id()
    query = Project.query.filter(Project.id == project_id)
    if user_id:
        # Keep legacy/unowned projects usable after account scoping was introduced.
        query = query.filter(or_(Project.user_id == user_id, Project.user_id.is_(None)))
    return query.first()


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

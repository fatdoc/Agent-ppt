"""Auth Controller - login and registration endpoints."""
import os
import secrets

from flask import Blueprint, request
from sqlalchemy import or_

from models import Settings, User, db
from utils import bad_request, error_response, success_response
from utils.auth import (
    auth_required_enabled,
    create_auth_token,
    current_user,
    single_user_mode_allows,
    single_user_mode_maintenance_response,
    single_user_mode_user_id,
    validate_username,
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def _auth_payload(user: User):
    return {'user': user.to_dict()}


def _with_auth_cookie(response_tuple, token: str):
    response, status = response_tuple
    secure_default = os.getenv('FLASK_ENV', '').strip().lower() == 'production'
    secure_cookie = os.getenv('AUTH_COOKIE_SECURE')
    secure_cookie = (
        secure_default
        if secure_cookie is None
        else secure_cookie.lower() in {'1', 'true', 'yes', 'on'}
    )
    max_age = int(os.getenv('AUTH_TOKEN_MAX_AGE_SECONDS', str(30 * 24 * 60 * 60)))
    response.set_cookie(
        'banana_auth_token',
        token,
        max_age=max_age,
        httponly=True,
        secure=secure_cookie,
        samesite='Lax',
    )
    response.set_cookie(
        'banana_csrf_token',
        secrets.token_urlsafe(32),
        max_age=max_age,
        httponly=False,
        secure=secure_cookie,
        samesite='Lax',
    )
    return response, status


@auth_bp.route('/config', methods=['GET'])
def auth_config():
    return success_response({'enabled': auth_required_enabled()})


@auth_bp.route('/register', methods=['POST'])
def register():
    if single_user_mode_user_id():
        return single_user_mode_maintenance_response()

    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower() or None
    password = data.get('password') or ''

    if not validate_username(username):
        return bad_request('用户名需要 3-80 位，只能包含字母、数字、下划线、点和连字符')
    if len(password) < 6:
        return bad_request('密码至少需要 6 位')
    if email and '@' not in email:
        return bad_request('邮箱格式不正确')

    exists_query = User.query.filter(User.username == username)
    if email:
        exists_query = User.query.filter(or_(User.username == username, User.email == email))
    if exists_query.first():
        return error_response('USER_EXISTS', '用户名或邮箱已存在', 409)

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(Settings(user_id=user.id))
    db.session.commit()

    payload = _auth_payload(user)
    return _with_auth_cookie(success_response(payload, status_code=201), create_auth_token(user))


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    identifier = (data.get('identifier') or data.get('username') or '').strip()
    password = data.get('password') or ''

    if not identifier or not password:
        return bad_request('用户名/邮箱和密码不能为空')

    user = User.query.filter(
        or_(User.username == identifier, User.email == identifier.lower())
    ).first()
    if not user or not user.is_active or not user.check_password(password):
        return error_response('INVALID_CREDENTIALS', '账号或密码错误', 401)
    if not single_user_mode_allows(user):
        return single_user_mode_maintenance_response()
    if user.password_reset_required:
        return error_response(
            'PASSWORD_RESET_REQUIRED',
            '该账号必须由管理员重置密码后才能登录',
            403,
        )

    payload = _auth_payload(user)
    return _with_auth_cookie(success_response(payload), create_auth_token(user))


@auth_bp.route('/me', methods=['GET'])
def me():
    user = current_user()
    if not user:
        return error_response('AUTH_REQUIRED', 'Login required', 401)
    return success_response({'user': user.to_dict()})


@auth_bp.route('/logout', methods=['POST'])
def logout():
    user = current_user()
    if user:
        user.auth_version = int(user.auth_version or 0) + 1
        db.session.commit()
    response, status = success_response(message='Logged out')
    response.delete_cookie('banana_auth_token')
    response.delete_cookie('banana_csrf_token')
    return response, status

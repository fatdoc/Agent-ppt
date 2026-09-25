"""Immutable, in-memory provider configuration and explicit execution scoping.

No credentials are serialized. Flask's compatibility mapping routes provider reads
only; the application defaults are never changed by requests or settings updates.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from types import MappingProxyType
import hashlib
import hmac
import json
import os
import secrets
from flask.config import Config as FlaskConfig

_ACTIVE = ContextVar('banana_provider_snapshot', default=None)
_DIGEST_KEY = secrets.token_bytes(32)

# Keep the compatibility layer restricted to model/runtime configuration.
_PREFIXES = ('GOOGLE_', 'OPENAI_', 'ANTHROPIC_', 'VERTEX_', 'GENAI_', 'TEXT_',
             'IMAGE_', 'CAPTION_', 'MINERU_', 'BAIDU_', 'LAZYLLM_', 'CODEX_')
_NAMES = {'AI_PROVIDER_FORMAT', 'DEFAULT_RESOLUTION', 'DEFAULT_ASPECT_RATIO',
          'MAX_DESCRIPTION_WORKERS', 'MAX_IMAGE_WORKERS', 'OUTPUT_LANGUAGE',
          'ENABLE_TEXT_REASONING', 'ENABLE_IMAGE_REASONING', 'PROVIDER_OAUTH_TOKEN'}
_VENDORS = {'qwen', 'doubao', 'deepseek', 'glm', 'siliconflow', 'sensenova',
            'minimax', 'kimi', 'openai'}


def is_provider_key(key):
    return isinstance(key, str) and (key in _NAMES or key.startswith(_PREFIXES)
                                    or key in {v.upper() + '_API_KEY' for v in _VENDORS})


@dataclass(frozen=True)
class ProviderConfigSnapshot:
    user_id: str | None
    version: str
    values: object = field(repr=False, compare=False)
    app_id: int | None = field(default=None, repr=False)

    def __post_init__(self):
        values = dict(self.values)
        if any(not isinstance(v, (str, int, float, bool, type(None))) for v in values.values()):
            raise TypeError('Provider configuration must contain scalar values')
        object.__setattr__(self, 'values', MappingProxyType(values))

    @property
    def tenant_id(self):
        # Local tenant isolation is ownership by user_id, not a separate tenant table.
        return self.user_id

    @property
    def cache_scope(self):
        payload = json.dumps(dict(self.values), sort_keys=True, separators=(',', ':'))
        digest = hmac.new(_DIGEST_KEY, payload.encode(), hashlib.sha256).hexdigest()
        return (self.app_id, self.tenant_id, self.user_id, self.version, digest)

    def __reduce__(self):
        raise TypeError('Provider snapshots contain secrets and cannot be serialized')


def active_provider_snapshot():
    return _ACTIVE.get()


@contextmanager
def provider_snapshot_scope(snapshot):
    token = _ACTIVE.set(snapshot)
    try:
        yield snapshot
    finally:
        _ACTIVE.reset(token)


class ProviderScopedConfig(FlaskConfig):
    """Read compatibility for existing provider consumers; storage stays global defaults."""
    def __getitem__(self, key):
        snapshot = _ACTIVE.get()
        if snapshot is not None and snapshot.app_id == id(self) and is_provider_key(key):
            return snapshot.values[key]
        return super().__getitem__(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        snapshot = _ACTIVE.get()
        if snapshot is not None and snapshot.app_id == id(self) and is_provider_key(key):
            return key in snapshot.values
        return super().__contains__(key)

    def __setitem__(self, key, value):
        snapshot = _ACTIVE.get()
        if snapshot is not None and snapshot.app_id == id(self) and is_provider_key(key):
            raise RuntimeError('Provider defaults cannot be mutated inside a snapshot scope')
        super().__setitem__(key, value)

    def update(self, *args, **kwargs):
        values = dict(*args, **kwargs)
        for key, value in values.items():
            self[key] = value

    def pop(self, key, *default):
        snapshot = _ACTIVE.get()
        if snapshot is not None and snapshot.app_id == id(self) and is_provider_key(key):
            raise RuntimeError('Provider defaults cannot be mutated inside a snapshot scope')
        return super().pop(key, *default)


_FIELD_MAP = {
    'api_key': ('GOOGLE_API_KEY', 'OPENAI_API_KEY'),
    'api_base_url': ('GOOGLE_API_BASE', 'OPENAI_API_BASE'),
    'image_resolution': ('DEFAULT_RESOLUTION',),
    'image_aspect_ratio': ('DEFAULT_ASPECT_RATIO',),
}
for _name in ('ai_provider_format', 'text_model', 'image_model', 'image_caption_model',
              'max_description_workers', 'max_image_workers', 'mineru_provider',
              'mineru_api_base', 'mineru_token', 'output_language', 'baidu_api_key',
              'enable_text_reasoning', 'text_thinking_budget', 'enable_image_reasoning',
              'image_thinking_budget', 'text_model_source', 'image_model_source',
              'image_caption_model_source', 'openai_image_api_protocol'):
    _FIELD_MAP[_name] = (_name.upper(),)
for _kind in ('text', 'image', 'image_caption'):
    _FIELD_MAP[f'{_kind}_api_key'] = (f'{_kind.upper()}_API_KEY',)
    _FIELD_MAP[f'{_kind}_api_base_url'] = (f'{_kind.upper()}_API_BASE',)


def _overlay(values, fields):
    for name, keys in _FIELD_MAP.items():
        value = fields.get(name)
        if value is not None:
            for key in keys:
                values[key] = value
    raw = fields.get('lazyllm_api_keys')
    if raw:
        try:
            vendors = json.loads(raw) if isinstance(raw, str) else raw
            for vendor, value in vendors.items():
                if vendor.lower() in _VENDORS and isinstance(value, str):
                    values[vendor.upper() + '_API_KEY'] = value
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Invalid provider vendor configuration') from None


def capture_provider_snapshot(*, user_id=None, settings=None, overrides=None):
    from flask import current_app, has_app_context, has_request_context, g
    active = _ACTIVE.get()
    app_id = id(current_app.config) if has_app_context() else None
    if settings is None and user_id is None and active is not None and (not has_app_context() or active.app_id == app_id):
        if not overrides:
            return active
        values = dict(active.values)
        _overlay(values, overrides)
        return ProviderConfigSnapshot(active.user_id, active.version, values, app_id)
    if has_app_context():
        # dict.items bypasses compatibility reads: start from server defaults only.
        values = {k: v for k, v in dict.items(current_app.config) if is_provider_key(k)}
    else:
        from config import Config
        values = {k: getattr(Config, k) for k in dir(Config) if is_provider_key(k)}
    for vendor in _VENDORS:
        key = vendor.upper() + '_API_KEY'
        values.setdefault(key, os.getenv(key, ''))
    if user_id is None and has_request_context():
        user = getattr(g, 'current_user', None)
        user_id = user.id if user else None
    version = 'server-v1'
    managed = os.getenv('SERVER_MANAGED_AI_CONFIG', '').lower() in {'1', 'true', 'yes', 'on'}
    if settings is None and user_id and has_app_context() and not managed:
        from models import Settings
        # Capture is read-only; a missing row means this user's server defaults.
        settings = Settings.query.filter_by(user_id=user_id).first()
    if settings is not None and not managed:
        if user_id is not None and settings.user_id != user_id:
            raise ValueError('Provider settings owner mismatch')
        user_id = settings.user_id
        fields = {name: getattr(settings, name, None) for name in _FIELD_MAP}
        fields['lazyllm_api_keys'] = settings.lazyllm_api_keys
        _overlay(values, fields)
        version = str(settings.updated_at or settings.id or 'unsaved')
    # OAuth identity remains account-scoped even for server-managed model routes.
    # Resolve/refresh at capture time, never halfway through a background job.
    if 'codex' in {values.get(k) for k in ('AI_PROVIDER_FORMAT', 'TEXT_MODEL_SOURCE',
                                          'IMAGE_MODEL_SOURCE', 'IMAGE_CAPTION_MODEL_SOURCE')}:
        if settings is None and user_id and has_app_context():
            from models import Settings
            settings = Settings.query.filter_by(user_id=user_id).first()
        values['PROVIDER_OAUTH_TOKEN'] = settings.get_openai_oauth_token() if settings else None
    if overrides:
        _overlay(values, overrides)
    return ProviderConfigSnapshot(user_id, version, values, app_id)


class ContextThreadPoolExecutor(ThreadPoolExecutor):
    """Propagate only immutable provider state, never Flask request/session objects."""
    def submit(self, fn, /, *args, **kwargs):
        snapshot = _ACTIVE.get()
        from services.task_execution import current_task_execution, task_execution_scope
        control = current_task_execution()
        def run():
            with provider_snapshot_scope(snapshot), task_execution_scope(control):
                return fn(*args, **kwargs)
        return super().submit(run)


def redact_provider_text(value):
    """Remove active credentials from diagnostics (including remote error echoes)."""
    snapshot = _ACTIVE.get()
    if snapshot is None or not isinstance(value, str):
        return value
    secrets_to_hide = {v for k, v in snapshot.values.items()
                       if ('KEY' in k or 'TOKEN' in k or 'SECRET' in k)
                       and isinstance(v, str) and v}
    for secret in sorted(secrets_to_hide, key=len, reverse=True):
        value = value.replace(secret, '[REDACTED]')
    return value


def install_provider_log_redaction():
    import logging
    import traceback
    class ProviderSecretFilter(logging.Filter):
        def filter(self, record):
            if _ACTIVE.get() is not None:
                record.msg = redact_provider_text(record.getMessage())
                record.args = ()
                if record.exc_info:
                    record.exc_text = redact_provider_text(''.join(traceback.format_exception(*record.exc_info)))
                    record.exc_info = None
            return True
    for handler in logging.getLogger().handlers:
        if not getattr(handler, '_provider_redaction', False):
            handler.addFilter(ProviderSecretFilter())
            handler._provider_redaction = True


def redact_provider_data(value):
    if isinstance(value, dict):
        return {k: redact_provider_data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_provider_data(v) for v in value]
    return redact_provider_text(value)

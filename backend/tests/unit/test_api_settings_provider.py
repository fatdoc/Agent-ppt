"""
Settings controller tests for provider format handling.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask

from controllers.settings_controller import update_settings, verify_api_key


def _build_settings(**overrides):
    defaults = {
        'ai_provider_format': 'gemini',
        'api_key': None,
        'api_base_url': None,
        'text_model': None,
    }
    defaults.update(overrides)

    settings = SimpleNamespace(**defaults)
    settings.to_dict = lambda: {
        'ai_provider_format': settings.ai_provider_format,
        'api_key_length': len(settings.api_key) if settings.api_key else 0,
    }
    return settings


def test_update_settings_accepts_lazyllm_provider():
    """`lazyllm` should be accepted as a valid provider format."""
    app = Flask(__name__)

    settings = _build_settings()
    with app.app_context():
        with app.test_request_context('/api/settings/', method='PUT', json={'ai_provider_format': 'lazyllm'}):
            with patch('controllers.settings_controller.Settings.get_settings', return_value=settings):
                with patch('controllers.settings_controller.db.session.commit'):
                    with patch('controllers.settings_controller._sync_settings_to_config'):
                        response, status_code = update_settings()

    assert status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['data']['ai_provider_format'] == 'lazyllm'


def test_verify_uses_configured_text_model():
    """Verify endpoint should use configured text model, not a hardcoded gemini model."""
    app = Flask(__name__)
    app.config.update(
        TEXT_MODEL='gemini-3-flash-preview',
        AI_PROVIDER_FORMAT='lazyllm',
    )

    settings = _build_settings(ai_provider_format='lazyllm', text_model='deepseek-chat')
    mock_provider = MagicMock()
    mock_provider.generate_text.return_value = 'OK'

    with app.app_context():
        with app.test_request_context('/api/settings/verify', method='POST'):
            with patch('controllers.settings_controller.Settings.get_settings', return_value=settings):
                with patch('services.ai_providers.get_text_provider', return_value=mock_provider) as mock_get_provider:
                    response, status_code = verify_api_key()

    assert status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['data']['available'] is True
    mock_get_provider.assert_called_once_with(model='deepseek-chat')
    mock_provider.generate_text.assert_called_once()


def test_vendor_source_with_explicit_gateway_uses_timeout_capable_openai_provider():
    """A custom /v1 gateway must not be discarded when source is qwen."""
    from services.ai_providers import _get_model_type_provider_config

    app = Flask(__name__)
    app.config.update(
        TEXT_MODEL_SOURCE='qwen',
        TEXT_API_KEY='test-key',
        TEXT_API_BASE='https://gateway.example/v1',
    )

    with app.app_context():
        provider_config = _get_model_type_provider_config('text')

    assert provider_config == {
        'format': 'openai',
        'api_key': 'test-key',
        'api_base': 'https://gateway.example/v1',
    }


def test_vendor_source_without_explicit_gateway_keeps_lazyllm_provider():
    from services.ai_providers import _get_model_type_provider_config

    app = Flask(__name__)
    app.config.update(TEXT_MODEL_SOURCE='qwen')

    with app.app_context():
        provider_config = _get_model_type_provider_config('text')

    assert provider_config == {'format': 'lazyllm', 'source': 'qwen'}

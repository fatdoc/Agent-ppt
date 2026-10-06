"""Owner-scoped provider caching and fresh request/task AIService instances."""
import logging
from threading import Lock
from .ai_service import AIService
from .ai_providers import get_text_provider, get_image_provider, get_caption_provider, TextProvider, ImageProvider

logger = logging.getLogger(__name__)


# Provider cache to avoid re-initialization when models don't change
_text_provider_cache: dict = {}
_image_provider_cache: dict = {}
_caption_provider_cache: dict = {}
_cache_lock = Lock()


def _config_fingerprint(kind: str, model: str) -> tuple:
    from .provider_config import capture_provider_snapshot
    snapshot = capture_provider_snapshot()
    return (model, kind, *snapshot.cache_scope)


def _get_cached_text_provider(model: str) -> TextProvider:
    """
    Get or create a cached text provider instance
    
    Args:
        model: Model name to use
        
    Returns:
        Cached or new TextProvider instance
    """
    cache_key = _config_fingerprint("text", model)
    with _cache_lock:
        if cache_key not in _text_provider_cache:
            if len(_text_provider_cache) >= 128:
                _text_provider_cache.pop(next(iter(_text_provider_cache)))
            logger.info(f"Creating new TextProvider for model: {model}")
            _text_provider_cache[cache_key] = get_text_provider(model=model)
        else:
            logger.debug(f"Reusing cached TextProvider for model: {model}")
        return _text_provider_cache[cache_key]


def _get_cached_image_provider(model: str) -> ImageProvider:
    """
    Get or create a cached image provider instance
    
    Args:
        model: Model name to use
        
    Returns:
        Cached or new ImageProvider instance
    """
    cache_key = _config_fingerprint("image", model)
    with _cache_lock:
        if cache_key not in _image_provider_cache:
            if len(_image_provider_cache) >= 128:
                _image_provider_cache.pop(next(iter(_image_provider_cache)))
            logger.info(f"Creating new ImageProvider for model: {model}")
            _image_provider_cache[cache_key] = get_image_provider(model=model)
        else:
            logger.debug(f"Reusing cached ImageProvider for model: {model}")
        return _image_provider_cache[cache_key]


def _get_cached_caption_provider(model: str) -> TextProvider:
    """Get or create a cached caption provider instance"""
    cache_key = _config_fingerprint("caption", model)
    with _cache_lock:
        if cache_key not in _caption_provider_cache:
            if len(_caption_provider_cache) >= 128:
                _caption_provider_cache.pop(next(iter(_caption_provider_cache)))
            logger.info(f"Creating new CaptionProvider for model: {model}")
            _caption_provider_cache[cache_key] = get_caption_provider(model=model)
        return _caption_provider_cache[cache_key]


def create_ai_service(snapshot=None, factory=None) -> AIService:
    """Build a fresh service; only providers may be cached within an owner scope.

    factory(snapshot) is the offline test/adapter seam. Snapshot credentials are
    never passed to logs, task JSON, or public diagnostics.
    """
    from .provider_config import capture_provider_snapshot, provider_snapshot_scope
    snapshot = snapshot or capture_provider_snapshot()
    with provider_snapshot_scope(snapshot):
        try:
            if factory is not None:
                return factory(snapshot)
            values = snapshot.values
            service = AIService(
                text_provider=_get_cached_text_provider(values['TEXT_MODEL']),
                image_provider=_get_cached_image_provider(values['IMAGE_MODEL']),
                caption_provider=_get_cached_caption_provider(values['IMAGE_CAPTION_MODEL']),
            )
            service.provider_snapshot = snapshot
            return service
        except Exception as exc:
            from .provider_config import redact_provider_text
            message = redact_provider_text(str(exc))
            if message != str(exc):
                raise RuntimeError(message) from None
            raise


def get_ai_service(force_new: bool = False, *, snapshot=None, factory=None) -> AIService:
    """Compatibility entry point. Never shares mutable AIService instances."""
    if force_new:
        clear_ai_service_cache()
    return create_ai_service(snapshot=snapshot, factory=factory)


def clear_ai_service_cache():
    with _cache_lock:
        _text_provider_cache.clear()
        _image_provider_cache.clear()
        _caption_provider_cache.clear()


def get_provider_cache_info() -> dict:
    with _cache_lock:
        return {
            'text_providers': len(_text_provider_cache),
            'image_providers': len(_image_provider_cache),
            'caption_providers': len(_caption_provider_cache),
            'total_cached': sum(map(len, (_text_provider_cache, _image_provider_cache, _caption_provider_cache))),
        }

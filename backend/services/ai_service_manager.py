"""
AIService singleton manager for optimizing provider initialization

This module provides a singleton pattern implementation for AIService to avoid
repeated initialization of AI providers (TextProvider and ImageProvider) on every request.

Benefits:
- Reuses AI provider instances across requests
- Reduces initialization overhead
- Better resource management
- Thread-safe for Flask multi-threaded environment

Usage:
    from services.ai_service_manager import get_ai_service
    
    # In your controller
    ai_service = get_ai_service()
    outline = ai_service.generate_outline(project_context)
"""

import logging
from threading import Lock
from typing import Optional
from flask import current_app, has_app_context
from .ai_service import AIService
from .ai_providers import get_text_provider, get_image_provider, get_caption_provider, TextProvider, ImageProvider

logger = logging.getLogger(__name__)

# Global singleton instance
_ai_service_instance: Optional[AIService] = None
_lock = Lock()

# Provider cache to avoid re-initialization when models don't change
_text_provider_cache: dict = {}
_image_provider_cache: dict = {}
_caption_provider_cache: dict = {}
_cache_lock = Lock()


def _config_fingerprint(kind: str, model: str) -> tuple:
    """Build a provider cache key that changes when credentials/config change."""
    if not (has_app_context() and current_app and hasattr(current_app, "config")):
        return (model,)

    cfg = current_app.config
    provider_format = cfg.get("AI_PROVIDER_FORMAT")
    source_key = {
        "text": "TEXT_MODEL_SOURCE",
        "image": "IMAGE_MODEL_SOURCE",
        "caption": "IMAGE_CAPTION_MODEL_SOURCE",
    }.get(kind)
    api_key_key = {
        "text": "TEXT_API_KEY",
        "image": "IMAGE_API_KEY",
        "caption": "IMAGE_CAPTION_API_KEY",
    }.get(kind)
    api_base_key = {
        "text": "TEXT_API_BASE",
        "image": "IMAGE_API_BASE",
        "caption": "IMAGE_CAPTION_API_BASE",
    }.get(kind)

    explicit_key = cfg.get(api_key_key or "", "") or cfg.get("OPENAI_API_KEY", "") or cfg.get("GOOGLE_API_KEY", "")
    explicit_base = cfg.get(api_base_key or "", "") or cfg.get("OPENAI_API_BASE", "") or cfg.get("GOOGLE_API_BASE", "")

    # Keep only a short deterministic fingerprint in memory/loggable structures.
    import hashlib
    secret_hash = hashlib.sha256((explicit_key or "").encode("utf-8")).hexdigest()[:12] if explicit_key else ""
    return (
        model,
        provider_format,
        cfg.get(source_key or "", ""),
        explicit_base,
        secret_hash,
        cfg.get("OPENAI_IMAGE_API_PROTOCOL", ""),
    )


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
            logger.info(f"Creating new CaptionProvider for model: {model}")
            _caption_provider_cache[cache_key] = get_caption_provider(model=model)
        return _caption_provider_cache[cache_key]


def get_ai_service(force_new: bool = False) -> AIService:
    """
    Get the singleton AIService instance with optimized provider caching
    
    This function creates and returns a singleton AIService instance that reuses
    AI providers (TextProvider and ImageProvider) across requests, significantly
    reducing initialization overhead.
    
    Args:
        force_new: If True, forces creation of a new instance (useful for testing)
        
    Returns:
        AIService singleton instance with cached providers
        
    Note:
        The providers are cached per model name. If TEXT_MODEL or IMAGE_MODEL
        changes in Flask config, new providers will be created automatically.
    """
    global _ai_service_instance
    
    if force_new:
        with _lock:
            logger.info("Force creating new AIService instance")
            _ai_service_instance = None
    
    if _ai_service_instance is None:
        with _lock:
            # Double-check locking pattern
            if _ai_service_instance is None:
                logger.info("Initializing AIService singleton with provider caching")
                
                # Get model names from Flask config or use defaults
                from config import get_config
                config = get_config()
                
                if has_app_context() and current_app and hasattr(current_app, "config"):
                    text_model = current_app.config.get("TEXT_MODEL", config.TEXT_MODEL)
                    image_model = current_app.config.get("IMAGE_MODEL", config.IMAGE_MODEL)
                    caption_model = current_app.config.get("IMAGE_CAPTION_MODEL", config.IMAGE_CAPTION_MODEL)
                else:
                    text_model = config.TEXT_MODEL
                    image_model = config.IMAGE_MODEL
                    caption_model = config.IMAGE_CAPTION_MODEL

                # Get cached providers
                text_provider = _get_cached_text_provider(text_model)
                image_provider = _get_cached_image_provider(image_model)
                caption_provider = _get_cached_caption_provider(caption_model)

                # Create AIService with cached providers
                _ai_service_instance = AIService(
                    text_provider=text_provider,
                    image_provider=image_provider,
                    caption_provider=caption_provider
                )

                logger.info(f"AIService singleton created with models: text={text_model}, image={image_model}, caption={caption_model}")
    
    return _ai_service_instance


def clear_ai_service_cache():
    """
    Clear the AIService singleton and provider cache
    
    This is useful when:
    - Configuration changes (API keys, endpoints, models)
    - Testing scenarios requiring fresh instances
    - Memory cleanup needed
    
    Note:
    - Uses nested locks to ensure atomic cache clearing operation
    - Prevents race conditions where new instances could be created
      with stale cached providers during the clearing process
    """
    global _ai_service_instance
    
    with _lock:
        _ai_service_instance = None
        logger.info("AIService singleton cache cleared")
        with _cache_lock:
            _text_provider_cache.clear()
            _image_provider_cache.clear()
            _caption_provider_cache.clear()
            logger.info("Provider cache cleared")


def get_provider_cache_info() -> dict:
    """
    Get information about cached providers (for debugging/monitoring)
    
    Returns:
        Dictionary with cache statistics
    """
    with _cache_lock:
        return {
            "text_providers": [str(key[0] if isinstance(key, tuple) else key) for key in _text_provider_cache.keys()],
            "image_providers": [str(key[0] if isinstance(key, tuple) else key) for key in _image_provider_cache.keys()],
            "caption_providers": [str(key[0] if isinstance(key, tuple) else key) for key in _caption_provider_cache.keys()],
            "total_cached": len(_text_provider_cache) + len(_image_provider_cache) + len(_caption_provider_cache)
        }

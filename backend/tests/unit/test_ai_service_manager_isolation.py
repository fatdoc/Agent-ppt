"""Regression tests for task-scoped AI service creation."""

from types import SimpleNamespace

from services import ai_service_manager as manager


def test_create_ai_service_does_not_replace_active_singleton(monkeypatch):
    existing_singleton = object()
    monkeypatch.setattr(manager, "_ai_service_instance", existing_singleton)

    monkeypatch.setattr(manager, "_get_cached_text_provider", lambda model: ("text", model))
    monkeypatch.setattr(manager, "_get_cached_image_provider", lambda model: ("image", model))
    monkeypatch.setattr(manager, "_get_cached_caption_provider", lambda model: ("caption", model))
    monkeypatch.setattr(
        manager,
        "AIService",
        lambda **providers: SimpleNamespace(**providers),
    )

    task_service = manager.create_ai_service()

    assert task_service is not existing_singleton
    assert manager._ai_service_instance is existing_singleton
    assert task_service.caption_provider[0] == "caption"

import json

import pytest

from services.ai_service import AIService, ProjectContext


class DummyTextProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_text(self, prompt, thinking_budget=0):
        self.calls += 1
        if self.responses:
            return self.responses.pop(0)
        return "[]"


class DummyProvider:
    pass


def make_service(*responses):
    text_provider = DummyTextProvider(responses)
    service = AIService(
        text_provider=text_provider,
        image_provider=DummyProvider(),
        caption_provider=DummyProvider(),
    )
    return service, text_provider


def test_flatten_outline_rejects_string_items():
    service, _ = make_service()

    with pytest.raises(ValueError, match="Invalid outline item at index 0"):
        service.flatten_outline(["封面页", "目录页"])


def test_flatten_outline_rejects_non_object_pages_inside_part():
    service, _ = make_service()

    with pytest.raises(ValueError, match="Invalid outline page at part index 0, page index 0"):
        service.flatten_outline([{"part": "第一章", "pages": ["封面页"]}])


def test_parse_description_to_outline_retries_invalid_schema():
    invalid_outline = json.dumps(["封面页"])
    valid_outline = json.dumps([{"title": "封面页", "points": ["项目背景"]}], ensure_ascii=False)
    service, text_provider = make_service(invalid_outline, valid_outline)

    outline = service.parse_description_to_outline(
        ProjectContext({"creation_type": "descriptions", "description_text": "封面页：项目背景"})
    )

    assert outline == [{"title": "封面页", "points": ["项目背景"]}]
    assert text_provider.calls == 2


def test_parse_description_to_page_descriptions_retries_count_mismatch():
    one_description = json.dumps(["页面标题：封面"], ensure_ascii=False)
    two_descriptions = json.dumps(["页面标题：封面", "页面标题：目录"], ensure_ascii=False)
    service, text_provider = make_service(one_description, two_descriptions)
    outline = [
        {"title": "封面", "points": []},
        {"title": "目录", "points": []},
    ]

    descriptions = service.parse_description_to_page_descriptions(
        ProjectContext({"creation_type": "descriptions", "description_text": "封面和目录"}),
        outline,
    )

    assert descriptions == ["页面标题：封面", "页面标题：目录"]
    assert text_provider.calls == 2

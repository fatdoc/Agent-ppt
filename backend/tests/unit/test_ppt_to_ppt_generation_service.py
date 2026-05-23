import json

import pytest

from services.ppt_to_ppt.data_models import PagePattern, PptToPptBlueprint, PptToPptOptions
from services.ppt_to_ppt.generation_service import PptToPptGenerationService


def _blueprint(patterns=None):
    return PptToPptBlueprint(
        deck_summary="Pitch deck",
        style_profile={"color_palette": "navy", "tone": "confident"},
        narrative_profile={"section_flow": ["cover"]},
        page_patterns=patterns
        or [
            PagePattern(
                reference_page_index=1,
                page_role="cover",
                layout_pattern="Large title left",
                content_pattern="Project name plus tagline",
                visual_pattern="Hero product visual",
            )
        ],
    )


class FakeAIService:
    def __init__(self, response=None):
        self.prompt = None
        self.response = response or {
            "outline": "第1页：智能客服项目\n- 痛点\n- 方案",
            "pages": [
                {
                    "title": "智能客服项目",
                    "points": ["痛点明确", "方案可落地"],
                    "description": "页面展示智能客服项目定位，左侧标题右侧产品示意图。",
                }
            ],
        }

    def generate_text(self, prompt):
        self.prompt = prompt
        assert "User content is the source of truth" in prompt
        return json.dumps(self.response, ensure_ascii=False)


def test_generate_pages_uses_blueprint_patterns():
    ai_service = FakeAIService()

    result = PptToPptGenerationService(ai_service).generate(
        user_content="我们做智能客服项目，面向银行。",
        blueprint=_blueprint(),
        options=PptToPptOptions.from_form({"page_count": "1"}),
    )

    assert result.outline_text.startswith("第1页")
    assert result.pages[0].reference_page_index == 1
    assert result.pages[0].reference_page_role == "cover"
    assert "Reference Page Pattern: cover" in result.pages[0].description
    assert "Reference Page Index: 1" in result.pages[0].description
    assert "Layout: Large title left" in result.pages[0].description
    assert "Visual Elements: Hero product visual" in result.pages[0].description
    assert "Style Guidance:" in result.pages[0].description


def test_generate_prompt_includes_generation_context():
    ai_service = FakeAIService()
    options = PptToPptOptions.from_form(
        {
            "page_count": "1",
            "language": "en",
            "match_strength": "strict",
            "extra_requirements": "Use board-ready wording",
        }
    )

    PptToPptGenerationService(ai_service).generate(
        user_content="Bank customer support automation.",
        blueprint=_blueprint(),
        options=options,
    )

    assert '"outline"' in ai_service.prompt
    assert '"pages"' in ai_service.prompt
    assert "Language: en" in ai_service.prompt
    assert "Match strength: strict" in ai_service.prompt
    assert "Target page count: 1" in ai_service.prompt
    assert "Additional guidance: Use board-ready wording" in ai_service.prompt
    assert '"deck_summary": "Pitch deck"' in ai_service.prompt
    assert "Bank customer support automation." in ai_service.prompt


def test_generate_parses_fenced_ai_json_and_builds_outline_fallback():
    class FencedAI:
        def generate_text(self, prompt):
            return """```json
{
  "pages": [
    {
      "title": "智能客服项目",
      "points": ["银行场景", "服务提效"],
      "description": "封面页描述"
    }
  ]
}
```"""

    result = PptToPptGenerationService(FencedAI()).generate(
        user_content="我们做智能客服项目。",
        blueprint=_blueprint(),
        options=PptToPptOptions.from_form({}),
    )

    assert result.outline_text == "第1页：智能客服项目\n- 银行场景\n- 服务提效"
    assert result.description_text.startswith("--- 第1页 ---")


def test_generated_pages_cycle_reference_patterns_by_index():
    patterns = [
        PagePattern(
            reference_page_index=1,
            page_role="cover",
            layout_pattern="Hero layout",
            content_pattern="Opening message",
            visual_pattern="Hero visual",
        ),
        PagePattern(
            reference_page_index=2,
            page_role="section",
            layout_pattern="Section divider",
            content_pattern="Section title",
            visual_pattern="Large number",
        ),
    ]
    ai_service = FakeAIService(
        {
            "pages": [
                {"title": "One", "points": [], "description": "First"},
                {"title": "Two", "points": [], "description": "Second"},
                {"title": "Three", "points": [], "description": "Third"},
            ]
        }
    )

    result = PptToPptGenerationService(ai_service).generate(
        user_content="content",
        blueprint=_blueprint(patterns),
        options=PptToPptOptions.from_form({}),
    )

    assert [page.reference_page_index for page in result.pages] == [1, 2, 1]
    assert "Reference Page Pattern: cover" in result.pages[2].description


def test_generate_raises_when_no_pages_returned():
    with pytest.raises(ValueError) as exc:
        PptToPptGenerationService(FakeAIService({"outline": "empty", "pages": []})).generate(
            user_content="content",
            blueprint=_blueprint(),
            options=PptToPptOptions.from_form({}),
        )

    assert str(exc.value) == "PPT to PPT generated no pages"

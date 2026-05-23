import json

from services.ppt_to_ppt.blueprint_service import BlueprintService
from services.ppt_to_ppt.data_models import PptToPptOptions


class FakeAIService:
    def __init__(self):
        self.prompt = None

    def generate_text(self, prompt):
        self.prompt = prompt
        assert "strict JSON" in prompt
        return json.dumps(
            {
                "deck_summary": "Startup pitch deck",
                "style_profile": {"color_palette": "dark navy with green accents"},
                "narrative_profile": {"section_flow": ["Cover", "Problem", "Solution"]},
                "page_patterns": [
                    {
                        "reference_page_index": 1,
                        "page_role": "cover",
                        "layout_pattern": "Big title left, visual right",
                        "content_pattern": "Name plus tagline",
                        "visual_pattern": "Hero illustration",
                    }
                ],
                "reference_material_notes": ["Reference content is not source content"],
            },
            ensure_ascii=False,
        )


def test_extract_blueprint_parses_ai_json(tmp_path):
    page_image = tmp_path / "page.png"
    page_image.write_bytes(b"png")
    ai_service = FakeAIService()
    service = BlueprintService(ai_service)

    blueprint = service.extract_blueprint(
        page_images=[page_image],
        page_texts=["Original reference page text"],
        options=PptToPptOptions.from_form({}),
    )

    assert blueprint.deck_summary == "Startup pitch deck"
    assert blueprint.page_patterns[0].reference_page_index == 1
    assert blueprint.reference_material_notes == ["Reference content is not source content"]
    assert "Reference scope: structure_and_style" in ai_service.prompt
    assert "Match strength: balanced" in ai_service.prompt
    assert "Reference image count: 1" in ai_service.prompt


def test_extract_blueprint_fallback_when_ai_json_is_invalid(tmp_path):
    class BadAI:
        def generate_text(self, prompt):
            return "not json"

    page_image = tmp_path / "page.png"
    page_image.write_bytes(b"png")

    blueprint = BlueprintService(BadAI()).extract_blueprint(
        page_images=[page_image],
        page_texts=["Cover\nProblem"],
        options=PptToPptOptions.from_form({}),
    )

    assert blueprint.deck_summary == "Reference deck with 1 pages"
    assert blueprint.page_patterns[0].page_role == "page_1"

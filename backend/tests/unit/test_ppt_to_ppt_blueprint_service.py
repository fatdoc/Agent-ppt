import json
import logging
from pathlib import Path

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


def test_layout_captions_are_included_in_prompt(tmp_path):
    class CaptionAI(FakeAIService):
        def __init__(self):
            super().__init__()
            self.caption_path = None

        def generate_layout_caption(self, image_path):
            self.caption_path = image_path
            return f"layout caption for {Path(image_path).name}"

    page_image = tmp_path / "page.png"
    page_image.write_bytes(b"png")
    ai_service = CaptionAI()

    BlueprintService(ai_service).extract_blueprint(
        page_images=[page_image],
        page_texts=["Reference text"],
        options=PptToPptOptions.from_form({}),
    )

    assert "Layout/style notes:" in ai_service.prompt
    assert "layout caption for page.png" in ai_service.prompt
    assert isinstance(ai_service.caption_path, str)


def test_extract_blueprint_parses_fenced_json(tmp_path):
    class FencedAI:
        def generate_text(self, prompt):
            return """Here is the analysis:
```json
{
  "deck_summary": "Fenced deck",
  "page_patterns": [
    {
      "reference_page_index": 1,
      "page_role": "agenda",
      "layout_pattern": "List",
      "content_pattern": "Agenda items",
      "visual_pattern": "Minimal"
    }
  ]
}
```
"""

    page_image = tmp_path / "page.png"
    page_image.write_bytes(b"png")

    blueprint = BlueprintService(FencedAI()).extract_blueprint(
        page_images=[page_image],
        page_texts=["Agenda"],
        options=PptToPptOptions.from_form({}),
    )

    assert blueprint.deck_summary == "Fenced deck"
    assert blueprint.page_patterns[0].page_role == "agenda"


def test_extract_blueprint_parses_json_with_surrounding_prose(tmp_path):
    class ProseAI:
        def generate_text(self, prompt):
            return (
                "Analysis follows. "
                '{"deck_summary": "Prose deck", "page_patterns": ['
                '{"reference_page_index": 1, "page_role": "cover", '
                '"layout_pattern": "Hero", "content_pattern": "Title", '
                '"visual_pattern": "Image"}'
                "]} Extra notes after JSON."
            )

    page_image = tmp_path / "page.png"
    page_image.write_bytes(b"png")

    blueprint = BlueprintService(ProseAI()).extract_blueprint(
        page_images=[page_image],
        page_texts=["Cover"],
        options=PptToPptOptions.from_form({}),
    )

    assert blueprint.deck_summary == "Prose deck"
    assert blueprint.page_patterns[0].page_role == "cover"


def test_extract_blueprint_fallback_logs_warning_for_invalid_json(tmp_path, caplog):
    class BadAI:
        def generate_text(self, prompt):
            return "not json"

    page_image = tmp_path / "page.png"
    page_image.write_bytes(b"png")

    with caplog.at_level(logging.WARNING):
        blueprint = BlueprintService(BadAI()).extract_blueprint(
            page_images=[page_image],
            page_texts=["Cover\nProblem"],
            options=PptToPptOptions.from_form({}),
        )

    assert blueprint.deck_summary == "Reference deck with 1 pages"
    assert "PPT-to-PPT blueprint extraction failed" in caplog.text
    assert "page_count=1" in caplog.text


def test_caption_failure_logs_warning_and_extraction_continues(tmp_path, caplog):
    class CaptionFailsAI(FakeAIService):
        def generate_layout_caption(self, image_path):
            raise RuntimeError("caption unavailable")

    page_image = tmp_path / "page.png"
    page_image.write_bytes(b"png")
    ai_service = CaptionFailsAI()

    with caplog.at_level(logging.WARNING):
        blueprint = BlueprintService(ai_service).extract_blueprint(
            page_images=[page_image],
            page_texts=["Reference text"],
            options=PptToPptOptions.from_form({}),
        )

    assert blueprint.deck_summary == "Startup pitch deck"
    assert "PPT-to-PPT layout caption failed" in caplog.text
    assert "caption unavailable" in caplog.text


def test_prompt_blocks_are_bounded(tmp_path):
    class CaptureAI(FakeAIService):
        def generate_layout_caption(self, image_path):
            return "caption " + ("C" * 5000) + " caption-tail-marker"

    page_images = []
    for index in range(30):
        page_image = tmp_path / f"page_{index}.png"
        page_image.write_bytes(b"png")
        page_images.append(page_image)

    ai_service = CaptureAI()
    BlueprintService(ai_service).extract_blueprint(
        page_images=page_images,
        page_texts=[("T" * 5000) + " text-tail-marker" for _ in page_images],
        options=PptToPptOptions.from_form({}),
    )

    assert len(ai_service.prompt) <= 20000
    assert "text-tail-marker" not in ai_service.prompt
    assert "caption-tail-marker" not in ai_service.prompt

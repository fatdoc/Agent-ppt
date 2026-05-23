import json
from pathlib import Path
from typing import Any

from .data_models import PagePattern, PptToPptBlueprint, PptToPptOptions


class BlueprintService:
    def __init__(self, ai_service):
        self.ai_service = ai_service

    def extract_blueprint(
        self,
        page_images: list[Path],
        page_texts: list[str],
        options: PptToPptOptions,
    ) -> PptToPptBlueprint:
        prompt = self._build_prompt(page_images, page_texts, options)
        try:
            raw = self.ai_service.generate_text(prompt)
            data = self._parse_json(raw)
            blueprint = PptToPptBlueprint.from_dict(data)
            if blueprint.page_patterns:
                return blueprint
        except Exception:
            pass
        return self._fallback_blueprint(page_images, page_texts)

    def _build_prompt(
        self,
        page_images: list[Path],
        page_texts: list[str],
        options: PptToPptOptions,
    ) -> str:
        text_blocks = []
        for index, text in enumerate(page_texts):
            truncated = (text or "")[:2000]
            text_blocks.append(f"Reference page {index + 1} text:\n{truncated}")

        match_strength = getattr(options.match_strength, "value", options.match_strength)
        return f"""
You are a professional PPT design analyst. Analyze the reference deck as a reusable design and storytelling blueprint.

Return strict JSON with these keys:
- deck_summary
- style_profile
- narrative_profile
- page_patterns
- reference_material_notes

Each page_patterns item must include reference_page_index, page_role, layout_pattern, content_pattern, and visual_pattern.
Treat reference slide text as analysis input, not source content for the new deck.

Reference scope: {options.reference_scope}
Match strength: {match_strength}
Reference image count: {len(page_images)}

{chr(10).join(text_blocks)}
""".strip()

    def _parse_json(self, raw: str) -> dict[str, Any]:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Blueprint response must be a JSON object")
        return data

    def _fallback_blueprint(
        self, page_images: list[Path], page_texts: list[str]
    ) -> PptToPptBlueprint:
        patterns = [
            PagePattern(
                reference_page_index=index + 1,
                page_role=f"page_{index + 1}",
                layout_pattern="Use the corresponding reference page as layout rhythm guidance.",
                content_pattern="Replace all reference facts with user-provided content.",
                visual_pattern="Follow the reference page's visual density and composition impression.",
            )
            for index, _image in enumerate(page_images)
        ]
        return PptToPptBlueprint(
            deck_summary=f"Reference deck with {len(page_images)} pages",
            style_profile={
                "visual_language": "Use the reference deck as a broad visual style guide.",
                "layout_tendencies": "Follow page-level composition rhythm.",
            },
            narrative_profile={
                "section_flow": [pattern.page_role for pattern in patterns],
                "density_style": "balanced",
            },
            page_patterns=patterns,
            reference_material_notes=[
                "Reference material is used as inspiration and pattern guidance."
            ],
        )

import json
import logging
import re
from pathlib import Path
from typing import Any

from .data_models import PagePattern, PptToPptBlueprint, PptToPptOptions

logger = logging.getLogger(__name__)

MAX_PROMPT_CHARS = 18000
MAX_PAGE_BLOCKS = 20
MAX_PAGE_TEXT_CHARS = 700
MAX_CAPTION_CHARS = 500


class BlueprintService:
    def __init__(self, ai_service):
        self.ai_service = ai_service

    def extract_blueprint(
        self,
        page_images: list[Path],
        page_texts: list[str],
        options: PptToPptOptions,
    ) -> PptToPptBlueprint:
        layout_captions = self._collect_layout_captions(page_images)
        prompt = self._build_prompt(page_images, page_texts, options, layout_captions)
        try:
            raw = self.ai_service.generate_text(prompt)
            data = self._parse_json(raw)
            blueprint = PptToPptBlueprint.from_dict(data)
            if blueprint.page_patterns:
                return blueprint
            raise ValueError("Blueprint response did not include page_patterns")
        except Exception as exc:
            logger.warning(
                "PPT-to-PPT blueprint extraction failed; using fallback blueprint "
                "page_count=%s error=%s",
                len(page_images),
                exc,
            )
        return self._fallback_blueprint(page_images, page_texts)

    def _build_prompt(
        self,
        page_images: list[Path],
        page_texts: list[str],
        options: PptToPptOptions,
        layout_captions: list[str] | None = None,
    ) -> str:
        text_blocks = []
        layout_captions = layout_captions or []
        included_pages = min(max(len(page_images), len(page_texts)), MAX_PAGE_BLOCKS)
        for index in range(included_pages):
            text = page_texts[index] if index < len(page_texts) else ""
            caption = layout_captions[index] if index < len(layout_captions) else ""
            block_parts = [
                f"Reference page {index + 1}",
                f"Text:\n{self._truncate(text, MAX_PAGE_TEXT_CHARS)}",
            ]
            if caption:
                block_parts.append(
                    f"Layout/style notes:\n{self._truncate(caption, MAX_CAPTION_CHARS)}"
                )
            text_blocks.append("\n".join(block_parts))

        omitted_count = max(len(page_images), len(page_texts)) - included_pages
        if omitted_count > 0:
            text_blocks.append(
                f"{omitted_count} additional reference pages omitted from prompt budget."
            )

        match_strength = getattr(options.match_strength, "value", options.match_strength)
        prompt = f"""
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
Included reference page blocks: {included_pages}

{chr(10).join(text_blocks)}
""".strip()
        return self._truncate(prompt, MAX_PROMPT_CHARS)

    def _parse_json(self, raw: str) -> dict[str, Any]:
        text = (raw or "").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = json.loads(self._extract_json_payload(text))
        if not isinstance(data, dict):
            raise ValueError("Blueprint response must be a JSON object")
        return data

    def _extract_json_payload(self, raw: str) -> str:
        text = (raw or "").strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            return fenced.group(1)

        start = text.find("{")
        if start < 0:
            raise ValueError("Blueprint response did not contain a JSON object")

        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]

        raise ValueError("Blueprint response contained incomplete JSON")

    def _collect_layout_captions(self, page_images: list[Path]) -> list[str]:
        caption_method = getattr(self.ai_service, "generate_layout_caption", None)
        if not callable(caption_method):
            return []

        captions: list[str] = []
        for index, image_path in enumerate(page_images[:MAX_PAGE_BLOCKS]):
            try:
                captions.append(str(caption_method(str(image_path)) or ""))
            except Exception as exc:
                logger.warning(
                    "PPT-to-PPT layout caption failed; continuing with text-only "
                    "notes page_index=%s image_path=%s error=%s",
                    index + 1,
                    image_path,
                    exc,
                )
                captions.append("")
        return captions

    def _truncate(self, value: str, max_chars: int) -> str:
        text = str(value or "").strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "\n[truncated]"

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

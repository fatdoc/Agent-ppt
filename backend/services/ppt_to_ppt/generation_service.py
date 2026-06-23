import json
import re
from dataclasses import dataclass
from typing import Any

from services.prompt_registry import prompt_registry

from .data_models import GeneratedPptToPptPage, PptToPptBlueprint, PptToPptOptions

MAX_PAGES_PER_GENERATION_CALL = 8
DEFAULT_AUTO_PAGE_COUNT = 5


@dataclass
class PptToPptGenerationResult:
    outline_text: str
    description_text: str
    pages: list[GeneratedPptToPptPage]


class PptToPptGenerationService:
    def __init__(self, ai_service):
        self.ai_service = ai_service

    def generate(
        self,
        user_content: str,
        blueprint: PptToPptBlueprint,
        options: PptToPptOptions,
    ) -> PptToPptGenerationResult:
        target_count = self.resolve_target_page_count(user_content, blueprint, options)
        pages, outline_text = self._generate_pages(user_content, blueprint, options, target_count)
        if not pages:
            raise ValueError("PPT to PPT generated no pages")
        if len(pages) < target_count:
            raise ValueError(
                f"PPT to PPT generated {len(pages)} pages, expected {target_count}"
            )

        outline_text = outline_text or self._outline_from_pages(pages)
        description_text = "\n\n".join(
            f"--- 第{index + 1}页 ---\n{page.description}"
            for index, page in enumerate(pages)
        )
        return PptToPptGenerationResult(
            outline_text=outline_text,
            description_text=description_text,
            pages=pages,
        )

    def resolve_target_page_count(
        self,
        user_content: str,
        blueprint: PptToPptBlueprint,
        options: PptToPptOptions,
    ) -> int:
        if blueprint.page_patterns:
            reference_page_count = len(blueprint.page_patterns)
            if options.page_count is not None and options.page_count != reference_page_count:
                raise ValueError(
                    f"page_count must match reference page count "
                    f"({reference_page_count}) for PPT to PPT"
                )
            return reference_page_count

        if options.page_count is not None:
            return options.page_count

        return DEFAULT_AUTO_PAGE_COUNT

    def _generate_pages(
        self,
        user_content: str,
        blueprint: PptToPptBlueprint,
        options: PptToPptOptions,
        target_count: int,
    ) -> tuple[list[GeneratedPptToPptPage], str]:
        if target_count <= MAX_PAGES_PER_GENERATION_CALL:
            scoped_blueprint = self._blueprint_for_page_range(blueprint, 0, target_count)
            data = self._generate_json(user_content, scoped_blueprint, options, target_count)
            raw_pages = self._extract_raw_pages(data)[:target_count]
            return self._build_pages(raw_pages, scoped_blueprint), str(data.get("outline") or "")

        pages: list[GeneratedPptToPptPage] = []
        patterns = blueprint.page_patterns
        for start in range(0, target_count, MAX_PAGES_PER_GENERATION_CALL):
            end = min(start + MAX_PAGES_PER_GENERATION_CALL, target_count)
            chunk_blueprint = self._blueprint_for_page_range(blueprint, start, end)
            chunk_count = end - start
            data = self._generate_json(
                user_content,
                chunk_blueprint,
                options,
                chunk_count,
                page_range=(start + 1, end),
                total_page_count=target_count,
            )
            raw_pages = self._extract_raw_pages(data)
            if len(raw_pages) < chunk_count:
                raise ValueError(
                    f"PPT to PPT generated {len(raw_pages)} pages for range "
                    f"{start + 1}-{end}, expected {chunk_count}"
                )
            pages.extend(self._build_pages(raw_pages[:chunk_count], chunk_blueprint))

        return pages, self._outline_from_pages(pages)

    def _blueprint_for_page_range(
        self,
        blueprint: PptToPptBlueprint,
        start: int,
        end: int,
    ) -> PptToPptBlueprint:
        return PptToPptBlueprint(
            deck_summary=blueprint.deck_summary,
            style_profile=blueprint.style_profile,
            narrative_profile=blueprint.narrative_profile,
            page_patterns=blueprint.page_patterns[start:end],
            reference_material_notes=blueprint.reference_material_notes,
        )

    def _generate_json(
        self,
        user_content: str,
        blueprint: PptToPptBlueprint,
        options: PptToPptOptions,
        target_count: int,
        page_range: tuple[int, int] | None = None,
        total_page_count: int | None = None,
    ) -> dict[str, Any]:
        prompt = self._build_prompt(
            user_content,
            blueprint,
            options,
            target_count,
            page_range=page_range,
            total_page_count=total_page_count,
        )
        raw = self.ai_service.generate_text(prompt)
        return self._parse_json(raw)

    def _extract_raw_pages(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        raw_pages = data.get("pages") or []
        if not isinstance(raw_pages, list):
            raise ValueError("PPT to PPT generation pages must be a list")
        return raw_pages

    def _build_prompt(
        self,
        user_content: str,
        blueprint: PptToPptBlueprint,
        options: PptToPptOptions,
        target_count: int,
        page_range: tuple[int, int] | None = None,
        total_page_count: int | None = None,
    ) -> str:
        match_strength = getattr(options.match_strength, "value", options.match_strength)
        page_range_instruction = ""
        if page_range:
            page_range_instruction = (
                f"\nGenerate only pages {page_range[0]}-{page_range[1]} "
                f"of the full {total_page_count or target_count}-page deck."
            )
        return prompt_registry.render(
            "ppt_to_ppt.generation",
            language=options.language,
            match_strength=match_strength,
            target_count=target_count,
            page_range_instruction=page_range_instruction,
            extra_requirements=options.extra_requirements or "none",
            blueprint_json=json.dumps(blueprint.to_dict(), ensure_ascii=False),
            user_content=user_content,
        ).strip()

    def _parse_json(self, raw: str) -> dict[str, Any]:
        text = (raw or "").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = json.loads(self._extract_json_payload(text))
        if not isinstance(data, dict):
            raise ValueError("PPT to PPT generation response must be a JSON object")
        return data

    def _extract_json_payload(self, raw: str) -> str:
        text = (raw or "").strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            return fenced.group(1)

        start = text.find("{")
        if start < 0:
            raise ValueError("PPT to PPT generation response did not contain a JSON object")

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

        raise ValueError("PPT to PPT generation response contained incomplete JSON")

    def _build_pages(
        self, raw_pages: list[dict[str, Any]], blueprint: PptToPptBlueprint
    ) -> list[GeneratedPptToPptPage]:
        pages: list[GeneratedPptToPptPage] = []
        patterns = blueprint.page_patterns
        for index, raw_page in enumerate(raw_pages):
            if not isinstance(raw_page, dict):
                continue

            pattern = patterns[index % len(patterns)] if patterns else None
            description = str(raw_page.get("description") or "").strip()

            pages.append(
                GeneratedPptToPptPage(
                    title=str(raw_page.get("title") or f"Page {index + 1}"),
                    points=self._normalize_points(raw_page.get("points")),
                    description=description,
                    reference_page_index=pattern.reference_page_index if pattern else None,
                    reference_page_role=pattern.page_role if pattern else None,
                    reference_visual_guidance=(
                        self._reference_visual_guidance(pattern, blueprint)
                        if pattern
                        else None
                    ),
                )
            )
        return pages

    def _reference_visual_guidance(
        self, pattern: Any, blueprint: PptToPptBlueprint
    ) -> dict[str, Any]:
        return {
            "page_pattern": pattern.page_role,
            "page_index": pattern.reference_page_index,
            "layout": pattern.layout_pattern,
            "content_pattern": pattern.content_pattern,
            "visual_elements": pattern.visual_pattern,
            "style_guidance": blueprint.style_profile,
        }

    def _normalize_points(self, raw_points: Any) -> list[str]:
        if isinstance(raw_points, list):
            return [str(point) for point in raw_points]
        if raw_points:
            return [str(raw_points)]
        return []

    def _outline_from_pages(self, pages: list[GeneratedPptToPptPage]) -> str:
        blocks = []
        for index, page in enumerate(pages):
            block = f"第{index + 1}页：{page.title}"
            if page.points:
                block += "\n" + "\n".join(f"- {point}" for point in page.points)
            blocks.append(block)
        return "\n\n".join(blocks)

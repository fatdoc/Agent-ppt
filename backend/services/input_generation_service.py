"""Unified text generation orchestration for project inputs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import re
from typing import Any

from models import Page, db

logger = logging.getLogger(__name__)


@dataclass
class InputGenerationOptions:
    input_kind: str
    target_depth: str
    language: str
    detail_level: str | None = None
    reference_file_ids: list[str] | None = None
    style_policy: str | None = None
    page_count_hint: str | None = None
    scenario: str | None = None
    tone: str | None = None


@dataclass
class InputGenerationResult:
    input_kind: str
    outline: list[dict[str, Any]]
    page_descriptions: list[dict[str, Any]] | None
    status: str
    page_count: int


class InputGenerationService:
    """Generate, validate, and persist text artifacts for slide projects."""

    VALID_INPUT_KINDS = {"idea", "outline", "description", "no_think", "blueprint_topic"}
    VALID_TARGET_DEPTHS = {"outline_only", "outline_and_descriptions"}
    PAGE_HEADER_RE = re.compile(
        r"^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?"
        r"(?:(?:第\s*)?([0-9]+|[一二三四五六七八九十百两]+)\s*(?:页|頁)|slide\s*([0-9]+)|page\s*([0-9]+))"
        r"\s*[：:.\-、]?\s*(.*)$",
        re.IGNORECASE,
    )
    BULLET_RE = re.compile(r"^\s*(?:[-*•]\s+|[0-9]+[.)、]\s*)(.+?)\s*$")

    def __init__(self, ai_service):
        self.ai_service = ai_service

    @classmethod
    def _parse_page_blocks(cls, text: str) -> list[dict[str, Any]]:
        """Parse common slide/page headed text into ordered blocks."""
        if not text or not text.strip():
            return []

        blocks: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        body_lines: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            match = cls.PAGE_HEADER_RE.match(line)
            if match:
                if current is not None:
                    current["body"] = "\n".join(body_lines).strip()
                    blocks.append(current)

                number_text = next((group for group in match.groups()[:3] if group), "")
                title = (match.group(4) or "").strip()
                current = {"number": number_text, "title": title, "header": line.strip()}
                body_lines = []
            elif current is not None:
                body_lines.append(line)

        if current is not None:
            current["body"] = "\n".join(body_lines).strip()
            blocks.append(current)

        return blocks

    @classmethod
    def _parse_outline_text_locally(cls, outline_text: str) -> list[dict[str, Any]] | None:
        blocks = cls._parse_page_blocks(outline_text)
        if not blocks:
            return None

        pages = []
        for block in blocks:
            title = block.get("title") or block.get("header") or ""
            points = []
            for raw_line in str(block.get("body") or "").splitlines():
                stripped = raw_line.strip()
                if not stripped:
                    continue
                bullet_match = cls.BULLET_RE.match(stripped)
                points.append((bullet_match.group(1) if bullet_match else stripped).strip())
            pages.append({"title": title.strip(), "points": points})

        return pages if pages else None

    @classmethod
    def _split_descriptions_text_locally(
        cls,
        description_text: str,
        expected_count: int,
    ) -> list[dict[str, Any]] | None:
        blocks = cls._parse_page_blocks(description_text)
        descriptions: list[str] = []

        if blocks:
            descriptions = []
            for block in blocks:
                body = str(block.get("body") or "").strip()
                title = str(block.get("title") or "").strip()
                if title and body:
                    descriptions.append(f"页面标题：{title}\n{body}")
                else:
                    descriptions.append(body or title or str(block.get("header") or "").strip())
        else:
            descriptions = [part.strip() for part in re.split(r"\n\s*\n+", description_text or "") if part.strip()]

        if len(descriptions) != expected_count:
            return None

        return [{"text": text} for text in descriptions if text.strip()]

    @staticmethod
    def _flatten_outline(outline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pages = []
        for item in outline:
            if isinstance(item, dict) and "part" in item and "pages" in item:
                for page in item.get("pages") or []:
                    if isinstance(page, dict):
                        page_with_part = page.copy()
                        page_with_part["part"] = item["part"]
                        pages.append(page_with_part)
                    else:
                        pages.append(page)
            else:
                pages.append(item)
        return pages

    def validate_outline(self, outline: Any) -> list[dict[str, Any]]:
        if not isinstance(outline, list) or not outline:
            raise ValueError("Outline must be a non-empty list")

        pages = self._flatten_outline(outline)
        if not isinstance(pages, list) or not pages:
            raise ValueError("Outline must contain at least one page")

        for index, page in enumerate(pages, start=1):
            if not isinstance(page, dict):
                raise ValueError(f"Outline page {index} must be an object")
            title = page.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ValueError(f"Outline page {index} is missing a title")
            points = page.get("points", [])
            if points is not None and not isinstance(points, list):
                raise ValueError(f"Outline page {index} points must be a list")

        return outline

    def validate_page_descriptions(
        self,
        page_descriptions: Any,
        expected_count: int,
    ) -> list[dict[str, Any]]:
        if not isinstance(page_descriptions, list):
            raise ValueError("Page descriptions must be a list")

        if len(page_descriptions) != expected_count:
            raise ValueError(
                f"Page description count mismatch: expected {expected_count}, got {len(page_descriptions)}"
            )

        normalized = []
        for index, item in enumerate(page_descriptions, start=1):
            if isinstance(item, str):
                text = item.strip()
                extra_fields = None
            elif isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                extra_fields = item.get("extra_fields")
            else:
                text = str(item).strip()
                extra_fields = None

            if not text:
                raise ValueError(f"Page description {index} is empty")

            desc = {"text": text}
            if isinstance(extra_fields, dict) and extra_fields:
                desc["extra_fields"] = extra_fields
            normalized.append(desc)

        return normalized

    def build_outline(
        self,
        input_kind: str,
        project_context,
        options: InputGenerationOptions,
    ) -> list[dict[str, Any]]:
        if input_kind == "outline":
            outline = (
                self._parse_outline_text_locally(getattr(project_context, "outline_text", "") or "")
                or self.ai_service.parse_outline_text(project_context, language=options.language)
            )
        elif input_kind in {"description", "descriptions"}:
            if getattr(project_context, "outline_text", None):
                outline = (
                    self._parse_outline_text_locally(project_context.outline_text or "")
                    or self.ai_service.parse_outline_text(project_context, language=options.language)
                )
            else:
                outline = self.ai_service.parse_description_to_outline(project_context, language=options.language)
        elif input_kind in {"idea", "no_think", "blueprint_topic"}:
            outline = self.ai_service.generate_outline(project_context, language=options.language)
        else:
            raise ValueError(f"Unsupported input_kind: {input_kind}")

        return self.validate_outline(outline)

    def build_descriptions(
        self,
        input_kind: str,
        outline: list[dict[str, Any]],
        project_context,
        options: InputGenerationOptions,
    ) -> list[dict[str, Any]] | None:
        if options.target_depth == "outline_only":
            return None

        pages = self._flatten_outline(outline)

        if input_kind in {"description", "descriptions"}:
            raw_descriptions = self._split_descriptions_text_locally(
                getattr(project_context, "description_text", "") or "",
                expected_count=len(pages),
            )
            if raw_descriptions is None:
                raw_descriptions = self.ai_service.parse_description_to_page_descriptions(
                    project_context,
                    outline,
                    language=options.language,
                )
            return self.validate_page_descriptions(raw_descriptions, expected_count=len(pages))

        descriptions = []
        for page_index, page_outline in enumerate(pages, start=1):
            desc = self.ai_service.generate_page_description(
                project_context,
                outline,
                page_outline,
                page_index,
                language=options.language,
                detail_level=options.detail_level or "default",
            )
            descriptions.append(desc)

        return self.validate_page_descriptions(descriptions, expected_count=len(pages))

    def save_pages(
        self,
        project_id: str,
        outline: list[dict[str, Any]],
        page_descriptions: list[dict[str, Any]] | None = None,
        mode: str = "merge_by_index",
    ) -> list[Page]:
        if mode not in {"replace", "merge_by_index"}:
            raise ValueError(f"Unsupported save mode: {mode}")

        outline = self.validate_outline(outline)
        pages_data = self._flatten_outline(outline)
        if page_descriptions is not None:
            page_descriptions = self.validate_page_descriptions(
                page_descriptions,
                expected_count=len(pages_data),
            )

        old_pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
        if mode == "replace":
            for old_page in old_pages:
                db.session.delete(old_page)
            old_pages = []

        pages_list = []
        for index, page_data in enumerate(pages_data):
            if mode == "merge_by_index" and index < len(old_pages):
                page = old_pages[index]
            else:
                page = Page(project_id=project_id, status="DRAFT")
                db.session.add(page)

            page.order_index = index
            page.part = page_data.get("part")
            page.set_outline_content({
                "title": page_data.get("title"),
                "points": page_data.get("points", []),
            })

            if page_descriptions is not None:
                desc = dict(page_descriptions[index])
                desc.setdefault("generated_at", datetime.utcnow().isoformat())
                page.set_description_content(desc)
                page.status = "DESCRIPTION_GENERATED"

            pages_list.append(page)

        if mode == "merge_by_index":
            for old_page in old_pages[len(pages_data):]:
                db.session.delete(old_page)

        return pages_list

    def generate(
        self,
        project,
        project_context,
        options: InputGenerationOptions,
        save_mode: str = "merge_by_index",
    ) -> InputGenerationResult:
        if options.input_kind not in self.VALID_INPUT_KINDS:
            raise ValueError(f"Unsupported input_kind: {options.input_kind}")
        if options.target_depth not in self.VALID_TARGET_DEPTHS:
            raise ValueError(f"Unsupported target_depth: {options.target_depth}")

        logger.info(
            "input_generation started: project=%s input_kind=%s target_depth=%s",
            project.id,
            options.input_kind,
            options.target_depth,
        )
        outline = self.build_outline(options.input_kind, project_context, options)
        flat_outline = self._flatten_outline(outline)
        logger.info("input_generation outline ready: project=%s pages=%s", project.id, len(flat_outline))
        page_descriptions = self.build_descriptions(options.input_kind, outline, project_context, options)
        if page_descriptions is not None:
            logger.info("input_generation descriptions ready: project=%s pages=%s", project.id, len(page_descriptions))
        pages = self.save_pages(project.id, outline, page_descriptions, mode=save_mode)

        if page_descriptions is not None and pages:
            status = "DESCRIPTIONS_GENERATED"
        elif all(page.description_content for page in pages) and pages:
            status = "DESCRIPTIONS_GENERATED"
        else:
            status = "OUTLINE_GENERATED"

        project.status = status
        project.updated_at = datetime.utcnow()

        return InputGenerationResult(
            input_kind=options.input_kind,
            outline=outline,
            page_descriptions=page_descriptions,
            status=status,
            page_count=len(pages),
        )

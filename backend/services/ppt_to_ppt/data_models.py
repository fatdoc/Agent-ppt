from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class MatchStrength(str, Enum):
    LOOSE = "loose"
    BALANCED = "balanced"
    STRICT = "strict"


VALID_CONTENT_TYPES = {"idea", "outline", "notes", "document_text"}
VALID_REFERENCE_SCOPES = {"style_only", "structure_and_style", "full_blueprint"}
VALID_STYLE_SOURCES = {"original", "template"}


@dataclass
class PptToPptOptions:
    content_type: str = "notes"
    match_strength: MatchStrength = MatchStrength.BALANCED
    page_count: int | None = None
    language: str = "zh"
    extra_requirements: str | None = None
    reference_scope: str = "structure_and_style"
    style_source: str = "original"
    template_style: str | None = None

    @classmethod
    def from_form(cls, form: dict[str, Any]) -> "PptToPptOptions":
        content_type = (form.get("content_type") or "notes").strip()
        if content_type not in VALID_CONTENT_TYPES:
            raise ValueError("content_type must be one of idea, outline, notes, document_text")

        raw_match_strength = (form.get("match_strength") or MatchStrength.BALANCED.value).strip()
        try:
            match_strength = MatchStrength(raw_match_strength)
        except ValueError as exc:
            raise ValueError("match_strength must be loose, balanced, or strict") from exc

        raw_page_count = form.get("page_count")
        if raw_page_count in (None, ""):
            page_count = None
        else:
            try:
                page_count = int(str(raw_page_count).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError("page_count must be between 1 and 80") from exc
        if page_count is not None and (page_count < 1 or page_count > 80):
            raise ValueError("page_count must be between 1 and 80")

        reference_scope = (form.get("reference_scope") or "structure_and_style").strip()
        if reference_scope not in VALID_REFERENCE_SCOPES:
            raise ValueError("reference_scope must be style_only, structure_and_style, or full_blueprint")

        style_source = (form.get("style_source") or "original").strip()
        if style_source not in VALID_STYLE_SOURCES:
            raise ValueError("style_source must be original or template")

        return cls(
            content_type=content_type,
            match_strength=match_strength,
            page_count=page_count,
            language=(form.get("language") or "zh").strip() or "zh",
            extra_requirements=(form.get("extra_requirements") or "").strip() or None,
            reference_scope=reference_scope,
            style_source=style_source,
            template_style=(form.get("template_style") or "").strip() or None,
        )


@dataclass
class PagePattern:
    reference_page_index: int
    page_role: str
    layout_pattern: str
    content_pattern: str
    visual_pattern: str


@dataclass
class PptToPptBlueprint:
    deck_summary: str
    style_profile: dict[str, Any] = field(default_factory=dict)
    narrative_profile: dict[str, Any] = field(default_factory=dict)
    page_patterns: list[PagePattern] = field(default_factory=list)
    reference_material_notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PptToPptBlueprint":
        patterns = [
            PagePattern(
                reference_page_index=int(item.get("reference_page_index", index + 1)),
                page_role=str(item.get("page_role") or f"page_{index + 1}"),
                layout_pattern=str(item.get("layout_pattern") or ""),
                content_pattern=str(item.get("content_pattern") or ""),
                visual_pattern=str(item.get("visual_pattern") or ""),
            )
            for index, item in enumerate(data.get("page_patterns") or [])
        ]
        notes = data.get("reference_material_notes")
        if notes is None:
            notes = data.get("constraints") or []
        return cls(
            deck_summary=str(data.get("deck_summary") or ""),
            style_profile=dict(data.get("style_profile") or {}),
            narrative_profile=dict(data.get("narrative_profile") or {}),
            page_patterns=patterns,
            reference_material_notes=[str(note) for note in notes if str(note).strip()],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GeneratedPptToPptPage:
    title: str
    points: list[str]
    description: str
    reference_page_index: int | None
    reference_page_role: str | None
    reference_visual_guidance: dict[str, Any] | None = None

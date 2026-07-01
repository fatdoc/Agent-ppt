"""Schema validation helpers for Agent Mode v1 structured outputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class SchemaValidationError(ValueError):
    """Raised when model output cannot safely enter the next pipeline step."""


@dataclass
class QAIssue:
    severity: str
    message: str
    field: str | None = None


@dataclass
class QAResult:
    passed: bool
    issues: list[QAIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [issue.__dict__ for issue in self.issues],
        }


def _require_dict(data: Any, name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SchemaValidationError(f"{name} must be an object")
    return data


def _require_list(data: Any, name: str) -> list[Any]:
    if not isinstance(data, list):
        raise SchemaValidationError(f"{name} must be an array")
    return data


def _require_text(data: dict[str, Any], key: str, *, max_len: int | None = None) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError(f"{key} is required")
    value = value.strip()
    if max_len and len(value) > max_len:
        return value[:max_len].strip()
    return value


def validate_deck_plan(data: Any, requested_page_count: int | None = None) -> dict[str, Any]:
    plan = _require_dict(data, "DeckPlan")
    plan["title"] = _require_text(plan, "title", max_len=120)
    plan["audience"] = _require_text(plan, "audience", max_len=160)
    plan["goal"] = _require_text(plan, "goal", max_len=240)
    slides = _require_list(plan.get("slides"), "slides")
    if requested_page_count and len(slides) != requested_page_count:
        raise SchemaValidationError(f"slides count must be {requested_page_count}, got {len(slides)}")
    if not slides:
        raise SchemaValidationError("slides cannot be empty")
    plan["slides"] = [validate_slide_plan(slide, index) for index, slide in enumerate(slides)]
    return plan


def validate_slide_plan(data: Any, index: int | None = None) -> dict[str, Any]:
    slide = _require_dict(data, "SlidePlan")
    slide["slide_id"] = str(slide.get("slide_id") or f"slide-{(index or 0) + 1}")
    slide["title"] = _require_text(slide, "title", max_len=120)
    slide["main_message"] = _require_text(slide, "main_message", max_len=300)
    slide["content_points"] = [str(item).strip() for item in _require_list(slide.get("content_points"), "content_points") if str(item).strip()]
    if not slide["content_points"]:
        raise SchemaValidationError("content_points cannot be empty")
    slide["layout_intent"] = str(slide.get("layout_intent") or "balanced PPT slide layout").strip()
    slide["visual_focus"] = str(slide.get("visual_focus") or slide["main_message"]).strip()
    return slide


def validate_deck_visual_system(data: Any) -> dict[str, Any]:
    system = _require_dict(data, "DeckVisualSystem")
    system["strategy_id"] = _require_text(system, "strategy_id", max_len=64)
    required = (
        "color_palette",
        "typography",
        "illustration_style",
        "paper_operator_density",
        "chinese_label_density",
        "background_style",
        "forbidden_patterns",
        "consistency_rules",
    )
    for key in required:
        if key not in system:
            raise SchemaValidationError(f"{key} is required")
    if not isinstance(system["forbidden_patterns"], list):
        raise SchemaValidationError("forbidden_patterns must be an array")
    if not isinstance(system["consistency_rules"], list):
        raise SchemaValidationError("consistency_rules must be an array")
    return system


def validate_page_visual_plan(data: Any, page_ids: set[str] | None = None) -> dict[str, Any]:
    plan = _require_dict(data, "PageVisualPlan")
    plan["page_id"] = _require_text(plan, "page_id", max_len=64)
    if page_ids is not None and plan["page_id"] not in page_ids:
        raise SchemaValidationError(f"page_id does not exist: {plan['page_id']}")
    plan["strategy_id"] = _require_text(plan, "strategy_id", max_len=64)
    plan["source_anchor"] = _require_text(plan, "source_anchor", max_len=300)
    plan["reader_takeaway"] = _require_text(plan, "reader_takeaway", max_len=300)
    plan["operator_required"] = bool(plan.get("operator_required"))
    plan["operator_family"] = str(plan.get("operator_family") or "None").strip()
    plan["metaphor_world"] = _require_text(plan, "metaphor_world", max_len=180)
    plan["composition"] = _require_text(plan, "composition", max_len=600)
    labels = [str(item).strip() for item in _require_list(plan.get("labels"), "labels") if str(item).strip()]
    if len(labels) > 10:
        raise SchemaValidationError("labels cannot exceed 10 items")
    plan["labels"] = labels
    negatives = plan.get("negative_prompts") or []
    if not isinstance(negatives, list):
        raise SchemaValidationError("negative_prompts must be an array")
    plan["negative_prompts"] = [str(item).strip() for item in negatives if str(item).strip()]
    plan["visual_prompt"] = _require_text(plan, "visual_prompt", max_len=4000)
    return plan


def hard_qa_deck_plan(plan: dict[str, Any], requested_page_count: int | None = None) -> QAResult:
    issues: list[QAIssue] = []
    try:
        validate_deck_plan(plan, requested_page_count)
    except SchemaValidationError as exc:
        issues.append(QAIssue("error", str(exc)))
    titles = [slide.get("title") for slide in plan.get("slides", []) if isinstance(slide, dict)]
    if len(titles) != len(set(titles)):
        issues.append(QAIssue("warning", "slide titles contain duplicates", "slides.title"))
    return QAResult(passed=not any(issue.severity == "error" for issue in issues), issues=issues)


def hard_qa_page_visual_plan(plan: dict[str, Any], *, locked: bool = False) -> QAResult:
    issues: list[QAIssue] = []
    if locked:
        issues.append(QAIssue("error", "cannot overwrite locked slide", "locked"))
    try:
        validate_page_visual_plan(plan)
    except SchemaValidationError as exc:
        issues.append(QAIssue("error", str(exc)))
    labels = plan.get("labels", []) if isinstance(plan, dict) else []
    if isinstance(labels, list) and len(labels) > 8:
        issues.append(QAIssue("warning", "Chinese labels may be too dense", "labels"))
    return QAResult(passed=not any(issue.severity == "error" for issue in issues), issues=issues)

"""Schema validation helpers for Agent Mode v1 structured outputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.harness_skills.quality import (
    ASSET_ROLES,
    COMPOSITION_MODES,
    RELATIONSHIP_TYPES,
    deck_continuity_issues,
    swap_test_issues,
)


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
    if "quality_constraints" in system and not isinstance(system["quality_constraints"], list):
        raise SchemaValidationError("quality_constraints must be an array")
    return system


def validate_page_visual_plan(data: Any, page_ids: set[str] | None = None) -> dict[str, Any]:
    plan = _require_dict(data, "PageVisualPlan")
    plan["page_id"] = _require_text(plan, "page_id", max_len=64)
    if page_ids is not None and plan["page_id"] not in page_ids:
        raise SchemaValidationError(f"page_id does not exist: {plan['page_id']}")
    plan["strategy_id"] = _require_text(plan, "strategy_id", max_len=64)
    plan["source_anchor"] = _require_text(plan, "source_anchor", max_len=300)
    plan["reader_takeaway"] = _require_text(plan, "reader_takeaway", max_len=300)
    plan["page_role"] = str(plan.get("page_role") or "content").strip()
    if plan.get("page_role_name") is not None:
        plan["page_role_name"] = str(plan["page_role_name"]).strip()
    # Pack-specific optional fields (paper_operators keeps these at top level).
    if "operator_required" in plan:
        plan["operator_required"] = bool(plan.get("operator_required"))
    if "operator_family" in plan:
        plan["operator_family"] = str(plan.get("operator_family") or "None").strip()
    if "metaphor_world" in plan and plan.get("metaphor_world") is not None:
        plan["metaphor_world"] = str(plan["metaphor_world"]).strip()[:180]
    if plan.get("material_status") is not None:
        material_status = str(plan["material_status"]).strip()
        if material_status not in ("real", "concept_placeholder"):
            raise SchemaValidationError("material_status must be real or concept_placeholder")
        plan["material_status"] = material_status
    if plan.get("asset_role") is not None:
        asset_role = str(plan["asset_role"]).strip()
        if asset_role not in ASSET_ROLES:
            raise SchemaValidationError(f"asset_role must be one of: {', '.join(ASSET_ROLES)}")
        plan["asset_role"] = asset_role
    if plan.get("relationship_type") is not None:
        rel = str(plan["relationship_type"]).strip()
        if rel not in RELATIONSHIP_TYPES:
            raise SchemaValidationError(f"relationship_type must be one of: {', '.join(RELATIONSHIP_TYPES)}")
        plan["relationship_type"] = rel
    if plan.get("composition_mode") is not None:
        mode = str(plan["composition_mode"]).strip()
        if mode not in COMPOSITION_MODES:
            raise SchemaValidationError(f"composition_mode must be one of: {', '.join(COMPOSITION_MODES)}")
        plan["composition_mode"] = mode
    if plan.get("truth_constraints") is not None:
        tc = plan["truth_constraints"]
        if not isinstance(tc, list):
            raise SchemaValidationError("truth_constraints must be an array")
        plan["truth_constraints"] = [str(item).strip() for item in tc if str(item).strip()]
    if plan.get("data_contract") is not None:
        dc = plan["data_contract"]
        if not isinstance(dc, dict):
            raise SchemaValidationError("data_contract must be an object")
        plan["data_contract"] = dc
    if plan.get("variation_axes") is not None and not isinstance(plan["variation_axes"], list):
        raise SchemaValidationError("variation_axes must be an array")
    if plan.get("throughline") is not None and not isinstance(plan["throughline"], dict):
        raise SchemaValidationError("throughline must be an object")
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
    # 结构/风格分离：structure_prompt 对所有视觉来源注入，style_prompt 仅默认视觉时注入。
    plan["structure_prompt"] = str(plan.get("structure_prompt") or "").strip()[:4000]
    plan["style_prompt"] = str(plan.get("style_prompt") or "").strip()[:4000]
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
    for index, slide in enumerate(plan.get("slides", [])):
        if not isinstance(slide, dict):
            continue
        msg = str(slide.get("main_message") or "").strip()
        if len(msg) < 10:
            issues.append(QAIssue(
                "warning",
                f"Slide {index + 1} main_message 过短，Deck 级 Swap Test 可能无法锁定具体内容",
                f"slides[{index}].main_message",
            ))
    return QAResult(passed=not any(issue.severity == "error" for issue in issues), issues=issues)


def hard_qa_page_visual_plan(
    plan: dict[str, Any],
    *,
    locked: bool = False,
    previous_plan: dict[str, Any] | None = None,
) -> QAResult:
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
    for severity, message, field in swap_test_issues(plan, previous_plan=previous_plan):
        issues.append(QAIssue(severity, message, field))
    return QAResult(passed=not any(issue.severity == "error" for issue in issues), issues=issues)


def hard_qa_deck_page_plans(plans: list[dict[str, Any]]) -> QAResult:
    """Deck-level Harness QA: per-page Swap Test + series continuity."""
    issues: list[QAIssue] = []
    previous: dict[str, Any] | None = None
    for index, plan in enumerate(plans):
        if not isinstance(plan, dict):
            continue
        page_qa = hard_qa_page_visual_plan(plan, previous_plan=previous)
        for issue in page_qa.issues:
            field = f"pages[{index}].{issue.field}" if issue.field else f"pages[{index}]"
            issues.append(QAIssue(issue.severity, issue.message, field))
        previous = plan
    for severity, message, field in deck_continuity_issues(plans):
        issues.append(QAIssue(severity, message, field))
    return QAResult(passed=not any(issue.severity == "error" for issue in issues), issues=issues)

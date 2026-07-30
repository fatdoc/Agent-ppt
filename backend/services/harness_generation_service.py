"""Harness mode support for the regular PPT generation pipeline."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func

from models import (
    DeckVersion,
    DeckVisualSystem,
    Page,
    PageVisualPlan,
    SlideVersion,
    db,
)
from services.harness_skills import ScenarioPack, get_scenario_pack
from services.agent_mode_schemas import hard_qa_deck_page_plans, hard_qa_page_visual_plan, validate_page_visual_plan


def get_project_scenario_pack(project) -> ScenarioPack | None:
    if (getattr(project, "generation_mode", None) or "fast") != "harness":
        return None
    return get_scenario_pack(getattr(project, "harness_template", None))


def is_harness_project(project) -> bool:
    return get_project_scenario_pack(project) is not None


def enhance_project_context(project, project_context):
    """Attach Harness instructions to the AI text-generation context."""
    pack = get_project_scenario_pack(project)
    if pack is None:
        return project_context

    project_context.outline_requirements = _append_instruction(
        getattr(project_context, "outline_requirements", None),
        pack.outline_instruction(),
    )
    project_context.description_requirements = _append_instruction(
        getattr(project_context, "description_requirements", None),
        pack.description_instruction(),
    )
    return project_context


def ensure_page_visual_plans(project, pages: list[Page] | None = None) -> None:
    """Create a lightweight DeckVersion/PageVisualPlan set for Harness projects.

    This makes normal generation projects consumable by the same image-stage
    guidance used by Agent Mode, without changing the native visual strategy.
    """
    pack = get_project_scenario_pack(project)
    if pack is None:
        return

    pages = pages or Page.query.filter_by(project_id=project.id).order_by(Page.order_index).all()
    if not pages:
        return

    clear_harness_artifacts(project.id)

    topic = _project_topic(project)
    audience = "目标受众"
    style = _harness_style(project)
    deck_plan = _build_deck_plan(project, pages, topic, audience)
    version_number = (db.session.query(func.max(DeckVersion.version_number)).filter_by(project_id=project.id).scalar() or 0) + 1

    deck_version = DeckVersion(
        project_id=project.id,
        version_number=version_number,
        status="generated_from_harness_mode",
    )
    deck_version.set_deck_plan(deck_plan)
    deck_version.set_qa_result({"passed": True, "issues": []})
    db.session.add(deck_version)
    db.session.flush()

    visual_system_data = pack.deck_visual_system(
        topic,
        audience,
        style,
        use_default_visual=not _has_explicit_visual_source(project),
    )
    visual_system = DeckVisualSystem(
        project_id=project.id,
        deck_version_id=deck_version.id,
        strategy_id=pack.pack_id,
    )
    visual_system.set_system(visual_system_data)
    visual_system.set_qa_result({"passed": True, "issues": []})
    db.session.add(visual_system)
    db.session.flush()

    page_ids = [page.id for page in pages]
    page_plans = pack.build_deck_page_plans(
        deck_plan["slides"],
        visual_system_data,
        topic=topic,
        page_ids=page_ids,
    )
    deck_plans_qa = hard_qa_deck_page_plans(page_plans)
    deck_version.set_qa_result(deck_plans_qa.to_dict())

    for index, (page, slide_plan, plan) in enumerate(zip(pages, deck_plan["slides"], page_plans)):
        slide_version = SlideVersion(
            deck_version_id=deck_version.id,
            page_id=page.id,
            order_index=page.order_index,
            status="generated_from_harness_mode",
        )
        slide_version.set_slide_plan(slide_plan)
        slide_version.set_qa_result({"passed": True, "issues": []})
        db.session.add(slide_version)
        db.session.flush()

        plan = validate_page_visual_plan(plan, {page.id})
        previous_plan = page_plans[index - 1] if index > 0 else None
        plan_qa = hard_qa_page_visual_plan(plan, previous_plan=previous_plan)
        visual_plan = PageVisualPlan(
            project_id=project.id,
            page_id=page.id,
            slide_version_id=slide_version.id,
            deck_visual_system_id=visual_system.id,
            strategy_id=pack.pack_id,
            status="generated_from_harness_mode",
        )
        visual_plan.set_plan(plan)
        visual_plan.set_qa_result(plan_qa.to_dict())
        db.session.add(visual_plan)

    project.updated_at = datetime.utcnow()


def clear_harness_artifacts(project_id: str) -> None:
    """Remove generated Harness plan artifacts before rebuilding pages/plans."""
    for deck_version in DeckVersion.query.filter_by(project_id=project_id).all():
        db.session.delete(deck_version)
    db.session.flush()


def _append_instruction(existing: str | None, instruction: str) -> str:
    existing = (existing or "").strip()
    instruction = instruction.strip()
    if not existing:
        return instruction
    if instruction in existing:
        return existing
    return f"{existing}\n\n{instruction}"


def _project_topic(project) -> str:
    for value in (project.project_title, project.idea_prompt, project.outline_text, project.description_text):
        text = (value or "").strip()
        if text:
            return text[:120]
    return "Untitled PPT"


def _harness_style(project) -> str:
    payload = project.get_harness_payload() if hasattr(project, "get_harness_payload") else None
    if isinstance(payload, dict) and payload.get("style"):
        return str(payload["style"])
    return (getattr(project, "template_style", None) or "").strip()


def _has_explicit_visual_source(project) -> bool:
    """Whether the user already owns the visual layer for this project."""
    return bool(
        (getattr(project, "visual_strategy", None) or "native") == "external_skill"
        or getattr(project, "template_image_path", None)
        or getattr(project, "ppt_to_ppt_blueprint", None)
        or _harness_style(project)
    )


def _build_deck_plan(project, pages: list[Page], topic: str, audience: str) -> dict[str, Any]:
    slides = []
    for index, page in enumerate(pages, start=1):
        outline = page.get_outline_content() or {}
        desc = page.get_description_content() or {}
        desc_text = desc.get("text", "") if isinstance(desc, dict) else str(desc or "")
        title = str(outline.get("title") or f"第 {index} 页").strip()
        points = [str(item) for item in (outline.get("points") or [])]
        main_message = str(
            (desc.get("main_message") if isinstance(desc, dict) else None)
            or _first_sentence(desc_text)
            or (points[0] if points else title)
        ).strip()
        slide: dict[str, Any] = {
            "slide_id": page.id,
            "title": title,
            "main_message": main_message,
            "content_points": points,
            "description_text": desc_text,
            "layout_intent": str((desc.get("layout_intent") if isinstance(desc, dict) else None) or "信息层级清晰，读者能快速识别本页主张、证据和结论。"),
            "visual_focus": str((desc.get("visual_focus") if isinstance(desc, dict) else None) or main_message or title),
        }
        slides.append(slide)

    return {
        "title": topic,
        "audience": audience,
        "goal": f"用 Harness 流程帮助{audience}理解并判断：{topic}",
        "slides": slides,
    }


def _first_sentence(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    for sep in ("。", "！", "？", ".", "!", "?"):
        if sep in cleaned:
            return cleaned.split(sep, 1)[0][:120]
    return cleaned[:120]

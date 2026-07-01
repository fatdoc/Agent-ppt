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
from services.visual_strategies import PaperOperatorsStrategy


HARNESS_OUTLINE_INSTRUCTION = """
Harness 高质量模式已启用，当前模板为 paper-operators。
大纲阶段必须先理解交付对象、读者、证据链和页面角色，再组织页面顺序。
每一页都要有清晰 reader takeaway：读者看完这一页应该带走什么判断。
避免只堆主题词；优先形成“问题/证据/机制/取舍/结论/行动”的可校验叙事链。
paper-operators 在这里是流程模板，不是固定视觉风格；不要把纸片人画风写进大纲。
"""


HARNESS_DESCRIPTION_INSTRUCTION = """
Harness 高质量模式已启用，当前模板为 paper-operators。
逐页描述阶段必须补足：页面主张、读者收获、信息层级、构图意图、素材/图表需求和可读性校验。
如果页面适合后续生成 PageVisualPlan，请明确 source anchor、reader takeaway、visual_focus 和 layout_intent。
paper-operators 在这里是页面组织与校验流程，不覆盖用户选择的模板图、文字风格或视觉方案。
"""


def is_harness_project(project) -> bool:
    return (
        (getattr(project, "generation_mode", None) or "fast") == "harness"
        and (getattr(project, "harness_template", None) or "") == "paper_operators"
    )


def enhance_project_context(project, project_context):
    """Attach Harness instructions to the AI text-generation context."""
    if not is_harness_project(project):
        return project_context

    project_context.outline_requirements = _append_instruction(
        getattr(project_context, "outline_requirements", None),
        HARNESS_OUTLINE_INSTRUCTION,
    )
    project_context.description_requirements = _append_instruction(
        getattr(project_context, "description_requirements", None),
        HARNESS_DESCRIPTION_INSTRUCTION,
    )
    return project_context


def ensure_page_visual_plans(project, pages: list[Page] | None = None) -> None:
    """Create a lightweight DeckVersion/PageVisualPlan set for Harness projects.

    This makes normal generation projects consumable by the same image-stage
    guidance used by Agent Mode, without changing the native visual strategy.
    """
    if not is_harness_project(project):
        return

    pages = pages or Page.query.filter_by(project_id=project.id).order_by(Page.order_index).all()
    if not pages:
        return

    clear_harness_artifacts(project.id)

    strategy = PaperOperatorsStrategy()
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

    visual_system_data = strategy.deck_visual_system(topic, audience, style)
    visual_system = DeckVisualSystem(
        project_id=project.id,
        deck_version_id=deck_version.id,
        strategy_id="paper_operators",
    )
    visual_system.set_system(visual_system_data)
    visual_system.set_qa_result({"passed": True, "issues": []})
    db.session.add(visual_system)
    db.session.flush()

    for page, slide_plan in zip(pages, deck_plan["slides"]):
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

        plan = strategy.build_page_plan(slide_plan, visual_system_data, page_id=page.id)
        visual_plan = PageVisualPlan(
            project_id=project.id,
            page_id=page.id,
            slide_version_id=slide_version.id,
            deck_visual_system_id=visual_system.id,
            strategy_id="paper_operators",
            status="generated_from_harness_mode",
        )
        visual_plan.set_plan(plan)
        visual_plan.set_qa_result({"passed": True, "issues": []})
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
        slides.append({
            "slide_id": page.id,
            "title": title,
            "main_message": main_message,
            "content_points": points,
            "layout_intent": str((desc.get("layout_intent") if isinstance(desc, dict) else None) or "信息层级清晰，读者能快速识别本页主张、证据和结论。"),
            "visual_focus": str((desc.get("visual_focus") if isinstance(desc, dict) else None) or main_message or title),
        })

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

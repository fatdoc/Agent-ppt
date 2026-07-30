"""Agent Mode v1 prompt pipeline: structured plans, no general-purpose agent runtime."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from models import (
    AgentRun,
    AgentStep,
    DeckVersion,
    DeckVisualSystem,
    PageVisualPlan,
    SlideVersion,
    db,
)
from services.agent_mode_schemas import (
    SchemaValidationError,
    hard_qa_deck_page_plans,
    hard_qa_deck_plan,
    hard_qa_page_visual_plan,
    validate_deck_plan,
    validate_deck_visual_system,
    validate_page_visual_plan,
)
from services.agent_mode_tools import AgentToolRegistry
from services.ai_service_manager import get_ai_service
from services.harness_skills import get_scenario_pack, list_scenario_pack_ids, normalize_pack_id
from services.harness_skills.base import HARNESS_MAX_PAGE_COUNT
from utils.auth import current_user_id


class AgentModeService:
    """Stable v1 pipeline for planning first, image generation second."""

    def create_agent_deck_plan(
        self,
        *,
        topic: str,
        audience: str,
        page_count: int,
        style: str,
        generation_mode: str,
        harness_template: str,
        harness_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not topic.strip():
            raise ValueError("topic is required")
        if not audience.strip():
            raise ValueError("audience is required")
        page_count = max(1, min(int(page_count or 8), HARNESS_MAX_PAGE_COUNT))
        if generation_mode != "harness":
            raise ValueError("Agent Mode only supports generation_mode=harness")
        harness_template = normalize_pack_id(harness_template) or ""
        pack = get_scenario_pack(harness_template)
        if pack is None:
            raise ValueError(f"harness_template must be one of: {', '.join(list_scenario_pack_ids())}")
        run = AgentRun(user_id=current_user_id(), run_type="agent_mode_v1", status="running")
        run.set_input({
            "topic": topic,
            "audience": audience,
            "page_count": page_count,
            "style": style,
            "generation_mode": generation_mode,
            "harness_template": harness_template,
            "harness_payload": harness_payload,
        })
        db.session.add(run)
        db.session.flush()
        tools = AgentToolRegistry(agent_run=run)

        try:
            deck_plan = self._step(run, "generate_deck_plan", {"topic": topic, "audience": audience, "page_count": page_count}, lambda: self._generate_deck_plan(topic, audience, page_count, pack, harness_payload))
            deck_plan = validate_deck_plan(deck_plan, page_count)
            deck_qa = hard_qa_deck_plan(deck_plan, page_count).to_dict()
            if not deck_qa["passed"]:
                raise SchemaValidationError("DeckPlan hard QA failed")

            project = tools.create_project(topic=topic, audience=audience, page_count=page_count, generation_mode=generation_mode, harness_template=harness_template)
            run.project_id = project.id
            pages = tools.create_pages_from_slide_plans(project, deck_plan["slides"])
            tools.set_harness_template(project, harness_template, {**(harness_payload or {}), **({"style": style} if style else {})})

            deck_version = DeckVersion(project_id=project.id, version_number=1, status="pending_confirmation")
            deck_version.set_deck_plan(deck_plan)
            deck_version.set_qa_result(deck_qa)
            db.session.add(deck_version)
            db.session.flush()

            visual_system_data = pack.deck_visual_system(
                topic,
                audience,
                style,
                use_default_visual=not bool(style.strip()),
            )
            visual_system_data = validate_deck_visual_system(visual_system_data)
            visual_system = DeckVisualSystem(project_id=project.id, deck_version_id=deck_version.id, strategy_id=harness_template)
            visual_system.set_system(visual_system_data)
            visual_system.set_qa_result({"passed": True, "issues": []})
            db.session.add(visual_system)
            db.session.flush()

            page_ids = [pages[index].id for index in range(len(deck_plan["slides"]))]
            page_plans = pack.build_deck_page_plans(
                deck_plan["slides"],
                visual_system_data,
                topic=topic,
                page_ids=page_ids,
            )
            deck_plans_qa = hard_qa_deck_page_plans(page_plans).to_dict()

            for index, slide in enumerate(deck_plan["slides"]):
                page = pages[index]
                slide["slide_id"] = page.id
                slide_version = SlideVersion(deck_version_id=deck_version.id, page_id=page.id, order_index=page.order_index, status="pending_confirmation")
                slide_version.set_slide_plan(slide)
                slide_version.set_qa_result({"passed": True, "issues": []})
                db.session.add(slide_version)
                db.session.flush()

                plan = page_plans[index]
                plan = validate_page_visual_plan(plan, {page.id})
                previous_plan = page_plans[index - 1] if index > 0 else None
                plan_qa = hard_qa_page_visual_plan(plan, previous_plan=previous_plan).to_dict()
                visual_plan = PageVisualPlan(
                    project_id=project.id,
                    page_id=page.id,
                    slide_version_id=slide_version.id,
                    deck_visual_system_id=visual_system.id,
                    strategy_id=harness_template,
                    status="pending_confirmation",
                )
                visual_plan.set_plan(plan)
                visual_plan.set_qa_result(plan_qa)
                db.session.add(visual_plan)

            deck_version.set_qa_result({
                "passed": deck_qa["passed"],
                "issues": [*deck_qa.get("issues", []), *deck_plans_qa.get("issues", [])],
            })

            project.status = "AGENT_PLAN_PENDING_CONFIRMATION"
            db.session.flush()
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            output = {"project_id": project.id, "deck_version_id": deck_version.id}
            run.set_output(output)
            db.session.commit()
            return self.get_deck_version(project.id, deck_version.id)
        except Exception as exc:
            db.session.rollback()
            try:
                run.status = "failed"
                run.error_message = str(exc)
                run.completed_at = datetime.utcnow()
                db.session.add(run)
                db.session.commit()
            except Exception:
                db.session.rollback()
            raise

    def get_deck_version(self, project_id: str, deck_version_id: str) -> dict[str, Any]:
        deck_version = DeckVersion.query.filter_by(project_id=project_id, id=deck_version_id).first()
        if not deck_version:
            raise ValueError("DeckVersion not found")
        return deck_version.to_dict()

    def select_default_preview_slides(self, deck_version: DeckVersion) -> list[SlideVersion]:
        slides = list(deck_version.slide_versions)
        if len(slides) <= 2:
            return slides
        return [slides[0], slides[1]]

    def _generate_deck_plan(self, topic: str, audience: str, page_count: int, pack=None, harness_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        pack_hint = ""
        if pack is not None:
            hint = pack.deck_plan_hint().strip()
            if hint:
                pack_hint = f"\n场景包「{pack.name}」的叙事组织要求：{hint}\n"
        prompt = f"""
你是 Banana Slides 的 Presentation Planner。只输出 JSON，不要 Markdown。

为下面的 PPT 生成结构化 DeckPlan：
主题：{topic}
受众：{audience}
页数：{page_count}
{pack_hint}
JSON schema:
{{
  "title": "string",
  "audience": "string",
  "goal": "string",
  "slides": [
    {{
      "slide_id": "slide-1",
      "title": "string",
      "main_message": "string",
      "content_points": ["string"],
      "layout_intent": "string",
      "visual_focus": "string"
    }}
  ]
}}

要求：slides 数量必须等于 {page_count}；每页 main_message 不能空；内容不要重复；中文优先。
"""
        try:
            result = get_ai_service().generate_json(prompt)
            return validate_deck_plan(result, page_count)
        except Exception:
            return self._fallback_deck_plan(topic, audience, page_count)

    def _fallback_deck_plan(self, topic: str, audience: str, page_count: int) -> dict[str, Any]:
        titles = ["封面", "问题背景", "核心洞察", "方案设计", "关键路径", "价值证明", "风险与应对", "行动计划", "总结"]
        slides = []
        for index in range(page_count):
            title = titles[index] if index < len(titles) else f"第 {index + 1} 页"
            slides.append({
                "slide_id": f"slide-{index + 1}",
                "title": f"{title}：{topic}" if index == 0 else title,
                "main_message": f"面向{audience}说明{topic}的{title}。",
                "content_points": [f"{topic}的关键事实", "主要判断", "对受众的意义"],
                "layout_intent": "标题清晰，中心视觉承载主线，底部保留简短要点。",
                "visual_focus": f"用一个可读的视觉隐喻表达{title}。",
            })
        return validate_deck_plan({"title": topic, "audience": audience, "goal": f"让{audience}理解并接受{topic}。", "slides": slides}, page_count)

    def _step(self, run: AgentRun, name: str, input_data: dict[str, Any], fn):
        step = AgentStep(agent_run_id=run.id, step_name=name, status="running")
        step.input_json = json.dumps(input_data, ensure_ascii=False)
        db.session.add(step)
        db.session.flush()
        try:
            output = fn()
            step.status = "completed"
            step.output_json = json.dumps(output, ensure_ascii=False)
            step.completed_at = datetime.utcnow()
            return output
        except Exception as exc:
            step.status = "failed"
            step.error_message = str(exc)
            step.completed_at = datetime.utcnow()
            raise

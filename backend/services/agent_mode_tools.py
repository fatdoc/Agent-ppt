"""Controlled business tools used by Agent Mode v1."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from flask import current_app

from models import (
    AgentToolCall,
    DeckVersion,
    GenerationJob,
    Page,
    Project,
    SlideVersion,
    Task,
    db,
)
from services import FileService
from services.ai_service_manager import get_ai_service
from services.task_manager import generate_images_task, task_manager
from utils.auth import current_user_id
from utils.page_utils import get_filtered_pages


class AgentToolRegistry:
    """Small controlled tool layer; no free-form DB or filesystem access."""

    def __init__(self, agent_run=None):
        self.agent_run = agent_run

    def _record(self, tool_name: str, input_data: dict[str, Any], fn):
        call = None
        if self.agent_run:
            call = AgentToolCall(agent_run_id=self.agent_run.id, tool_name=tool_name, status="running")
            call.input_json = json.dumps(input_data, ensure_ascii=False)
            db.session.add(call)
            db.session.flush()
        try:
            output = fn()
            if call:
                call.status = "completed"
                call.output_json = json.dumps(output, ensure_ascii=False)
                call.completed_at = datetime.utcnow()
            return output
        except Exception as exc:
            if call:
                call.status = "failed"
                call.error_message = str(exc)
                call.completed_at = datetime.utcnow()
            raise

    def create_project(self, *, topic: str, audience: str, page_count: int, generation_mode: str, harness_template: str) -> Project:
        def run():
            project = Project(
                user_id=current_user_id(),
                project_title=topic[:255],
                idea_prompt=f"主题：{topic}\n受众：{audience}\n页数：{page_count}",
                creation_type="agent_mode",
                generation_mode=generation_mode,
                harness_template=harness_template,
                visual_strategy="native",
                status="AGENT_PLAN_GENERATED",
            )
            db.session.add(project)
            db.session.flush()
            return {"project_id": project.id}

        result = self._record("create_project", {
            "topic": topic,
            "audience": audience,
            "page_count": page_count,
            "generation_mode": generation_mode,
            "harness_template": harness_template,
        }, run)
        return Project.query.get(result["project_id"])

    def create_pages_from_slide_plans(self, project: Project, slides: list[dict[str, Any]]) -> list[Page]:
        def run():
            pages = []
            for index, slide in enumerate(slides):
                page = Page(project_id=project.id, order_index=index, status="PLAN_PENDING_CONFIRMATION")
                page.set_outline_content({
                    "title": slide["title"],
                    "points": slide.get("content_points", []),
                })
                page.set_description_content({
                    "text": self._description_text(slide),
                    "main_message": slide.get("main_message"),
                    "layout_intent": slide.get("layout_intent"),
                    "visual_focus": slide.get("visual_focus"),
                })
                db.session.add(page)
                pages.append(page)
            db.session.flush()
            return {"page_ids": [page.id for page in pages]}

        result = self._record("generate_slide_plans", {"project_id": project.id, "slides": slides}, run)
        return Page.query.filter(Page.id.in_(result["page_ids"])).order_by(Page.order_index).all()

    def set_harness_template(self, project: Project, harness_template: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        def run():
            project.generation_mode = "harness"
            project.harness_template = harness_template
            if payload is not None:
                project.set_harness_payload(payload)
            db.session.flush()
            return {"project_id": project.id, "generation_mode": project.generation_mode, "harness_template": harness_template}

        return self._record("set_harness_template", {"project_id": project.id, "harness_template": harness_template}, run)

    def create_generation_jobs(self, *, deck_version: DeckVersion, slide_versions: list[SlideVersion], job_type: str) -> list[GenerationJob]:
        def run():
            jobs = []
            for slide_version in slide_versions:
                visual_plan = slide_version.current_visual_plan
                if not visual_plan:
                    raise ValueError(f"Slide {slide_version.id} has no visual plan")
                input_hash = hashlib.sha256(
                    json.dumps({
                        "slide_version_id": slide_version.id,
                        "visual_plan_id": visual_plan.id,
                        "slide_plan": slide_version.get_slide_plan(),
                        "visual_plan": visual_plan.get_plan(),
                    }, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest()
                idempotency_key = f"{job_type}:{slide_version.id}:{visual_plan.id}:{input_hash[:16]}"
                existing = GenerationJob.query.filter_by(idempotency_key=idempotency_key).first()
                if existing:
                    jobs.append(existing)
                    continue
                job = GenerationJob(
                    project_id=deck_version.project_id,
                    page_id=slide_version.page_id,
                    slide_version_id=slide_version.id,
                    visual_plan_version_id=visual_plan.id,
                    job_type=job_type,
                    idempotency_key=idempotency_key,
                    input_hash=input_hash,
                    status="pending",
                )
                db.session.add(job)
                jobs.append(job)
            db.session.flush()
            return {"generation_job_ids": [job.id for job in jobs]}

        result = self._record("generate_images_for_slides", {
            "deck_version_id": deck_version.id,
            "slide_version_ids": [slide.id for slide in slide_versions],
            "job_type": job_type,
        }, run)
        return GenerationJob.query.filter(GenerationJob.id.in_(result["generation_job_ids"])).all()

    def submit_image_generation(self, project: Project, page_ids: list[str], jobs: list[GenerationJob], *, job_type: str) -> Task:
        def run():
            pages = get_filtered_pages(project.id, page_ids)
            if not pages:
                raise ValueError("No pages selected")
            task = Task(user_id=current_user_id(), project_id=project.id, task_type="AGENT_STYLE_PREVIEW" if job_type == "style_preview" else "AGENT_GENERATE_IMAGES", status="PENDING")
            task.set_progress({"total": len(pages), "completed": 0, "failed": 0})
            db.session.add(task)
            db.session.flush()
            for job in jobs:
                job.task_id = task.id
                job.status = "queued"
            for page in pages:
                page.status = "QUEUED"
            db.session.flush()
            return {"task_id": task.id}

        result = self._record("generate_images_for_slides.submit", {"project_id": project.id, "page_ids": page_ids, "job_type": job_type}, run)
        task = Task.query.get(result["task_id"])

        file_service = FileService(current_app.config["UPLOAD_FOLDER"])
        ai_service = get_ai_service()
        outline = self._outline_for_pages(get_filtered_pages(project.id, None))
        app = current_app._get_current_object()
        task_manager.submit_task(
            task.id,
            generate_images_task,
            project.id,
            ai_service,
            file_service,
            outline,
            False,
            current_app.config.get("MAX_IMAGE_WORKERS", 4),
            project.image_aspect_ratio,
            current_app.config["DEFAULT_RESOLUTION"],
            app,
            None,
            current_app.config.get("OUTPUT_LANGUAGE", "zh"),
            page_ids,
        )
        return task

    @staticmethod
    def _description_text(slide: dict[str, Any]) -> str:
        points = "\n".join(f"- {point}" for point in slide.get("content_points", []))
        return f"{slide.get('title', '')}\n主旨：{slide.get('main_message', '')}\n{points}\n版式意图：{slide.get('layout_intent', '')}\n视觉焦点：{slide.get('visual_focus', '')}".strip()

    @staticmethod
    def _outline_for_pages(pages: list[Page]) -> list[dict[str, Any]]:
        outline = []
        for page in pages:
            item = page.get_outline_content() or {}
            if page.part:
                item["part"] = page.part
            outline.append(item)
        return outline

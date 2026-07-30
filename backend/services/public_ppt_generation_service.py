"""Public outline -> page descriptions -> images workflow."""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import current_app, g

from models import Page, Project, PublicPptGeneration, Task, UserTemplate, db
from services import FileService, InputGenerationOptions, InputGenerationService, ProjectContext
from services.credit_service import (
    attach_task_credit_progress,
    ensure_credits_available,
    estimate_operation,
    reserve_credits,
    settle_task_credits,
)
from services.harness_generation_service import (
    clear_harness_artifacts,
    enhance_project_context,
    ensure_page_visual_plans,
)
from services.harness_skills import list_scenario_pack_ids, normalize_pack_id
from services.task_manager import generate_images_task
from utils.validators import normalize_aspect_ratio


logger = logging.getLogger(__name__)


class IdempotencyConflict(ValueError):
    """The same idempotency key was reused with a different request body."""


def _canonical_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_outline(raw_outline: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_outline, list) or not raw_outline:
        raise ValueError("outline must be a non-empty array")

    max_pages = max(1, int(os.getenv("PUBLIC_API_MAX_PAGES", "30")))
    if len(raw_outline) > max_pages:
        raise ValueError(f"outline may contain at most {max_pages} pages")

    outline: list[dict[str, Any]] = []
    for index, raw_page in enumerate(raw_outline, start=1):
        if not isinstance(raw_page, dict):
            raise ValueError(f"outline page {index} must be an object")
        title = str(raw_page.get("title") or "").strip()
        if not title:
            raise ValueError(f"outline page {index} requires title")
        if len(title) > 300:
            raise ValueError(f"outline page {index} title must be at most 300 characters")
        points = raw_page.get("points") or []
        if not isinstance(points, list):
            raise ValueError(f"outline page {index} points must be an array")
        if len(points) > 50:
            raise ValueError(f"outline page {index} may contain at most 50 points")
        if any(not isinstance(point, str) for point in points):
            raise ValueError(f"outline page {index} points must contain strings only")
        normalized_points = [point.strip() for point in points if point.strip()]
        if any(len(point) > 2000 for point in normalized_points):
            raise ValueError(f"outline page {index} points must be at most 2000 characters each")
        page = {"title": title, "points": normalized_points}
        part = str(raw_page.get("part") or "").strip()
        if part:
            if len(part) > 200:
                raise ValueError(f"outline page {index} part must be at most 200 characters")
            page["part"] = part
        outline.append(page)
    return outline


def validate_request(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("JSON request body is required")

    outline = _validate_outline(data.get("outline"))
    visual = data.get("visual") or {}
    options = data.get("options") or {}
    if not isinstance(visual, dict) or not isinstance(options, dict):
        raise ValueError("visual and options must be objects")

    language = str(options.get("language") or "zh").strip().lower()
    if language not in {"zh", "en", "ja", "auto"}:
        raise ValueError("options.language must be zh, en, ja, or auto")
    detail_level = str(options.get("detail_level") or "default").strip().lower()
    if detail_level not in {"concise", "default", "detailed"}:
        raise ValueError("options.detail_level must be concise, default, or detailed")

    aspect_ratio = normalize_aspect_ratio(str(visual.get("aspect_ratio") or "16:9"))
    harness_template = normalize_pack_id(options.get("harness_template"))
    if harness_template and harness_template not in set(list_scenario_pack_ids()):
        raise ValueError(
            f"options.harness_template must be one of: {', '.join(sorted(list_scenario_pack_ids()))}"
        )

    template_id = str(visual.get("template_id") or "").strip() or None
    style = str(visual.get("style") or "").strip()
    if len(style) > 4000:
        raise ValueError("visual.style must be at most 4000 characters")
    if not template_id and not style and not harness_template:
        style = "专业商务演示，简洁清晰，统一版式，适合正式汇报"

    title = str(data.get("title") or outline[0]["title"]).strip()[:255]
    description_requirements = str(options.get("description_requirements") or "").strip()
    extra_requirements = str(options.get("extra_requirements") or "").strip()
    if len(description_requirements) > 8000 or len(extra_requirements) > 8000:
        raise ValueError("generation requirements must be at most 8000 characters")

    return {
        "title": title,
        "outline": outline,
        "visual": {
            "template_id": template_id,
            "style": style,
            "aspect_ratio": aspect_ratio,
        },
        "options": {
            "language": language,
            "detail_level": detail_level,
            "harness_template": harness_template,
            "description_requirements": description_requirements,
            "extra_requirements": extra_requirements,
        },
    }


def _outline_as_text(outline: list[dict[str, Any]]) -> str:
    blocks = []
    for index, page in enumerate(outline, start=1):
        lines = [f"第 {index} 页：{page['title']}"]
        lines.extend(f"- {point}" for point in page.get("points", []))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _attach_user_template(project: Project, template_id: str | None, user_id: str, file_service: FileService) -> None:
    if not template_id:
        return
    template = UserTemplate.query.filter_by(id=template_id, user_id=user_id).first()
    if not template:
        raise ValueError("visual.template_id was not found for this account")

    source = Path(file_service.get_absolute_path(template.file_path))
    if not source.is_file():
        raise ValueError("visual.template_id file is missing")
    target_dir = Path(file_service.upload_folder) / project.id / "template"
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() or ".png"
    target = target_dir / f"template{suffix}"
    shutil.copy2(source, target)
    project.template_image_path = target.relative_to(file_service.upload_folder).as_posix()


def create_generation(
    *,
    user_id: str,
    api_key_id: str,
    data: dict,
    idempotency_key: str | None,
) -> tuple[PublicPptGeneration, bool]:
    """Persist a queued public workflow and reserve both stage charges."""
    normalized = validate_request(data)
    idempotency_key = (idempotency_key or "").strip() or None
    if idempotency_key and len(idempotency_key) > 128:
        raise ValueError("Idempotency-Key must be at most 128 characters")

    if idempotency_key:
        existing = PublicPptGeneration.query.filter_by(
            user_id=user_id,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            if _canonical_json(existing.get_request_data()) != _canonical_json(normalized):
                raise IdempotencyConflict("Idempotency-Key was already used with a different request")
            return existing, False

    visual = normalized["visual"]
    options = normalized["options"]
    harness_template = options["harness_template"]
    page_count = len(normalized["outline"])
    description_estimate = estimate_operation("descriptions", page_count=page_count)
    image_estimate = estimate_operation("images", page_count=page_count)
    ensure_credits_available(user_id, description_estimate.amount + image_estimate.amount)

    project = Project(
        user_id=user_id,
        project_title=normalized["title"],
        creation_type="outline",
        outline_text=_outline_as_text(normalized["outline"]),
        description_requirements=options["description_requirements"] or None,
        extra_requirements=options["extra_requirements"] or None,
        template_style=visual["style"] or None,
        generation_mode="harness" if harness_template else "fast",
        harness_template=harness_template,
        visual_strategy="native",
        image_aspect_ratio=visual["aspect_ratio"],
        status="DRAFT",
    )
    db.session.add(project)
    db.session.flush()

    file_service = FileService(current_app.config["UPLOAD_FOLDER"])
    _attach_user_template(project, visual["template_id"], user_id, file_service)

    # Persist the supplied outline immediately; only descriptions and images use AI.
    generation_service = InputGenerationService(ai_service=None)
    pages = generation_service.save_pages(project.id, normalized["outline"], mode="replace")

    description_task = Task(
        user_id=user_id,
        project_id=project.id,
        task_type="PUBLIC_GENERATE_DESCRIPTIONS",
        status="PENDING",
    )
    description_task.set_progress({"stage": "descriptions", "total": page_count, "completed": 0, "failed": 0})
    image_task = Task(
        user_id=user_id,
        project_id=project.id,
        task_type="PUBLIC_GENERATE_IMAGES",
        status="PENDING",
    )
    image_task.set_progress({"stage": "images", "total": page_count, "completed": 0, "failed": 0})
    db.session.add_all([description_task, image_task])
    db.session.flush()

    reserve_credits(
        user_id=user_id,
        amount=description_estimate.amount,
        operation=description_estimate.operation,
        project_id=project.id,
        task_id=description_task.id,
        metadata={**description_estimate.details, "endpoint": "public_ppt_generation"},
    )
    reserve_credits(
        user_id=user_id,
        amount=image_estimate.amount,
        operation=image_estimate.operation,
        project_id=project.id,
        task_id=image_task.id,
        metadata={**image_estimate.details, "endpoint": "public_ppt_generation"},
    )
    attach_task_credit_progress(description_task, description_estimate)
    attach_task_credit_progress(image_task, image_estimate)

    generation = PublicPptGeneration(
        user_id=user_id,
        api_key_id=api_key_id,
        project_id=project.id,
        description_task_id=description_task.id,
        image_task_id=image_task.id,
        idempotency_key=idempotency_key,
        status="QUEUED",
        current_stage="descriptions",
        request_json="{}",
    )
    generation.set_request_data(normalized)
    db.session.add(generation)
    db.session.commit()
    return generation, True


def _mark_task_failed(task: Task | None, message: str) -> None:
    if not task or task.status in {"COMPLETED", "FAILED", "CANCELLED"}:
        return
    task.status = "FAILED"
    task.error_message = message
    task.completed_at = datetime.utcnow()


def fail_queued_generation(generation_id: str, message: str) -> None:
    """Fail a committed job when it could not be submitted to the worker."""
    generation = db.session.get(PublicPptGeneration, generation_id)
    if not generation:
        return
    generation.status = "FAILED"
    generation.current_stage = "failed"
    generation.error_message = message
    generation.completed_at = datetime.utcnow()
    _mark_task_failed(db.session.get(Task, generation.description_task_id), message)
    _mark_task_failed(db.session.get(Task, generation.image_task_id), message)
    settle_task_credits(generation.description_task_id, force_release=True)
    settle_task_credits(generation.image_task_id, force_release=True)
    project = db.session.get(Project, generation.project_id)
    if project:
        project.status = "FAILED"
    db.session.commit()


def run_generation(generation_id: str, ai_service, app) -> None:
    """Run both stages sequentially in a background worker."""
    with app.app_context():
        generation = db.session.get(PublicPptGeneration, generation_id)
        if not generation:
            logger.error("Public PPT generation %s not found", generation_id)
            return

        try:
            g.current_user = generation.api_key.user
            request_data = generation.get_request_data()
            outline = request_data["outline"]
            options = request_data["options"]
            project = db.session.get(Project, generation.project_id)
            description_task = db.session.get(Task, generation.description_task_id)

            generation.status = "PROCESSING"
            generation.current_stage = "descriptions"
            description_task.status = "PROCESSING"
            project.status = "GENERATING_DESCRIPTIONS"
            db.session.commit()

            generation_service = InputGenerationService(ai_service)
            project_context = enhance_project_context(project, ProjectContext(project, []))
            generation_options = InputGenerationOptions(
                input_kind="outline",
                target_depth="outline_and_descriptions",
                language=options["language"],
                detail_level=options["detail_level"],
            )
            descriptions = generation_service.build_descriptions(
                "outline",
                outline,
                project_context,
                generation_options,
            )
            clear_harness_artifacts(project.id)
            pages = generation_service.save_pages(project.id, outline, descriptions, mode="merge_by_index")
            ensure_page_visual_plans(project, pages)
            project.status = "DESCRIPTIONS_GENERATED"
            project.updated_at = datetime.utcnow()
            description_task.status = "COMPLETED"
            description_task.completed_at = datetime.utcnow()
            description_task.set_progress(
                {"stage": "descriptions", "total": len(pages), "completed": len(pages), "failed": 0}
            )
            settle_task_credits(
                description_task.id,
                completed_units=len(pages),
                total_units=len(pages),
            )

            generation.current_stage = "images"
            image_task = db.session.get(Task, generation.image_task_id)
            image_task.status = "PENDING"
            for page in pages:
                page.status = "QUEUED"
            db.session.commit()

            file_service = FileService(current_app.config["UPLOAD_FOLDER"])
            generate_images_task(
                image_task.id,
                project.id,
                ai_service,
                file_service,
                outline,
                bool(project.template_image_path),
                current_app.config.get("MAX_IMAGE_WORKERS", 8),
                project.image_aspect_ratio,
                current_app.config.get("DEFAULT_RESOLUTION", "2K"),
                app,
                project.extra_requirements or None,
                options["language"],
                None,
            )

            db.session.expire_all()
            generation = db.session.get(PublicPptGeneration, generation_id)
            image_task = db.session.get(Task, generation.image_task_id)
            image_progress = image_task.get_progress()
            failed = int(image_progress.get("failed") or 0)
            if image_task.status == "FAILED":
                generation.status = "FAILED"
                generation.current_stage = "failed"
                generation.error_message = image_task.error_message or "Image generation failed"
            elif failed:
                generation.status = "PARTIAL"
                generation.current_stage = "completed"
                generation.error_message = f"{failed} page image(s) failed"
            else:
                generation.status = "COMPLETED"
                generation.current_stage = "completed"
            generation.completed_at = datetime.utcnow()
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.exception("Public PPT generation %s failed", generation_id)
            generation = db.session.get(PublicPptGeneration, generation_id)
            if not generation:
                return
            generation.status = "FAILED"
            generation.current_stage = "failed"
            generation.error_message = str(exc)
            generation.completed_at = datetime.utcnow()
            description_task = db.session.get(Task, generation.description_task_id)
            image_task = db.session.get(Task, generation.image_task_id)
            _mark_task_failed(description_task, str(exc))
            _mark_task_failed(image_task, str(exc))
            settle_task_credits(generation.description_task_id, force_release=True)
            settle_task_credits(generation.image_task_id, force_release=True)
            project = db.session.get(Project, generation.project_id)
            if project:
                project.status = "FAILED"
            db.session.commit()

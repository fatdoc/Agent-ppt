"""Versioned public API for outline -> descriptions -> images."""
from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, current_app, g, request, send_file, url_for

from models import Page, PublicPptGeneration, Task, UserTemplate, db
from services.ai_service_manager import create_ai_service
from services.credit_service import InsufficientCredits
from services.public_ppt_generation_service import (
    IdempotencyConflict,
    create_generation,
    fail_queued_generation,
    run_generation,
    validate_request,
)
from services.task_manager import task_manager
from utils import error_response, not_found, success_response
from utils.api_key_auth import authenticate_api_key


logger = logging.getLogger(__name__)
public_ppt_bp = Blueprint("public_ppt", __name__, url_prefix="/v1")


@public_ppt_bp.before_request
def _authenticate_public_api():
    auth_error = authenticate_api_key("ppt:generate")
    if auth_error:
        return auth_error

    # Reuse the account's existing model configuration. In server-managed mode
    # this is a no-op; otherwise it mirrors the web API behavior.
    from app import _load_settings_to_config

    _load_settings_to_config(current_app._get_current_object(), g.current_user.id)
    return None


def _owned_generation(generation_id: str) -> PublicPptGeneration | None:
    return PublicPptGeneration.query.filter_by(
        id=generation_id,
        user_id=g.current_user.id,
    ).first()


def _generation_payload(generation: PublicPptGeneration) -> dict:
    data = generation.to_dict()
    description_task = db.session.get(Task, generation.description_task_id)
    image_task = db.session.get(Task, generation.image_task_id)
    active_task = image_task if description_task and description_task.status == "COMPLETED" else description_task
    progress = active_task.get_progress() if active_task else {}
    progress.setdefault("stage", generation.current_stage)
    progress["stages"] = {
        "descriptions": description_task.get_progress() if description_task else {},
        "images": image_task.get_progress() if image_task else {},
    }
    data["progress"] = progress
    data["links"] = {
        "self": url_for("public_ppt.get_generation", generation_id=generation.id),
        "pages": url_for("public_ppt.get_generation_pages", generation_id=generation.id),
    }
    return data


@public_ppt_bp.route("/ppt-generations", methods=["POST"])
def submit_generation():
    try:
        data = request.get_json(silent=True)
        validate_request(data)
        ai_service = create_ai_service()
        generation, created = create_generation(
            user_id=g.current_user.id,
            api_key_id=g.current_api_key.id,
            data=data,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        if created:
            app = current_app._get_current_object()
            try:
                task_manager.submit_task(generation.id, run_generation, ai_service, app)
            except Exception as exc:
                fail_queued_generation(generation.id, f"Failed to submit background task: {exc}")
                raise
        return success_response(
            _generation_payload(generation),
            message="Generation queued" if created else "Existing idempotent generation returned",
            status_code=202 if created else 200,
        )
    except IdempotencyConflict as exc:
        db.session.rollback()
        return error_response("IDEMPOTENCY_CONFLICT", str(exc), 409)
    except InsufficientCredits as exc:
        db.session.rollback()
        return error_response(
            "INSUFFICIENT_CREDITS",
            f"积分不足：需要 {exc.required}，当前可用 {exc.available}",
            402,
        )
    except ValueError as exc:
        db.session.rollback()
        return error_response("INVALID_REQUEST", str(exc), 400)
    except Exception:
        db.session.rollback()
        logger.exception("Failed to submit public PPT generation")
        return error_response("SERVER_ERROR", "Failed to submit generation", 500)


@public_ppt_bp.route("/ppt-generations/<generation_id>", methods=["GET"])
def get_generation(generation_id: str):
    generation = _owned_generation(generation_id)
    if not generation:
        return not_found("Generation")
    return success_response(_generation_payload(generation))


def _page_payload(generation: PublicPptGeneration, page: Page) -> dict:
    outline = page.get_outline_content() or {}
    description = page.get_description_content()
    image_url = None
    if page.generated_image_path:
        image_url = url_for(
            "public_ppt.get_page_image",
            generation_id=generation.id,
            page_id=page.id,
        )
    return {
        "page_id": page.id,
        "index": page.order_index + 1,
        "part": page.part,
        "title": outline.get("title"),
        "points": outline.get("points") or [],
        "description": description,
        "image": {"url": image_url} if image_url else None,
        "status": page.status,
    }


@public_ppt_bp.route("/ppt-generations/<generation_id>/pages", methods=["GET"])
def get_generation_pages(generation_id: str):
    generation = _owned_generation(generation_id)
    if not generation:
        return not_found("Generation")
    pages = Page.query.filter_by(project_id=generation.project_id).order_by(Page.order_index).all()
    return success_response(
        {
            "generation_id": generation.id,
            "status": generation.status,
            "pages": [_page_payload(generation, page) for page in pages],
        }
    )


@public_ppt_bp.route(
    "/ppt-generations/<generation_id>/pages/<page_id>/image",
    methods=["GET"],
)
def get_page_image(generation_id: str, page_id: str):
    generation = _owned_generation(generation_id)
    if not generation:
        return not_found("Generation")
    page = Page.query.filter_by(id=page_id, project_id=generation.project_id).first()
    if not page or not page.generated_image_path:
        return not_found("Image")

    upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    image_path = (upload_root / page.generated_image_path).resolve()
    if upload_root not in image_path.parents or not image_path.is_file():
        return not_found("Image")
    return send_file(image_path, as_attachment=False, download_name=image_path.name)


@public_ppt_bp.route("/templates", methods=["GET"])
def list_templates():
    templates = UserTemplate.query.filter_by(user_id=g.current_user.id).order_by(UserTemplate.created_at.desc()).all()
    return success_response(
        {
            "templates": [
                {
                    "template_id": template.id,
                    "name": template.name,
                    "created_at": template.created_at.isoformat() if template.created_at else None,
                }
                for template in templates
            ]
        }
    )

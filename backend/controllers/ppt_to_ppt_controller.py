"""
PPT-to-PPT project endpoint.
"""
import logging
from pathlib import Path

from flask import Blueprint, current_app, request

from models import Project, Task, db
from services import FileService
from services.ai_service_manager import get_ai_service
from services.credit_service import (
    InsufficientCredits,
    attach_task_credit_progress,
    estimate_operation,
    reserve_credits,
)
from services.ppt_to_ppt import (
    BlueprintService,
    PptToPptGenerationService,
    PptToPptOptions,
    ReferenceRenderer,
)
from services.task_manager import process_ppt_to_ppt_task, task_manager
from utils import bad_request, error_response, success_response

logger = logging.getLogger(__name__)

ppt_to_ppt_bp = Blueprint("ppt_to_ppt", __name__, url_prefix="/api/projects")


def _credit_error_response(exc: InsufficientCredits):
    return error_response(
        'INSUFFICIENT_CREDITS',
        f'积分不足：需要 {exc.required}，当前可用 {exc.available}',
        402,
    )


@ppt_to_ppt_bp.route("/ppt-to-ppt", methods=["POST"])
def create_ppt_to_ppt_project():
    """
    Create a PPT-to-PPT project from user content plus a reference deck.
    """
    temp_reference_path = None
    project = None
    task = None

    try:
        reference_file = request.files.get("reference_file")
        if not reference_file or not reference_file.filename:
            return bad_request("reference_file is required")

        content = (request.form.get("content") or "").strip()
        if not content:
            return bad_request("content is required")

        options = PptToPptOptions.from_form(request.form)
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        renderer = ReferenceRenderer(upload_folder)
        renderer.validate_reference_file(reference_file)
        template_image = request.files.get("template_image")
        if options.style_source == "template" and not options.template_style and not (
            template_image and template_image.filename
        ):
            return bad_request("template_style or template_image is required when style_source is template")

        project = Project(
            creation_type="ppt_to_ppt",
            idea_prompt=content,
            extra_requirements=options.extra_requirements,
            template_style=options.template_style,
            status="PROCESSING",
        )
        db.session.add(project)
        db.session.flush()

        if template_image and template_image.filename:
            file_service = FileService(upload_folder)
            project.template_image_path = file_service.save_template_image(template_image, project.id)

        temp_reference_path = _save_temp_reference_file(reference_file, project.id)
        reference_page_count = _count_reference_pages(temp_reference_path)
        estimated_reference_pages = reference_page_count or options.page_count or 10
        estimated_target_pages = options.page_count or estimated_reference_pages
        estimate = estimate_operation(
            'ppt_to_ppt',
            reference_page_count=estimated_reference_pages,
            target_page_count=estimated_target_pages,
        )

        task = Task(
            project_id=project.id,
            user_id=project.user_id,
            task_type="PPT_TO_PPT_ANALYSIS",
            status="PENDING",
        )
        task.set_progress({
            "total": 5,
            "completed": 0,
            "failed": 0,
            "current_step": "queued",
            "reference_page_count": reference_page_count,
        })
        db.session.add(task)
        db.session.flush()
        reserve_credits(
            user_id=project.user_id,
            amount=estimate.amount,
            operation=estimate.operation,
            project_id=project.id,
            task_id=task.id,
            metadata={**estimate.details, 'endpoint': 'create_ppt_to_ppt_project'},
        )
        attach_task_credit_progress(task, estimate)
        db.session.commit()

        ai_service = get_ai_service()
        blueprint_service = BlueprintService(ai_service)
        generation_service = PptToPptGenerationService(ai_service)
        app = current_app._get_current_object()
        task_manager.submit_task(
            task.id,
            process_ppt_to_ppt_task,
            project.id,
            str(temp_reference_path),
            renderer,
            blueprint_service,
            generation_service,
            request.form.to_dict(),
            app=app,
        )

        return success_response(
            {
                "project_id": project.id,
                "task_id": task.id,
                "reference_page_count": reference_page_count,
                "credit_estimate": estimate.to_dict(),
            }
        )
    except InsufficientCredits as exc:
        db.session.rollback()
        _cleanup_failed_create(project, task, temp_reference_path)
        return _credit_error_response(exc)
    except ValueError as exc:
        db.session.rollback()
        _cleanup_failed_create(project, task, temp_reference_path)
        return bad_request(str(exc))
    except Exception as exc:
        db.session.rollback()
        _cleanup_failed_create(project, task, temp_reference_path)
        logger.error("create_ppt_to_ppt_project failed: %s", exc, exc_info=True)
        return error_response("SERVER_ERROR", str(exc), 500)


def _save_temp_reference_file(reference_file, project_id: str) -> Path:
    filename = reference_file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".pptx", ".ppt"}:
        raise ValueError("Only PDF and PPT files are supported")

    temp_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "tmp" / "ppt_to_ppt"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{project_id}{suffix}"
    reference_file.save(str(temp_path))
    return temp_path


def _count_reference_pages(reference_path: Path) -> int | None:
    if reference_path.suffix.lower() != ".pdf":
        return None

    doc = None
    try:
        import fitz

        doc = fitz.open(str(reference_path))
        return len(doc)
    except Exception as exc:
        raise ValueError(f"Reference PDF could not be opened: {exc}") from exc
    finally:
        if doc is not None:
            doc.close()


def _cleanup_failed_create(project, task, temp_reference_path) -> None:
    if task and getattr(task, "id", None):
        db.session.delete(task)
    if project and getattr(project, "id", None):
        db.session.delete(project)
    if task or project:
        db.session.commit()

    if temp_reference_path:
        try:
            Path(temp_reference_path).unlink(missing_ok=True)
        except Exception:
            logger.warning("Failed to remove temp reference file %s", temp_reference_path)

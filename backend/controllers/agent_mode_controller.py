"""Agent Mode v1 API: structured planning, editable plans, style preview."""
from __future__ import annotations

from flask import Blueprint, current_app, request

from models import DeckVersion, GenerationJob, PageVisualPlan, SlideVersion, db
from services.agent_mode_schemas import hard_qa_page_visual_plan, validate_page_visual_plan, validate_slide_plan
from services.agent_mode_service import AgentModeService
from services.agent_mode_tools import AgentToolRegistry
from utils import bad_request, error_response, not_found, success_response
from utils.auth import owned_project_or_404


agent_mode_bp = Blueprint("agent_mode", __name__, url_prefix="/api/agent-mode")


@agent_mode_bp.route('/plans', methods=['POST'])
def create_agent_plan():
    try:
        data = request.get_json() or {}
        result = AgentModeService().create_agent_deck_plan(
            topic=str(data.get('topic') or '').strip(),
            audience=str(data.get('audience') or '').strip(),
            page_count=int(data.get('page_count') or 8),
            style=str(data.get('style') or '').strip(),
            generation_mode=str(data.get('generation_mode') or 'harness').strip(),
            harness_template=str(data.get('harness_template') or data.get('visual_strategy') or 'paper_operators').strip(),
            harness_payload=data.get('harness_payload') if isinstance(data.get('harness_payload'), dict) else None,
        )
        return success_response(result, status_code=201)
    except ValueError as exc:
        return bad_request(str(exc))
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("create_agent_plan failed")
        return error_response('SERVER_ERROR', str(exc), 500)


@agent_mode_bp.route('/projects/<project_id>/deck-versions/<deck_version_id>', methods=['GET'])
def get_agent_plan(project_id, deck_version_id):
    try:
        if not owned_project_or_404(project_id):
            return not_found('Project')
        return success_response(AgentModeService().get_deck_version(project_id, deck_version_id))
    except ValueError:
        return not_found('DeckVersion')


@agent_mode_bp.route('/projects/<project_id>/deck-versions/<deck_version_id>/slides/<slide_version_id>/content', methods=['PUT'])
def revise_slide_content(project_id, deck_version_id, slide_version_id):
    try:
        if not owned_project_or_404(project_id):
            return not_found('Project')
        slide = _get_slide_version(project_id, deck_version_id, slide_version_id)
        if slide.locked:
            return bad_request('Cannot overwrite locked slide')
        data = request.get_json() or {}
        plan = validate_slide_plan(data.get('slide_plan') or data)
        slide.set_slide_plan(plan)
        slide.status = 'pending_confirmation'
        slide.set_qa_result({'passed': True, 'issues': []})
        page = slide.page
        page.set_outline_content({'title': plan['title'], 'points': plan.get('content_points', [])})
        page.set_description_content({
            'text': AgentToolRegistry._description_text(plan),
            'main_message': plan.get('main_message'),
            'layout_intent': plan.get('layout_intent'),
            'visual_focus': plan.get('visual_focus'),
        })
        db.session.commit()
        return success_response(slide.to_dict())
    except ValueError as exc:
        db.session.rollback()
        return bad_request(str(exc))


@agent_mode_bp.route('/projects/<project_id>/deck-versions/<deck_version_id>/slides/<slide_version_id>/visual-plan', methods=['PUT'])
def revise_slide_visual_plan(project_id, deck_version_id, slide_version_id):
    try:
        if not owned_project_or_404(project_id):
            return not_found('Project')
        slide = _get_slide_version(project_id, deck_version_id, slide_version_id)
        if slide.locked:
            return bad_request('Cannot overwrite locked slide')
        data = request.get_json() or {}
        current_plan = slide.current_visual_plan
        if not current_plan:
            return bad_request('Slide has no visual plan')
        plan = current_plan.get_plan()
        plan.update(data.get('visual_plan') or data)
        plan['page_id'] = slide.page_id
        plan = validate_page_visual_plan(plan, {slide.page_id})
        qa = hard_qa_page_visual_plan(plan).to_dict()
        visual_plan = PageVisualPlan(
            project_id=project_id,
            page_id=slide.page_id,
            slide_version_id=slide.id,
            deck_visual_system_id=current_plan.deck_visual_system_id,
            strategy_id=current_plan.strategy_id,
            version_number=(current_plan.version_number or 1) + 1,
            status='pending_confirmation',
        )
        visual_plan.set_plan(plan)
        visual_plan.set_qa_result(qa)
        db.session.add(visual_plan)
        slide.status = 'pending_confirmation'
        db.session.commit()
        return success_response(slide.to_dict())
    except ValueError as exc:
        db.session.rollback()
        return bad_request(str(exc))


@agent_mode_bp.route('/projects/<project_id>/deck-versions/<deck_version_id>/slides/<slide_version_id>/lock', methods=['POST'])
def set_slide_lock(project_id, deck_version_id, slide_version_id):
    try:
        if not owned_project_or_404(project_id):
            return not_found('Project')
        slide = _get_slide_version(project_id, deck_version_id, slide_version_id)
        data = request.get_json() or {}
        slide.locked = bool(data.get('locked', True))
        slide.status = 'locked' if slide.locked else 'pending_confirmation'
        db.session.commit()
        return success_response(slide.to_dict())
    except ValueError as exc:
        return bad_request(str(exc))


@agent_mode_bp.route('/projects/<project_id>/deck-versions/<deck_version_id>/style-preview', methods=['POST'])
def generate_style_preview(project_id, deck_version_id):
    return _submit_generation(project_id, deck_version_id, job_type='style_preview', preview_only=True)


@agent_mode_bp.route('/projects/<project_id>/deck-versions/<deck_version_id>/generate-remaining', methods=['POST'])
def generate_remaining(project_id, deck_version_id):
    return _submit_generation(project_id, deck_version_id, job_type='batch_remaining', preview_only=False)


@agent_mode_bp.route('/projects/<project_id>/generation-jobs', methods=['GET'])
def list_generation_jobs(project_id):
    try:
        if not owned_project_or_404(project_id):
            return not_found('Project')
        jobs = GenerationJob.query.filter_by(project_id=project_id).order_by(GenerationJob.created_at.desc()).all()
        return success_response({'jobs': [job.to_dict() for job in jobs]})
    except Exception as exc:
        return error_response('SERVER_ERROR', str(exc), 500)


def _submit_generation(project_id: str, deck_version_id: str, *, job_type: str, preview_only: bool):
    try:
        project = owned_project_or_404(project_id)
        if not project:
            return not_found('Project')
        deck_version = DeckVersion.query.filter_by(project_id=project_id, id=deck_version_id).first()
        if not deck_version:
            return not_found('DeckVersion')
        data = request.get_json() or {}
        slide_ids = data.get('slide_version_ids')
        if slide_ids:
            slides = SlideVersion.query.filter(SlideVersion.deck_version_id == deck_version_id, SlideVersion.id.in_(slide_ids)).order_by(SlideVersion.order_index).all()
        elif preview_only:
            slides = AgentModeService().select_default_preview_slides(deck_version)
        else:
            preview_page_ids = {
                job.page_id for job in GenerationJob.query.filter_by(project_id=project_id, job_type='style_preview').all()
            }
            slides = [slide for slide in deck_version.slide_versions if slide.page_id not in preview_page_ids]
        slides = [slide for slide in slides if not slide.locked]
        if not slides:
            return bad_request('No unlocked slides selected')
        tools = AgentToolRegistry()
        jobs = tools.create_generation_jobs(deck_version=deck_version, slide_versions=slides, job_type=job_type)
        db.session.commit()
        task = tools.submit_image_generation(project, [slide.page_id for slide in slides], jobs, job_type=job_type)
        project.status = 'STYLE_PREVIEW_GENERATING' if preview_only else 'GENERATING_IMAGES'
        db.session.commit()
        return success_response({
            'task_id': task.id,
            'generation_jobs': [job.to_dict() for job in jobs],
            'page_ids': [slide.page_id for slide in slides],
        }, status_code=202)
    except ValueError as exc:
        db.session.rollback()
        return bad_request(str(exc))
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('agent generation submit failed')
        return error_response('SERVER_ERROR', str(exc), 500)


def _get_slide_version(project_id: str, deck_version_id: str, slide_version_id: str) -> SlideVersion:
    slide = (
        SlideVersion.query
        .join(DeckVersion, SlideVersion.deck_version_id == DeckVersion.id)
        .filter(DeckVersion.project_id == project_id, DeckVersion.id == deck_version_id, SlideVersion.id == slide_version_id)
        .first()
    )
    if not slide:
        raise ValueError('SlideVersion not found')
    return slide

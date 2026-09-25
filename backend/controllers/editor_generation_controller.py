"""Explicit billable conversion; intentionally NOT on Provider-free editor_bp."""
from flask import Blueprint, current_app, request
from time import monotonic
from models import db, Project, Page, Task
from models.editor_document import EditorDocument
from services.pptist_editor.generation import TASK_TYPE, GenerationError, capture_sources, generate_document
from services.credit_service import InsufficientCredits, estimate_operation, reserve_credits, attach_task_credit_progress, settle_task_credits
from services.provider_config import active_provider_snapshot
from services.task_manager import task_manager
from services.task_execution import TaskExecutionContext
from utils import success_response, error_response, not_found
from utils.auth import require_auth, owned_project_or_404, current_user_id

editor_generation_bp = Blueprint('editor_generation', __name__, url_prefix='/api/projects/<project_id>')


@editor_generation_bp.route('/editable-generation', methods=['GET', 'POST'])
@require_auth
def editable_generation(project_id):
    if not owned_project_or_404(project_id): return not_found('Project')
    try:
        if request.method == 'POST':
            body=request.get_json(silent=True)
            if body not in ({}, None): return error_response('INVALID_REQUEST', '转换范围为整个项目，不接受客户端文件路径或用户 ID', 400)
            # DB write lock makes duplicate submit / reservation atomic across
            # workers, not just within this Python process.
            db.session.execute(db.update(Project).where(Project.id==project_id).values(updated_at=Project.updated_at))
        doc=db.session.get(EditorDocument, project_id)
        task=Task.query.filter_by(project_id=project_id, user_id=current_user_id(), task_type=TASK_TYPE).order_by(Task.created_at.desc()).first()
        if doc:
            db.session.rollback()
            return success_response(dict(ready=True, editor_url=f'/project/{project_id}/editor', task=task.to_dict() if task else None))
        if request.method == 'GET' or (task and task.status in ('PENDING', 'PROCESSING')):
            result=dict(ready=False, task=task.to_dict() if task else None,
                        credit_estimate=estimate_operation('editable_export', page_count=Page.query.filter_by(project_id=project_id).count()).to_dict())
            db.session.rollback(); return success_response(result)
        sources=capture_sources(project_id)
        estimate=estimate_operation('editable_export', page_count=len(sources))
        task=Task(project_id=project_id, user_id=current_user_id(), task_type=TASK_TYPE, status='PENDING')
        db.session.add(task); db.session.flush()
        reserve_credits(user_id=current_user_id(), amount=estimate.amount, operation=estimate.operation,
                        project_id=project_id, task_id=task.id, metadata={**estimate.details, 'endpoint':'editable_generation'})
        attach_task_credit_progress(task, estimate)
        p=task.get_progress(); p.update(total=len(sources), completed=0, current_step='等待转换')
        task.set_progress(p); db.session.commit()
        try:
            task_manager.submit_task(task.id, generate_document, project_id=project_id, user_id=current_user_id(), sources=sources,
                                     app=current_app._get_current_object(), provider_snapshot=active_provider_snapshot(),
                                     execution_context=TaskExecutionContext(task.id, current_user_id(), project_id, deadline=monotonic()+max(900, 300*len(sources))))
        except Exception:
            task.status='FAILED'; task.error_message='转换任务提交失败，请重试'
            settle_task_credits(task.id, force_release=True); db.session.commit()
            return error_response('EDITOR_GENERATION_SUBMIT_FAILED', task.error_message, 503)
        return success_response(dict(ready=False, task=task.to_dict(), credit_estimate=estimate.to_dict()), status_code=202)
    except InsufficientCredits as exc:
        db.session.rollback(); return error_response('INSUFFICIENT_CREDITS', f'积分不足：需要 {exc.required}，当前可用 {exc.available}', 402)
    except (GenerationError, OSError):
        db.session.rollback(); return error_response('EDITOR_SOURCE_NOT_READY', '请确认所有页面已生成图片且文件完整，再生成可编辑 PPT', 400)

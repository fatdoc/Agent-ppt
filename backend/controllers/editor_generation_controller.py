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


def failed_page(task, pages):
    if not task or task.status != 'FAILED':
        return None
    progress = task.get_progress()
    page_id = progress.get('failed_page_id')
    if page_id:
        return next(((i + 1, page.id) for i, page in enumerate(pages) if page.id == page_id), None)
    # Compatibility for pre-diagnostics failures; never infer a packaging failure.
    import re
    match = re.fullmatch(r'正在转换第 (\d+)/(\d+) 页', progress.get('current_step', ''))
    if match and int(match[2]) == len(pages) and 1 <= int(match[1]) <= len(pages):
        index = int(match[1]) - 1
        return index + 1, pages[index].id
    return None


@editor_generation_bp.route('/editable-generation', methods=['GET', 'POST'])
@require_auth
def editable_generation(project_id):
    if not owned_project_or_404(project_id): return not_found('Project')
    try:
        validation_only = False
        if request.method == 'POST':
            body=request.get_json(silent=True)
            if body not in ({}, None, {'mode': 'validate_failed_page'}): return error_response('INVALID_REQUEST', '仅支持整套转换或验证失败页，不接受客户端路径、页 ID 或用户 ID', 400)
            validation_only = body == {'mode': 'validate_failed_page'}
            # DB write lock makes duplicate submit / reservation atomic across
            # workers, not just within this Python process.
            db.session.execute(db.update(Project).where(Project.id==project_id).values(updated_at=Project.updated_at))
        doc=db.session.get(EditorDocument, project_id)
        task=Task.query.filter_by(project_id=project_id, user_id=current_user_id(), task_type=TASK_TYPE).order_by(Task.created_at.desc()).first()
        if doc:
            db.session.rollback()
            return success_response(dict(ready=True, editor_url=f'/project/{project_id}/editor', task=task.to_dict() if task else None))
        pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
        target = failed_page(task, pages)
        if request.method == 'GET' or (task and task.status in ('PENDING', 'PROCESSING')):
            result=dict(ready=False, task=task.to_dict() if task else None,
                        credit_estimate=estimate_operation('editable_export', page_count=len(pages)).to_dict(),
                        validation_page_number=target[0] if target else None,
                        validation_credit_estimate=estimate_operation('editable_export', page_count=1).to_dict() if target else None)
            db.session.rollback(); return success_response(result)
        if validation_only and not target:
            db.session.rollback()
            return error_response('NO_FAILED_PAGE', '没有可单独验证的失败页，请刷新状态', 409)
        sources=capture_sources(project_id)
        estimate=estimate_operation('editable_export', page_count=1 if validation_only else len(sources))
        task=Task(project_id=project_id, user_id=current_user_id(), task_type=TASK_TYPE, status='PENDING')
        db.session.add(task); db.session.flush()
        reserve_credits(user_id=current_user_id(), amount=estimate.amount, operation=estimate.operation,
                        project_id=project_id, task_id=task.id, metadata={**estimate.details, 'endpoint':'editable_generation'})
        attach_task_credit_progress(task, estimate)
        p=task.get_progress(); p.update(total=1 if validation_only else len(sources), completed=0, current_step='等待验证' if validation_only else '等待转换',
                                       validation_only=validation_only, validation_page_number=target[0] if validation_only else None)
        task.set_progress(p); db.session.commit()
        try:
            task_manager.submit_task(task.id, generate_document, project_id=project_id, user_id=current_user_id(), sources=sources,
                                     validation_page_id=target[1] if validation_only else None,
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

"""
Project Controller - handles project-related endpoints
"""
import json
import logging
import os
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from sqlalchemy import desc
from utils.validators import normalize_aspect_ratio
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename

from models import db, Project, Page, Task, ReferenceFile
from services import (
    CompetitionDocumentEditService,
    CompetitionUnderstandingService,
    FileService,
    InputGenerationOptions,
    InputGenerationService,
    NoThinkOptions,
    NoThinkService,
    ProjectContext,
)
from services.ai_service_manager import get_ai_service
from services.competition_spec_state import merge_plain_values_into_state, normalize_spec_state, unwrap_spec_state
from services.task_manager import (
    task_manager,
    generate_descriptions_task,
    generate_images_task,
    process_ppt_renovation_task
)
from utils import (
    success_response, error_response, not_found, bad_request,
    parse_page_ids_from_body, get_filtered_pages, allowed_file
)
from utils.auth import current_user_id, owned_project_or_404

logger = logging.getLogger(__name__)

project_bp = Blueprint('projects', __name__, url_prefix='/api/projects')


def _is_ai_auth_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None) or getattr(error, "http_status", None)
    if status_code == 401:
        return True

    message = str(error).lower()
    auth_markers = (
        "invalid api key",
        "incorrect api key",
        "unauthorized",
        "401",
        "authentication",
        "api key",
    )
    return any(marker in message for marker in auth_markers)


def _ai_generation_error_response(error: Exception):
    if _is_ai_auth_error(error):
        provider = current_app.config.get("AI_PROVIDER_FORMAT") or "unknown"
        return error_response(
            "AI_SERVICE_AUTH_ERROR",
            f"AI 服务认证失败：当前模型配置（{provider}）的 API Key 无效或已过期。请在设置页更新密钥，或修改 .env 后重启后端。",
            503,
        )

    return error_response("AI_SERVICE_ERROR", str(error), 503)


def _build_competition_idea_prompt(spec: dict) -> str:
    spec = unwrap_spec_state(spec)
    positioning = spec.get('project_positioning') or {}
    problem = spec.get('problem_definition') or {}
    team_roles = spec.get('team_roles') or []
    skill_modules = spec.get('skill_modules') or []
    validation = spec.get('result_validation') or {}
    value = spec.get('value_innovation') or {}

    lines = [
        "职业教育争夺赛 PPT 生成需求",
        "固定主线：世界职业院校技能大赛/争夺赛",
        "生成目标：1小时现场技能展示作战稿",
        f"项目名称：{positioning.get('project_name') or '未命名项目'}",
        f"赛道/专业方向：{positioning.get('track') or positioning.get('industry') or '待补充'}",
        f"真实场景：{positioning.get('real_scene') or '待补充'}",
        f"服务对象：{positioning.get('service_object') or '待补充'}",
        f"最终成果形态：{positioning.get('final_deliverable') or '待补充'}",
        f"一句话介绍：{positioning.get('one_sentence_intro') or '待补充'}",
        f"真实问题：{'；'.join(problem.get('pain_points') or []) or '待补充'}",
        f"项目目标：{problem.get('project_goal') or '待补充'}",
        "四名选手分工：",
    ]
    for role in team_roles:
        lines.append(
            f"- {role.get('member') or ''} {role.get('role') or '待补充'}："
            f"{role.get('responsibility') or '待补充'}；现场动作：{role.get('onsite_action') or '待补充'}"
        )
    lines.append("技能展示模块：")
    for module in skill_modules:
        lines.append(
            f"- {module.get('skill_name') or '待补充'}：负责人 {module.get('responsible_role') or '待补充'}；"
            f"验证方式 {module.get('verification_method') or '待补充'}；"
            f"现场演示动作 {module.get('onsite_demo_action') or '待补充'}"
        )
    lines.extend([
        f"成果清单：{'；'.join(validation.get('deliverables') or []) or '待补充'}",
        f"证据材料：{'；'.join(validation.get('evidence_materials') or []) or '待补充'}",
        f"实用性：{value.get('practical_value') or '待补充'}",
        f"创新点：{'；'.join(value.get('innovation_points') or []) or '待补充'}",
        "表达约束：不要写营销路演、融资汇报或虚构收益；每页应服务于现场可演示的任务、动作、证据和评委理解。",
    ])
    return "\n".join(lines)


def _build_competition_dialogue_reply_prompt(source_text: str, draft_payload: dict) -> str:
    spec = unwrap_spec_state(draft_payload.get('competition_project_spec') or {})
    positioning = spec.get('project_positioning') or {}
    problem = spec.get('problem_definition') or {}
    missing_fields = draft_payload.get('missing_fields') or []
    risk_flags = draft_payload.get('risk_flags') or []
    latest_user_input = _extract_latest_user_instruction(source_text)
    missing_labels = _competition_missing_field_labels(missing_fields)

    return "\n".join([
        "你是一个大赛文档对话共创助手，正在和用户一起完善职业院校技能大赛项目文档。",
        "请根据本轮用户修改意见和已经生成的结构化稿件，给用户一个真实、简短、自然的对话回复。",
        "当前结构化结果是唯一可信状态；不要被本轮输入里出现的 Markdown 模板、待补充占位、历史脏内容误导。",
        "要求：",
        "1. 只输出聊天回复，不输出 JSON、代码块、完整结构化稿件。",
        "2. 语气像正在共同改稿的助手，说明本轮已经吸收了什么。",
        "3. 如果信息还缺，只能从【仍缺字段】里最多点出 2 个下一轮最该补充的问题。",
        "4. 控制在 80-140 个中文字符。",
        "5. 不使用 Markdown 加粗、标题、编号列表或项目符号，像聊天气泡里的自然短句。",
        "6. 不要建议用户补充当前结构化结果里已经有值的字段。",
        "",
        "【本轮用户修改意见】",
        (latest_user_input or "")[:1200],
        "",
        "【当前结构化结果摘要】",
        f"项目名称：{positioning.get('project_name') or '待补充'}",
        f"赛道/方向：{positioning.get('track') or positioning.get('industry') or '待补充'}",
        f"真实场景：{positioning.get('real_scene') or '待补充'}",
        f"服务对象：{positioning.get('service_object') or '待补充'}",
        f"项目目标：{problem.get('project_goal') or '待补充'}",
        f"痛点：{'；'.join(problem.get('pain_points') or []) or '待补充'}",
        f"仍缺字段：{'、'.join(missing_labels) if missing_labels else '无'}",
        f"风险提示：{'；'.join(risk_flags) if risk_flags else '无'}",
    ])


def _extract_latest_user_instruction(source_text: str) -> str:
    if not source_text:
        return ""
    marker = "【用户本轮修改意见或新增资料】"
    if marker in source_text:
        return source_text.rsplit(marker, 1)[-1].strip()
    return source_text.strip()


def _competition_missing_field_labels(missing_fields: list[str]) -> list[str]:
    label_map = {
        'project_positioning.project_name': '项目名称',
        'project_positioning.track_or_industry': '赛道/专业方向',
        'project_positioning.real_scene': '真实场景',
        'project_positioning.service_object': '服务对象',
        'project_positioning.final_deliverable': '最终成果形态',
        'problem_definition.pain_points': '真实痛点',
        'problem_definition.project_goal': '项目目标',
        'skill_modules': '技能展示模块',
        'result_validation.deliverables': '成果清单',
        'result_validation.evidence_materials': '证据材料',
        'value_innovation.practical_value_or_innovation_points': '实用性或创新点',
    }
    labels: list[str] = []
    for field in missing_fields:
        if field.startswith('team_roles.'):
            label = '四名选手分工'
        elif field.startswith('skill_modules.'):
            label = '技能展示模块'
        else:
            label = label_map.get(field, field)
        if label not in labels:
            labels.append(label)
    return labels


def _build_competition_dialogue_fallback_reply(draft_payload: dict) -> str:
    spec = unwrap_spec_state(draft_payload.get('competition_project_spec') or {})
    positioning = spec.get('project_positioning') or {}
    project_name = positioning.get('project_name') or draft_payload.get('project_title') or '当前项目'
    missing_fields = draft_payload.get('missing_fields') or []
    if missing_fields:
        return f"已把本轮内容同步进《{project_name}》的结构化稿件。接下来建议继续补充真实场景、选手动作和成果证据，方便后续生成 PPT 大纲。"
    return f"已把本轮内容同步进《{project_name}》的结构化稿件。当前核心信息比较完整，可以确认稿子后生成 PPT 大纲。"


def _get_project_reference_files_content(project_id: str) -> list:
    """
    Get reference files content for a project
    
    Args:
        project_id: Project ID
        
    Returns:
        List of dicts with 'filename' and 'content' keys
    """
    query = ReferenceFile.query.filter_by(
        project_id=project_id,
        parse_status='completed'
    )
    user_id = current_user_id()
    if user_id:
        query = query.filter(ReferenceFile.user_id == user_id)
    reference_files = query.all()
    
    files_content = []
    for ref_file in reference_files:
        if ref_file.markdown_content:
            files_content.append({
                'filename': ref_file.filename,
                'content': ref_file.markdown_content
            })
    
    return files_content


def _reconstruct_outline_from_pages(pages: list) -> list:
    """
    Reconstruct outline structure from Page objects
    
    Args:
        pages: List of Page objects ordered by order_index
        
    Returns:
        Outline structure (list) with optional part grouping
    """
    outline = []
    current_part = None
    current_part_pages = []
    
    for page in pages:
        outline_content = page.get_outline_content()
        if not outline_content:
            continue
            
        page_data = outline_content.copy()
        
        # 如果当前页面属于一个 part
        if page.part:
            # 如果这是新的 part，先保存之前的 part（如果有）
            if current_part and current_part != page.part:
                outline.append({
                    "part": current_part,
                    "pages": current_part_pages
                })
                current_part_pages = []
            
            current_part = page.part
            # 移除 part 字段，因为它在顶层
            if 'part' in page_data:
                del page_data['part']
            current_part_pages.append(page_data)
        else:
            # 如果当前页面不属于任何 part，先保存之前的 part（如果有）
            if current_part:
                outline.append({
                    "part": current_part,
                    "pages": current_part_pages
                })
                current_part = None
                current_part_pages = []
            
            # 直接添加页面
            outline.append(page_data)
    
    # 保存最后一个 part（如果有）
    if current_part:
        outline.append({
            "part": current_part,
            "pages": current_part_pages
        })
    
    return outline


def _smart_merge_pages(project_id, pages_data):
    """Position-based merge: reuse existing pages by index to preserve descriptions/images.

    For each new page at index i:
      - If an old page exists at the same position, update its outline (title/points/part)
        in place, keeping description_content and image fields untouched.
      - If no old page at that position, create a new page.
    Old pages beyond the new page count are deleted.
    """
    old_pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
    pages_list = []

    for i, page_data in enumerate(pages_data):
        if i < len(old_pages):
            page = old_pages[i]
        else:
            page = Page(project_id=project_id, status='DRAFT')
            db.session.add(page)

        page.order_index = i
        page.part = page_data.get('part')
        page.set_outline_content({
            'title': page_data.get('title'),
            'points': page_data.get('points', [])
        })
        pages_list.append(page)

    for p in old_pages[len(pages_data):]:
        db.session.delete(p)

    return pages_list


@project_bp.route('', methods=['GET'])
def list_projects():
    """
    GET /api/projects - Get all projects (for history)
    
    Query params:
    - limit: number of projects to return (default: 50, max: 100)
    - offset: offset for pagination (default: 0)
    """
    try:
        # Parameter validation
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        # Enforce limits to prevent performance issues
        limit = min(max(1, limit), 100)  # Between 1-100
        offset = max(0, offset)  # Non-negative

        # Get total count for pagination
        user_id = current_user_id()
        base_query = Project.query
        if user_id:
            base_query = base_query.filter(Project.user_id == user_id)

        total = base_query.count()

        projects = base_query\
            .options(joinedload(Project.pages))\
            .order_by(desc(Project.updated_at))\
            .limit(limit)\
            .offset(offset)\
            .all()

        return success_response({
            'projects': [project.to_dict(include_pages=True) for project in projects],
            'total': total,
            'limit': limit,
            'offset': offset
        })
    
    except Exception as e:
        logger.error(f"list_projects failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@project_bp.route('', methods=['POST'])
def create_project():
    """
    POST /api/projects - Create a new project
    
    Request body:
    {
        "creation_type": "idea|outline|descriptions",
        "idea_prompt": "...",  # required for idea type
        "outline_text": "...",  # required for outline type
        "description_text": "...",  # required for descriptions type
        "template_id": "optional"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return bad_request("Request body is required")
        
        # creation_type is required
        if 'creation_type' not in data:
            return bad_request("creation_type is required")
        
        creation_type = data.get('creation_type')
        
        if creation_type not in ['idea', 'outline', 'descriptions', 'no_think', 'ppt_renovation', 'ppt_to_ppt']:
            return bad_request("Invalid creation_type")
        
        # Validate and set aspect ratio if provided
        image_aspect_ratio = '16:9'
        if 'image_aspect_ratio' in data:
            try:
                image_aspect_ratio = normalize_aspect_ratio(data['image_aspect_ratio'])
            except ValueError as e:
                return bad_request(str(e))

        idea_prompt = data.get('idea_prompt')
        if creation_type == 'no_think':
            options = NoThinkOptions.from_dict(data.get('no_think_options'))
            idea_prompt = NoThinkService().normalize_prompt(idea_prompt, options)

        generation_mode = data.get('generation_mode') or 'fast'
        if generation_mode not in ['fast', 'harness']:
            return bad_request("Invalid generation_mode")
        harness_template = data.get('harness_template') if generation_mode == 'harness' else None
        if harness_template and harness_template not in ['paper-operators']:
            return bad_request("Invalid harness_template")

        # Create project
        project = Project(
            user_id=current_user_id(),
            creation_type=creation_type,
            idea_prompt=idea_prompt,
            outline_text=data.get('outline_text'),
            description_text=data.get('description_text'),
            template_style=data.get('template_style'),
            generation_mode=generation_mode,
            harness_template=harness_template,
            image_aspect_ratio=image_aspect_ratio,
            status='DRAFT'
        )
        
        db.session.add(project)
        db.session.commit()
        
        return success_response({
            'project_id': project.id,
            'status': project.status,
            'pages': []
        }, status_code=201)
    
    except BadRequest as e:
        # Handle JSON parsing errors (invalid JSON body)
        db.session.rollback()
        logger.warning(f"create_project: Invalid JSON body - {str(e)}")
        return bad_request("Invalid JSON in request body")
    
    except Exception as e:
        db.session.rollback()
        error_trace = traceback.format_exc()
        logger.error(f"create_project failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@project_bp.route('/understand', methods=['POST'])
def understand_project():
    """
    POST /api/projects/understand - Normalize precise vocational competition inputs.

    Request body:
    {
        "generation_mode": "precise",
        "project_id": "optional existing draft id",
        "input_mode": "raw_text|uploaded_file|structured_input",
        "raw_text": "...",
        "file_id": "...",
        "structured_input": {...}
    }
    """
    try:
        data = request.get_json()
        if not data:
            return bad_request("Request body is required")

        if data.get('generation_mode') != 'precise':
            return bad_request("generation_mode must be precise")

        input_mode = data.get('input_mode')
        service = CompetitionUnderstandingService()
        project_id = data.get('project_id')
        project = owned_project_or_404(project_id) if project_id else None
        if project_id and not project:
            return not_found('Project')
        base_spec = project.get_competition_project_spec() if project else None

        if input_mode == 'structured_input':
            incoming_state = normalize_spec_state(data.get('structured_input') or base_spec or {})
            result = service.build_from_structured_input(unwrap_spec_state(incoming_state))
            result.spec = merge_plain_values_into_state(incoming_state, result.spec, source="ai")
        elif input_mode == 'patch':
            edit_service = CompetitionDocumentEditService(get_ai_service())
            result = edit_service.apply_user_patch(
                data.get('structured_input') or base_spec or {},
                data.get('patch_ops') or [],
            )
        elif input_mode == 'raw_text':
            raw_text = data.get('raw_text') or ''
            if not raw_text.strip():
                return bad_request("raw_text is required")
            edit_service = CompetitionDocumentEditService(get_ai_service())
            result = edit_service.build_from_user_message(
                raw_text,
                current_spec=data.get('structured_input') or base_spec,
            )
        elif input_mode == 'uploaded_file':
            file_id = data.get('file_id')
            if not file_id:
                return bad_request("file_id is required")
            query = ReferenceFile.query.filter_by(id=file_id)
            user_id = current_user_id()
            if user_id:
                query = query.filter(ReferenceFile.user_id == user_id)
            reference_file = query.first()
            if not reference_file:
                return not_found('Reference file')
            edit_service = CompetitionDocumentEditService(get_ai_service())
            result = edit_service.build_from_reference_text(
                reference_file.markdown_content or '',
                current_spec=data.get('structured_input') or base_spec,
                filename=reference_file.filename or '',
            )
        else:
            return bad_request("input_mode must be raw_text, uploaded_file, structured_input, or patch")

        spec = result.spec
        plain_spec = unwrap_spec_state(spec)
        positioning = plain_spec.get('project_positioning') or {}
        project_title = positioning.get('project_name') or '职业教育争夺赛项目'
        idea_prompt = _build_competition_idea_prompt(spec)

        if project is None:
            project = Project(
                user_id=current_user_id(),
                creation_type='no_think',
                status='UNDERSTOOD',
            )
            db.session.add(project)

        project.project_title = project_title
        project.idea_prompt = idea_prompt
        project.status = 'UNDERSTOOD'
        project.set_competition_project_spec(spec)
        db.session.commit()

        return success_response({
            'project_id': project.id,
            'generation_mode': 'precise',
            'input_mode': input_mode,
            'project_title': project.project_title,
            'competition_project_spec': spec,
            'missing_fields': result.missing_fields,
            'risk_flags': result.risk_flags,
            'confidence': result.confidence,
            'input_quality': result.input_quality,
            'next_action': 'edit_structured_spec',
            'reply': getattr(result, 'reply', ''),
            'change_summary': getattr(result, 'change_summary', []),
            'destructive_changes': getattr(result, 'destructive_changes', []),
            'needs_confirmation': getattr(result, 'needs_confirmation', False),
            'questions': getattr(result, 'questions', []),
            'ops': getattr(result, 'ops', []),
            'rejected_ops': getattr(result, 'rejected_ops', []),
        }, status_code=201)

    except ValueError as e:
        db.session.rollback()
        return bad_request(str(e))

    except BadRequest:
        db.session.rollback()
        return bad_request("Invalid JSON in request body")

    except Exception as e:
        db.session.rollback()
        logger.error(f"understand_project failed: {str(e)}", exc_info=True)
        if _is_ai_auth_error(e):
            return _ai_generation_error_response(e)
        return error_response('SERVER_ERROR', str(e), 500)


@project_bp.route('/understand/stream', methods=['POST'])
def understand_project_stream():
    """
    POST /api/projects/understand/stream - Stream dialogue reply and draft updates via SSE.

    SSE events:
    - status: current workflow stage
    - draft: persisted structured draft
    - assistant_delta: assistant reply text delta from the configured model
    - done: stream finished
    - error: recoverable stream error
    """
    try:
        data = request.get_json()
        if not data:
            return bad_request("Request body is required")

        if data.get('generation_mode') != 'precise':
            return bad_request("generation_mode must be precise")

        input_mode = data.get('input_mode')
        if input_mode not in ('raw_text', 'uploaded_file', 'structured_input'):
            return bad_request("input_mode must be raw_text, uploaded_file, or structured_input")

        if input_mode == 'raw_text' and not (data.get('raw_text') or '').strip():
            return bad_request("raw_text is required")
        if input_mode == 'uploaded_file' and not data.get('file_id'):
            return bad_request("file_id is required")

        project_id = data.get('project_id')
        existing_project = owned_project_or_404(project_id) if project_id else None
        if project_id and not existing_project:
            return not_found('Project')
        base_spec = existing_project.get_competition_project_spec() if existing_project else None

        user_id = current_user_id()

        def sse_generate():
            try:
                yield _sse_event('status', {'message': '正在理解本轮输入'})

                if input_mode == 'structured_input':
                    service = CompetitionUnderstandingService()
                    incoming_state = normalize_spec_state(data.get('structured_input') or base_spec or {})
                    result = service.build_from_structured_input(unwrap_spec_state(incoming_state))
                    result.spec = merge_plain_values_into_state(incoming_state, result.spec, source="ai")
                    source_for_reply = json.dumps(unwrap_spec_state(incoming_state), ensure_ascii=False)
                elif input_mode == 'raw_text':
                    source_for_reply = data.get('raw_text') or ''
                    edit_service = CompetitionDocumentEditService(get_ai_service())
                    result = edit_service.build_from_user_message(
                        source_for_reply,
                        current_spec=data.get('structured_input') or base_spec,
                    )
                else:
                    file_id = data.get('file_id')
                    query = ReferenceFile.query.filter_by(id=file_id)
                    if user_id:
                        query = query.filter(ReferenceFile.user_id == user_id)
                    reference_file = query.first()
                    if not reference_file:
                        yield _sse_event('error', {'message': 'Reference file not found'})
                        return
                    source_for_reply = reference_file.markdown_content or reference_file.filename or ''
                    edit_service = CompetitionDocumentEditService(get_ai_service())
                    result = edit_service.build_from_reference_text(
                        reference_file.markdown_content or '',
                        current_spec=data.get('structured_input') or base_spec,
                        filename=reference_file.filename or '',
                    )

                spec = result.spec
                plain_spec = unwrap_spec_state(spec)
                positioning = plain_spec.get('project_positioning') or {}
                project_title = positioning.get('project_name') or '职业教育争夺赛项目'
                idea_prompt = _build_competition_idea_prompt(spec)

                project = existing_project
                if project is None:
                    project = Project(
                        user_id=user_id,
                        creation_type='no_think',
                        status='UNDERSTOOD',
                    )
                    db.session.add(project)

                project.project_title = project_title
                project.idea_prompt = idea_prompt
                project.status = 'UNDERSTOOD'
                project.set_competition_project_spec(spec)
                db.session.commit()

                draft_payload = {
                    'project_id': project.id,
                    'generation_mode': 'precise',
                    'input_mode': input_mode,
                    'project_title': project.project_title,
                    'competition_project_spec': spec,
                    'missing_fields': result.missing_fields,
                    'risk_flags': result.risk_flags,
                    'confidence': result.confidence,
                    'input_quality': result.input_quality,
                    'next_action': 'edit_structured_spec',
                    'reply': getattr(result, 'reply', ''),
                    'change_summary': getattr(result, 'change_summary', []),
                    'destructive_changes': getattr(result, 'destructive_changes', []),
                    'needs_confirmation': getattr(result, 'needs_confirmation', False),
                    'questions': getattr(result, 'questions', []),
                    'ops': getattr(result, 'ops', []),
                    'rejected_ops': getattr(result, 'rejected_ops', []),
                }
                yield _sse_event('draft', draft_payload)
                yield _sse_event('status', {'message': '正在生成本轮对话回复'})

                reply_text = getattr(result, 'reply', '') or _build_competition_dialogue_fallback_reply(draft_payload)
                yield _sse_event('assistant_delta', {'text': reply_text})

                yield _sse_event('done', {'project_id': project.id})

            except ValueError as e:
                db.session.rollback()
                yield _sse_event('error', {'message': str(e)})
            except Exception as e:
                db.session.rollback()
                logger.error(f"understand_project_stream failed: {str(e)}", exc_info=True)
                if _is_ai_auth_error(e):
                    yield _sse_event('error', {
                        'code': 'AI_SERVICE_AUTH_ERROR',
                        'message': 'AI 服务密钥无效或已过期。请先到设置页更新模型 API Key，或修改 .env 后重启后端。',
                    })
                else:
                    yield _sse_event('error', {'message': '流式对话生成失败'})

        return Response(
            stream_with_context(sse_generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache, no-transform',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive',
            },
        )

    except BadRequest:
        db.session.rollback()
        return bad_request("Invalid JSON in request body")
    except Exception as e:
        db.session.rollback()
        logger.error(f"understand_project_stream setup failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@project_bp.route('/<project_id>', methods=['GET'])
def get_project(project_id):
    """
    GET /api/projects/{project_id} - Get project details
    """
    try:
        # Use eager loading to load project and related pages
        query = Project.query.options(joinedload(Project.pages)).filter(Project.id == project_id)
        user_id = current_user_id()
        if user_id:
            query = query.filter(Project.user_id == user_id)
        project = query.first()
        
        if not project:
            return not_found('Project')
        
        return success_response(project.to_dict(include_pages=True))
    
    except Exception as e:
        logger.error(f"get_project failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@project_bp.route('/<project_id>', methods=['PUT'])
def update_project(project_id):
    """
    PUT /api/projects/{project_id} - Update project
    
    Request body:
    {
        "idea_prompt": "...",
        "pages_order": ["page-uuid-1", "page-uuid-2", ...]
    }
    """
    try:
        # Use eager loading to load project and pages (for page order updates)
        query = Project.query.options(joinedload(Project.pages)).filter(Project.id == project_id)
        user_id = current_user_id()
        if user_id:
            query = query.filter(Project.user_id == user_id)
        project = query.first()
        
        if not project:
            return not_found('Project')
        
        data = request.get_json()

        # Update project_title if provided
        if 'project_title' in data:
            project.project_title = data['project_title']
        
        # Update idea_prompt if provided
        if 'idea_prompt' in data:
            project.idea_prompt = data['idea_prompt']

        # Update outline_text if provided
        if 'outline_text' in data:
            project.outline_text = data['outline_text']

        # Update description_text if provided
        if 'description_text' in data:
            project.description_text = data['description_text']

        # Update extra_requirements if provided
        if 'extra_requirements' in data:
            project.extra_requirements = data['extra_requirements']

        # Update generation requirements if provided
        if 'outline_requirements' in data:
            project.outline_requirements = data['outline_requirements']
        if 'description_requirements' in data:
            project.description_requirements = data['description_requirements']

        if 'platform_context' in data:
            platform_context = data['platform_context']
            if platform_context is not None and not isinstance(platform_context, dict):
                return bad_request("platform_context must be an object")
            project.set_platform_context(platform_context)
        if 'outline_template_id' in data:
            project.outline_template_id = data['outline_template_id'] or None
        if 'ppt_template_id' in data:
            project.ppt_template_id = data['ppt_template_id'] or None
        
        # Update template_style if provided
        if 'template_style' in data:
            project.template_style = data['template_style']

        # Update generation mode if provided. This is independent from visual style control.
        if 'generation_mode' in data or 'harness_template' in data:
            generation_mode = data.get('generation_mode', project.generation_mode or 'fast')
            if generation_mode not in ['fast', 'harness']:
                return bad_request("Invalid generation_mode")
            harness_template = data.get('harness_template', project.harness_template)
            if generation_mode == 'harness' and harness_template and harness_template not in ['paper-operators']:
                return bad_request("Invalid harness_template")
            project.generation_mode = generation_mode
            project.harness_template = harness_template if generation_mode == 'harness' else None
        
        # Update aspect ratio if provided
        if 'image_aspect_ratio' in data:
            try:
                project.image_aspect_ratio = normalize_aspect_ratio(data['image_aspect_ratio'])
            except ValueError as e:
                return bad_request(str(e))

        # Update export settings if provided
        if 'export_extractor_method' in data:
            project.export_extractor_method = data['export_extractor_method']
        if 'export_inpaint_method' in data:
            project.export_inpaint_method = data['export_inpaint_method']
        if 'export_allow_partial' in data:
            project.export_allow_partial = data['export_allow_partial']
        if 'enable_icon_subject_extraction' in data:
            project.enable_icon_subject_extraction = bool(data['enable_icon_subject_extraction'])
        
        # Update page order if provided
        if 'pages_order' in data:
            pages_order = data['pages_order']
            # Optimization: batch query all pages to update, avoiding N+1 queries
            pages_to_update = Page.query.filter(
                Page.id.in_(pages_order),
                Page.project_id == project_id
            ).all()
            
            # Create page_id -> page mapping for O(1) lookup
            pages_map = {page.id: page for page in pages_to_update}
            
            # Batch update order
            for index, page_id in enumerate(pages_order):
                if page_id in pages_map:
                    pages_map[page_id].order_index = index
        
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        return success_response(project.to_dict(include_pages=True))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"update_project failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@project_bp.route('/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """
    DELETE /api/projects/{project_id} - Delete project
    """
    try:
        project = owned_project_or_404(project_id)
        
        if not project:
            return not_found('Project')
        
        # Delete project files
        from services import FileService
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        file_service.delete_project_files(project_id)
        
        # Delete project from database (cascade will delete pages and tasks)
        db.session.delete(project)
        db.session.commit()
        
        return success_response(message="Project deleted successfully")
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"delete_project failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@project_bp.route('/<project_id>/generate/outline', methods=['POST'])
def generate_outline(project_id):
    """
    POST /api/projects/{project_id}/generate/outline - Generate outline

    For 'idea' type: Generate outline from idea_prompt
    For 'outline' type: Parse outline_text into structured format
    For 'descriptions' type: Extract outline structure from description_text

    Request body (optional):
    {
        "idea_prompt": "...",  # for idea type
        "language": "zh"  # output language: zh, en, ja, auto
    }
    """
    try:
        project = owned_project_or_404(project_id)
        
        if not project:
            return not_found('Project')
        
        # Get singleton AI service instance
        ai_service = get_ai_service()
        
        # Get request data and language parameter
        data = request.get_json() or {}
        language = data.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))
        
        # Get reference files content and create project context
        reference_files_content = _get_project_reference_files_content(project_id)
        if reference_files_content:
            logger.info(f"Found {len(reference_files_content)} reference files for project {project_id}")
            for rf in reference_files_content:
                logger.info(f"  - {rf['filename']}: {len(rf['content'])} characters")
        else:
            logger.info(f"No reference files found for project {project_id}")
        
        if project.creation_type == 'outline':
            if not project.outline_text:
                return bad_request("outline_text is required for outline type project")
            input_kind = 'outline'
        elif project.creation_type == 'descriptions':
            if not project.description_text:
                return bad_request("description_text is required for descriptions type project")
            input_kind = 'description'
        elif project.creation_type == 'no_think':
            if not project.idea_prompt:
                return bad_request("idea_prompt is required for no_think type project")
            input_kind = 'no_think'
        else:
            idea_prompt = data.get('idea_prompt') or project.idea_prompt

            if not idea_prompt:
                return bad_request("idea_prompt is required")

            project.idea_prompt = idea_prompt
            input_kind = 'idea'

        requested_target_depth = data.get('target_depth')
        valid_target_depths = {'outline_only', 'outline_and_descriptions'}
        if requested_target_depth in valid_target_depths:
            target_depth = requested_target_depth
        else:
            target_depth = 'outline_only'

        existing_pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
        if existing_pages and not data.get('force'):
            logger.info(
                "generate_outline skipped existing result: project=%s status=%s pages=%s",
                project_id,
                project.status,
                len(existing_pages),
            )
            return success_response({
                'status': project.status,
                'pages': [page.to_dict() for page in existing_pages],
                'reused_existing': True,
            })

        if project.status == 'GENERATING_OUTLINE':
            logger.info("generate_outline already running: project=%s", project_id)
            return success_response({
                'status': 'GENERATING_OUTLINE',
                'pages': [],
                'in_progress': True,
            }, status_code=202)

        logger.info(
            "generate_outline request accepted: project=%s input_kind=%s target_depth=%s language=%s",
            project_id,
            input_kind,
            target_depth,
            language,
        )

        project.status = 'GENERATING_OUTLINE'
        db.session.commit()

        project_context = ProjectContext(project, reference_files_content)
        generation_service = InputGenerationService(ai_service)
        generation_service.generate(
            project,
            project_context,
            InputGenerationOptions(
                input_kind=input_kind,
                target_depth=target_depth,
                language=language,
                detail_level=data.get('detail_level'),
            ),
            save_mode='merge_by_index',
        )
        pages_list = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()

        db.session.commit()
        
        logger.info(f"大纲生成完成: 项目 {project_id}, 创建了 {len(pages_list)} 个页面")
        
        # Return pages
        return success_response({
            'pages': [page.to_dict() for page in pages_list]
        })
    
    except Exception as e:
        db.session.rollback()
        try:
            project = Project.query.get(project_id)
            if project and project.status == 'GENERATING_OUTLINE':
                project.status = 'UNDERSTOOD' if project.creation_type == 'no_think' else 'DRAFT'
                db.session.commit()
        except Exception:
            db.session.rollback()
        logger.error(f"generate_outline failed: {str(e)}", exc_info=True)
        return _ai_generation_error_response(e)


@project_bp.route('/<project_id>/generate/outline/stream', methods=['POST'])
def generate_outline_stream(project_id):
    """
    POST /api/projects/{project_id}/generate/outline/stream - Stream outline generation via SSE

    Streams pages one-by-one as they are generated. Each page is sent as an SSE event.
    After all pages are streamed, saves them to the database.

    SSE events:
      event: page    — a single page object {index, title, points, part?}
      event: done    — generation complete {total, pages: [...with ids...]}
      event: error   — error occurred {message}
    """
    # Validate project exists before entering the generator
    project = owned_project_or_404(project_id)
    if not project:
        return not_found('Project')

    data = request.get_json() or {}
    language = data.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))

    # Capture app reference for use inside the generator (which runs outside request context)
    app = current_app._get_current_object()

    def sse_generate():
        with app.app_context():
            try:
                # Re-fetch project inside app context to attach to this session
                proj = db.session.get(Project, project_id)
                ai_service = get_ai_service()
                if proj.creation_type == 'no_think' and proj.get_competition_project_spec():
                    reference_files_content = []
                else:
                    reference_files_content = _get_project_reference_files_content(project_id)

                # Validate input based on creation type
                if proj.creation_type == 'outline' and not proj.outline_text:
                    yield _sse_event('error', {'message': 'outline_text is required'})
                    return
                if proj.creation_type == 'descriptions' and not proj.description_text:
                    yield _sse_event('error', {'message': 'description_text is required'})
                    return

                # Update idea_prompt if provided
                if proj.creation_type not in ('outline', 'descriptions'):
                    idea_prompt = data.get('idea_prompt') or proj.idea_prompt
                    if not idea_prompt:
                        yield _sse_event('error', {'message': 'idea_prompt is required'})
                        return
                    proj.idea_prompt = idea_prompt

                project_context = ProjectContext(proj, reference_files_content)

                # Stream pages from AI
                streamed_pages = []
                stream_complete = False
                for page_data in ai_service.generate_outline_stream(project_context, language=language):
                    # Check for completion sentinel
                    if '__stream_complete__' in page_data:
                        stream_complete = page_data['__stream_complete__']
                        continue
                    i = len(streamed_pages)
                    streamed_pages.append(page_data)
                    yield _sse_event('page', {
                        'index': i,
                        'title': page_data.get('title', ''),
                        'points': page_data.get('points', []),
                        'part': page_data.get('part'),
                    })

                # Handle lock_page_count: pad with blank pages if needed
                lock_page_count = data.get('lock_page_count', False)
                if lock_page_count:
                    old_pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
                    old_count = len(old_pages)
                    new_count = len(streamed_pages)
                    if new_count < old_count:
                        for _ in range(old_count - new_count):
                            streamed_pages.append({'title': '', 'points': []})

                # Save all pages to database
                pages_list = _smart_merge_pages(project_id, streamed_pages)

                if all(p.description_content for p in pages_list) and pages_list:
                    proj.status = 'DESCRIPTIONS_GENERATED'
                else:
                    proj.status = 'OUTLINE_GENERATED'
                proj.updated_at = datetime.utcnow()
                db.session.commit()

                logger.info(f"流式大纲生成完成: 项目 {project_id}, {len(pages_list)} 个页面")

                yield _sse_event('done', {
                    'total': len(pages_list),
                    'pages': [p.to_dict() for p in pages_list],
                    'complete': stream_complete,
                })

            except Exception as e:
                try:
                    db.session.rollback()
                except Exception as rollback_exc:
                    logger.warning(f"Session rollback failed: {rollback_exc}", exc_info=True)
                logger.error(f"generate_outline_stream failed: {str(e)}", exc_info=True)
                yield _sse_event('error', {'message': '生成过程中发生内部错误'})

    return Response(
        stream_with_context(sse_generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-transform',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@project_bp.route('/<project_id>/generate/from-description', methods=['POST'])
def generate_from_description(project_id):
    """
    POST /api/projects/{project_id}/generate/from-description - Generate outline and page descriptions from description text
    
    This endpoint:
    1. Parses the description_text to extract outline structure
    2. Splits the description_text into individual page descriptions
    3. Creates pages with both outline and description content filled
    4. Sets project status to DESCRIPTIONS_GENERATED
    
    Request body (optional):
    {
        "description_text": "...",  # if not provided, uses project.description_text
        "language": "zh"  # output language: zh, en, ja, auto
    }
    """
    
    try:
        project = owned_project_or_404(project_id)
        
        if not project:
            return not_found('Project')
        
        if project.creation_type != 'descriptions':
            return bad_request("This endpoint is only for descriptions type projects")
        
        # Get description text and language
        data = request.get_json() or {}
        description_text = data.get('description_text') or project.description_text
        language = data.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))
        
        if not description_text:
            return bad_request("description_text is required")
        
        project.description_text = description_text
        
        # Get singleton AI service instance
        ai_service = get_ai_service()
        
        # Get reference files content and create project context
        reference_files_content = _get_project_reference_files_content(project_id)
        project_context = ProjectContext(project, reference_files_content)
        
        logger.info(f"开始从描述生成大纲和页面描述: 项目 {project_id}")

        generation_service = InputGenerationService(ai_service)
        generation_service.generate(
            project,
            project_context,
            InputGenerationOptions(
                input_kind='description',
                target_depth='outline_and_descriptions',
                language=language,
                detail_level=data.get('detail_level'),
            ),
            save_mode='replace',
        )
        pages_list = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()

        db.session.commit()
        
        logger.info(f"从描述生成完成: 项目 {project_id}, 创建了 {len(pages_list)} 个页面，已填充大纲和描述")
        
        # Return pages
        return success_response({
            'pages': [page.to_dict() for page in pages_list],
            'status': 'DESCRIPTIONS_GENERATED'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"generate_from_description failed: {str(e)}", exc_info=True)
        return error_response('AI_SERVICE_ERROR', str(e), 503)


@project_bp.route('/<project_id>/generate/descriptions', methods=['POST'])
def generate_descriptions(project_id):
    """
    POST /api/projects/{project_id}/generate/descriptions - Generate descriptions
    
    Request body:
    {
        "max_workers": 5,
        "language": "zh"  # output language: zh, en, ja, auto
    }
    """
    try:
        project = owned_project_or_404(project_id)
        
        if not project:
            return not_found('Project')
        
        if not project.pages:
            return bad_request("Project must have outline generated first")

        # IMPORTANT: Expire cached objects to ensure fresh data
        db.session.expire_all()
        
        # Get pages
        pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
        
        if not pages:
            return bad_request("No pages found for project")
        
        # Reconstruct outline from pages with part structure
        outline = _reconstruct_outline_from_pages(pages)
        
        data = request.get_json() or {}
        # 从配置中读取默认并发数，如果请求中提供了则使用请求的值
        max_workers = int(data.get('max_workers', current_app.config.get('MAX_DESCRIPTION_WORKERS', 4)))
        max_workers = max(1, min(max_workers, 20))
        language = data.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))
        detail_level = data.get('detail_level', 'default')
        logger.info(
            "generate_descriptions request accepted: project=%s pages=%s max_workers=%s language=%s",
            project_id,
            len(pages),
            max_workers,
            language,
        )
        
        # Create task
        task = Task(
            user_id=current_user_id(),
            project_id=project_id,
            task_type='GENERATE_DESCRIPTIONS',
            status='PENDING'
        )
        task.set_progress({
            'total': len(pages),
            'completed': 0,
            'failed': 0
        })
        
        db.session.add(task)
        db.session.commit()
        
        # Get singleton AI service instance
        ai_service = get_ai_service()
        
        # Get reference files content and create project context
        reference_files_content = _get_project_reference_files_content(project_id)
        project_context = ProjectContext(project, reference_files_content)
        
        # Get app instance for background task
        app = current_app._get_current_object()
        
        # Submit background task
        task_manager.submit_task(
            task.id,
            generate_descriptions_task,
            project_id,
            ai_service,
            project_context,
            outline,
            max_workers,
            app,
            language,
            detail_level
        )
        
        # Update project status
        project.status = 'GENERATING_DESCRIPTIONS'
        db.session.commit()
        
        return success_response({
            'task_id': task.id,
            'status': 'GENERATING_DESCRIPTIONS',
            'total_pages': len(pages)
        }, status_code=202)
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"generate_descriptions failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@project_bp.route('/<project_id>/generate/descriptions/stream', methods=['POST'])
def generate_descriptions_stream(project_id):
    """
    POST /api/projects/{project_id}/generate/descriptions/stream - Stream description generation via SSE

    Streams page descriptions one-by-one as they are generated by a single AI call.

    SSE events:
      event: description — {page_index, page_id, text, extra_fields?}
      event: done        — {total, pages: [...]}
      event: error       — {message}
    """
    project = owned_project_or_404(project_id)
    if not project:
        return not_found('Project')

    if not project.pages:
        return bad_request("Project must have outline generated first")

    data = request.get_json() or {}
    language = data.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))
    detail_level = data.get('detail_level', 'default')

    app = current_app._get_current_object()

    def sse_generate():
        with app.app_context():
            try:
                proj = db.session.get(Project, project_id)
                ai_service = get_ai_service()
                reference_files_content = _get_project_reference_files_content(project_id)
                project_context = ProjectContext(proj, reference_files_content)

                pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
                if not pages:
                    yield _sse_event('error', {'message': 'No pages found for project'})
                    return

                outline = _reconstruct_outline_from_pages(pages)
                flat_pages = ai_service.flatten_outline(outline)

                # Set all pages to GENERATING_DESCRIPTION
                for page in pages:
                    page.status = 'GENERATING_DESCRIPTION'
                proj.status = 'GENERATING_DESCRIPTIONS'
                db.session.commit()

                # Stream descriptions
                for result in ai_service.generate_descriptions_stream(
                    project_context, outline, flat_pages,
                    language=language, detail_level=detail_level
                ):
                    if '__stream_complete__' in result:
                        continue

                    idx = result.get('page_index', -1)
                    if idx < 0 or idx >= len(pages):
                        continue

                    page = pages[idx]
                    desc_content = {
                        'text': result.get('description_text', ''),
                        'generated_at': datetime.utcnow().isoformat(),
                    }
                    if result.get('extra_fields'):
                        desc_content['extra_fields'] = result['extra_fields']

                    page.set_description_content(desc_content)
                    page.status = 'DESCRIPTION_GENERATED'
                    page.updated_at = datetime.utcnow()
                    db.session.commit()

                    yield _sse_event('description', {
                        'page_index': idx,
                        'page_id': page.id,
                        'text': desc_content['text'],
                        'extra_fields': result.get('extra_fields'),
                    })

                # 检查是否所有页面都已生成描述
                missing = [p for p in pages if p.status == 'GENERATING_DESCRIPTION']
                if missing:
                    for p in missing:
                        # 有旧描述的保留，无描述的恢复 DRAFT
                        p.status = 'DESCRIPTION_GENERATED' if p.description_content else 'DRAFT'
                        p.updated_at = datetime.utcnow()
                    logger.warning(f"流式描述生成不完整: {len(missing)}/{len(pages)} 页未生成")

                proj.status = 'DESCRIPTIONS_GENERATED'
                proj.updated_at = datetime.utcnow()
                db.session.commit()

                # Re-fetch pages for final response
                pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
                yield _sse_event('done', {
                    'total': len(pages),
                    'pages': [p.to_dict() for p in pages],
                    **(({'warning': f'{len(missing)} 页描述未生成，请重试'}) if missing else {}),
                })

            except Exception as e:
                try:
                    db.session.rollback()
                except Exception as rollback_exc:
                    logger.warning(f"Session rollback failed: {rollback_exc}", exc_info=True)
                logger.error(f"generate_descriptions_stream failed: {str(e)}", exc_info=True)

                # 恢复未完成页面的状态：已生成描述的保留，未生成的恢复为 DRAFT
                try:
                    pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
                    proj = db.session.get(Project, project_id)
                    has_any_desc = False
                    for page in pages:
                        if page.status == 'GENERATING_DESCRIPTION':
                            # 如果之前就有描述内容，恢复为 DESCRIPTION_GENERATED
                            if page.description_content:
                                page.status = 'DESCRIPTION_GENERATED'
                                has_any_desc = True
                            else:
                                page.status = 'DRAFT'
                        elif page.status == 'DESCRIPTION_GENERATED':
                            has_any_desc = True
                    if proj:
                        proj.status = 'DESCRIPTIONS_GENERATED' if has_any_desc else 'OUTLINE_GENERATED'
                        proj.updated_at = datetime.utcnow()
                    db.session.commit()
                except Exception as recover_exc:
                    logger.warning(f"Failed to recover page statuses: {recover_exc}", exc_info=True)

                yield _sse_event('error', {'message': '生成过程中发生内部错误'})

    return Response(
        stream_with_context(sse_generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-transform',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@project_bp.route('/<project_id>/generate/images', methods=['POST'])
def generate_images(project_id):
    """
    POST /api/projects/{project_id}/generate/images - Generate images

    Request body:
    {
        "max_workers": 8,
        "use_template": true,
        "language": "zh",  # output language: zh, en, ja, auto
        "page_ids": ["id1", "id2"]  # optional: specific page IDs to generate (if not provided, generates all)
    }
    """
    try:
        project = owned_project_or_404(project_id)
        
        if not project:
            return not_found('Project')
        
        # if project.status not in ['DESCRIPTIONS_GENERATED', 'OUTLINE_GENERATED']:
        #     return bad_request("Project must have descriptions generated first")
        
        # IMPORTANT: Expire cached objects to ensure fresh data
        db.session.expire_all()
        
        data = request.get_json() or {}
        
        # Get page_ids from request body and fetch filtered pages
        selected_page_ids = parse_page_ids_from_body(data)
        pages = get_filtered_pages(project_id, selected_page_ids if selected_page_ids else None)
        
        if not pages:
            return bad_request("No pages found for project")
        
        # 检查是否有模板图片或风格描述
        from services import FileService
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        use_template = data.get('use_template', True)
        ref_image_path = None
        if use_template:
            ref_image_path = file_service.get_template_path(project_id)
        
        if not ref_image_path and not project.template_style:
            return bad_request("请先上传模板图片或添加风格描述。")
        
        # Reconstruct outline from pages with part structure
        outline = _reconstruct_outline_from_pages(pages)
        
        # 从配置中读取默认并发数，如果请求中提供了则使用请求的值
        max_workers = data.get('max_workers', current_app.config.get('MAX_IMAGE_WORKERS', 8))
        use_template = data.get('use_template', True)
        language = data.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))
        
        # Create task
        task = Task(
            user_id=current_user_id(),
            project_id=project_id,
            task_type='GENERATE_IMAGES',
            status='PENDING'
        )
        task.set_progress({
            'total': len(pages),
            'completed': 0,
            'failed': 0
        })
        
        db.session.add(task)
        db.session.commit()
        
        # Get singleton AI service instance
        ai_service = get_ai_service()
        
        extra_requirements = project.extra_requirements or ""
        
        # Set all target pages to QUEUED before submitting background task
        # This ensures the status is visible to frontend immediately after API returns
        for page in pages:
            page.status = 'QUEUED'
        db.session.commit()

        # Get app instance for background task
        app = current_app._get_current_object()

        # Submit background task
        task_manager.submit_task(
            task.id,
            generate_images_task,
            project_id,
            ai_service,
            file_service,
            outline,
            use_template,
            max_workers,
            project.image_aspect_ratio,
            current_app.config['DEFAULT_RESOLUTION'],
            app,
            extra_requirements if extra_requirements.strip() else None,
            language,
            selected_page_ids if selected_page_ids else None
        )
        
        # Update project status
        project.status = 'GENERATING_IMAGES'
        db.session.commit()
        
        return success_response({
            'task_id': task.id,
            'status': 'GENERATING_IMAGES',
            'total_pages': len(pages)
        }, status_code=202)
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"generate_images failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@project_bp.route('/<project_id>/tasks/<task_id>', methods=['GET'])
def get_task_status(project_id, task_id):
    """
    GET /api/projects/{project_id}/tasks/{task_id} - Get task status
    """
    try:
        task = Task.query.get(task_id)
        
        if not task or task.project_id != project_id:
            return not_found('Task')

        user_id = current_user_id()
        if task.user_id and user_id and task.user_id != user_id:
            return not_found('Task')
        if project_id not in ('global', 'settings-test'):
            project = owned_project_or_404(project_id)
            if not project:
                return not_found('Task')
        
        return success_response(task.to_dict())
    
    except Exception as e:
        logger.error(f"get_task_status failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


@project_bp.route('/<project_id>/refine/outline', methods=['POST'])
def refine_outline(project_id):
    """
    POST /api/projects/{project_id}/refine/outline - Refine outline based on user requirements
    
    Request body:
    {
        "user_requirement": "用户要求，例如：增加一页关于XXX的内容",
        "language": "zh"  # output language: zh, en, ja, auto
    }
    """
    try:
        project = owned_project_or_404(project_id)
        
        if not project:
            return not_found('Project')
        
        data = request.get_json()
        
        if not data or not data.get('user_requirement'):
            return bad_request("user_requirement is required")
        
        user_requirement = data['user_requirement']
        
        # IMPORTANT: Expire all cached objects to ensure we get fresh data from database
        # This prevents issues when multiple refine operations are called in sequence
        db.session.expire_all()
        
        # Get current outline from pages
        pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
        
        # Reconstruct current outline from pages (如果没有页面，使用空列表)
        if not pages:
            logger.info(f"项目 {project_id} 当前没有页面，将从空开始生成")
            current_outline = []  # 空大纲
        else:
            current_outline = _reconstruct_outline_from_pages(pages)
        
        # Get singleton AI service instance
        ai_service = get_ai_service()
        
        # Get reference files content and create project context
        reference_files_content = _get_project_reference_files_content(project_id)
        if reference_files_content:
            logger.info(f"Found {len(reference_files_content)} reference files for refine_outline")
            for rf in reference_files_content:
                logger.info(f"  - {rf['filename']}: {len(rf['content'])} characters")
        else:
            logger.info(f"No reference files found for project {project_id}")
        
        project_context = ProjectContext(project.to_dict(), reference_files_content)
        
        # Get previous requirements and language from request
        previous_requirements = data.get('previous_requirements', [])
        language = data.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))
        
        # Refine outline
        logger.info(f"开始修改大纲: 项目 {project_id}, 用户要求: {user_requirement}, 历史要求数: {len(previous_requirements)}")
        refined_outline = ai_service.refine_outline(
            current_outline=current_outline,
            user_requirement=user_requirement,
            project_context=project_context,
            previous_requirements=previous_requirements,
            language=language
        )
        
        # Flatten outline to pages and smart merge with existing
        pages_data = ai_service.flatten_outline(refined_outline)
        pages_list = _smart_merge_pages(project_id, pages_data)

        preserved_count = sum(1 for p in pages_list if p.description_content)
        new_count = len(pages_list) - preserved_count
        logger.info(f"描述匹配完成: 保留了 {preserved_count} 个页面的描述, {new_count} 个页面需要重新生成描述")

        # Update project status
        if preserved_count and all(p.description_content for p in pages_list):
            project.status = 'DESCRIPTIONS_GENERATED'
        else:
            project.status = 'OUTLINE_GENERATED'
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"大纲修改完成: 项目 {project_id}, 创建了 {len(pages_list)} 个页面")
        
        # Return pages
        return success_response({
            'pages': [page.to_dict() for page in pages_list],
            'message': '大纲修改成功'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"refine_outline failed: {str(e)}", exc_info=True)
        return error_response('AI_SERVICE_ERROR', str(e), 503)


@project_bp.route('/<project_id>/refine/descriptions', methods=['POST'])
def refine_descriptions(project_id):
    """
    POST /api/projects/{project_id}/refine/descriptions - Refine page descriptions based on user requirements
    
    Request body:
    {
        "user_requirement": "用户要求，例如：让描述更详细一些",
        "language": "zh"  # output language: zh, en, ja, auto
    }
    """
    try:
        project = owned_project_or_404(project_id)
        
        if not project:
            return not_found('Project')
        
        data = request.get_json()
        
        if not data or not data.get('user_requirement'):
            return bad_request("user_requirement is required")
        
        user_requirement = data['user_requirement']
        
        db.session.expire_all()
        
        # Get current pages
        pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
        
        if not pages:
            logger.info(f"项目 {project_id} 当前没有页面，无法修改描述")
            return bad_request("No pages found for project. Please generate outline first.")
        
        # Check if pages have descriptions (允许没有描述，从空开始)
        has_descriptions = any(page.description_content for page in pages)
        if not has_descriptions:
            logger.info(f"项目 {project_id} 当前没有描述，将基于大纲生成新描述")
        
        # Reconstruct outline from pages
        outline = _reconstruct_outline_from_pages(pages)
        
        # Prepare current descriptions
        current_descriptions = []
        for i, page in enumerate(pages):
            outline_content = page.get_outline_content()
            desc_content = page.get_description_content()
            
            current_descriptions.append({
                'index': i,
                'title': outline_content.get('title', '未命名') if outline_content else '未命名',
                'description_content': desc_content if desc_content else ''
            })
        
        # Get singleton AI service instance
        ai_service = get_ai_service()
        
        # Get reference files content and create project context
        reference_files_content = _get_project_reference_files_content(project_id)
        if reference_files_content:
            logger.info(f"Found {len(reference_files_content)} reference files for refine_descriptions")
            for rf in reference_files_content:
                logger.info(f"  - {rf['filename']}: {len(rf['content'])} characters")
        else:
            logger.info(f"No reference files found for project {project_id}")
        
        project_context = ProjectContext(project.to_dict(), reference_files_content)
        
        # Get previous requirements and language from request
        previous_requirements = data.get('previous_requirements', [])
        language = data.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))
        
        # Refine descriptions
        logger.info(f"开始修改页面描述: 项目 {project_id}, 用户要求: {user_requirement}, 历史要求数: {len(previous_requirements)}")
        refined_descriptions = ai_service.refine_descriptions(
            current_descriptions=current_descriptions,
            user_requirement=user_requirement,
            project_context=project_context,
            outline=outline,
            previous_requirements=previous_requirements,
            language=language
        )
        
        # 验证返回的描述数量
        if len(refined_descriptions) != len(pages):
            error_msg = ""
            logger.error(f"AI 返回的描述数量不匹配: 期望 {len(pages)} 个页面，实际返回 {len(refined_descriptions)} 个描述。")
            
            # 如果 AI 试图增删页面，给出明确提示
            if len(refined_descriptions) > len(pages):
                error_msg += " 提示：如需增加页面，请在大纲页面进行操作。"
            elif len(refined_descriptions) < len(pages):
                error_msg += " 提示：如需删除页面，请在大纲页面进行操作。"
            
            return bad_request(error_msg)
        
        # Update pages with refined descriptions
        for page, refined_desc in zip(pages, refined_descriptions):
            desc_content = {
                "text": refined_desc,
                "generated_at": datetime.utcnow().isoformat()
            }
            page.set_description_content(desc_content)
            page.status = 'DESCRIPTION_GENERATED'
        
        # Update project status
        project.status = 'DESCRIPTIONS_GENERATED'
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"页面描述修改完成: 项目 {project_id}, 更新了 {len(pages)} 个页面")
        
        # Return pages
        return success_response({
            'pages': [page.to_dict() for page in pages],
            'message': '页面描述修改成功'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"refine_descriptions failed: {str(e)}", exc_info=True)
        return error_response('AI_SERVICE_ERROR', str(e), 503)


@project_bp.route('/renovation', methods=['POST'])
def create_ppt_renovation_project():
    """
    POST /api/projects/renovation - Create a PPT renovation project

    Accepts a PDF/PPTX file upload, creates project with pages from PDF images,
    then submits an async task to parse content and fill outline + descriptions.

    Content-Type: multipart/form-data
    Form:
        file: PDF or PPTX file (required)
        keep_layout: "true"/"false" - whether to preserve layout via caption model (optional, default false)
        template_style: style description text (optional)
        template_image: style template image (optional)

    Returns:
        {project_id, task_id, page_count}
    """
    try:
        # Validate file
        if 'file' not in request.files:
            return bad_request("No file uploaded")

        file = request.files['file']
        if file.filename == '':
            return bad_request("No file selected")

        # Check file extension
        filename = file.filename.lower()
        if not (filename.endswith('.pdf') or filename.endswith('.pptx') or filename.endswith('.ppt')):
            return bad_request("Only PDF and PPTX files are supported")

        keep_layout = request.form.get('keep_layout', 'false').lower() == 'true'
        template_style = request.form.get('template_style', '').strip() or None
        language = request.form.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))
        template_image = request.files.get('template_image')
        if template_image and template_image.filename:
            if not allowed_file(template_image.filename, current_app.config['ALLOWED_EXTENSIONS']):
                return bad_request("Invalid template image type. Allowed types: png, jpg, jpeg, gif, webp")

        # Create project
        project = Project(
            creation_type='ppt_renovation',
            template_style=template_style,
            status='DRAFT'
        )
        db.session.add(project)
        db.session.commit()

        project_id = project.id

        # Save uploaded file
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        project_dir = Path(current_app.config['UPLOAD_FOLDER']) / project_id
        template_dir = project_dir / "template"
        template_dir.mkdir(parents=True, exist_ok=True)

        if template_image and template_image.filename:
            template_image_path = file_service.save_template_image(template_image, project_id)
            project.template_image_path = template_image_path
            db.session.commit()

        # Save original file with a standardized name to avoid encoding issues
        # (secure_filename strips non-ASCII chars, causing Chinese filenames like
        # '演示文稿.pdf' to become 'pdf' with no extension, breaking PDF discovery)
        original_ext = file.filename.rsplit('.', 1)[-1].lower()
        safe_name = f'original.{original_ext}'
        original_path = template_dir / safe_name
        file.save(str(original_path))

        # Convert PPTX to PDF if needed
        pdf_path = str(original_path)
        if safe_name.lower().endswith(('.pptx', '.ppt')):
            try:
                subprocess.run(
                    ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', str(template_dir), str(original_path)],
                    check=True, timeout=120, capture_output=True
                )
                pdf_name = safe_name.rsplit('.', 1)[0] + '.pdf'
                pdf_path = str(template_dir / pdf_name)
                if not os.path.exists(pdf_path):
                    raise ValueError("PDF conversion failed - output file not found")
                logger.info(f"Converted PPTX to PDF: {pdf_path}")
            except subprocess.TimeoutExpired:
                raise ValueError(
                    "PPTX 转 PDF 超时，请稍后重试或手动转为 PDF 后上传。"
                    if language == 'zh' else
                    "PPTX to PDF conversion timed out. Please retry or convert to PDF manually before uploading."
                )
            except FileNotFoundError:
                raise ValueError(
                    "PPTX 转换需要安装 LibreOffice，但当前环境未检测到。请在本地将 PPTX 转为 PDF 后再上传。"
                    if language == 'zh' else
                    "PPTX conversion requires LibreOffice, which is not installed. Please convert your PPTX to PDF locally before uploading."
                )

        # Convert PDF to page images using PyMuPDF or pdf2image
        pages_dir = project_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        page_image_paths = []
        pdf_page_width = None
        pdf_page_height = None
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            # Extract page dimensions from the first page before rendering
            if len(doc) > 0:
                rect = doc[0].rect
                pdf_page_width = rect.width
                pdf_page_height = rect.height
            for i, fitz_page in enumerate(doc):
                try:
                    mat = fitz.Matrix(2, 2)
                    pix = fitz_page.get_pixmap(matrix=mat)
                    img_path = str(pages_dir / f"page_{i + 1}_original.png")
                    pix.save(img_path)
                    page_image_paths.append(img_path)
                except Exception as e:
                    logger.error(f"Failed to render page {i + 1} with PyMuPDF: {e}")
                    page_image_paths.append(None)
            doc.close()
        except ImportError:
            # Fallback: use pdf2image
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(pdf_path, dpi=200)
                for i, img in enumerate(images):
                    try:
                        # Extract page dimensions from the first image
                        if pdf_page_width is None:
                            pdf_page_width = img.width
                            pdf_page_height = img.height
                        img_path = str(pages_dir / f"page_{i + 1}_original.png")
                        img.save(img_path, 'PNG')
                        page_image_paths.append(img_path)
                    except Exception as e:
                        logger.error(f"Failed to render page {i + 1} with pdf2image: {e}")
                        page_image_paths.append(None)
            except ImportError:
                raise ValueError("Neither PyMuPDF nor pdf2image is available for PDF rendering")

        # Fail-fast if no pages rendered at all
        valid_pages = [p for p in page_image_paths if p is not None]
        if not valid_pages:
            raise ValueError("All pages failed to render from PDF")

        logger.info(f"Rendered {len(valid_pages)}/{len(page_image_paths)} page images from PDF")

        # Set project aspect ratio from PDF page dimensions
        if pdf_page_width and pdf_page_height and pdf_page_width > 0 and pdf_page_height > 0:
            try:
                raw_ratio = f"{int(round(pdf_page_width))}:{int(round(pdf_page_height))}"
                project.image_aspect_ratio = normalize_aspect_ratio(raw_ratio)
                logger.info(f"Set project aspect ratio from PDF: {pdf_page_width}x{pdf_page_height} -> {project.image_aspect_ratio}")
            except (ValueError, OverflowError) as e:
                logger.warning(f"Could not normalize PDF aspect ratio ({pdf_page_width}x{pdf_page_height}): {e}, keeping default 16:9")

        # Create Page records with initial images
        from services.task_manager import save_image_with_version
        from PIL import Image as PILImage

        pages_list = []
        for i, img_path in enumerate(page_image_paths):
            if img_path is None:
                logger.warning(f"Skipping page {i + 1}: render failed")
                continue

            page = Page(
                project_id=project_id,
                order_index=len(pages_list),
                status='DRAFT'
            )
            page.set_outline_content({
                'title': f'Page {i + 1}',
                'points': []
            })
            db.session.add(page)
            db.session.flush()  # Get page.id

            # Save the PDF page image as initial version
            img = PILImage.open(img_path)
            image_path, _version = save_image_with_version(
                img, project_id, page.id, file_service, page_obj=page
            )
            img.close()

            pages_list.append(page)

        db.session.commit()

        # Create async task
        task = Task(
            user_id=current_user_id(),
            project_id=project_id,
            task_type='PPT_RENOVATION',
            status='PENDING'
        )
        task.set_progress({
            'total': len(pages_list),
            'completed': 0,
            'failed': 0,
            'current_step': 'queued'
        })
        db.session.add(task)
        db.session.commit()

        # Get services
        ai_service = get_ai_service()
        from services.file_parser_service import FileParserService
        file_parser_service = FileParserService(
            mineru_token=current_app.config['MINERU_TOKEN'],
            mineru_api_base=current_app.config['MINERU_API_BASE'],
            google_api_key=current_app.config.get('GOOGLE_API_KEY', ''),
            google_api_base=current_app.config.get('GOOGLE_API_BASE', ''),
            openai_api_key=current_app.config.get('OPENAI_API_KEY', ''),
            openai_api_base=current_app.config.get('OPENAI_API_BASE', ''),
            image_caption_model=current_app.config['IMAGE_CAPTION_MODEL'],
            provider_format=current_app.config.get('AI_PROVIDER_FORMAT', 'gemini'),
            lazyllm_image_caption_source=current_app.config.get('IMAGE_CAPTION_MODEL_SOURCE', 'doubao'),
            mineru_provider=current_app.config.get('MINERU_PROVIDER', 'cloud'),
            local_api_base=current_app.config.get('MINERU_LOCAL_API_BASE', 'http://127.0.0.1:8000'),
            local_backend=current_app.config.get('MINERU_LOCAL_BACKEND', 'pipeline'),
            local_parse_method=current_app.config.get('MINERU_LOCAL_PARSE_METHOD', 'auto'),
            local_return_images=current_app.config.get('MINERU_LOCAL_RETURN_IMAGES', True),
            local_response_format_zip=current_app.config.get('MINERU_LOCAL_RESPONSE_FORMAT_ZIP', True),
            local_return_original_file=current_app.config.get('MINERU_LOCAL_RETURN_ORIGINAL_FILE', False),
        )

        app = current_app._get_current_object()

        # Submit async task
        task_manager.submit_task(
            task.id,
            process_ppt_renovation_task,
            project_id,
            ai_service,
            file_service,
            file_parser_service,
            keep_layout,
            5,  # max_workers
            app,
            language
        )

        project.status = 'PROCESSING'
        db.session.commit()

        return success_response({
            'project_id': project_id,
            'task_id': task.id,
            'page_count': len(pages_list)
        }, status_code=202)

    except Exception as e:
        db.session.rollback()
        logger.error(f"create_ppt_renovation_project failed: {str(e)}", exc_info=True)
        return error_response('SERVER_ERROR', str(e), 500)


# Style extraction blueprint (not bound to any project)
style_bp = Blueprint('style', __name__, url_prefix='/api')


@style_bp.route('/extract-style', methods=['POST'])
def extract_style():
    """
    POST /api/extract-style - Extract style description from an image

    Content-Type: multipart/form-data
    Form:
        image: Image file (required)

    Returns:
        {style_description: "..."}
    """
    try:
        if 'image' not in request.files:
            return bad_request("No image file uploaded")

        file = request.files['image']
        if file.filename == '':
            return bad_request("No file selected")

        # Save to temp location
        import tempfile

        ext = secure_filename(file.filename).rsplit('.', 1)[-1].lower() if '.' in file.filename else 'png'
        with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            ai_service = get_ai_service()
            style_description = ai_service.extract_style_description(tmp_path)

            return success_response({
                'style_description': style_description
            })
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"extract_style failed: {str(e)}", exc_info=True)
        return error_response('AI_SERVICE_ERROR', str(e), 503)

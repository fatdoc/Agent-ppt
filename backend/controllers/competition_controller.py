"""Edition-gated education API. Authentication, credits and providers are shared."""

from flask import Blueprint, Response, current_app, request
from models import Page, Project, Task, db
from models.competition import (
    CompetitionDocument,
    CompetitionOperation,
    CompetitionRevision,
)
from services.ai_service_manager import get_ai_service
from services.competition.content import (
    STYLES,
    VISUAL_EVIDENCE_RULES,
    Conflict,
    digest,
    dumps,
    export_markdown,
    initial_content,
    is_team_page,
    new_id,
    parse_import,
    required,
    save_content,
    structure_warnings,
    validate_content,
)
from services.competition.generation import run_text_task, source_context
from services.credit_service import (
    InsufficientCredits,
    attach_task_credit_progress,
    estimate_operation,
    reserve_credits,
    settle_task_credits,
)
from services.file_service import FileService
from services.task_manager import generate_images_task, task_manager
from sqlalchemy.exc import IntegrityError
from utils import error_response, not_found, success_response
from utils.auth import current_user_id, owned_project_or_404, require_auth

competition_bp = Blueprint("competition", __name__)
ACTIVE = {"PENDING", "PROCESSING", "RUNNING"}


@competition_bp.before_request
def education_only():
    if current_app.config.get("APP_EDITION", "general") != "education":
        return not_found("Education")


@competition_bp.errorhandler(ValueError)
def invalid(exc):
    db.session.rollback()
    return error_response(
        "COMPETITION_CONFLICT" if isinstance(exc, Conflict) else "COMPETITION_INVALID",
        str(exc),
        409 if isinstance(exc, Conflict) else 400,
    )


@competition_bp.errorhandler(TypeError)
@competition_bp.errorhandler(KeyError)
@competition_bp.errorhandler(AttributeError)
def malformed(exc):
    db.session.rollback()
    return error_response(
        "COMPETITION_INVALID", "请求字段格式错误，请检查内容后重试", 400
    )


@competition_bp.errorhandler(InsufficientCredits)
def no_credits(exc):
    db.session.rollback()
    return error_response("INSUFFICIENT_CREDITS", str(exc), 402)


@competition_bp.errorhandler(IntegrityError)
def duplicate(exc):
    db.session.rollback()
    return error_response(
        "COMPETITION_CONFLICT", "请求已提交或内容已更新，请刷新后重试", 409
    )


def get_document(project_id, write=False):
    project = owned_project_or_404(project_id)
    if project is None:
        return None, None
    if write:
        # Consistent lock order across education writes, also serializes task admission.
        db.session.execute(
            db.update(Project)
            .where(Project.id == project_id)
            .values(updated_at=Project.updated_at)
        )
    doc = db.session.get(CompetitionDocument, project_id)
    return project, doc


def assert_editable(project_id):
    busy = Task.query.filter(
        Task.project_id == project_id,
        Task.status.in_(ACTIVE),
        Task.task_type.in_(["GENERATE_IMAGES", "GENERATE_EDITOR_DOCUMENT"]),
    ).first()
    if busy:
        raise Conflict("图片生成或可编辑转换正在进行，请完成后再修改内容")


def snapshot(project, doc):
    data = doc.content()
    task = db.session.get(Task, doc.active_task_id) if doc.active_task_id else None
    pages = Page.query.filter_by(project_id=project.id).order_by(Page.order_index).all()
    trial = []
    for pred in [
        lambda p: p["kind"] == "cover",
        is_team_page,
        lambda p: p["chapter"] == 3 and p["kind"] == "content",
    ]:
        p = next((p for p in data["pages"] if pred(p) and p["id"] not in trial), None)
        if p:
            trial.append(p["id"])
    for p in data["pages"]:
        if len(trial) >= 3:
            break
        if p["id"] not in trial:
            trial.append(p["id"])
    remaining = [p.id for p in pages if not p.generated_image_path]
    return {
        "project_id": project.id,
        "revision": doc.revision,
        "content": data,
        "pages": [p.to_dict() for p in pages],
        "warnings": data["warnings"] + structure_warnings(data),
        "task": task.to_dict() if task else None,
        "default_trial_page_ids": trial,
        "remaining_page_ids": remaining,
        "styles": STYLES,
        "template_image_path": project.template_image_path,
        "image_unit_estimate": estimate_operation("images", page_count=1).amount,
        "estimates": {
            "plan": estimate_operation(
                "outline_and_descriptions",
                page_count=data["preferences"]["target_pages"],
            ).to_dict(),
            "messages": estimate_operation("page_description", page_count=1).to_dict(),
            "trial": estimate_operation("images", page_count=len(trial)).to_dict()
            if trial
            else None,
            "remaining": estimate_operation(
                "images", page_count=len(remaining)
            ).to_dict()
            if remaining
            else None,
            "editable": estimate_operation(
                "editable_export", page_count=len(pages)
            ).to_dict()
            if pages
            else None,
        },
    }


@competition_bp.route("/api/competition/projects", methods=["GET", "POST"])
@require_auth
def education_projects():
    if request.method == "GET":
        from services.competition.space import visible_query
        rows = (
            visible_query(Project.query, Project, 'project').join(
                CompetitionDocument, Project.id == CompetitionDocument.project_id
            )
            .filter(Project.user_id == current_user_id())
            .order_by(Project.updated_at.desc())
            .limit(100)
            .all()
        )
        return success_response([p.to_dict() for p in rows])
    body = request.get_json(silent=True) or {}
    name = body.get("name", "未命名竞赛项目")
    required(
        isinstance(name, str) and 0 < len(name.strip()) <= 255, "请输入有效项目名称"
    )
    p = Project(
        user_id=current_user_id(),
        project_title=name,
        creation_type="idea",
        idea_prompt=name,
    )
    db.session.add(p)
    db.session.flush()
    data = initial_content(name)
    doc = CompetitionDocument(project_id=p.id, revision=1, payload=dumps(data))
    db.session.add(doc)
    db.session.add(
        CompetitionRevision(project_id=p.id, revision=1, payload=dumps(data))
    )
    db.session.commit()
    return success_response(snapshot(p, doc), status_code=201)


@competition_bp.route(
    "/api/projects/<project_id>/competition", methods=["GET", "PATCH"]
)
@require_auth
def document(project_id):
    p, doc = get_document(project_id, request.method == "PATCH")
    if not p or not doc:
        return not_found("Competition")
    if request.method == "PATCH":
        assert_editable(project_id)
        body = request.get_json(silent=True) or {}
        required(type(body.get("revision")) is int, "必须提供内容版本")
        patch = body.get("patch", {})
        required(
            isinstance(patch, dict)
            and set(patch)
            <= {
                "profile",
                "preferences",
                "locks",
                "raw_material",
                "reference_file_ids",
                "pages",
                "checklist",
                "bindings",
            },
            "修改字段无效",
        )
        data = doc.content()
        for k, v in patch.items():
            data[k] = v
        if "pages" in patch and patch["pages"] != doc.content()["pages"]:
            old = {x["id"]: x for x in doc.content()["pages"]}
            for page in data["pages"]:
                before = old.get(page.get("id"))
                if before and any(
                    page.get(k) != before.get(k)
                    for k in ["title", "text", "layout", "materials"]
                ):
                    page.pop("original_description", None)
            ids = {x["id"] for x in data["pages"]}
            data["bindings"] = [b for b in data["bindings"] if b["page_id"] in ids]
            for item in data["checklist"]:
                previous_ids = item["page_ids"]
                item["page_ids"] = [i for i in previous_ids if i in ids]
                if previous_ids and not item["page_ids"]:
                    item["status"] = "原关联页已移除，待重新关联"
                    item["action"] = (
                        "请确认此事项仍适用并重新关联页面。" + item["action"]
                    )
            data["imported_outline"] = ""
            data["imported_descriptions"] = ""
        save_content(doc, data, body["revision"], p)
        db.session.commit()
    return success_response(snapshot(p, doc))


@competition_bp.route("/api/projects/<project_id>/competition/import", methods=["POST"])
@require_auth
def import_content(project_id):
    p, doc = get_document(project_id, True)
    if not p or not doc:
        return not_found("Competition")
    assert_editable(project_id)
    body = request.get_json(silent=True) or {}
    required(type(body.get("revision")) is int, "必须提供内容版本")
    required(
        not any(x.get("locked") for x in doc.content()["pages"]),
        "请先解除页面锁定，再导入新稿件",
    )
    outline = body.get("outline", "")
    descriptions = body.get("descriptions", "")
    required(
        isinstance(outline, str)
        and isinstance(descriptions, str)
        and max(len(outline), len(descriptions)) <= 250000,
        "导入内容无效或过长",
    )
    data = parse_import(outline, descriptions, doc.content())
    save_content(doc, data, body["revision"], p)
    db.session.commit()
    return success_response(snapshot(p, doc))


@competition_bp.route(
    "/api/projects/<project_id>/competition/exports/<kind>", methods=["GET"]
)
@require_auth
def content_export(project_id, kind):
    p, doc = get_document(project_id)
    if not p or not doc:
        return not_found("Competition")
    required(kind in {"outline", "descriptions", "checklist"}, "导出类型无效")
    from pathlib import Path
    text = export_markdown(doc.content())[kind]
    folder = Path(current_app.config['UPLOAD_FOLDER']) / project_id / 'exports'
    folder.mkdir(parents=True, exist_ok=True)
    labels = {'outline': '大纲', 'descriptions': '逐页描述', 'checklist': '待补清单'}
    (folder / f'{labels[kind]}-v{doc.revision}.md').write_text(text, encoding='utf-8')
    return Response(
        text,
        mimetype="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{kind}.md"'},
    )


@competition_bp.route(
    "/api/projects/<project_id>/competition/revisions", methods=["GET"]
)
@require_auth
def revisions(project_id):
    p, doc = get_document(project_id)
    if not p or not doc:
        return not_found("Competition")
    rows = (
        CompetitionRevision.query.filter_by(project_id=project_id)
        .order_by(CompetitionRevision.revision.desc())
        .limit(100)
        .all()
    )
    return success_response(
        [{"revision": r.revision, "created_at": r.created_at.isoformat()} for r in rows]
    )


@competition_bp.route(
    "/api/projects/<project_id>/competition/restore", methods=["POST"]
)
@require_auth
def restore(project_id):
    p, doc = get_document(project_id, True)
    if not p or not doc:
        return not_found("Competition")
    assert_editable(project_id)
    body = request.get_json(silent=True) or {}
    row = CompetitionRevision.query.filter_by(
        project_id=project_id, revision=body.get("restore_revision")
    ).first()
    required(row is not None, "内容版本不存在")
    import json

    save_content(doc, json.loads(row.payload), body.get("revision"), p)
    db.session.commit()
    return success_response(snapshot(p, doc))


@competition_bp.route(
    "/api/projects/<project_id>/competition/<action>", methods=["POST"]
)
@require_auth
def launch(project_id, action):
    required(action in {"plan", "messages", "images"}, "任务类型无效")
    p, doc = get_document(project_id, True)
    if not p or not doc:
        return not_found("Competition")
    body = request.get_json(silent=True) or {}
    key = body.get("request_key")
    required(isinstance(key, str) and 1 <= len(key) <= 80, "必须提供请求标识")
    request_hash = digest({"action": action, **body})
    previous = CompetitionOperation.query.filter_by(
        project_id=project_id, request_key=key
    ).first()
    if previous:
        if previous.request_hash != request_hash:
            raise Conflict("请求标识已用于其他内容")
        task = db.session.get(Task, previous.task_id)
        return success_response(
            {"task": task.to_dict(), "revision": doc.revision}, status_code=202
        )
    if doc.revision != body.get("revision"):
        raise Conflict("内容已更新，请刷新后重新提交")
    active = db.session.get(Task, doc.active_task_id) if doc.active_task_id else None
    if active and active.status in ACTIVE:
        raise Conflict("已有任务进行中，请等待完成")
    assert_editable(project_id)
    data = doc.content()
    validate_content(data, p)
    if action == "images":
        ids = body.get("page_ids")
        required(
            isinstance(ids, list) and ids and len(ids) == len(set(ids)),
            "请选择不重复的试稿或生成页面",
        )
        available = {x.id: x for x in Page.query.filter_by(project_id=project_id).all()}
        required(set(ids) <= available.keys(), "生成页面不属于项目")
        # Successful pages are reused; retry only missing/invalidated pages.
        ids = [i for i in ids if not available[i].generated_image_path]
        required(ids, "所选页面已有成稿，无需重复生成；修改内容后才会重新生成")
        estimate = estimate_operation("images", page_count=len(ids))
        task_type = "GENERATE_IMAGES"
    else:
        source_context(p, data)
        if action == "messages":
            message = body.get("message", "")
            required(
                isinstance(message, str) and 0 < len(message.strip()) <= 10000,
                "请输入补充要求",
            )
            data["messages"].append({"id": new_id(), "role": "user", "text": message})
            save_content(doc, data, doc.revision, p)
        estimate = estimate_operation(
            "page_description" if action == "messages" else "outline_and_descriptions",
            page_count=1
            if action == "messages"
            else data["preferences"]["target_pages"],
        )
        task_type = (
            "COMPETITION_MESSAGE" if action == "messages" else "COMPETITION_PLAN"
        )
    task = Task(
        project_id=project_id,
        user_id=current_user_id(),
        task_type=task_type,
        status="PENDING",
    )
    task.set_progress(
        {
            "current_step": "等待处理",
            "completed": 0,
            "total": len(ids)
            if action == "images"
            else data["preferences"]["target_pages"],
        }
    )
    db.session.add(task)
    db.session.flush()
    reserve_credits(
        user_id=current_user_id(),
        amount=estimate.amount,
        operation=estimate.operation,
        project_id=project_id,
        task_id=task.id,
        metadata=estimate.details,
    )
    attach_task_credit_progress(task, estimate)
    db.session.add(
        CompetitionOperation(
            project_id=project_id,
            request_key=key,
            request_hash=request_hash,
            task_id=task.id,
        )
    )
    doc.active_task_id = task.id
    if action == "images":
        for pid in ids:
            available[pid].status = "QUEUED"
        p.status = "GENERATING_IMAGES"
    db.session.commit()
    result = {"task": task.to_dict(), "revision": doc.revision}
    try:
        if action == "images":
            outline = [
                {"title": x["title"], "points": x["text"]} for x in data["pages"]
            ]
            task_manager.submit_task(
                task.id,
                generate_images_task,
                project_id,
                get_ai_service(),
                FileService(current_app.config["UPLOAD_FOLDER"]),
                outline,
                use_template=True,
                max_workers=min(4, current_app.config["MAX_IMAGE_WORKERS"]),
                aspect_ratio="16:9",
                resolution=current_app.config["DEFAULT_RESOLUTION"],
                app=current_app._get_current_object(),
                extra_requirements="\n".join(
                    filter(None, [p.extra_requirements, VISUAL_EVIDENCE_RULES])
                ),
                language="zh",
                page_ids=ids,
            )
        else:
            task_manager.submit_task(
                task.id,
                run_text_task,
                project_id=project_id,
                revision=doc.revision,
                payload=data,
                action=action,
                message=body.get("message", ""),
                page_id=body.get("page_id"),
                convert=body.get("convert_structure") is True,
                app=current_app._get_current_object(),
            )
    except Exception:
        task.status = "FAILED"
        task.error_message = "任务提交失败，请重试"
        settle_task_credits(task.id, force_release=True)
        db.session.commit()
        return error_response("COMPETITION_SUBMIT_FAILED", task.error_message, 503)
    return success_response(result, status_code=202)


@competition_bp.route(
    "/api/projects/<project_id>/competition/template", methods=["POST", "DELETE"]
)
@require_auth
def template(project_id):
    from utils import allowed_file

    p, doc = get_document(project_id, True)
    if not p or not doc:
        return not_found("Competition")
    assert_editable(project_id)
    body = request.get_json(silent=True) or {}
    revision = (
        request.form.get("revision")
        if request.method == "POST"
        else body.get("revision")
    )
    required(str(revision) == str(doc.revision), "内容已更新，请刷新后修改模板")
    if request.method == "POST":
        file = request.files.get("template_image")
        required(
            file
            and allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]),
            "请上传支持的模板图片",
        )
        p.template_image_path = FileService(
            current_app.config["UPLOAD_FOLDER"]
        ).save_template_image(file, project_id)
    else:
        p.template_image_path = None
    data = doc.content()
    save_content(doc, data, doc.revision, p)
    for page in Page.query.filter_by(project_id=project_id):
        page.generated_image_path = None
        page.cached_image_path = None
        page.status = "DESCRIPTIONS_GENERATED"
    db.session.commit()
    return success_response(snapshot(p, doc))


def protect_education_content():
    """Legacy mutators cannot bypass the canonical record or running-job lock."""
    if current_app.config.get("APP_EDITION") != "education" or request.method in {
        "GET",
        "HEAD",
        "OPTIONS",
    }:
        return
    if request.blueprint not in {"projects", "pages", "templates"}:
        return
    pid = (request.view_args or {}).get("project_id")
    if not pid:
        return
    if db.session.get(CompetitionDocument, pid) and owned_project_or_404(pid):
        return error_response(
            "COMPETITION_CANONICAL_REQUIRED",
            "请在竞赛工作台修改内容、模板或生成页面，以保持大纲和描述同步",
            409,
        )

"""Education-only file organization and reversible project lifecycle."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4
import shutil
from flask import Blueprint, current_app, request, send_file, make_response
from models import db, Project, Material, ReferenceFile, Task
from models.competition import CompetitionDocument
from models.education_space import EducationSpaceEntry
from services.competition.space import (
    ACTIVE,
    inventory,
    owned_resource,
    safe_path,
    usage_map,
    is_trashed,
)
from services.competition.content import save_content, Conflict
from utils import success_response, error_response, not_found
from utils.auth import current_user_id, require_auth, owned_project_or_404

space_bp = Blueprint("education_space", __name__, url_prefix="/api/competition/space")


def protect_recycled_resources():
    if (
        current_app.config.get("APP_EDITION") != "education"
        or request.blueprint == "education_space"
    ):
        return
    args = request.view_args or {}
    for key, kind in [
        ("file_id", "reference"),
        ("material_id", "material"),
        ("project_id", "project"),
    ]:
        if args.get(key) and is_trashed(kind, args[key]):
            return not_found("File")


@space_bp.before_request
def gate():
    if current_app.config.get("APP_EDITION") != "education":
        return not_found("Education")


@space_bp.errorhandler(ValueError)
def invalid(exc):
    db.session.rollback()
    return error_response("SPACE_CONFLICT", str(exc), 409)


@space_bp.route("", methods=["GET"])
@require_auth
def listing():
    return success_response({"items": inventory()})


@space_bp.route("/<kind>/<ident>", methods=["PATCH"])
@require_auth
def update(kind, ident):
    row = owned_resource(kind, ident)
    if not row:
        return not_found("File")
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return error_response("INVALID_BODY", "请求内容格式无效", 400)
    action = body.get("action")
    if action not in {"permanent", "trash", "restore", "rename"}:
        return error_response("INVALID_ACTION", "操作无效", 400)
    key = f"{kind}:{ident}"
    meta = db.session.get(EducationSpaceEntry, key)
    linked = usage_map().get(key, set()) if kind != "project" else set()
    if kind != "project" and row.project_id:
        linked.add(row.project_id)
    if not meta:
        meta = EducationSpaceEntry(
            key=key,
            user_id=current_user_id(),
            category=(
                "projects"
                if kind == "project"
                else "permanent" if linked else "temporary"
            ),
        )
        db.session.add(meta)
    if action == "restore":
        if meta.category == "trash":
            meta.category = meta.previous_category or (
                "projects" if kind == "project" else "temporary"
            )
            meta.deleted_at = None
    else:
        if meta.category == "trash":
            raise Conflict("请先从回收站恢复")
        if (
            kind == "project"
            and Task.query.filter(
                Task.project_id == ident, Task.status.in_(ACTIVE)
            ).first()
        ):
            raise Conflict("作品任务仍在进行，完成后再操作")
        if kind == "reference" and row.parse_status == "parsing":
            raise Conflict("材料正在解析，完成后再操作")
        if action == "trash":
            if linked:
                raise Conflict(
                    "文件仍关联作品，请先在作品中解除关联；回收站中的作品也保留素材引用"
                )
            meta.previous_category = meta.category
            meta.category = "trash"
            meta.deleted_at = datetime.utcnow()
        elif action == "permanent":
            if kind == "project":
                raise Conflict("作品不需要转为长期文件")
            meta.category = "permanent"
        elif action == "rename":
            name = body.get("name")
            if (
                not isinstance(name, str)
                or not name.strip()
                or len(name.strip()) > 200
                or any(c in name for c in "/\\")
                or any(ord(c) < 32 for c in name)
            ):
                return error_response(
                    "INVALID_NAME", "名称须为 1–200 个字符，且不能包含路径分隔符", 400
                )
            if kind == "project":
                db.session.execute(
                    db.update(Project)
                    .where(Project.id == ident)
                    .values(updated_at=Project.updated_at)
                )
                doc = db.session.get(CompetitionDocument, ident)
                content = doc.content()
                content["profile"]["name"] = name.strip()
                save_content(doc, content, doc.revision, row)
            else:
                old_suffix = Path(
                    row.original_filename or row.filename
                    if kind == "material"
                    else row.filename
                ).suffix
                meta.display_name = (
                    name.strip()
                    if name.lower().endswith(old_suffix.lower())
                    else name.strip() + old_suffix
                )
    db.session.commit()
    return success_response({"key": key, "category": meta.category})


@space_bp.route("/<kind>/<ident>/download", methods=["GET"])
@require_auth
def download(kind, ident):
    row = owned_resource(kind, ident)
    if not row or is_trashed(kind, ident):
        return not_found("File")
    if kind == "project":
        filename = request.args.get("filename", "")
        if not filename or Path(filename).name != filename or "\\" in filename:
            return not_found("File")
        path = safe_path(f"{ident}/exports/{filename}")
        name = filename
    else:
        path = safe_path(row.relative_path if kind == "material" else row.file_path)
        meta = db.session.get(EducationSpaceEntry, f"{kind}:{ident}")
        name = (meta.display_name if meta else None) or (
            row.original_filename or row.filename
            if kind == "material"
            else row.filename
        )
    if not path:
        return not_found("File")
    return send_file(path, as_attachment=True, download_name=name)


@space_bp.route("/<kind>/<ident>/use", methods=["POST"])
@require_auth
def use_file(kind, ident):
    source = owned_resource(kind, ident)
    if kind not in {"material", "reference"} or not source or is_trashed(kind, ident):
        return not_found("File")
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return error_response("INVALID_BODY", "请求内容格式无效", 400)
    project = owned_project_or_404(body.get("project_id"))
    doc = db.session.get(CompetitionDocument, project.id) if project else None
    if not doc:
        return not_found("Project")
    binding = body.get('binding')
    if binding is not None:
        if kind != 'material' or not isinstance(binding, dict) or set(binding) - {'page_id', 'purpose', 'role_id'}:
            return error_response('INVALID_BINDING', '素材绑定参数无效', 400)
        if type(body.get('revision')) is not int:
            return error_response('INVALID_REVISION', '绑定素材必须提供内容版本', 400)
    db.session.execute(db.update(Project).where(Project.id == project.id).values(updated_at=Project.updated_at))
    db.session.refresh(doc)
    if 'revision' in body and body['revision'] != doc.revision:
        raise Conflict('内容已更新，请刷新后重新选择')
    if Task.query.filter(
        Task.project_id == project.id, Task.status.in_(ACTIVE)
    ).first():
        raise Conflict("作品任务仍在进行，请完成后再添加材料")
    if kind == "reference" and source.parse_status == "parsing":
        raise Conflict("材料正在解析，请稍后再添加")
    origin = safe_path(source.relative_path if kind == "material" else source.file_path)
    if not origin:
        return not_found("File")
    source_meta = db.session.get(EducationSpaceEntry, f"{kind}:{ident}")
    source_name = (source_meta.display_name if source_meta else None) or (
        source.original_filename or source.filename
        if kind == "material"
        else source.filename
    )
    # Independent copy keeps the library asset reusable without moving ownership.
    ident_new = str(uuid4())
    filename = ident_new + origin.suffix
    relative = (
        f"{project.id}/materials/{filename}"
        if kind == "material"
        else f"reference_files/{filename}"
    )
    dest = Path(current_app.config["UPLOAD_FOLDER"]) / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origin, dest)
    try:
        db.session.execute(
            db.update(Project)
            .where(Project.id == project.id)
            .values(updated_at=Project.updated_at)
        )
        if kind == "material":
            copy = Material(
                id=ident_new,
                user_id=current_user_id(),
                project_id=project.id,
                filename=filename,
                original_filename=source_name,
                relative_path=relative,
                url=f"/files/{relative}",
                caption=source.caption,
            )
        else:
            copy = ReferenceFile(
                id=ident_new,
                user_id=current_user_id(),
                project_id=project.id,
                filename=source_name,
                file_path=relative,
                file_size=source.file_size,
                file_type=source.file_type,
                parse_status=source.parse_status,
                markdown_content=source.markdown_content,
                error_message=source.error_message,
            )
        db.session.add(copy)
        db.session.flush()
        if kind == "reference":
            content = doc.content()
            content["reference_file_ids"].append(copy.id)
            save_content(doc, content, doc.revision, project)
        elif binding is not None:
            content = doc.content()
            if binding.get('purpose') == 'person':
                content['bindings'] = [b for b in content['bindings'] if not (
                    b['page_id'] == binding.get('page_id') and b['purpose'] == 'person' and b.get('role_id') == binding.get('role_id'))]
            content['bindings'].append({**binding, 'material_id': copy.id})
            save_content(doc, content, doc.revision, project)
        db.session.commit()
    except Exception:
        db.session.rollback()
        dest.unlink(missing_ok=True)
        raise
    return success_response({"id": copy.id, "project_id": project.id, "parse_status": getattr(copy, 'parse_status', None)})


@space_bp.route("/<kind>/<ident>/preview", methods=["GET"])
@require_auth
def preview(kind, ident):
    """Only return previews for an owned, recoverable file; never launch parsing jobs."""
    from services.competition.preview import preview_info, pdf_page

    row = owned_resource(kind, ident)
    if kind not in {"material", "reference"} or not row or is_trashed(kind, ident):
        return not_found("File")
    path = safe_path(row.relative_path if kind == "material" else row.file_path)
    if not path:
        return not_found("File")
    try:
        info = preview_info(path, getattr(row, "markdown_content", None))
        if request.args.get("mode") == "image":
            if info["kind"] == "pdf":
                page = request.args.get("page", "1")
                if not page.isdecimal() or len(page) > 6:
                    return error_response("INVALID_PAGE", "页码无效", 400)
                response = send_file(
                    pdf_page(path, int(page)), mimetype="image/png", max_age=0
                )
            elif info["kind"] == "image":
                mime = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                    ".bmp": "image/bmp",
                }[path.suffix.lower()]
                response = send_file(
                    path, mimetype=mime, as_attachment=False, max_age=0
                )
            else:
                return error_response("PREVIEW_UNSUPPORTED", "该文件没有图片预览", 400)
        else:
            response = make_response(success_response(info))
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    except Exception:
        # The source file remains downloadable; avoid exposing filesystem paths.
        return error_response(
            "PREVIEW_FAILED", "暂时无法预览此文件，请重试或下载原文件查看。", 422
        )

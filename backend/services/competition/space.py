"""Ownership-aware space inventory. Files are never automatically expired or removed."""

from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from flask import current_app
from models import db, Project, Material, ReferenceFile, Task, Page
from models.competition import CompetitionDocument
from models.education_space import EducationSpaceEntry
from utils.auth import current_user_id

MODELS = {"project": Project, "material": Material, "reference": ReferenceFile}
ACTIVE = {"PENDING", "PROCESSING", "RUNNING"}


def is_trashed(kind, ident):
    if current_app.config.get("APP_EDITION") != "education":
        return False
    row = db.session.get(EducationSpaceEntry, f"{kind}:{ident}")
    return bool(row and row.category == "trash")


def visible_query(query, model, kind):
    if current_app.config.get("APP_EDITION") == "education":
        query = query.filter(
            ~db.exists().where(
                EducationSpaceEntry.key == (kind + ":" + model.id),
                EducationSpaceEntry.category == "trash",
            )
        )
    return query


def safe_path(relative):
    root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    path = (root / relative).resolve()
    return path if path.is_relative_to(root) and path.is_file() else None


def owned_resource(kind, ident):
    model = MODELS.get(kind)
    if model is None:
        return None
    row = model.query.filter_by(id=ident, user_id=current_user_id()).first()
    if kind == "project" and row and not db.session.get(CompetitionDocument, ident):
        return None
    return row


def usage_map():
    """Include trashed projects: restoring a project must restore intact references."""
    result = {}
    projects = Project.query.filter_by(user_id=current_user_id()).all()
    for project in projects:
        doc = db.session.get(CompetitionDocument, project.id)
        if not doc:
            continue
        content = doc.content()
        for ident in content.get("reference_file_ids", []):
            result.setdefault(f"reference:{ident}", set()).add(project.id)
        for binding in content.get("bindings", []):
            result.setdefault(f'material:{binding["material_id"]}', set()).add(
                project.id
            )
    return result


def inventory():
    uid = current_user_id()
    projects = (
        Project.query.join(CompetitionDocument).filter(Project.user_id == uid).all()
    )
    titles = {p.id: p.project_title or "未命名竞赛项目" for p in projects}
    metadata = {
        x.key: x for x in EducationSpaceEntry.query.filter_by(user_id=uid).all()
    }
    usages = usage_map()
    rows = []
    for kind, resources in [
        ("project", projects),
        ("reference", ReferenceFile.query.filter_by(user_id=uid).all()),
        ("material", Material.query.filter_by(user_id=uid).all()),
    ]:
        for resource in resources:
            key = f"{kind}:{resource.id}"
            meta = metadata.get(key)
            linked = set(usages.get(key, set()))
            if kind != "project" and resource.project_id:
                linked.add(resource.project_id)
            default = (
                "projects"
                if kind == "project"
                else ("permanent" if linked else "temporary")
            )
            category = meta.category if meta else default
            if category == "temporary" and linked:
                category = "permanent"
            path = (
                None
                if kind == "project"
                else safe_path(
                    resource.relative_path if kind == "material" else resource.file_path
                )
            )
            name = (
                (resource.project_title or "未命名竞赛项目")
                if kind == "project"
                else (
                    (resource.original_filename or resource.filename)
                    if kind == "material"
                    else resource.filename
                )
            )
            # A project rename updates its content model, file rename is display-only.
            name = (meta.display_name if meta and kind != "project" else None) or name
            pages = (
                Page.query.filter_by(project_id=resource.id)
                .order_by(Page.order_index)
                .all()
                if kind == "project"
                else []
            )
            tasks = (
                Task.query.filter_by(project_id=resource.id).all()
                if kind == "project"
                else []
            )
            busy = (
                any(t.status in ACTIVE for t in tasks)
                if kind == "project"
                else kind == "reference" and resource.parse_status == "parsing"
            )
            status = (
                (
                    "生成中"
                    if busy
                    else (
                        "已生成"
                        if pages and all(p.generated_image_path for p in pages)
                        else "草稿"
                    )
                )
                if kind == "project"
                else (
                    "文件缺失"
                    if not path
                    else (
                        "使用中"
                        if linked
                        else "已保存" if category == "permanent" else "待整理"
                    )
                )
            )
            rows.append(
                dict(
                    key=key,
                    id=resource.id,
                    kind=kind,
                    category=category,
                    name=name,
                    updated_at=max(
                        resource.updated_at,
                        meta.updated_at if meta else resource.updated_at,
                    ).isoformat()
                    + "Z",
                    deleted_at=(
                        meta.deleted_at.isoformat() + "Z"
                        if meta and meta.deleted_at
                        else None
                    ),
                    format=(
                        "作品"
                        if kind == "project"
                        else Path(name).suffix.lstrip(".").upper() or "文件"
                    ),
                    size=path.stat().st_size if path else None,
                    page_count=len(pages),
                    status=status,
                    projects=[
                        dict(
                            id=i,
                            name=titles.get(i, "关联作品"),
                            trashed=is_trashed("project", i),
                        )
                        for i in sorted(linked)
                    ],
                    can_trash=not linked and not busy,
                    busy=busy,
                    download_url=(
                        f"/api/competition/space/{kind}/{resource.id}/download"
                        if path and category != "trash"
                        else None
                    ),
                )
            )
    # These are actual exported artifacts, not a claim that a browser saved them.
    for project in projects:
        if is_trashed("project", project.id):
            continue
        folder = Path(current_app.config["UPLOAD_FOLDER"]) / project.id / "exports"
        if not folder.is_dir():
            continue
        for candidate in folder.iterdir():
            if candidate.name.startswith(
                (".", "_")
            ) or candidate.suffix.lower() not in {
                ".pdf",
                ".pptx",
                ".md",
                ".zip",
                ".png",
                ".jpg",
                ".jpeg",
                ".mp4",
            }:
                continue
            path = safe_path(f"{project.id}/exports/{candidate.name}")
            if not path:
                continue
            stat = path.stat()
            rows.append(
                dict(
                    key=f"export:{project.id}:{candidate.name}",
                    id=candidate.name,
                    kind="export",
                    category="downloads",
                    name=candidate.name,
                    updated_at=datetime.utcfromtimestamp(stat.st_mtime).isoformat()
                    + "Z",
                    format=path.suffix.lstrip(".").upper(),
                    size=stat.st_size,
                    projects=[
                        dict(id=project.id, name=titles[project.id], trashed=False)
                    ],
                    status="可下载",
                    can_trash=False,
                    download_url=f"/api/competition/space/project/{project.id}/download?filename="
                    + quote(candidate.name, safe=""),
                )
            )
    return sorted(
        rows,
        key=lambda x: (
            x["deleted_at"] if x.get("category") == "trash" else x["updated_at"]
        ),
        reverse=True,
    )

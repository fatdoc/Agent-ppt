"""Canonical education content. Page IDs, not page numbers, own all references."""

import hashlib
import json
import re
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from models import Material, Page, ReferenceFile, db
from models.competition import CompetitionDocument, CompetitionRevision

from .skill_contract import (
    CHAPTERS,
    navigation,
    render_checklist,
    render_pair,
    validate_record,
)

RESOURCE_DIR = Path(__file__).parent / "resources"
SKILL_VERSION = "world-skills-2026-09-21.v1"
STYLES = {
    "technology": {
        "name": "科技蓝",
        "prompt": "深蓝标题、白色背景、蓝色强调，清晰工程图与简洁卡片，正文高对比。",
    },
    "minimal": {
        "name": "简洁白",
        "prompt": "白底、深灰标题、克制留白，蓝色少量强调，清晰表格与信息层级。",
    },
    "ecology": {
        "name": "生态绿",
        "prompt": "米白背景、墨绿标题、绿色强调，使用项目真实场景与轻量线条，避免装饰干扰。",
    },
}
VISUAL_EVIDENCE_RULES = """教育版证据边界（优先于视觉美化）：
不得生成虚构参赛成员照片、证书、专利、签约或获奖证明。缺失处用明确待补占位。
没有绑定真实产品图、系统截图、日志或测试图时，使用线框图、简笔示意或标有“待补真实截图”的空框，禁止补绘以假乱真的软件截图、实物照片或测试记录。
示意界面中的未知数值只能写“—”或“待实测”，不要编造日期、传感器读数、性能或比例。
任何补绘场景、示意界面和操作示意的相邻位置必须清晰上屏“设计示意 · 非实测/实拍”。不能只在备注说明。
已绑定真实素材保留原貌；不得修改其中文字或读数。只把页面正文作为已确认文案，不额外添加宣传标语。
"""
PROFILE_FIELDS = {
    "name",
    "track",
    "education_level",
    "duration",
    "focus",
    "roles",
    "rule_year",
    "rule_source",
}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def digest(value):
    return hashlib.sha256(dumps(value).encode()).hexdigest()


def new_id():
    return str(uuid.uuid4())


def initial_content(name="未命名竞赛项目"):
    return {
        "schema_version": 1,
        "skill_version": SKILL_VERSION,
        "profile": {
            "name": name,
            "track": "",
            "education_level": "高职专科",
            "duration": "",
            "focus": "",
            "roles": [
                {"id": new_id(), "name": "", "responsibility": ""} for _ in range(4)
            ],
            "rule_year": "",
            "rule_source": "",
        },
        "preferences": {
            "complexity": "balanced",
            "pagination": "skill",
            "target_pages": 47,
            "style": "technology",
        },
        "locks": [],
        "raw_material": "",
        "reference_file_ids": [],
        "pages": [],
        "checklist": [],
        "bindings": [],
        "messages": [],
        "questions": [],
        "warnings": [],
        "structure_mode": "skill",
        "imported_outline": "",
        "imported_descriptions": "",
    }


class ContentError(ValueError):
    """Validated, safe user-facing content error."""


def required(ok, message):
    if not ok:
        raise ContentError(message)


def validate_content(data, project):
    required(isinstance(data, dict), "项目内容格式错误")
    profile = data.get("profile", {})
    required(
        isinstance(profile, dict) and set(profile) <= PROFILE_FIELDS, "项目字段无效"
    )
    for k in PROFILE_FIELDS - {"roles"}:
        required(
            isinstance(profile.get(k), str) and len(profile[k]) <= 4000, f"{k} 字段无效"
        )
    roles = profile.get("roles")
    required(isinstance(roles, list) and 1 <= len(roles) <= 12, "团队支持 1–12 个岗位")
    role_ids = set()
    for r in roles:
        required(
            isinstance(r, dict)
            and {"id", "name", "responsibility"}
            <= set(r)
            <= {"id", "name", "responsibility", "member_name"},
            "岗位格式错误",
        )
        required(
            isinstance(r["id"], str) and r["id"] not in role_ids and len(r["id"]) <= 40,
            "岗位 ID 无效",
        )
        required(
            isinstance(r.get("member_name", ""), str)
            and len(r.get("member_name", "")) <= 100,
            "成员姓名无效",
        )
        role_ids.add(r["id"])
        required(
            all(
                isinstance(r[k], str) and len(r[k]) <= 2000
                for k in ["name", "responsibility"]
            ),
            "岗位文字无效",
        )
    prefs = data.get("preferences", {})
    required(
        isinstance(prefs, dict)
        and set(prefs) == {"complexity", "pagination", "target_pages", "style"},
        "生成偏好字段无效",
    )
    required(prefs["complexity"] in {"simple", "balanced", "complex"}, "页面复杂度无效")
    required(prefs["pagination"] in {"skill", "compact", "step"}, "分页方式无效")
    required(
        type(prefs["target_pages"]) is int and 1 <= prefs["target_pages"] <= 100,
        "目标页数支持 1–100 页",
    )
    required(prefs["style"] in STYLES, "请选择可用风格")
    required(
        isinstance(data.get("locks"), list) and set(data["locks"]) <= PROFILE_FIELDS,
        "锁定字段无效",
    )
    required(data.get("structure_mode") in {"skill", "preserve"}, "结构模式无效")
    required(
        isinstance(data.get("raw_material"), str)
        and len(data["raw_material"]) <= 250000,
        "材料请控制在 25 万字符以内",
    )
    for k in ["imported_outline", "imported_descriptions"]:
        required(
            isinstance(data.get(k, ""), str) and len(data.get(k, "")) <= 250000,
            "导入内容过长",
        )
    refs = data.get("reference_file_ids")
    required(
        isinstance(refs, list)
        and len(refs) <= 30
        and all(isinstance(x, str) for x in refs),
        "参考文件无效",
    )
    for fid in refs:
        from services.competition.space import is_trashed
        required(not is_trashed('reference', fid), '请先从回收站恢复材料')
        row = db.session.get(ReferenceFile, fid)
        required(
            row is not None
            and row.user_id == project.user_id
            and row.project_id == project.id,
            "参考文件不属于此项目",
        )
    pages = data.get("pages")
    required(isinstance(pages, list) and len(pages) <= 100, "最多支持 100 页")
    ids = set()
    for p in pages:
        required(isinstance(p, dict), "页面格式无效")
        required(type(p.get("team_page", False)) is bool, "团队页标记无效")
        pid = p.get("id")
        required(
            isinstance(pid, str)
            and re.fullmatch(r"[a-f0-9-]{36}", pid)
            and pid not in ids,
            "页面 ID 无效或重复",
        )
        other = db.session.get(Page, pid)
        required(other is None or other.project_id == project.id, "页面不属于当前项目")
        ids.add(pid)
        required(
            p.get("kind") in {"cover", "content", "contents", "transition"},
            "页面类型无效",
        )
        required(
            type(p.get("chapter")) is int and 0 <= p["chapter"] <= 5, "章节必须为 0–5"
        )
        for k in ["title", "purpose"]:
            required(
                isinstance(p.get(k), str) and bool(p[k].strip()) and len(p[k]) <= 3000,
                f"页面 {k} 不可为空",
            )
        for k in ["text", "layout", "materials", "speaker_notes", "action_notes"]:
            required(
                isinstance(p.get(k), list)
                and all(
                    isinstance(v, str) and "\n" not in v and len(v) <= 8000
                    for v in p[k]
                ),
                f"页面 {k} 格式错误",
            )
        required(
            p["text"] and p["layout"] and p["materials"],
            "页面文字、版式与素材要求不可为空",
        )
        required(
            isinstance(p.get("role_ids", []), list)
            and set(p.get("role_ids", [])) <= role_ids,
            "页面引用了不存在的岗位",
        )
    checklist = data.get("checklist")
    required(isinstance(checklist, list) and len(checklist) <= 500, "清单格式无效")
    for item in checklist:
        required(
            item.get("category") in {"fact", "proposal", "missing"}, "清单分类无效"
        )
        required(
            isinstance(item.get("page_ids"), list) and set(item["page_ids"]) <= ids,
            "清单引用了不存在的页面",
        )
        for key in ["content", "status", "basis", "action"]:
            required(
                isinstance(item.get(key), str) and bool(item[key].strip()),
                "清单内容、状态、依据和处理办法均需填写",
            )
    bindings = data.get("bindings")
    required(isinstance(bindings, list) and len(bindings) <= 300, "素材绑定无效")
    person_slots = set()
    for b in bindings:
        required(b.get("page_id") in ids, "素材绑定的页面不存在")
        required(
            b.get("purpose")
            in {"person", "product", "screenshot", "certificate", "reference"},
            "素材用途无效",
        )
        material = db.session.get(Material, b.get("material_id"))
        from services.competition.space import is_trashed
        required(not is_trashed('material', b.get('material_id')), '请先从回收站恢复素材')
        required(
            material
            and material.project_id == project.id
            and material.user_id == project.user_id,
            "素材不属于当前项目",
        )
        if b["purpose"] == "person":
            required(b.get("role_id") in role_ids, "请选择照片对应岗位")
            slot = (b["page_id"], b["role_id"])
            required(
                slot not in person_slots, "同一成员槽位只能绑定一张照片，请更换原照片"
            )
            person_slots.add(slot)
            target = next(p for p in pages if p["id"] == b["page_id"])
            required(
                is_team_page(target),
                "人物照片仅能绑定开场团队介绍页",
            )
    return data


def record(data):
    pages = deepcopy(data["pages"])
    indices = {p["id"]: n for n, p in enumerate(pages, 1)}
    checklist = [
        {
            **item,
            "pages": [indices[i] for i in item["page_ids"] if i in indices]
            or list(indices.values()),
        }
        for item in data["checklist"]
    ]
    return {
        "project": data["profile"]["name"],
        "mode": "project",
        "pages": pages,
        "checklist": checklist,
    }


def structure_warnings(data):
    if not data["pages"]:
        return []
    try:
        validate_record(record(data))
        return []
    except (ValueError, KeyError, TypeError) as exc:
        return [f"与五章预设的差异：{exc}。保留原稿；需要时可选择按预设重新规划。"]


def export_markdown(data):
    rec = record(data)
    outline, description = render_pair(rec)
    # Untouched imports round-trip verbatim. They are cleared on page edits.
    return {
        "outline": data.get("imported_outline") or outline,
        "descriptions": data.get("imported_descriptions") or description,
        "checklist": render_checklist(rec),
    }


def is_team_page(p):
    return (
        p["kind"] == "content"
        and p["chapter"] == 0
        and p.get(
            "team_page", bool(re.search(r"团队|成员|team", p["title"], re.IGNORECASE))
        )
    )


def description_text(data, p):
    if p.get("original_description"):
        text = p["original_description"]
    else:
        text = "\n".join(
            [
                "页面标题：" + p["title"],
                "页面文字：",
                *p["text"],
                "页面画面与版式：",
                *p["layout"],
                "素材要求：",
                *p["materials"],
                "导航状态：" + navigation(p),
            ]
        )
    scoped_roles = (
        data["profile"]["roles"]
        if is_team_page(p)
        else [r for r in data["profile"]["roles"] if r["id"] in p.get("role_ids", [])]
    )
    if scoped_roles:
        text += "\n已确认的岗位与职责（相关页面按此同步，不增加其他成员）：" + dumps(
            scoped_roles
        )
    for b in data["bindings"]:
        if b["page_id"] == p["id"]:
            m = db.session.get(Material, b["material_id"])
            role = next(
                (
                    " ".join(filter(None, [r.get("member_name"), r["name"], r["id"]]))
                    for r in data["profile"]["roles"]
                    if r["id"] == b.get("role_id")
                ),
                "",
            )
            text += f"\n指定真实素材（{b['purpose']} {role}，保留原始内容，不虚构或改写）：![指定素材]({m.url})"
    if is_team_page(p):
        text += (
            "\n没有对应真实成员照片时使用带“待补照片”字样的中性占位框，禁止合成人脸。"
        )
    text += "\n" + VISUAL_EVIDENCE_RULES
    return text


def sync_pages(project, data, old):
    existing = {p.id: p for p in Page.query.filter_by(project_id=project.id).all()}
    keep = {p["id"] for p in data["pages"]}
    for pid, page in existing.items():
        if pid not in keep:
            db.session.delete(page)
    style_changed = old and data["preferences"]["style"] != old["preferences"]["style"]
    project.template_style = STYLES[data["preferences"]["style"]]["prompt"]
    project.project_title = data["profile"]["name"]
    for n, p in enumerate(data["pages"]):
        page = existing.get(p["id"])
        if page is None:
            page = Page(id=p["id"], project_id=project.id, order_index=n)
            db.session.add(page)
        outline = {"title": p["title"], "points": p["text"]}
        desc = {"text": description_text(data, p), "competition_page_id": p["id"]}
        # Reordering changes navigation/page context and must invalidate image reuse.
        changed = (
            style_changed
            or page.order_index != n
            or page.get_outline_content() != outline
            or page.get_description_content() != desc
        )
        if changed:
            page.generated_image_path = None
            page.cached_image_path = None
            page.status = "DESCRIPTIONS_GENERATED"
        page.order_index = n
        page.part = CHAPTERS[p["chapter"] - 1] if p["chapter"] else None
        page.set_outline_content(outline)
        page.set_description_content(desc)
    project.updated_at = datetime.utcnow()
    if data["pages"]:
        project.status = "DESCRIPTIONS_GENERATED"


def save_content(doc, data, expected, project):
    validate_content(data, project)
    changed = db.session.execute(
        db.update(CompetitionDocument)
        .where(
            CompetitionDocument.project_id == project.id,
            CompetitionDocument.revision == expected,
        )
        .values(revision=expected + 1, payload=dumps(data))
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise Conflict("内容已更新，请载入最新版本后重试")
    old = doc.content()
    sync_pages(project, data, old)
    db.session.add(
        CompetitionRevision(
            project_id=project.id, revision=expected + 1, payload=dumps(data)
        )
    )
    db.session.flush()
    db.session.refresh(doc)


class Conflict(ValueError):
    pass


def parse_import(outline, descriptions, data):
    from services.input_generation_service import InputGenerationService

    blocks = InputGenerationService._parse_page_blocks(outline)
    desc_blocks = InputGenerationService._parse_page_blocks(descriptions)
    required(blocks, "请使用“第 1 页：标题”格式的大纲")
    required(
        not descriptions.strip() or len(blocks) == len(desc_blocks),
        "大纲与逐页描述页数不一致，请先对齐",
    )
    pages = []
    for i, b in enumerate(blocks):
        if desc_blocks:
            required(
                b["title"] == desc_blocks[i]["title"],
                f"第 {i + 1} 页大纲与描述标题不一致",
            )
        raw = b["body"]
        ch = re.search(r"所属章节：\s*0?([1-5])", raw)
        kind = "content"
        for label, key in [
            ("首页", "cover"),
            ("目录页", "contents"),
            ("章节过渡页", "transition"),
        ]:
            if f"页面类型：{label}" in raw:
                kind = key
        pages.append(
            {
                "id": new_id(),
                "title": b["title"],
                "kind": kind,
                "chapter": int(ch[1]) if ch else 0,
                "purpose": "保留用户原稿",
                "text": raw.splitlines() or [b["title"]],
                "layout": (
                    [
                        line
                        for line in desc_blocks[i]["body"].splitlines()
                        if line.strip()
                    ]
                    if desc_blocks
                    else ["按所选视觉风格排版"]
                ),
                "materials": ["按原稿准备真实素材"],
                "speaker_notes": [],
                "action_notes": [],
                "original_description": desc_blocks[i]["body"] if desc_blocks else "",
            }
        )
    data["pages"] = pages
    data["checklist"] = []
    data["bindings"] = []
    data["structure_mode"] = "preserve"
    data["imported_outline"] = outline
    data["imported_descriptions"] = descriptions
    data["warnings"] = structure_warnings(data)
    return data

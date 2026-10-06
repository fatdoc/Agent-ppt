"""Behavioral contracts for education isolation, stable content and paid task admission."""

import json
import uuid
from copy import deepcopy
from unittest.mock import Mock

import pytest
from models import Material, Page, Project, ReferenceFile, User, db
from models.competition import (
    CompetitionOperation,
)
from services.competition.content import (
    RESOURCE_DIR,
)


@pytest.fixture
def edu(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_EDITION", "education")
    return client


def created(client):
    r = client.post("/api/competition/projects", json={"name": "脱敏测试项目"})
    assert r.status_code == 201, r.json
    return r.json["data"]


def endpoint(s):
    return "/api/projects/" + s["project_id"] + "/competition"


def save(client, s, patch):
    r = client.patch(endpoint(s), json={"revision": s["revision"], "patch": patch})
    assert r.status_code == 200, r.json
    return r.json["data"]


def seed(client, s, count=47):
    pages = json.loads((RESOURCE_DIR / "page-blueprint.json").read_text())["pages"][
        :count
    ]
    for p in pages:
        p["id"] = str(uuid.uuid4())
        p.setdefault("speaker_notes", [])
        p.setdefault("action_notes", [])
    return save(
        client,
        s,
        {
            "pages": pages,
            "raw_material": "项目为草莓水肥调控，团队四岗；准确率暂无实测，不知道展示时长。",
        },
    )


def test_general_edition_hidden(client, app):
    assert client.get("/api/competition/projects").status_code == 404
    assert client.get("/api/auth/config").json["data"]["edition"] == "general"
    assert (
        client.post(
            "/api/projects", json={"creation_type": "idea", "idea_prompt": "原有流程"}
        ).status_code
        == 201
    )


def test_create_and_defaults_are_not_official_requirements(edu):
    s = created(edu)
    assert s["revision"] == 1 and s["content"]["preferences"]["target_pages"] == 47
    assert (
        s["content"]["profile"]["duration"] == ""
        and s["content"]["profile"]["rule_year"] == ""
    )
    assert len(s["content"]["profile"]["roles"]) == 4
    assert (
        edu.get("/api/competition/projects").json["data"][0]["project_id"]
        == s["project_id"]
    )


def test_stable_ids_reorder_and_evidence_references(edu):
    s = seed(edu, created(edu), 3)
    ids = [p["id"] for p in s["content"]["pages"]]
    checklist = [
        dict(
            category="missing",
            page_ids=[ids[1]],
            content="照片",
            status="待补",
            basis="暂无依据",
            action="上传真实照片",
        )
    ]
    s = save(edu, s, {"checklist": checklist})
    pages = s["content"]["pages"]
    pages[1], pages[2] = pages[2], pages[1]
    s = save(edu, s, {"pages": pages})
    assert s["content"]["checklist"][0]["page_ids"] == [ids[1]]
    md = edu.get(endpoint(s) + "/exports/checklist").text
    assert "对应页码：P3" in md
    assert {p.id for p in Page.query.filter_by(project_id=s["project_id"])} == set(ids)


def test_revision_conflict_never_overwrites(edu):
    s = created(edu)
    save(edu, s, {"raw_material": "新版"})
    r = edu.patch(
        endpoint(s), json={"revision": s["revision"], "patch": {"raw_material": "旧版"}}
    )
    assert r.status_code == 409
    assert edu.get(endpoint(s)).json["data"]["content"]["raw_material"] == "新版"


def test_import_round_trip_survives_profile_save(edu):
    s = created(edu)
    outline = "第 1 页：原文标题\n\n* 准确率待测\n\n第 2 页：验证\n- 未实测\n"
    descriptions = "第 1 页：原文标题\n原始版式描述\n\n第 2 页：验证\n使用真实截图\n"
    r = edu.post(
        endpoint(s) + "/import",
        json={
            "revision": s["revision"],
            "outline": outline,
            "descriptions": descriptions,
        },
    )
    assert r.status_code == 200, r.json
    s = r.json["data"]
    assert s["content"]["structure_mode"] == "preserve"
    profile = s["content"]["profile"]
    profile["focus"] = "现场操作"
    s = save(edu, s, {"profile": profile, "pages": s["content"]["pages"]})
    assert edu.get(endpoint(s) + "/exports/outline").text == outline
    assert edu.get(endpoint(s) + "/exports/descriptions").text == descriptions
    assert s["warnings"]


def test_import_rejects_misaligned_titles(edu):
    s = created(edu)
    r = edu.post(
        endpoint(s) + "/import",
        json={
            "revision": 1,
            "outline": "第 1 页：A\n正文",
            "descriptions": "第 1 页：B\n正文",
        },
    )
    assert r.status_code == 400


def test_only_affected_images_are_invalidated(edu):
    s = seed(edu, created(edu), 3)
    for page in Page.query.filter_by(project_id=s["project_id"]):
        page.generated_image_path = f"{s['project_id']}/pages/{page.id}.png"
        page.status = "COMPLETED"
    db.session.commit()
    pages = s["content"]["pages"]
    pages[1]["text"] = ["更新后的岗位职责"]
    s = save(edu, s, {"pages": pages})
    assert [bool(p["generated_image_url"]) for p in s["pages"]] == [True, False, True]
    prefs = s["content"]["preferences"]
    prefs["style"] = "ecology"
    s = save(edu, s, {"preferences": prefs})
    assert not any(p["generated_image_url"] for p in s["pages"])


def test_notes_not_visible_on_slide(edu):
    s = seed(edu, created(edu), 1)
    pages = s["content"]["pages"]
    pages[0]["speaker_notes"] = ["讲稿专用句"]
    pages[0]["action_notes"] = ["现场操作专用句"]
    s = save(edu, s, {"pages": pages})
    assert "讲稿专用句" not in edu.get(endpoint(s) + "/exports/descriptions").text
    assert "现场操作专用句" in edu.get(endpoint(s) + "/exports/checklist").text
    assert "讲稿专用句" not in db.session.get(Page, pages[0]["id"]).description_content


def test_foreign_material_and_page_rejected(edu):
    s = seed(edu, created(edu), 2)
    other = created(edu)
    m = Material(
        project_id=other["project_id"],
        user_id=db.session.get(Project, other["project_id"]).user_id,
        filename="private.png",
        relative_path="other/private.png",
        url="/files/other/private.png",
    )
    db.session.add(m)
    db.session.commit()
    r = edu.patch(
        endpoint(s),
        json={
            "revision": s["revision"],
            "patch": {
                "bindings": [
                    dict(
                        page_id=s["content"]["pages"][0]["id"],
                        material_id=m.id,
                        purpose="reference",
                    )
                ]
            },
        },
    )
    assert r.status_code == 400
    assert edu.get(endpoint(s)).json["data"]["revision"] == s["revision"]


def test_photos_scoped_to_team_page(edu):
    s = seed(edu, created(edu), 2)
    m = Material(
        project_id=s["project_id"],
        user_id=db.session.get(Project, s["project_id"]).user_id,
        filename="face.png",
        relative_path="face.png",
        url="/files/face.png",
    )
    db.session.add(m)
    db.session.commit()
    b = dict(
        page_id=s["content"]["pages"][0]["id"],
        material_id=m.id,
        purpose="person",
        role_id=s["content"]["profile"]["roles"][0]["id"],
    )
    assert (
        edu.patch(
            endpoint(s), json={"revision": s["revision"], "patch": {"bindings": [b]}}
        ).status_code
        == 400
    )
    b["page_id"] = s["content"]["pages"][1]["id"]
    s = save(edu, s, {"bindings": [b]})
    assert (
        "/files/face.png"
        not in db.session.get(Page, s["content"]["pages"][0]["id"]).description_content
    )
    assert "/files/face.png" in db.session.get(Page, b["page_id"]).description_content


def test_duplicate_task_requests_reserve_once(edu, monkeypatch):
    s = seed(edu, created(edu), 3)
    submit = Mock()
    monkeypatch.setattr(
        "controllers.competition_controller.task_manager.submit_task", submit
    )
    body = {"revision": s["revision"], "request_key": "same-request"}
    r = edu.post(endpoint(s) + "/plan", json=body)
    assert r.status_code == 202, r.json
    r2 = edu.post(endpoint(s) + "/plan", json=body)
    assert r2.json["data"]["task"]["task_id"] == r.json["data"]["task"]["task_id"]
    assert submit.call_count == 1 and CompetitionOperation.query.count() == 1
    assert (
        edu.post(
            endpoint(s) + "/plan", json={**body, "request_key": "other"}
        ).status_code
        == 409
    )


def test_image_request_reuses_completed_pages_and_blocks_edits(edu, monkeypatch):
    s = seed(edu, created(edu), 3)
    ids = [p["id"] for p in s["content"]["pages"]]
    db.session.get(Page, ids[0]).generated_image_path = "existing.png"
    db.session.commit()
    submit = Mock()
    monkeypatch.setattr(
        "controllers.competition_controller.task_manager.submit_task", submit
    )
    monkeypatch.setattr("controllers.competition_controller.get_ai_service", Mock())
    r = edu.post(
        endpoint(s) + "/images",
        json={"revision": s["revision"], "request_key": "images", "page_ids": ids},
    )
    assert r.status_code == 202, r.json
    assert submit.call_args.kwargs["page_ids"] == ids[1:]
    assert (
        edu.patch(
            endpoint(s),
            json={"revision": s["revision"], "patch": {"raw_material": "new"}},
        ).status_code
        == 409
    )
    assert (
        edu.post(
            f"/api/projects/{s['project_id']}/generate/images", json={"page_ids": ids}
        ).status_code
        == 409
    )


def test_cross_account_cannot_read_education(edu, monkeypatch):
    from utils.auth import create_auth_token

    s = created(edu)
    user = User(username="second-education-user")
    user.set_password("not-a-real-password")
    db.session.add(user)
    db.session.commit()
    token = create_auth_token(user)
    assert (
        edu.get(endpoint(s), headers={"Authorization": "Bearer " + token}).status_code
        == 404
    )
    assert (
        edu.get(
            "/api/competition/projects", headers={"Authorization": "Bearer " + token}
        ).json["data"]
        == []
    )


class ModelFixture:
    def __init__(self, sector="草莓"):
        self.prompts = []
        self.sector = sector

    def generate_json(self, prompt):
        self.prompts.append(prompt)
        if "本批页面：" in prompt:
            pages = json.loads(prompt.split("本批页面：", 1)[1].split("\n材料：", 1)[0])
            for p in pages:
                p["text"] = [self.sector + "项目操作与验证，指标待实测"]
                p["materials"] = ["待补真实运行截图"]
                p["speaker_notes"] = []
                p["action_notes"] = []
            return {
                "pages": pages,
                "checklist": [
                    dict(
                        category="missing",
                        page_ids=[pages[0]["id"]],
                        content="实测记录",
                        status="待核验",
                        basis="输入材料未提供",
                        action="按真实操作采集记录",
                    )
                ],
            }
        return {
            "profile": {"focus": "AI建议重点", "duration": ""},
            "questions": ["请补充实际岗位操作"],
            "summary": "参数保持待核验",
        }


@pytest.mark.parametrize("sector", ["草莓", "餐饮服务"])
def test_47_page_atomic_plan_locked_fields_and_evidence(edu, app, monkeypatch, sector):
    s = created(edu)
    s = save(
        edu,
        s,
        {
            "raw_material": sector + "方案，测试指标不知道",
            "locks": ["focus"],
            "profile": {**s["content"]["profile"], "focus": "用户确认重点"},
        },
    )
    model = ModelFixture(sector)
    monkeypatch.setattr("services.competition.generation.get_ai_service", lambda: model)
    captured = []
    monkeypatch.setattr(
        "controllers.competition_controller.task_manager.submit_task",
        lambda *a, **k: captured.append((a, k)),
    )
    r = edu.post(
        endpoint(s) + "/plan", json={"revision": s["revision"], "request_key": "plan"}
    )
    assert r.status_code == 202, r.json
    a, k = captured[0]
    a[1](a[0], **k)
    s = edu.get(endpoint(s)).json["data"]
    assert s["task"]["status"] == "COMPLETED", s["task"]
    assert (
        len(s["content"]["pages"]) == 47
        and s["content"]["profile"]["focus"] == "用户确认重点"
    )
    assert len(s["content"]["checklist"]) == 10
    assert "待实测" in edu.get(endpoint(s) + "/exports/outline").text
    assert all(sector in p["text"][0] for p in s["content"]["pages"])


def test_stale_model_completion_cannot_publish(edu, app, monkeypatch):
    s = seed(edu, created(edu), 3)
    model = ModelFixture()
    monkeypatch.setattr("services.competition.generation.get_ai_service", lambda: model)
    captured = []
    monkeypatch.setattr(
        "controllers.competition_controller.task_manager.submit_task",
        lambda *a, **k: captured.append((a, k)),
    )
    edu.post(
        endpoint(s) + "/plan", json={"revision": s["revision"], "request_key": "plan"}
    )
    s = save(edu, s, {"raw_material": "用户刚更新的材料"})
    a, k = captured[0]
    a[1](a[0], **k)
    now = edu.get(endpoint(s)).json["data"]
    assert (
        now["revision"] == s["revision"]
        and now["content"]["raw_material"] == "用户刚更新的材料"
    )
    assert now["task"]["status"] == "FAILED"


def test_education_auth_cookie_namespace(edu):
    r = edu.post(
        "/api/auth/register",
        json={"username": "eduregister", "password": "education-test-password"},
    )
    assert r.status_code == 201, r.json
    cookies = r.headers.getlist("Set-Cookie")
    assert any(c.startswith("banana_education_auth_token=") for c in cookies)
    assert not any(c.startswith("banana_auth_token=") for c in cookies)


def test_clear_template_does_not_resurrect_legacy_file(edu, app):
    from io import BytesIO

    from PIL import Image
    from services.file_service import FileService

    s = seed(edu, created(edu), 3)
    image = BytesIO()
    Image.new("RGB", (64, 36), "blue").save(image, format="PNG")
    image.seek(0)
    r = edu.post(
        endpoint(s) + "/template",
        data={
            "revision": str(s["revision"]),
            "template_image": (image, "reference.png"),
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 200, r.json
    s = r.json["data"]
    assert s["template_image_path"]
    fs = FileService(app.config["UPLOAD_FOLDER"])
    assert fs.get_template_path(s["project_id"])
    r = edu.delete(endpoint(s) + "/template", json={"revision": s["revision"]})
    assert r.status_code == 200, r.json
    assert fs.get_template_path(s["project_id"]) is None


@pytest.mark.parametrize(
    "patch",
    [
        {"pages": ["bad"]},
        {"profile": []},
        {"preferences": None},
        {"checklist": [1]},
        {"bindings": [1]},
    ],
)
def test_bad_payload_is_400_and_no_partial_save(edu, patch):
    s = seed(edu, created(edu), 3)
    response = edu.patch(endpoint(s), json={"revision": s["revision"], "patch": patch})
    assert response.status_code == 400, response.json
    current = edu.get(endpoint(s)).json["data"]
    assert (
        current["revision"] == s["revision"] and len(current["content"]["pages"]) == 3
    )


def test_removing_page_flags_orphan_evidence(edu):
    s = seed(edu, created(edu), 3)
    pid = s["content"]["pages"][1]["id"]
    s = save(
        edu,
        s,
        {
            "checklist": [
                dict(
                    category="missing",
                    page_ids=[pid],
                    content="成员照片",
                    status="待补",
                    basis="未上传",
                    action="上传真实照片",
                )
            ]
        },
    )
    s = save(edu, s, {"pages": [p for p in s["content"]["pages"] if p["id"] != pid]})
    assert s["content"]["checklist"][0]["page_ids"] == []
    assert "原关联页已移除" in s["content"]["checklist"][0]["status"]


def test_failed_parse_never_starts_or_reserves_plan(edu, monkeypatch):
    s = created(edu)
    f = ReferenceFile(
        project_id=s["project_id"],
        user_id=db.session.get(Project, s["project_id"]).user_id,
        filename="broken.pdf",
        file_path="broken.pdf",
        file_size=12,
        file_type="pdf",
        parse_status="failed",
    )
    db.session.add(f)
    db.session.commit()
    s = save(edu, s, {"reference_file_ids": [f.id]})
    r = edu.post(
        endpoint(s) + "/plan",
        json={"revision": s["revision"], "request_key": "bad-parse"},
    )
    assert r.status_code == 400, r.json
    assert not CompetitionOperation.query.count()


def test_content_reads_and_saves_do_not_open_model_credentials(edu, monkeypatch):
    import app as app_module

    monkeypatch.setattr(
        app_module,
        "capture_provider_snapshot",
        lambda **kw: (_ for _ in ()).throw(
            AssertionError("content reads are provider-free")
        ),
    )
    s = created(edu)
    s = save(edu, s, {"raw_material": "仅保存材料"})
    assert edu.get(endpoint(s)).status_code == 200


def test_profile_annotations_do_not_mutate_unknown_fields_or_locks():
    from services.competition.content import initial_content
    from services.competition.generation import apply_profile

    data = initial_content()
    data["locks"] = ["focus"]
    data["profile"]["focus"] = "确认重点"
    apply_profile(
        data,
        {
            "name": "餐饮服务",
            "focus": "应忽略",
            "duration": None,
            "evidence_notes": "模型额外注释",
        },
    )
    assert (
        data["profile"]["name"] == "餐饮服务" and data["profile"]["focus"] == "确认重点"
    )
    assert data["profile"]["duration"] == "" and "evidence_notes" not in data["profile"]


def test_visual_evidence_guard_is_part_of_generation_not_import_export(edu):
    s = seed(edu, created(edu), 1)
    page = db.session.get(Page, s["content"]["pages"][0]["id"])
    prompt = page.get_description_content()["text"]
    assert "设计示意 · 非实测/实拍" in prompt
    assert "禁止补绘以假乱真的软件截图" in prompt
    assert "不要编造日期" in prompt


def test_photo_replacement_preserves_other_images_and_member_names(edu):
    s = seed(edu, created(edu), 3)
    ids = [p["id"] for p in s["content"]["pages"]]
    profile = deepcopy(s["content"]["profile"])
    profile["roles"][0]["member_name"] = "测试成员"
    s = save(edu, s, {"profile": profile})
    for pid in ids:
        page = db.session.get(Page, pid)
        page.generated_image_path = pid + ".png"
        page.status = "COMPLETED"
    materials = [
        Material(
            project_id=s["project_id"],
            user_id=db.session.get(Project, s["project_id"]).user_id,
            filename=f"photo-{i}.png",
            relative_path=f"photo-{i}.png",
            url=f"/files/photo-{i}.png",
        )
        for i in range(2)
    ]
    db.session.add_all(materials)
    db.session.commit()
    binding = dict(
        page_id=ids[1],
        material_id=materials[0].id,
        purpose="person",
        role_id=profile["roles"][0]["id"],
    )
    s = save(edu, s, {"bindings": [binding]})
    assert s["content"]["profile"]["roles"][0]["member_name"] == "测试成员"
    assert db.session.get(Page, ids[0]).generated_image_path == ids[0] + ".png"
    assert db.session.get(Page, ids[2]).generated_image_path == ids[2] + ".png"
    assert db.session.get(Page, ids[1]).generated_image_path is None
    duplicate = edu.patch(
        endpoint(s),
        json={"revision": s["revision"], "patch": {"bindings": [binding, binding]}},
    )
    assert duplicate.status_code == 400
    binding["material_id"] = materials[1].id
    s = save(edu, s, {"bindings": [binding]})
    desc = db.session.get(Page, ids[1]).description_content
    assert "/files/photo-1.png" in desc and "/files/photo-0.png" not in desc
    assert "测试成员" in desc
    assert len(s["content"]["bindings"]) == 1


def test_imported_opening_content_does_not_become_team_page():
    from services.competition.content import is_team_page
    from services.competition.generation import normalize_page

    page = {"kind": "content", "chapter": 0, "title": "系统操作演示"}
    assert not is_team_page(page)
    page["title"] = "团队分工"
    assert is_team_page(page)
    rewritten = normalize_page({"title": "我们的分工"}, page)
    assert is_team_page(rewritten)
    rewritten["team_page"] = False
    assert not is_team_page(rewritten)

"""Tests for the v1 outline -> descriptions -> images API."""
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PIL import Image


def _create_key(client):
    response = client.post("/api/api-keys", json={"name": "integration-test"})
    assert response.status_code == 201
    return response.get_json()["data"]["key"], response.get_json()["data"]["api_key"]


def _headers(key, idempotency_key=None):
    headers = {"Authorization": f"Bearer {key}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _payload():
    return {
        "title": "测试项目",
        "outline": [
            {"title": "项目背景", "points": ["行业变化", "用户痛点"], "part": "现状"},
            {"title": "解决方案", "points": ["核心能力", "实施路径"], "part": "方案"},
        ],
        "visual": {"style": "蓝色科技感", "aspect_ratio": "16:9"},
        "options": {"language": "zh", "detail_level": "default"},
    }


def test_public_api_requires_api_key(client):
    response = client.post("/v1/ppt-generations", json=_payload())
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "INVALID_API_KEY"


def test_create_key_submit_and_reuse_idempotency_key(client):
    key, _metadata = _create_key(client)

    with patch("controllers.public_ppt_controller.create_ai_service", return_value=object()), patch(
        "controllers.public_ppt_controller.task_manager.submit_task"
    ) as submit_task:
        first = client.post(
            "/v1/ppt-generations",
            headers=_headers(key, "deck-order-1"),
            json=_payload(),
        )
        second = client.post(
            "/v1/ppt-generations",
            headers=_headers(key, "deck-order-1"),
            json=_payload(),
        )

    assert first.status_code == 202
    assert second.status_code == 200
    first_data = first.get_json()["data"]
    second_data = second.get_json()["data"]
    assert first_data["generation_id"] == second_data["generation_id"]
    assert first_data["current_stage"] == "descriptions"
    submit_task.assert_called_once()

    pages = client.get(first_data["links"]["pages"], headers=_headers(key))
    assert pages.status_code == 200
    page_data = pages.get_json()["data"]["pages"]
    assert [page["title"] for page in page_data] == ["项目背景", "解决方案"]
    assert [page["part"] for page in page_data] == ["现状", "方案"]


def test_idempotency_key_rejects_different_body(client):
    key, _metadata = _create_key(client)
    with patch("controllers.public_ppt_controller.create_ai_service", return_value=object()), patch(
        "controllers.public_ppt_controller.task_manager.submit_task"
    ):
        first = client.post(
            "/v1/ppt-generations",
            headers=_headers(key, "same-key"),
            json=_payload(),
        )
        changed = _payload()
        changed["outline"][0]["title"] = "不同标题"
        second = client.post(
            "/v1/ppt-generations",
            headers=_headers(key, "same-key"),
            json=changed,
        )

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_revoked_key_cannot_access_public_api(client):
    key, metadata = _create_key(client)
    revoked = client.delete(f"/api/api-keys/{metadata['id']}")
    assert revoked.status_code == 200
    response = client.get("/v1/templates", headers=_headers(key))
    assert response.status_code == 401


def test_generation_can_attach_owned_visual_template(client, app, sample_image_file):
    from models import PublicPptGeneration, db

    key, _metadata = _create_key(client)
    uploaded = client.post(
        "/api/user-templates",
        data={"name": "API template", "template_image": (sample_image_file, "template.png")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 200
    template_id = uploaded.get_json()["data"]["template_id"]
    payload = _payload()
    payload["visual"] = {"template_id": template_id, "aspect_ratio": "16:9"}

    with patch("controllers.public_ppt_controller.create_ai_service", return_value=object()), patch(
        "controllers.public_ppt_controller.task_manager.submit_task"
    ):
        response = client.post("/v1/ppt-generations", headers=_headers(key), json=payload)
    assert response.status_code == 202

    with app.app_context():
        generation = db.session.get(
            PublicPptGeneration,
            response.get_json()["data"]["generation_id"],
        )
        assert generation.project.template_image_path
        copied = app.config["UPLOAD_FOLDER"] + "/" + generation.project.template_image_path
        assert Path(copied).is_file()


def test_pipeline_generates_descriptions_then_images(client, app):
    from models import Page, Project, PublicPptGeneration, Task, db
    from services.credit_service import settle_task_credits
    from services.public_ppt_generation_service import run_generation

    key, _metadata = _create_key(client)
    with patch("controllers.public_ppt_controller.create_ai_service", return_value=object()), patch(
        "controllers.public_ppt_controller.task_manager.submit_task"
    ):
        submitted = client.post("/v1/ppt-generations", headers=_headers(key), json=_payload())
    generation_id = submitted.get_json()["data"]["generation_id"]

    class FakeAiService:
        def generate_descriptions_stream(self, _context, outline, _pages, **_kwargs):
            for page in outline:
                yield {"description_text": f"{page['title']}的逐页视觉描述"}
            yield {"__stream_complete__": True}

    def fake_generate_images_task(task_id, project_id, _ai_service, file_service, *_args):
        task = db.session.get(Task, task_id)
        pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
        for page in pages:
            image = Image.new("RGB", (320, 180), color="blue")
            page.generated_image_path = file_service.save_generated_image(image, project_id, page.id)
            page.status = "COMPLETED"
        task.status = "COMPLETED"
        task.completed_at = datetime.utcnow()
        task.set_progress({"stage": "images", "total": len(pages), "completed": len(pages), "failed": 0})
        project = db.session.get(Project, project_id)
        project.status = "COMPLETED"
        settle_task_credits(task_id, completed_units=len(pages), total_units=len(pages))
        db.session.commit()

    with patch(
        "services.public_ppt_generation_service.generate_images_task",
        side_effect=fake_generate_images_task,
    ):
        run_generation(generation_id, FakeAiService(), app)

    with app.app_context():
        generation = db.session.get(PublicPptGeneration, generation_id)
        assert generation.status == "COMPLETED"
        pages = Page.query.filter_by(project_id=generation.project_id).order_by(Page.order_index).all()
        assert [page.get_description_content()["text"] for page in pages] == [
            "项目背景的逐页视觉描述",
            "解决方案的逐页视觉描述",
        ]
        assert all(page.generated_image_path for page in pages)

    result = client.get(f"/v1/ppt-generations/{generation_id}/pages", headers=_headers(key))
    assert result.status_code == 200
    assert all(page["image"]["url"] for page in result.get_json()["data"]["pages"])

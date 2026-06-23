import io
from pathlib import Path

from models import Project, Task, db


def _error_message(response):
    return response.get_json()["error"]["message"]


def test_ppt_to_ppt_requires_reference_file(client):
    response = client.post(
        "/api/projects/ppt-to-ppt",
        data={"content": "Create a deck about bank AI service"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "reference_file" in _error_message(response)


def test_ppt_to_ppt_requires_content(client):
    response = client.post(
        "/api/projects/ppt-to-ppt",
        data={
            "reference_file": (io.BytesIO(b"%PDF-1.4\n"), "reference.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "content" in _error_message(response)


def test_ppt_to_ppt_valid_pdf_creates_project_task_and_submits(
    app, client, monkeypatch
):
    import controllers.ppt_to_ppt_controller as controller

    submitted = {}

    class FakeRenderer:
        def __init__(self, upload_folder):
            self.upload_folder = upload_folder
            self.validated = []

        def validate_reference_file(self, file):
            self.validated.append(file.filename)

    class FakeBlueprintService:
        def __init__(self, ai_service):
            self.ai_service = ai_service

    class FakeGenerationService:
        def __init__(self, ai_service):
            self.ai_service = ai_service

    class FakeTaskManager:
        def submit_task(self, task_id, func, *args, **kwargs):
            submitted["task_id"] = task_id
            submitted["func"] = func
            submitted["args"] = args
            submitted["kwargs"] = kwargs

    def fake_process_task(*args, **kwargs):
        raise AssertionError("background task should not run in controller unit test")

    monkeypatch.setattr(controller, "ReferenceRenderer", FakeRenderer)
    monkeypatch.setattr(controller, "BlueprintService", FakeBlueprintService)
    monkeypatch.setattr(controller, "PptToPptGenerationService", FakeGenerationService)
    monkeypatch.setattr(controller, "get_ai_service", lambda: object())
    monkeypatch.setattr(controller, "task_manager", FakeTaskManager())
    monkeypatch.setattr(controller, "process_ppt_to_ppt_task", fake_process_task)
    monkeypatch.setattr(controller, "_count_reference_pages", lambda path: 7)

    response = client.post(
        "/api/projects/ppt-to-ppt",
        data={
            "content": "Create a deck about bank AI service",
            "extra_requirements": "Use concise headlines",
            "page_count": "5",
            "reference_file": (io.BytesIO(b"%PDF-1.4\n"), "reference.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["project_id"]
    assert payload["task_id"]
    assert payload["reference_page_count"] == 7

    with app.app_context():
        project = db.session.get(Project, payload["project_id"])
        task = db.session.get(Task, payload["task_id"])

        assert project.creation_type == "ppt_to_ppt"
        assert project.idea_prompt == "Create a deck about bank AI service"
        assert project.extra_requirements == "Use concise headlines"
        assert project.status == "PROCESSING"
        assert task.project_id == project.id
        assert task.task_type == "PPT_TO_PPT_ANALYSIS"
        assert task.status == "PENDING"
        assert task.get_progress()["current_step"] == "queued"

    assert submitted["task_id"] == payload["task_id"]
    assert submitted["func"] is fake_process_task
    assert submitted["args"][0] == payload["project_id"]
    assert Path(submitted["args"][1]).name == f"{payload['project_id']}.pdf"
    assert submitted["args"][2].upload_folder == app.config["UPLOAD_FOLDER"]
    assert isinstance(submitted["args"][5], dict)
    assert submitted["args"][5]["page_count"] == "5"
    assert submitted["kwargs"]["app"] is app

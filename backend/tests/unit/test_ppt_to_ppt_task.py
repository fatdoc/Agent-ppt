from pathlib import Path
from types import SimpleNamespace

from models import Page, Project, Task, db
from services.ppt_to_ppt.data_models import (
    GeneratedPptToPptPage,
    PptToPptBlueprint,
)
from services.ppt_to_ppt.generation_service import PptToPptGenerationResult
from services.task_manager import process_ppt_to_ppt_task


class FakeRenderer:
    def __init__(self, rendered):
        self.rendered = rendered
        self.calls = []

    def prepare_reference_deck_from_path(self, file_path, project_id):
        self.calls.append((file_path, project_id))
        return self.rendered


class FakeBlueprintService:
    def __init__(self):
        self.calls = []

    def extract_blueprint(self, page_images, page_texts, options):
        self.calls.append((page_images, page_texts, options))
        return PptToPptBlueprint(
            deck_summary="Reference",
            style_profile={"mood": "professional"},
            narrative_profile={"section_flow": ["cover"]},
            page_patterns=[],
            reference_material_notes=["Use reference for structure only"],
        )


class FakeGenerationService:
    def __init__(self):
        self.calls = []

    def generate(self, user_content, blueprint, options):
        self.calls.append((user_content, blueprint, options))
        return PptToPptGenerationResult(
            outline_text="第1页：智能客服",
            description_text="--- 第1页 ---\n智能客服页面描述",
            pages=[
                GeneratedPptToPptPage(
                    title="智能客服",
                    points=["银行场景"],
                    description="智能客服页面描述",
                    reference_page_index=1,
                    reference_page_role="cover",
                )
            ],
        )


class EmptyGenerationService:
    def generate(self, user_content, blueprint, options):
        return PptToPptGenerationResult(
            outline_text="",
            description_text="",
            pages=[],
        )


def test_process_ppt_to_ppt_task_creates_generated_pages(app, client):
    with app.app_context():
        project = Project(creation_type="ppt_to_ppt", idea_prompt="银行智能客服")
        db.session.add(project)
        db.session.flush()
        old_page = Page(project_id=project.id, order_index=0, status="DRAFT")
        old_page.set_outline_content({"title": "旧页面", "points": []})
        db.session.add(old_page)
        task = Task(project_id=project.id, task_type="PPT_TO_PPT_ANALYSIS", status="PENDING")
        db.session.add(task)
        db.session.commit()

        rendered = SimpleNamespace(
            page_images=[Path("/tmp/page1.png")],
            page_count=1,
            aspect_ratio="16:9",
        )
        renderer = FakeRenderer(rendered)
        blueprint_service = FakeBlueprintService()
        generation_service = FakeGenerationService()

        process_ppt_to_ppt_task(
            task.id,
            project.id,
            reference_file_path="/tmp/reference.pdf",
            renderer=renderer,
            blueprint_service=blueprint_service,
            generation_service=generation_service,
            options_payload={"language": "zh", "page_count": "1"},
            app=app,
        )

        db.session.expire_all()
        refreshed_project = Project.query.get(project.id)
        refreshed_task = Task.query.get(task.id)
        pages = Page.query.filter_by(project_id=project.id).order_by(Page.order_index).all()

        assert renderer.calls == [("/tmp/reference.pdf", project.id)]
        assert blueprint_service.calls[0][0] == rendered.page_images
        assert blueprint_service.calls[0][1] == [""]
        assert blueprint_service.calls[0][2].page_count == 1
        assert generation_service.calls[0][0] == "银行智能客服"
        assert refreshed_project.status == "DESCRIPTIONS_GENERATED"
        assert refreshed_project.outline_text == "第1页：智能客服"
        assert refreshed_project.description_text.startswith("--- 第1页 ---")
        assert refreshed_project.get_ppt_to_ppt_blueprint()["deck_summary"] == "Reference"
        assert refreshed_project.template_style == "{'mood': 'professional'}"
        assert refreshed_project.image_aspect_ratio == "16:9"
        assert refreshed_task.status == "COMPLETED"
        assert refreshed_task.get_progress()["current_step"] == "done"
        assert len(pages) == 1
        assert pages[0].get_outline_content() == {"title": "智能客服", "points": ["银行场景"]}
        assert pages[0].get_description_content()["text"] == "智能客服页面描述"
        assert pages[0].get_description_content()["ppt_to_ppt_reference"] == {
            "page_index": 1,
            "page_role": "cover",
        }


def test_process_ppt_to_ppt_task_empty_generation_fails_and_preserves_pages(app, client):
    with app.app_context():
        project = Project(creation_type="ppt_to_ppt", idea_prompt="银行智能客服")
        db.session.add(project)
        db.session.flush()
        old_page = Page(project_id=project.id, order_index=0, status="DRAFT")
        old_page.set_outline_content({"title": "旧页面", "points": ["保留"]})
        db.session.add(old_page)
        task = Task(project_id=project.id, task_type="PPT_TO_PPT_ANALYSIS", status="PENDING")
        db.session.add(task)
        db.session.commit()

        rendered = SimpleNamespace(
            page_images=[Path("/tmp/page1.png")],
            page_count=1,
            aspect_ratio="16:9",
        )

        process_ppt_to_ppt_task(
            task.id,
            project.id,
            reference_file_path="/tmp/reference.pdf",
            renderer=FakeRenderer(rendered),
            blueprint_service=FakeBlueprintService(),
            generation_service=EmptyGenerationService(),
            options_payload={"language": "zh"},
            app=app,
        )

        db.session.expire_all()
        refreshed_project = Project.query.get(project.id)
        refreshed_task = Task.query.get(task.id)
        pages = Page.query.filter_by(project_id=project.id).order_by(Page.order_index).all()

        assert refreshed_project.status == "DRAFT"
        assert refreshed_task.status == "FAILED"
        assert refreshed_task.error_message == "PPT to PPT generated no pages"
        assert refreshed_task.get_progress()["current_step"] == "failed"
        assert refreshed_task.get_progress()["failed"] == 1
        assert len(pages) == 1
        assert pages[0].id == old_page.id
        assert pages[0].get_outline_content() == {"title": "旧页面", "points": ["保留"]}


def test_process_ppt_to_ppt_task_invalid_options_fail_before_rendering(app, client):
    with app.app_context():
        project = Project(creation_type="ppt_to_ppt", idea_prompt="银行智能客服")
        db.session.add(project)
        db.session.flush()
        task = Task(project_id=project.id, task_type="PPT_TO_PPT_ANALYSIS", status="PENDING")
        db.session.add(task)
        db.session.commit()

        rendered = SimpleNamespace(
            page_images=[Path("/tmp/page1.png")],
            page_count=1,
            aspect_ratio="16:9",
        )
        renderer = FakeRenderer(rendered)

        process_ppt_to_ppt_task(
            task.id,
            project.id,
            reference_file_path="/tmp/reference.pdf",
            renderer=renderer,
            blueprint_service=FakeBlueprintService(),
            generation_service=FakeGenerationService(),
            options_payload={"page_count": "0"},
            app=app,
        )

        db.session.expire_all()
        refreshed_project = Project.query.get(project.id)
        refreshed_task = Task.query.get(task.id)

        assert renderer.calls == []
        assert refreshed_project.status == "DRAFT"
        assert refreshed_task.status == "FAILED"
        assert "page_count" in refreshed_task.error_message
        assert refreshed_task.get_progress()["current_step"] == "failed"

"""Tests for InputGenerationService."""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("GOOGLE_API_KEY", "mock")


def test_validate_outline_rejects_non_list():
    from services.input_generation_service import InputGenerationService

    service = InputGenerationService(ai_service=MagicMock())

    with pytest.raises(ValueError, match="Outline must be a non-empty list"):
        service.validate_outline({"title": "bad"})


def test_validate_outline_rejects_missing_title():
    from services.input_generation_service import InputGenerationService

    service = InputGenerationService(ai_service=MagicMock())

    with pytest.raises(ValueError, match="missing a title"):
        service.validate_outline([{"points": ["one"]}])


def test_validate_descriptions_rejects_count_mismatch():
    from services.input_generation_service import InputGenerationService

    service = InputGenerationService(ai_service=MagicMock())

    with pytest.raises(ValueError, match="Page description count mismatch"):
        service.validate_page_descriptions(["one"], expected_count=2)


def test_validate_descriptions_normalizes_dict_items():
    from services.input_generation_service import InputGenerationService

    service = InputGenerationService(ai_service=MagicMock())

    result = service.validate_page_descriptions(
        [{"text": "第一页面描述", "extra_fields": {"排版布局": "左右分栏"}}],
        expected_count=1,
    )

    assert result == [{"text": "第一页面描述", "extra_fields": {"排版布局": "左右分栏"}}]


def test_build_outline_dispatches_outline_input():
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    ai = MagicMock()
    ai.parse_outline_text.return_value = [{"title": "封面", "points": []}]
    service = InputGenerationService(ai_service=ai)

    options = InputGenerationOptions(input_kind="outline", target_depth="outline_only", language="zh")
    result = service.build_outline("outline", object(), options)

    assert result == [{"title": "封面", "points": []}]
    ai.parse_outline_text.assert_called_once()


def test_build_outline_dispatches_description_input():
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    ai = MagicMock()
    ai.parse_description_to_outline.return_value = [{"title": "背景", "points": []}]
    service = InputGenerationService(ai_service=ai)

    options = InputGenerationOptions(input_kind="description", target_depth="outline_only", language="zh")
    result = service.build_outline("description", object(), options)

    assert result == [{"title": "背景", "points": []}]
    ai.parse_description_to_outline.assert_called_once()


def test_build_outline_prefers_provided_outline_for_description_input():
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    class Context:
        outline_text = "第一页：封面\n第二页：方案"

    ai = MagicMock()
    ai.parse_outline_text.return_value = [{"title": "封面", "points": []}]
    service = InputGenerationService(ai_service=ai)

    options = InputGenerationOptions(input_kind="description", target_depth="outline_and_descriptions", language="zh")
    result = service.build_outline("description", Context(), options)

    assert result == [{"title": "封面", "points": []}, {"title": "方案", "points": []}]
    ai.parse_outline_text.assert_not_called()
    ai.parse_description_to_outline.assert_not_called()


def test_build_outline_parses_common_page_headers_without_ai():
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    class Context:
        outline_text = "第1页：封面\n- 项目名称\n\n第2页：方案\n- 目标\n- 路径"

    ai = MagicMock()
    service = InputGenerationService(ai_service=ai)

    options = InputGenerationOptions(input_kind="outline", target_depth="outline_only", language="zh")
    result = service.build_outline("outline", Context(), options)

    assert result == [
        {"title": "封面", "points": ["项目名称"]},
        {"title": "方案", "points": ["目标", "路径"]},
    ]
    ai.parse_outline_text.assert_not_called()


def test_build_descriptions_uses_description_split_for_description_input():
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    outline = [{"title": "背景", "points": []}]
    ai = MagicMock()
    ai.parse_description_to_page_descriptions.return_value = ["背景页描述"]
    service = InputGenerationService(ai_service=ai)

    options = InputGenerationOptions(input_kind="description", target_depth="outline_and_descriptions", language="zh")
    result = service.build_descriptions("description", outline, object(), options)

    assert result == [{"text": "背景页描述"}]
    ai.parse_description_to_page_descriptions.assert_called_once()


def test_build_descriptions_splits_common_page_headers_without_ai():
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    class Context:
        description_text = "第1页：封面\n展示项目名称。\n\n第2页：方案\n展示目标和路径。"

    outline = [{"title": "封面", "points": []}, {"title": "方案", "points": []}]
    ai = MagicMock()
    service = InputGenerationService(ai_service=ai)

    options = InputGenerationOptions(input_kind="description", target_depth="outline_and_descriptions", language="zh")
    result = service.build_descriptions("description", outline, Context(), options)

    assert result == [
        {"text": "页面标题：封面\n展示项目名称。"},
        {"text": "页面标题：方案\n展示目标和路径。"},
    ]
    ai.parse_description_to_page_descriptions.assert_not_called()


@pytest.fixture
def input_generation_app(tmp_path):
    from flask import Flask
    from models import db

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path}/test.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
    yield app


def test_save_pages_merge_by_index_preserves_existing_description_and_image(input_generation_app):
    from models import Page, Project, db
    from services.input_generation_service import InputGenerationService

    with input_generation_app.app_context():
        project = Project(id="merge-project", creation_type="idea", idea_prompt="test")
        db.session.add(project)
        page = Page(project_id=project.id, order_index=0, status="IMAGE_GENERATED")
        page.generated_image_path = "/tmp/page.png"
        page.set_outline_content({"title": "旧标题", "points": ["旧要点"]})
        page.set_description_content({"text": "保留描述"})
        db.session.add(page)
        db.session.commit()

        service = InputGenerationService(ai_service=MagicMock())

        saved = service.save_pages(
            project.id,
            [{"title": "新标题", "points": ["新要点"]}],
            page_descriptions=None,
            mode="merge_by_index",
        )
        db.session.commit()

        assert len(saved) == 1
        assert saved[0].id == page.id
        assert saved[0].get_outline_content()["title"] == "新标题"
        assert saved[0].get_description_content()["text"] == "保留描述"
        assert saved[0].generated_image_path == "/tmp/page.png"


def test_save_pages_replace_writes_descriptions(input_generation_app):
    from models import Page, Project, db
    from services.input_generation_service import InputGenerationService

    with input_generation_app.app_context():
        project = Project(id="replace-project", creation_type="descriptions", description_text="test")
        db.session.add(project)
        old_page = Page(project_id=project.id, order_index=0, status="IMAGE_GENERATED")
        old_page.set_outline_content({"title": "旧标题", "points": []})
        db.session.add(old_page)
        db.session.commit()

        service = InputGenerationService(ai_service=MagicMock())

        saved = service.save_pages(
            project.id,
            [{"title": "新标题", "points": ["要点"]}],
            page_descriptions=[{"text": "新描述"}],
            mode="replace",
        )
        db.session.commit()

        assert len(saved) == 1
        assert Page.query.count() == 1
        assert saved[0].id != old_page.id
        assert saved[0].status == "DESCRIPTION_GENERATED"
        assert saved[0].get_description_content()["text"] == "新描述"


def test_save_pages_merge_by_index_preserves_existing_status_without_description(input_generation_app):
    from models import Page, Project, db
    from services.input_generation_service import InputGenerationService

    with input_generation_app.app_context():
        project = Project(id="status-project", creation_type="idea", idea_prompt="test")
        db.session.add(project)
        page = Page(project_id=project.id, order_index=0, status="IMAGE_GENERATED")
        page.generated_image_path = "/tmp/page.png"
        page.set_outline_content({"title": "旧标题", "points": []})
        db.session.add(page)
        db.session.commit()

        service = InputGenerationService(ai_service=MagicMock())

        saved = service.save_pages(
            project.id,
            [{"title": "新标题", "points": []}],
            page_descriptions=None,
            mode="merge_by_index",
        )

        assert saved[0].status == "IMAGE_GENERATED"


def test_generate_saves_outline_and_descriptions(input_generation_app):
    from models import Project, db
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    with input_generation_app.app_context():
        project = Project(id="generate-project", creation_type="descriptions", description_text="完整描述")
        db.session.add(project)
        db.session.commit()

        ai = MagicMock()
        ai.parse_description_to_outline.return_value = [{"title": "封面", "points": []}]
        ai.parse_description_to_page_descriptions.return_value = ["封面描述"]
        service = InputGenerationService(ai_service=ai)
        options = InputGenerationOptions(
            input_kind="description",
            target_depth="outline_and_descriptions",
            language="zh",
        )

        result = service.generate(project, object(), options, save_mode="replace")
        db.session.commit()

        assert result.status == "DESCRIPTIONS_GENERATED"
        assert result.page_count == 1
        assert project.status == "DESCRIPTIONS_GENERATED"
        assert project.pages[0].get_outline_content()["title"] == "封面"
        assert project.pages[0].get_description_content()["text"] == "封面描述"


def test_generate_outline_only_preserves_descriptions_generated_status(input_generation_app):
    from models import Page, Project, db
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    with input_generation_app.app_context():
        project = Project(id="outlined-project", creation_type="idea", idea_prompt="test")
        db.session.add(project)
        page = Page(project_id=project.id, order_index=0, status="DESCRIPTION_GENERATED")
        page.set_outline_content({"title": "旧标题", "points": []})
        page.set_description_content({"text": "已有描述"})
        db.session.add(page)
        db.session.commit()

        ai = MagicMock()
        ai.generate_outline.return_value = [{"title": "新标题", "points": []}]
        service = InputGenerationService(ai_service=ai)
        options = InputGenerationOptions(
            input_kind="idea",
            target_depth="outline_only",
            language="zh",
        )

        result = service.generate(project, object(), options, save_mode="merge_by_index")

        assert result.status == "DESCRIPTIONS_GENERATED"
        assert project.status == "DESCRIPTIONS_GENERATED"
        assert project.pages[0].get_description_content()["text"] == "已有描述"

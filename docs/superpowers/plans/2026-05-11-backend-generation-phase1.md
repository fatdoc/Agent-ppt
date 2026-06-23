# Backend Generation Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a unified backend text generation service so outline generation and description-input generation share validation, page saving, and project status updates without changing the existing frontend API surface.

**Architecture:** Add `InputGenerationService` as a narrow service beneath the current project controller. The service delegates AI calls to the existing `AIService`, validates outline and description structures before persistence, and centralizes `Page` merge/replace behavior. Existing endpoints remain in `project_controller.py`, but `generate_outline` and `generate_from_description` call the new service instead of duplicating orchestration logic.

**Tech Stack:** Python, Flask, SQLAlchemy, pytest, existing `AIService`/`ProjectContext` abstractions

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/services/input_generation_service.py` | Dataclasses, outline/description orchestration, validation, page persistence |
| Modify | `backend/services/__init__.py` | Export `InputGenerationService`, `InputGenerationOptions`, `InputGenerationResult` |
| Modify | `backend/controllers/project_controller.py` | Route `generate_outline` and `generate_from_description` through the new service |
| Create | `backend/tests/unit/test_input_generation_service.py` | Unit tests for validation, AI dispatch, page save modes, status updates |
| Modify | `backend/tests/unit/test_api_project.py` | Regression tests for legacy endpoint behavior with mocked service |

---

### Task 1: Add InputGenerationService Data Contracts And Validation

**Files:**
- Create: `backend/services/input_generation_service.py`
- Test: `backend/tests/unit/test_input_generation_service.py`

- [ ] **Step 1: Write failing validation tests**

Create `backend/tests/unit/test_input_generation_service.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest backend/tests/unit/test_input_generation_service.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services.input_generation_service'`.

- [ ] **Step 3: Add service dataclasses and validation**

Create `backend/services/input_generation_service.py`:

```python
"""Unified text generation orchestration for project inputs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from models import db, Page


@dataclass
class InputGenerationOptions:
    input_kind: str
    target_depth: str
    language: str
    detail_level: str | None = None
    reference_file_ids: list[str] | None = None
    style_policy: str | None = None
    page_count_hint: str | None = None
    scenario: str | None = None
    tone: str | None = None


@dataclass
class InputGenerationResult:
    input_kind: str
    outline: list[dict[str, Any]]
    page_descriptions: list[dict[str, Any]] | None
    status: str
    page_count: int


class InputGenerationService:
    """Generate, validate, and persist text artifacts for slide projects."""

    VALID_INPUT_KINDS = {"idea", "outline", "description", "no_think", "blueprint_topic"}
    VALID_TARGET_DEPTHS = {"outline_only", "outline_and_descriptions"}

    def __init__(self, ai_service):
        self.ai_service = ai_service

    def validate_outline(self, outline: Any) -> list[dict[str, Any]]:
        if not isinstance(outline, list) or not outline:
            raise ValueError("Outline must be a non-empty list")

        pages = self.ai_service.flatten_outline(outline)
        if not isinstance(pages, list) or not pages:
            raise ValueError("Outline must contain at least one page")

        for index, page in enumerate(pages, start=1):
            if not isinstance(page, dict):
                raise ValueError(f"Outline page {index} must be an object")
            title = page.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ValueError(f"Outline page {index} is missing a title")
            points = page.get("points", [])
            if points is not None and not isinstance(points, list):
                raise ValueError(f"Outline page {index} points must be a list")

        return outline

    def validate_page_descriptions(
        self,
        page_descriptions: Any,
        expected_count: int,
    ) -> list[dict[str, Any]]:
        if not isinstance(page_descriptions, list):
            raise ValueError("Page descriptions must be a list")

        if len(page_descriptions) != expected_count:
            raise ValueError(
                f"Page description count mismatch: expected {expected_count}, got {len(page_descriptions)}"
            )

        normalized = []
        for index, item in enumerate(page_descriptions, start=1):
            if isinstance(item, str):
                text = item.strip()
                extra_fields = None
            elif isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                extra_fields = item.get("extra_fields")
            else:
                text = str(item).strip()
                extra_fields = None

            if not text:
                raise ValueError(f"Page description {index} is empty")

            desc = {"text": text}
            if isinstance(extra_fields, dict) and extra_fields:
                desc["extra_fields"] = extra_fields
            normalized.append(desc)

        return normalized
```

- [ ] **Step 4: Run validation tests**

Run:

```bash
uv run pytest backend/tests/unit/test_input_generation_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/input_generation_service.py backend/tests/unit/test_input_generation_service.py
git commit -m "feat(backend): add input generation validation service"
```

---

### Task 2: Implement Outline And Description Orchestration

**Files:**
- Modify: `backend/services/input_generation_service.py`
- Test: `backend/tests/unit/test_input_generation_service.py`

- [ ] **Step 1: Add failing AI dispatch tests**

Append to `backend/tests/unit/test_input_generation_service.py`:

```python
def test_build_outline_dispatches_outline_input():
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    ai = MagicMock()
    ai.parse_outline_text.return_value = [{"title": "封面", "points": []}]
    ai.flatten_outline.return_value = [{"title": "封面", "points": []}]
    service = InputGenerationService(ai_service=ai)

    options = InputGenerationOptions(input_kind="outline", target_depth="outline_only", language="zh")
    result = service.build_outline("outline", object(), options)

    assert result == [{"title": "封面", "points": []}]
    ai.parse_outline_text.assert_called_once()


def test_build_outline_dispatches_description_input():
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    ai = MagicMock()
    ai.parse_description_to_outline.return_value = [{"title": "背景", "points": []}]
    ai.flatten_outline.return_value = [{"title": "背景", "points": []}]
    service = InputGenerationService(ai_service=ai)

    options = InputGenerationOptions(input_kind="description", target_depth="outline_only", language="zh")
    result = service.build_outline("description", object(), options)

    assert result == [{"title": "背景", "points": []}]
    ai.parse_description_to_outline.assert_called_once()


def test_build_descriptions_uses_description_split_for_description_input():
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    outline = [{"title": "背景", "points": []}]
    ai = MagicMock()
    ai.flatten_outline.return_value = [{"title": "背景", "points": []}]
    ai.parse_description_to_page_descriptions.return_value = ["背景页描述"]
    service = InputGenerationService(ai_service=ai)

    options = InputGenerationOptions(input_kind="description", target_depth="outline_and_descriptions", language="zh")
    result = service.build_descriptions("description", outline, object(), options)

    assert result == [{"text": "背景页描述"}]
    ai.parse_description_to_page_descriptions.assert_called_once()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest backend/tests/unit/test_input_generation_service.py -q
```

Expected: FAIL with `AttributeError` for missing `build_outline` and `build_descriptions`.

- [ ] **Step 3: Add orchestration methods**

In `backend/services/input_generation_service.py`, add these methods inside `InputGenerationService`:

```python
    def build_outline(
        self,
        input_kind: str,
        project_context,
        options: InputGenerationOptions,
    ) -> list[dict[str, Any]]:
        if input_kind == "outline":
            outline = self.ai_service.parse_outline_text(project_context, language=options.language)
        elif input_kind in {"description", "descriptions"}:
            outline = self.ai_service.parse_description_to_outline(project_context, language=options.language)
        elif input_kind in {"idea", "no_think", "blueprint_topic"}:
            outline = self.ai_service.generate_outline(project_context, language=options.language)
        else:
            raise ValueError(f"Unsupported input_kind: {input_kind}")

        return self.validate_outline(outline)

    def build_descriptions(
        self,
        input_kind: str,
        outline: list[dict[str, Any]],
        project_context,
        options: InputGenerationOptions,
    ) -> list[dict[str, Any]] | None:
        if options.target_depth == "outline_only":
            return None

        pages = self.ai_service.flatten_outline(outline)

        if input_kind in {"description", "descriptions"}:
            raw_descriptions = self.ai_service.parse_description_to_page_descriptions(
                project_context,
                outline,
                language=options.language,
            )
            return self.validate_page_descriptions(raw_descriptions, expected_count=len(pages))

        descriptions = []
        for page_index, page_outline in enumerate(pages, start=1):
            desc = self.ai_service.generate_page_description(
                project_context,
                outline,
                page_outline,
                page_index,
                language=options.language,
                detail_level=options.detail_level or "default",
            )
            descriptions.append(desc)

        return self.validate_page_descriptions(descriptions, expected_count=len(pages))
```

- [ ] **Step 4: Run orchestration tests**

Run:

```bash
uv run pytest backend/tests/unit/test_input_generation_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/input_generation_service.py backend/tests/unit/test_input_generation_service.py
git commit -m "feat(backend): orchestrate input text generation"
```

---

### Task 3: Centralize Page Persistence

**Files:**
- Modify: `backend/services/input_generation_service.py`
- Test: `backend/tests/unit/test_input_generation_service.py`

- [ ] **Step 1: Add failing persistence tests**

Append to `backend/tests/unit/test_input_generation_service.py`:

```python
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
    from models import db, Page, Project
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

        ai = MagicMock()
        ai.flatten_outline.return_value = [{"title": "新标题", "points": ["新要点"]}]
        service = InputGenerationService(ai_service=ai)

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
    from models import db, Page, Project
    from services.input_generation_service import InputGenerationService

    with input_generation_app.app_context():
        project = Project(id="replace-project", creation_type="descriptions", description_text="test")
        db.session.add(project)
        old_page = Page(project_id=project.id, order_index=0, status="IMAGE_GENERATED")
        old_page.set_outline_content({"title": "旧标题", "points": []})
        db.session.add(old_page)
        db.session.commit()

        ai = MagicMock()
        ai.flatten_outline.return_value = [{"title": "新标题", "points": ["要点"]}]
        service = InputGenerationService(ai_service=ai)

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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest backend/tests/unit/test_input_generation_service.py -q
```

Expected: FAIL with `AttributeError: 'InputGenerationService' object has no attribute 'save_pages'`.

- [ ] **Step 3: Implement save_pages**

In `backend/services/input_generation_service.py`, add this method inside `InputGenerationService`:

```python
    def save_pages(
        self,
        project_id: str,
        outline: list[dict[str, Any]],
        page_descriptions: list[dict[str, Any]] | None = None,
        mode: str = "merge_by_index",
    ) -> list[Page]:
        if mode not in {"replace", "merge_by_index"}:
            raise ValueError(f"Unsupported save mode: {mode}")

        outline = self.validate_outline(outline)
        pages_data = self.ai_service.flatten_outline(outline)
        if page_descriptions is not None:
            page_descriptions = self.validate_page_descriptions(
                page_descriptions,
                expected_count=len(pages_data),
            )

        old_pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
        if mode == "replace":
            for old_page in old_pages:
                db.session.delete(old_page)
            old_pages = []

        pages_list = []
        for index, page_data in enumerate(pages_data):
            if mode == "merge_by_index" and index < len(old_pages):
                page = old_pages[index]
            else:
                page = Page(project_id=project_id, status="DRAFT")
                db.session.add(page)

            page.order_index = index
            page.part = page_data.get("part")
            page.set_outline_content({
                "title": page_data.get("title"),
                "points": page_data.get("points", []),
            })

            if page_descriptions is not None:
                desc = dict(page_descriptions[index])
                desc.setdefault("generated_at", datetime.utcnow().isoformat())
                page.set_description_content(desc)
                page.status = "DESCRIPTION_GENERATED"
            elif not page.description_content and page.status != "DRAFT":
                page.status = "DRAFT"

            pages_list.append(page)

        if mode == "merge_by_index":
            for old_page in old_pages[len(pages_data):]:
                db.session.delete(old_page)

        return pages_list
```

- [ ] **Step 4: Run persistence tests**

Run:

```bash
uv run pytest backend/tests/unit/test_input_generation_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/input_generation_service.py backend/tests/unit/test_input_generation_service.py
git commit -m "feat(backend): centralize input page persistence"
```

---

### Task 4: Add The Public Generate Method

**Files:**
- Modify: `backend/services/input_generation_service.py`
- Modify: `backend/services/__init__.py`
- Test: `backend/tests/unit/test_input_generation_service.py`

- [ ] **Step 1: Add failing generate test**

Append to `backend/tests/unit/test_input_generation_service.py`:

```python
def test_generate_saves_outline_and_descriptions(input_generation_app):
    from models import db, Project
    from services.input_generation_service import InputGenerationOptions, InputGenerationService

    with input_generation_app.app_context():
        project = Project(id="generate-project", creation_type="descriptions", description_text="完整描述")
        db.session.add(project)
        db.session.commit()

        ai = MagicMock()
        ai.parse_description_to_outline.return_value = [{"title": "封面", "points": []}]
        ai.parse_description_to_page_descriptions.return_value = ["封面描述"]
        ai.flatten_outline.return_value = [{"title": "封面", "points": []}]
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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest backend/tests/unit/test_input_generation_service.py -q
```

Expected: FAIL with `AttributeError: 'InputGenerationService' object has no attribute 'generate'`.

- [ ] **Step 3: Implement generate**

In `backend/services/input_generation_service.py`, add this method inside `InputGenerationService`:

```python
    def generate(
        self,
        project,
        project_context,
        options: InputGenerationOptions,
        save_mode: str = "merge_by_index",
    ) -> InputGenerationResult:
        if options.input_kind not in self.VALID_INPUT_KINDS:
            raise ValueError(f"Unsupported input_kind: {options.input_kind}")
        if options.target_depth not in self.VALID_TARGET_DEPTHS:
            raise ValueError(f"Unsupported target_depth: {options.target_depth}")

        outline = self.build_outline(options.input_kind, project_context, options)
        page_descriptions = self.build_descriptions(options.input_kind, outline, project_context, options)
        pages = self.save_pages(project.id, outline, page_descriptions, mode=save_mode)

        if page_descriptions is not None and pages:
            status = "DESCRIPTIONS_GENERATED"
        else:
            status = "OUTLINE_GENERATED"

        project.status = status
        project.updated_at = datetime.utcnow()

        return InputGenerationResult(
            input_kind=options.input_kind,
            outline=outline,
            page_descriptions=page_descriptions,
            status=status,
            page_count=len(pages),
        )
```

- [ ] **Step 4: Export the new service**

Modify `backend/services/__init__.py`:

```python
"""Services package"""
from .ai_service import AIService, ProjectContext
from .file_service import FileService
from .export_service import ExportService
from .input_generation_service import (
    InputGenerationOptions,
    InputGenerationResult,
    InputGenerationService,
)

__all__ = [
    'AIService',
    'ProjectContext',
    'FileService',
    'ExportService',
    'InputGenerationOptions',
    'InputGenerationResult',
    'InputGenerationService',
]
```

- [ ] **Step 5: Run service tests**

Run:

```bash
uv run pytest backend/tests/unit/test_input_generation_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/input_generation_service.py backend/services/__init__.py backend/tests/unit/test_input_generation_service.py
git commit -m "feat(backend): add unified input generation entrypoint"
```

---

### Task 5: Route Legacy Non-Streaming Endpoints Through The Service

**Files:**
- Modify: `backend/controllers/project_controller.py`
- Modify: `backend/tests/unit/test_api_project.py`

- [ ] **Step 1: Add endpoint regression tests**

Append to `backend/tests/unit/test_api_project.py`:

```python
class TestProjectGenerationEndpoints:
    """Legacy project generation endpoint tests."""

    def test_generate_outline_idea_uses_existing_api_shape(self, client, monkeypatch):
        from services.input_generation_service import InputGenerationResult

        created = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '生成 AI 主题 PPT',
        }).get_json()['data']
        project_id = created['project_id']

        class FakeInputGenerationService:
            def __init__(self, ai_service):
                self.ai_service = ai_service

            def generate(self, project, project_context, options, save_mode='merge_by_index'):
                from models import db, Page
                page = Page(project_id=project.id, order_index=0, status='DRAFT')
                page.set_outline_content({'title': '封面', 'points': ['主题']})
                db.session.add(page)
                project.pages.append(page)
                project.status = 'OUTLINE_GENERATED'
                return InputGenerationResult(
                    input_kind=options.input_kind,
                    outline=[{'title': '封面', 'points': ['主题']}],
                    page_descriptions=None,
                    status='OUTLINE_GENERATED',
                    page_count=1,
                )

        monkeypatch.setattr('controllers.project_controller.InputGenerationService', FakeInputGenerationService)

        response = client.post(f'/api/projects/{project_id}/generate/outline', json={'language': 'zh'})

        data = assert_success_response(response)
        assert data['data']['pages'][0]['outline_content']['title'] == '封面'

    def test_generate_from_description_uses_existing_api_shape(self, client, monkeypatch):
        from services.input_generation_service import InputGenerationResult

        created = client.post('/api/projects', json={
            'creation_type': 'descriptions',
            'description_text': '第1页 封面：介绍主题',
        }).get_json()['data']
        project_id = created['project_id']

        class FakeInputGenerationService:
            def __init__(self, ai_service):
                self.ai_service = ai_service

            def generate(self, project, project_context, options, save_mode='merge_by_index'):
                from models import db, Page
                page = Page(project_id=project.id, order_index=0, status='DESCRIPTION_GENERATED')
                page.set_outline_content({'title': '封面', 'points': ['介绍主题']})
                page.set_description_content({'text': '封面页描述'})
                db.session.add(page)
                project.pages.append(page)
                project.status = 'DESCRIPTIONS_GENERATED'
                return InputGenerationResult(
                    input_kind=options.input_kind,
                    outline=[{'title': '封面', 'points': ['介绍主题']}],
                    page_descriptions=[{'text': '封面页描述'}],
                    status='DESCRIPTIONS_GENERATED',
                    page_count=1,
                )

        monkeypatch.setattr('controllers.project_controller.InputGenerationService', FakeInputGenerationService)

        response = client.post(f'/api/projects/{project_id}/generate/from-description', json={'language': 'zh'})

        data = assert_success_response(response)
        assert data['data']['status'] == 'DESCRIPTIONS_GENERATED'
        assert data['data']['pages'][0]['description_content']['text'] == '封面页描述'
```

- [ ] **Step 2: Run endpoint tests and verify failure**

Run:

```bash
uv run pytest backend/tests/unit/test_api_project.py::TestProjectGenerationEndpoints -q
```

Expected: FAIL because `controllers.project_controller.InputGenerationService` is not imported.

- [ ] **Step 3: Import the service in project_controller**

Modify the imports near the top of `backend/controllers/project_controller.py`:

```python
from services import (
    ProjectContext,
    FileService,
    InputGenerationOptions,
    InputGenerationService,
)
```

- [ ] **Step 4: Replace generate_outline orchestration**

Inside `generate_outline`, keep the existing request validation and reference file loading, then replace the AI branching and `_smart_merge_pages` block with:

```python
        if project.creation_type == 'outline':
            if not project.outline_text:
                return bad_request("outline_text is required for outline type project")
            input_kind = 'outline'
        elif project.creation_type == 'descriptions':
            if not project.description_text:
                return bad_request("description_text is required for descriptions type project")
            input_kind = 'description'
        else:
            idea_prompt = data.get('idea_prompt') or project.idea_prompt
            if not idea_prompt:
                return bad_request("idea_prompt is required")
            project.idea_prompt = idea_prompt
            input_kind = 'idea'

        project_context = ProjectContext(project, reference_files_content)
        generation_service = InputGenerationService(ai_service)
        generation_service.generate(
            project,
            project_context,
            InputGenerationOptions(
                input_kind=input_kind,
                target_depth='outline_only',
                language=language,
                detail_level=data.get('detail_level'),
            ),
            save_mode='merge_by_index',
        )

        pages_list = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
```

- [ ] **Step 5: Replace generate_from_description orchestration**

Inside `generate_from_description`, keep validation of project existence, creation type, `description_text`, language, and reference file loading. Replace the duplicated parse/split/delete/create block with:

```python
        project_context = ProjectContext(project, reference_files_content)
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
```

- [ ] **Step 6: Run endpoint regression tests**

Run:

```bash
uv run pytest backend/tests/unit/test_api_project.py::TestProjectGenerationEndpoints -q
```

Expected: PASS.

- [ ] **Step 7: Run related smart merge regression tests**

Run:

```bash
uv run pytest backend/tests/unit/test_smart_merge.py backend/tests/unit/test_input_generation_service.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/controllers/project_controller.py backend/tests/unit/test_api_project.py
git commit -m "refactor(backend): route legacy input generation through service"
```

---

### Task 6: Verify Phase 1 Regression Surface

**Files:**
- No code changes

- [ ] **Step 1: Run focused backend unit tests**

Run:

```bash
uv run pytest backend/tests/unit/test_input_generation_service.py backend/tests/unit/test_smart_merge.py backend/tests/unit/test_api_project.py -q
```

Expected: PASS.

- [ ] **Step 2: Run generation-related integration smoke tests**

Run:

```bash
uv run pytest backend/tests/integration/test_full_workflow.py backend/tests/integration/test_api_full_flow.py -q
```

Expected: PASS, or failures only where tests require unavailable external AI credentials.

- [ ] **Step 3: Compile changed backend modules**

Run:

```bash
uv run python -m py_compile backend/services/input_generation_service.py backend/controllers/project_controller.py backend/services/__init__.py
```

Expected: No output.

- [ ] **Step 4: Review git diff**

Run:

```bash
git diff -- backend/services/input_generation_service.py backend/services/__init__.py backend/controllers/project_controller.py backend/tests/unit/test_input_generation_service.py backend/tests/unit/test_api_project.py
```

Expected: Diff only contains Phase 1 service extraction, endpoint routing, and tests.

---

## Phase 1 Completion Criteria

- `generate_outline` and `generate_from_description` share `InputGenerationService`.
- `InputGenerationService` does not upload files, split PPT/PDF files, decide renovation semantics, decide PPT-to-PPT semantics, or choose image reference priority.
- Description-input generation returns a clear `ValueError` when outline and description counts mismatch.
- AI returning malformed outline or empty description data fails before controller persistence.
- Existing frontend endpoints and response shapes remain unchanged.
- `_smart_merge_pages` remains available until streaming outline/refine endpoints are moved in a later phase.

## Deferred To Later Plans

- Streaming outline and streaming description generation refactor.
- `VisualGuidanceService` and image prompt layering.
- No Think PPT option normalization.
- `BlueprintService`, `ppt_blueprint` creation type, blueprint upload endpoint, and per-page blueprint image references.

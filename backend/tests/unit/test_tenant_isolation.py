"""Regression guards for account-scoped project and page APIs.

These tests deliberately use real signed web-auth tokens and two database users.
The attacker's token must never authorize access to IDs owned by the victim.
"""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from models import (
    DeckVersion,
    DeckVisualSystem,
    GenerationJob,
    Page,
    PageImageVersion,
    PageVisualPlan,
    Project,
    SlideVersion,
    Task,
    User,
    db,
)
from utils.auth import create_auth_token


def _slide_plan(title: str) -> dict:
    return {
        "slide_id": "slide-1",
        "title": title,
        "main_message": f"{title} main message",
        "content_points": [f"{title} point"],
        "layout_intent": "balanced layout",
        "visual_focus": f"{title} visual focus",
    }


def _visual_plan(page_id: str, takeaway: str) -> dict:
    return {
        "page_id": page_id,
        "strategy_id": "native",
        "source_anchor": "victim source",
        "reader_takeaway": takeaway,
        "page_role": "content",
        "composition": "single focal object with supporting labels",
        "labels": ["victim label"],
        "negative_prompts": [],
        "visual_prompt": "victim visual prompt",
        "structure_prompt": "victim structure prompt",
        "style_prompt": "victim style prompt",
    }


@pytest.fixture
def tenant_case(client, app):
    """Create an attacker plus a complete Agent/Page graph owned by a victim."""
    with app.app_context():
        attacker = User(username="tenant-attacker", email="attacker@example.test")
        attacker.set_password("attacker-password")
        victim = User(username="tenant-victim", email="victim@example.test")
        victim.set_password("victim-password")
        db.session.add_all([attacker, victim])
        db.session.flush()

        attacker_project = Project(
            user_id=attacker.id,
            project_title="Attacker project",
            creation_type="idea",
            idea_prompt="attacker content",
        )
        victim_project = Project(
            user_id=victim.id,
            project_title="Victim project",
            creation_type="agent_mode",
            idea_prompt="victim confidential content",
            status="AGENT_PLAN_PENDING_CONFIRMATION",
        )
        db.session.add_all([attacker_project, victim_project])
        db.session.flush()

        page = Page(
            project_id=victim_project.id,
            order_index=0,
            part="victim section",
            narration_text="victim narration",
            generated_image_path=f"{victim_project.id}/pages/victim-v1.png",
            status="IMAGE_GENERATED",
        )
        page.set_outline_content({"title": "Victim title", "points": ["Victim point"]})
        page.set_description_content({"text": "Victim description"})
        db.session.add(page)
        db.session.flush()

        first_image = PageImageVersion(
            page_id=page.id,
            image_path=f"{victim_project.id}/pages/victim-v1.png",
            version_number=1,
            is_current=True,
        )
        second_image = PageImageVersion(
            page_id=page.id,
            image_path=f"{victim_project.id}/pages/victim-v2.png",
            version_number=2,
            is_current=False,
        )
        db.session.add_all([first_image, second_image])

        deck = DeckVersion(project_id=victim_project.id, status="pending_confirmation")
        deck.set_deck_plan(
            {
                "title": "Victim confidential deck",
                "audience": "Victim audience",
                "goal": "Victim goal",
                "slides": [_slide_plan("Victim slide")],
            }
        )
        db.session.add(deck)
        db.session.flush()

        visual_system = DeckVisualSystem(
            project_id=victim_project.id,
            deck_version_id=deck.id,
            strategy_id="native",
        )
        visual_system.set_system({"strategy_id": "native"})
        db.session.add(visual_system)
        db.session.flush()

        slide = SlideVersion(
            deck_version_id=deck.id,
            page_id=page.id,
            order_index=0,
            status="pending_confirmation",
            locked=False,
        )
        slide.set_slide_plan(_slide_plan("Victim slide"))
        slide.set_qa_result({"passed": True, "issues": []})
        db.session.add(slide)
        db.session.flush()

        visual_plan = PageVisualPlan(
            project_id=victim_project.id,
            page_id=page.id,
            slide_version_id=slide.id,
            deck_visual_system_id=visual_system.id,
            strategy_id="native",
            status="pending_confirmation",
        )
        visual_plan.set_plan(_visual_plan(page.id, "Victim takeaway"))
        visual_plan.set_qa_result({"passed": True, "issues": []})
        db.session.add(visual_plan)
        db.session.flush()

        existing_job = GenerationJob(
            project_id=victim_project.id,
            page_id=page.id,
            slide_version_id=slide.id,
            visual_plan_version_id=visual_plan.id,
            job_type="audit-existing",
            idempotency_key=f"audit-existing:{slide.id}",
            input_hash="audit-input-hash",
            status="pending",
        )
        db.session.add(existing_job)
        db.session.commit()

        token = create_auth_token(attacker)
        case = SimpleNamespace(
            headers={"Authorization": f"Bearer {token}"},
            attacker_id=attacker.id,
            attacker_project_id=attacker_project.id,
            victim_id=victim.id,
            project_id=victim_project.id,
            page_id=page.id,
            first_image_id=first_image.id,
            second_image_id=second_image.id,
            deck_id=deck.id,
            slide_id=slide.id,
            visual_plan_id=visual_plan.id,
            existing_job_id=existing_job.id,
        )

    return case


def _agent_url(case, suffix: str = "") -> str:
    base = f"/api/agent-mode/projects/{case.project_id}/deck-versions/{case.deck_id}"
    return f"{base}{suffix}"


def _page_url(case, suffix: str = "") -> str:
    base = f"/api/projects/{case.project_id}/pages/{case.page_id}"
    return f"{base}{suffix}"


def test_foreign_agent_deck_is_not_readable(client, tenant_case):
    response = client.get(_agent_url(tenant_case), headers=tenant_case.headers)

    assert response.status_code == 404, response.get_json()


def test_foreign_agent_slide_content_is_not_mutable(client, app, tenant_case):
    with app.app_context():
        before = deepcopy(db.session.get(SlideVersion, tenant_case.slide_id).get_slide_plan())

    response = client.put(
        _agent_url(tenant_case, f"/slides/{tenant_case.slide_id}/content"),
        headers=tenant_case.headers,
        json={"slide_plan": _slide_plan("Attacker replacement")},
    )

    with app.app_context():
        db.session.expire_all()
        after = db.session.get(SlideVersion, tenant_case.slide_id).get_slide_plan()
    assert (response.status_code, after) == (404, before), response.get_json()


def test_foreign_agent_visual_plan_is_not_mutable(client, app, tenant_case):
    with app.app_context():
        before_count = PageVisualPlan.query.filter_by(slide_version_id=tenant_case.slide_id).count()
        before = deepcopy(db.session.get(PageVisualPlan, tenant_case.visual_plan_id).get_plan())

    response = client.put(
        _agent_url(tenant_case, f"/slides/{tenant_case.slide_id}/visual-plan"),
        headers=tenant_case.headers,
        json={"visual_plan": {"reader_takeaway": "Attacker replacement"}},
    )

    with app.app_context():
        db.session.expire_all()
        after_count = PageVisualPlan.query.filter_by(slide_version_id=tenant_case.slide_id).count()
        after = db.session.get(PageVisualPlan, tenant_case.visual_plan_id).get_plan()
    assert (response.status_code, after_count, after) == (404, before_count, before), response.get_json()


def test_foreign_agent_slide_lock_is_not_mutable(client, app, tenant_case):
    response = client.post(
        _agent_url(tenant_case, f"/slides/{tenant_case.slide_id}/lock"),
        headers=tenant_case.headers,
        json={"locked": True},
    )

    with app.app_context():
        db.session.expire_all()
        slide = db.session.get(SlideVersion, tenant_case.slide_id)
        state = (slide.locked, slide.status)
    assert (response.status_code, state) == (
        404,
        (False, "pending_confirmation"),
    ), response.get_json()


def test_foreign_agent_generation_jobs_are_not_readable(client, app, tenant_case):
    response = client.get(
        f"/api/agent-mode/projects/{tenant_case.project_id}/generation-jobs",
        headers=tenant_case.headers,
    )

    with app.app_context():
        job_still_exists = db.session.get(GenerationJob, tenant_case.existing_job_id) is not None
    assert (response.status_code, job_still_exists) == (404, True), response.get_json()


@pytest.mark.parametrize("endpoint", ["style-preview", "generate-remaining"])
def test_foreign_agent_generation_cannot_create_jobs_or_tasks(
    client,
    app,
    tenant_case,
    endpoint,
):
    with app.app_context():
        before_jobs = GenerationJob.query.filter_by(project_id=tenant_case.project_id).count()
        before_tasks = Task.query.filter_by(project_id=tenant_case.project_id).count()
        before_status = db.session.get(Project, tenant_case.project_id).status

    response = client.post(
        _agent_url(tenant_case, f"/{endpoint}"),
        headers=tenant_case.headers,
        json={"slide_version_ids": [tenant_case.slide_id]},
    )

    with app.app_context():
        db.session.expire_all()
        after_jobs = GenerationJob.query.filter_by(project_id=tenant_case.project_id).count()
        after_tasks = Task.query.filter_by(project_id=tenant_case.project_id).count()
        after_status = db.session.get(Project, tenant_case.project_id).status
    assert (response.status_code, after_jobs, after_tasks, after_status) == (
        404,
        before_jobs,
        before_tasks,
        before_status,
    ), response.get_json()


def test_foreign_page_cannot_be_deleted(client, app, tenant_case):
    victim_dir = Path(app.config["UPLOAD_FOLDER"]) / tenant_case.project_id
    assert not victim_dir.exists()

    response = client.delete(_page_url(tenant_case), headers=tenant_case.headers)

    with app.app_context():
        page_still_exists = db.session.get(Page, tenant_case.page_id) is not None
    assert (response.status_code, page_still_exists, victim_dir.exists()) == (
        404,
        True,
        False,
    ), response.get_json()


def test_foreign_page_metadata_cannot_be_updated(client, app, tenant_case):
    response = client.put(
        _page_url(tenant_case),
        headers=tenant_case.headers,
        json={"part": "attacker section"},
    )

    with app.app_context():
        db.session.expire_all()
        part = db.session.get(Page, tenant_case.page_id).part
    assert (response.status_code, part) == (404, "victim section"), response.get_json()


def test_foreign_page_outline_cannot_be_updated(client, app, tenant_case):
    response = client.put(
        _page_url(tenant_case, "/outline"),
        headers=tenant_case.headers,
        json={"outline_content": {"title": "Attacker title", "points": ["Attacker point"]}},
    )

    with app.app_context():
        db.session.expire_all()
        outline = db.session.get(Page, tenant_case.page_id).get_outline_content()
    assert (response.status_code, outline) == (
        404,
        {"title": "Victim title", "points": ["Victim point"]},
    ), response.get_json()


def test_foreign_page_description_cannot_be_updated(client, app, tenant_case):
    response = client.put(
        _page_url(tenant_case, "/description"),
        headers=tenant_case.headers,
        json={"description_content": {"text": "Attacker description"}},
    )

    with app.app_context():
        db.session.expire_all()
        description = db.session.get(Page, tenant_case.page_id).get_description_content()
    assert (response.status_code, description) == (
        404,
        {"text": "Victim description"},
    ), response.get_json()


def test_foreign_page_image_versions_are_not_readable(client, app, tenant_case):
    response = client.get(
        _page_url(tenant_case, "/image-versions"),
        headers=tenant_case.headers,
    )

    with app.app_context():
        version_count = PageImageVersion.query.filter_by(page_id=tenant_case.page_id).count()
    assert (response.status_code, version_count) == (404, 2), response.get_json()


def test_foreign_page_image_version_cannot_be_selected(client, app, tenant_case):
    response = client.post(
        _page_url(
            tenant_case,
            f"/image-versions/{tenant_case.second_image_id}/set-current",
        ),
        headers=tenant_case.headers,
    )

    with app.app_context():
        db.session.expire_all()
        page = db.session.get(Page, tenant_case.page_id)
        first = db.session.get(PageImageVersion, tenant_case.first_image_id)
        second = db.session.get(PageImageVersion, tenant_case.second_image_id)
        state = (page.generated_image_path, first.is_current, second.is_current)
    assert (response.status_code, state) == (
        404,
        (f"{tenant_case.project_id}/pages/victim-v1.png", True, False),
    ), response.get_json()


def test_foreign_page_narration_cannot_be_updated(client, app, tenant_case):
    response = client.put(
        _page_url(tenant_case, "/narration"),
        headers=tenant_case.headers,
        json={"narration_text": "attacker narration"},
    )

    with app.app_context():
        db.session.expire_all()
        narration = db.session.get(Page, tenant_case.page_id).narration_text
    assert (response.status_code, narration) == (
        404,
        "victim narration",
    ), response.get_json()

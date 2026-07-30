from models import Project, Task, User, db
from services.credit_service import (
    InsufficientCredits,
    account_payload,
    estimate_operation,
    get_or_create_account,
    reserve_credits,
    settle_task_credits,
)


def test_credit_estimates_match_initial_pricing():
    assert estimate_operation("outline", page_count=10).amount == 50
    assert estimate_operation("outline_and_descriptions", page_count=10).amount == 100
    assert estimate_operation("images", page_count=10).amount == 1000
    assert estimate_operation("editable_export", page_count=10).amount == 830
    assert estimate_operation("ppt_to_ppt", reference_page_count=20, target_page_count=20).amount == 480


def test_account_initial_grant_and_task_settlement(app, monkeypatch):
    monkeypatch.setenv("CREDIT_INITIAL_BALANCE", "500")
    with app.app_context():
        user = User(username="credit-user")
        user.set_password("password")
        project = Project(user_id=user.id, creation_type="idea", idea_prompt="demo")
        db.session.add(user)
        db.session.flush()
        project.user_id = user.id
        db.session.add(project)
        db.session.flush()
        task = Task(user_id=user.id, project_id=project.id, task_type="GENERATE_IMAGES")
        db.session.add(task)
        db.session.flush()

        account = get_or_create_account(user.id)
        assert account.balance == 500
        assert account.available_balance == 500

        reserve_credits(
            user_id=user.id,
            amount=100,
            operation="images",
            project_id=project.id,
            task_id=task.id,
        )
        assert account.balance == 500
        assert account.reserved_balance == 100
        assert account.available_balance == 400

        settle_task_credits(task.id, completed_units=1, total_units=1)
        assert account.balance == 400
        assert account.reserved_balance == 0
        assert account.available_balance == 400
        assert account.lifetime_spent == 100


def test_failed_task_releases_reserved_credits(app, monkeypatch):
    monkeypatch.setenv("CREDIT_INITIAL_BALANCE", "300")
    with app.app_context():
        user = User(username="release-user")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        project = Project(user_id=user.id, creation_type="idea", idea_prompt="demo")
        db.session.add(project)
        db.session.flush()
        task = Task(user_id=user.id, project_id=project.id, task_type="GENERATE_IMAGES")
        db.session.add(task)
        db.session.flush()

        account = get_or_create_account(user.id)
        reserve_credits(user_id=user.id, amount=100, operation="images", project_id=project.id, task_id=task.id)
        settle_task_credits(task.id, force_release=True)

        assert account.balance == 300
        assert account.reserved_balance == 0
        assert account.available_balance == 300
        assert account.lifetime_spent == 0


def test_reserve_rejects_insufficient_credits(app, monkeypatch):
    monkeypatch.setenv("CREDIT_INITIAL_BALANCE", "50")
    with app.app_context():
        user = User(username="poor-user")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        account = get_or_create_account(user.id)

        try:
            reserve_credits(user_id=user.id, amount=100, operation="images")
        except InsufficientCredits as exc:
            assert exc.required == 100
            assert exc.available == 50
        else:
            raise AssertionError("Expected InsufficientCredits")

        assert account.balance == 50
        assert account.reserved_balance == 0


def test_credit_account_api_payload(app, monkeypatch):
    monkeypatch.setenv("CREDIT_INITIAL_BALANCE", "123")
    with app.app_context():
        user = User(username="payload-user")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()

        payload = account_payload(user.id)
        assert payload["account"]["available_balance"] == 123
        assert payload["pricing"]["rules"]["images"] == "100/page"

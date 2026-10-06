import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import event

from models import CreditAccount, CreditLedger, Project, Task, User, db
from services.credit_service import (
    InsufficientCredits,
    account_payload,
    debit_credits_now,
    ensure_credits_available,
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


def test_admin_has_unlimited_credits(app, monkeypatch):
    monkeypatch.setenv("CREDIT_INITIAL_BALANCE", "10")
    with app.app_context():
        user = User(username="unlimited-admin", is_admin=True)
        user.set_password("password")
        db.session.add(user)
        db.session.flush()

        account = get_or_create_account(user.id)
        reserve = reserve_credits(
            user_id=user.id,
            amount=1_000_000,
            operation="images",
        )
        debit = debit_credits_now(
            user_id=user.id,
            amount=1_000_000,
            operation="from_description",
        )
        ensure_credits_available(user.id, 1_000_000)

        assert reserve is None
        assert debit is None
        assert account.balance == 10
        assert account.reserved_balance == 0
        assert account_payload(user.id)["account"]["unlimited"] is True
        assert CreditLedger.query.filter_by(user_id=user.id, entry_type="debit").count() == 0


def _create_user_with_tasks(app, *, balance: int, task_count: int):
    """Commit shared fixtures before worker threads open independent sessions."""
    with app.app_context():
        user = User(username=f"credit-race-{uuid4().hex}")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        project = Project(user_id=user.id, creation_type="idea", idea_prompt="race")
        db.session.add(project)
        db.session.flush()
        tasks = [
            Task(user_id=user.id, project_id=project.id, task_type="GENERATE_IMAGES")
            for _ in range(task_count)
        ]
        db.session.add_all(tasks)
        account = CreditAccount(
            user_id=user.id,
            balance=balance,
            reserved_balance=0,
            lifetime_credited=balance,
            lifetime_spent=0,
        )
        db.session.add(account)
        db.session.commit()
        return user.id, project.id, [task.id for task in tasks]


def test_concurrent_reservations_cannot_oversubscribe_one_account(app, monkeypatch):
    """Two independent sessions must atomically compete for one balance."""
    monkeypatch.setenv("CREDIT_INITIAL_BALANCE", "100")
    user_id, project_id, task_ids = _create_user_with_tasks(app, balance=100, task_count=2)
    start = threading.Barrier(2)

    def reserve(task_id):
        with app.app_context():
            start.wait(timeout=10)
            try:
                reserve_credits(
                    user_id=user_id,
                    amount=80,
                    operation="images",
                    project_id=project_id,
                    task_id=task_id,
                )
                db.session.commit()
                return "reserved"
            except InsufficientCredits:
                db.session.rollback()
                return "insufficient"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, task_ids))

    assert sorted(outcomes) == ["insufficient", "reserved"]
    with app.app_context():
        account = db.session.get(CreditAccount, user_id)
        assert account.balance == 100
        assert account.reserved_balance == 80
        assert account.available_balance == 20
        assert CreditLedger.query.filter_by(user_id=user_id, entry_type="reserve").count() == 1


def test_repeated_settlement_is_idempotent(app):
    user_id, project_id, (task_id,) = _create_user_with_tasks(app, balance=200, task_count=1)
    with app.app_context():
        reserve_credits(
            user_id=user_id,
            amount=80,
            operation="images",
            project_id=project_id,
            task_id=task_id,
        )
        db.session.commit()

        settle_task_credits(task_id, completed_units=1, total_units=1)
        db.session.commit()
        settle_task_credits(task_id, completed_units=1, total_units=1)
        db.session.commit()

        account = db.session.get(CreditAccount, user_id)
        assert account.balance == 120
        assert account.reserved_balance == 0
        assert account.lifetime_spent == 80
        assert CreditLedger.query.filter_by(task_id=task_id, entry_type="debit").count() == 1
        assert CreditLedger.query.filter_by(task_id=task_id, entry_type="release").count() == 0
        reserve = CreditLedger.query.filter_by(task_id=task_id, entry_type="reserve").one()
        assert reserve.settled_at is not None


def test_concurrent_settlement_claims_reservation_once(app):
    """Force both sessions past the stale read before the settled_at CAS update."""
    user_id, project_id, (task_id,) = _create_user_with_tasks(app, balance=200, task_count=1)
    with app.app_context():
        reserve_credits(
            user_id=user_id,
            amount=80,
            operation="images",
            project_id=project_id,
            task_id=task_id,
        )
        db.session.commit()
        engine = db.engine

    claim_barrier = threading.Barrier(2)
    synchronized_threads = set()
    synchronized_threads_lock = threading.Lock()

    def synchronize_claims(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if not normalized.startswith("update credit_ledger set") or "settled_at" not in normalized:
            return
        thread_id = threading.get_ident()
        with synchronized_threads_lock:
            if thread_id in synchronized_threads:
                return
            synchronized_threads.add(thread_id)
        claim_barrier.wait(timeout=10)

    def settle():
        with app.app_context():
            settle_task_credits(task_id, completed_units=1, total_units=1)
            db.session.commit()

    event.listen(engine, "before_cursor_execute", synchronize_claims)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(settle) for _ in range(2)]
            for future in futures:
                future.result(timeout=20)
    finally:
        event.remove(engine, "before_cursor_execute", synchronize_claims)

    with app.app_context():
        account = db.session.get(CreditAccount, user_id)
        assert account.balance == 120
        assert account.reserved_balance == 0
        assert account.lifetime_spent == 80
        assert CreditLedger.query.filter_by(task_id=task_id, entry_type="debit").count() == 1
        reserve = CreditLedger.query.filter_by(task_id=task_id, entry_type="reserve").one()
        assert reserve.settled_at is not None


def test_concurrent_first_account_creation_is_singleton(app, monkeypatch):
    """First use from two sessions must not leak an IntegrityError or double-grant."""
    monkeypatch.setenv("CREDIT_INITIAL_BALANCE", "250")
    with app.app_context():
        user = User(username=f"credit-first-use-{uuid4().hex}")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        engine = db.engine

    insert_barrier = threading.Barrier(2)
    synchronized_threads = set()
    synchronized_threads_lock = threading.Lock()

    def synchronize_first_inserts(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if not normalized.startswith("insert ") or " into credit_accounts " not in f" {normalized} ":
            return
        thread_id = threading.get_ident()
        with synchronized_threads_lock:
            if thread_id in synchronized_threads:
                return
            synchronized_threads.add(thread_id)
        insert_barrier.wait(timeout=10)

    def first_use():
        with app.app_context():
            account = get_or_create_account(user_id)
            db.session.commit()
            return account.user_id

    event.listen(engine, "before_cursor_execute", synchronize_first_inserts)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(first_use) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]
    finally:
        event.remove(engine, "before_cursor_execute", synchronize_first_inserts)

    assert results == [user_id, user_id]
    with app.app_context():
        assert CreditAccount.query.filter_by(user_id=user_id).count() == 1
        account = db.session.get(CreditAccount, user_id)
        assert account.balance == 250
        assert account.lifetime_credited == 250
        grants = CreditLedger.query.filter_by(
            user_id=user_id,
            entry_type="grant",
            operation="initial_grant",
        ).all()
        assert len(grants) == 1
        assert grants[0].amount == 250

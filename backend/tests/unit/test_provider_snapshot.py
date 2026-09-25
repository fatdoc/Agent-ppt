from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from threading import Barrier, Event
from types import SimpleNamespace
import os
import pickle
import pytest
from flask import current_app
from models import db, Settings, User, Task
from services.provider_config import (
    ProviderConfigSnapshot, capture_provider_snapshot, provider_snapshot_scope,
    active_provider_snapshot, ContextThreadPoolExecutor,
)
from services import ai_service_manager as manager
from services.task_manager import TaskManager
from services.task_execution import TaskExecutionContext, TaskCancelled, fail_interrupted_tasks


@pytest.fixture
def owners(client, app):
    with app.app_context():
        users = []
        for name in ('snapshot-A', 'snapshot-B'):
            user = User(username=name)
            user.set_password('test-password')
            db.session.add(user)
            db.session.flush()
            db.session.add(Settings(user_id=user.id, api_key=name+'-secret', text_model=name,
                                    lazyllm_api_keys='{"qwen":"'+name+'-vendor-secret"}'))
            users.append(user.id)
        db.session.commit()
        return users


def capture(app, user):
    with app.app_context():
        return capture_provider_snapshot(user_id=user)


def test_sequential_snapshots_do_not_mutate_app_or_environment(app, owners):
    baseline = dict(app.config)
    environment = dict(os.environ)
    for owner in owners * 2:
        snapshot = capture(app, owner)
        with app.app_context(), provider_snapshot_scope(snapshot):
            assert current_app.config['OPENAI_API_KEY'] == snapshot.values['OPENAI_API_KEY']
            assert Settings.get_settings().user_id == owner
            from services.ai_providers.lazyllm_env import get_lazyllm_api_key
            assert get_lazyllm_api_key('qwen') == snapshot.values['QWEN_API_KEY']
        assert active_provider_snapshot() is None
    assert dict(app.config) == baseline
    assert dict(os.environ) == environment


def test_concurrent_scopes_include_nested_worker_pool(app, owners):
    barrier = Barrier(2)
    def run(owner):
        snapshot = capture(app, owner)
        with app.app_context(), provider_snapshot_scope(snapshot):
            barrier.wait(timeout=5)
            def nested():
                with app.app_context():
                    return current_app.config['OPENAI_API_KEY'], Settings.get_settings().user_id
            with ContextThreadPoolExecutor(1) as pool:
                value = pool.submit(nested).result(timeout=5)
            assert value == (snapshot.values['OPENAI_API_KEY'], owner)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(run, owners))


def test_snapshot_is_immutable_redacted_and_not_serializable(app, owners):
    snapshot = capture(app, owners[0])
    with pytest.raises(TypeError):
        snapshot.values['OPENAI_API_KEY'] = 'changed'
    with pytest.raises(FrozenInstanceError):
        snapshot.user_id = 'changed'
    with pytest.raises(TypeError):
        pickle.dumps(snapshot)
    assert 'snapshot-A-secret' not in repr(snapshot)
    assert 'snapshot-A-secret' not in str(snapshot.cache_scope)
    with app.app_context(), provider_snapshot_scope(snapshot), pytest.raises(RuntimeError):
        current_app.config['OPENAI_API_KEY'] = 'changed'


def test_missing_user_settings_never_falls_back_to_first_owner(app, owners):
    with app.app_context():
        user = User(username='missing-settings')
        user.set_password('test-password')
        db.session.add(user); db.session.commit()
        snapshot = capture_provider_snapshot(user_id=user.id)
        assert snapshot.values['OPENAI_API_KEY'] != 'snapshot-A-secret'
        assert Settings.query.filter_by(user_id=user.id).first() is None
        assert Settings.get_settings().user_id is None


def test_background_submission_pins_config_during_rotation(app, owners):
    old = capture(app, owners[0])
    ready, proceed = Event(), Event()
    tm = TaskManager(1)
    with app.app_context():
        task = Task(user_id=owners[0], task_type='TEST'); db.session.add(task); db.session.commit()
        task_id = task.id
        with provider_snapshot_scope(old):
            def worker(_):
                ready.set(); assert proceed.wait(5)
                with app.app_context():
                    return current_app.config['OPENAI_API_KEY'], active_provider_snapshot().cache_scope
            future = tm.submit_task(task_id, worker)
        assert ready.wait(5)
        settings = Settings.query.filter_by(user_id=owners[0]).one()
        settings.api_key = 'rotated'; db.session.commit()
        new = capture_provider_snapshot(user_id=owners[0])
        with provider_snapshot_scope(capture_provider_snapshot(user_id=owners[1])):
            proceed.set()
        assert future.result(5) == ('snapshot-A-secret', old.cache_scope)
        assert new.cache_scope != old.cache_scope
    tm.shutdown()


def test_provider_cache_scoped_rotates_and_failed_creation_is_retryable(app, owners, monkeypatch):
    manager.clear_ai_service_cache()
    calls = []
    def factory(model):
        snapshot = active_provider_snapshot()
        calls.append(snapshot.user_id)
        return object()
    monkeypatch.setattr(manager, 'get_text_provider', factory)
    a, b = [capture(app, owner) for owner in owners]
    with app.app_context():
        with provider_snapshot_scope(a):
            p1 = manager._get_cached_text_provider('same')
            assert manager._get_cached_text_provider('same') is p1
        with provider_snapshot_scope(b):
            assert manager._get_cached_text_provider('same') is not p1
        rotated = ProviderConfigSnapshot(a.user_id, a.version, {**a.values, 'QWEN_API_KEY': 'new'}, a.app_id)
        with provider_snapshot_scope(rotated):
            assert manager._get_cached_text_provider('same') is not p1
        manager.clear_ai_service_cache()
        def broken(model):
            raise RuntimeError('fake failure')
        monkeypatch.setattr(manager, 'get_text_provider', broken)
        with provider_snapshot_scope(a):
            with pytest.raises(RuntimeError): manager._get_cached_text_provider('same')
            monkeypatch.setattr(manager, 'get_text_provider', factory)
            assert manager._get_cached_text_provider('same') is not p1
    assert len(calls) == 4
    assert 'secret' not in str(manager.get_provider_cache_info())
    manager.clear_ai_service_cache()


def test_temporary_overrides_nest_and_restore_even_on_failure(app, owners):
    from controllers.settings_controller import temporary_settings_override
    snapshot = capture(app, owners[0])
    with app.app_context(), provider_snapshot_scope(snapshot):
        with pytest.raises(RuntimeError):
            with temporary_settings_override({'api_key': 'temporary'}):
                assert current_app.config['OPENAI_API_KEY'] == 'temporary'
                raise RuntimeError('fake failure')
        assert current_app.config['OPENAI_API_KEY'] == 'snapshot-A-secret'


def test_fake_factory_and_new_services(app, owners):
    snapshot = capture(app, owners[0])
    calls = []
    def fake(s):
        calls.append(s); return SimpleNamespace(model=s.values['TEXT_MODEL'])
    a = manager.get_ai_service(snapshot=snapshot, factory=fake)
    b = manager.get_ai_service(snapshot=snapshot, factory=fake)
    assert a is not b and a.model == b.model == 'snapshot-A'
    assert calls == [snapshot, snapshot]


def test_controls_and_recovery_release_reservation_idempotently(app, owners):
    from services.credit_service import reserve_credits, get_or_create_account
    with app.app_context():
        task = Task(user_id=owners[0], task_type='TEST', status='PROCESSING')
        db.session.add(task); db.session.flush()
        reserve_credits(user_id=owners[0], amount=25, operation='images', task_id=task.id)
        db.session.commit()
        with pytest.raises(RuntimeError): fail_interrupted_tasks([task.id])
        assert fail_interrupted_tasks([task.id], workers_stopped=True) == [task.id]
        assert fail_interrupted_tasks([task.id], workers_stopped=True) == []
        account = get_or_create_account(owners[0])
        assert account.reserved_balance == 0 and account.lifetime_spent == 0
        assert task.status == 'FAILED' and 'WORKER_RESTARTED' in task.error_message
    control = TaskExecutionContext('task', owners[0], deadline=0)
    with pytest.raises(TimeoutError): control.checkpoint()
    control.cancel_event.set()
    with pytest.raises(TaskCancelled): control.checkpoint()
    progress = []
    TaskExecutionContext('task', owners[0], progress_callback=lambda **kw: progress.append(kw)).checkpoint('extract', 1, 2)
    assert progress == [{'stage': 'extract', 'completed': 1, 'total': 2}]


def test_task_rejects_wrong_owner_and_releases_on_unhandled_failure(app, owners):
    from services.credit_service import reserve_credits, get_or_create_account
    tm = TaskManager(1)
    with app.app_context():
        task = Task(user_id=owners[0], task_type='TEST'); db.session.add(task); db.session.flush()
        reserve_credits(user_id=owners[0], amount=25, operation='images', task_id=task.id)
        db.session.commit(); task_id = task.id
        with pytest.raises(ValueError):
            tm.submit_task(task_id, lambda _: None, provider_snapshot=capture_provider_snapshot(user_id=owners[1]))
        def fail(_): raise RuntimeError('remote echoed snapshot-A-secret')
        future = tm.submit_task(task_id, fail, provider_snapshot=capture_provider_snapshot(user_id=owners[0]))
    with pytest.raises(RuntimeError): future.result(5)
    tm.shutdown()
    with app.app_context():
        db.session.expire_all()
        assert db.session.get(Task, task_id).error_message == 'TASK_EXECUTION_FAILED'
        assert get_or_create_account(owners[0]).reserved_balance == 0


def test_secrets_redacted_in_task_errors_api_and_override_exceptions(app, owners):
    from services.provider_config import redact_provider_text
    from controllers.settings_controller import temporary_settings_override
    from utils.response import error_response
    snapshot = capture(app, owners[0])
    with app.app_context(), provider_snapshot_scope(snapshot):
        task = Task(user_id=owners[0], task_type='TEST', error_message='snapshot-A-secret rejected')
        assert task.error_message == '[REDACTED] rejected'
        response, _ = error_response('TEST', 'snapshot-A-vendor-secret failed')
        assert response.get_json()['error']['message'] == '[REDACTED] failed'
        with pytest.raises(RuntimeError, match=r'\[REDACTED\]') as err:
            with temporary_settings_override({'api_key': 'unsaved-provider-secret'}):
                raise ValueError('unsaved-provider-secret failed')
        assert 'unsaved-provider-secret' not in str(err.value)


def test_lazyllm_clients_receive_explicit_pinned_key_without_env_mutation(app, owners, monkeypatch):
    import sys
    from unittest.mock import MagicMock
    fake = MagicMock()
    from enum import Enum
    class LLMType(Enum):
        LLM = 'llm'
        VLM = 'vlm'
    fake.namespace.return_value.OnlineModule.return_value._type = LLMType.LLM
    monkeypatch.setitem(sys.modules, 'lazyllm', fake)
    from services.ai_providers.text.lazyllm_provider import LazyLLMTextProvider
    from services.ai_providers.image.lazyllm_provider import LazyLLMImageProvider
    before = dict(os.environ)
    snapshot = capture(app, owners[0])
    with app.app_context(), provider_snapshot_scope(snapshot):
        LazyLLMTextProvider(source='qwen', model='fake')
        LazyLLMImageProvider(source='qwen', model='fake')
    for call in fake.namespace.return_value.OnlineModule.call_args_list:
        assert call.kwargs['api_key'] == 'snapshot-A-vendor-secret'
    assert dict(os.environ) == before


def test_scope_and_version_alone_separate_cached_providers(app, owners, monkeypatch):
    manager.clear_ai_service_cache()
    monkeypatch.setattr(manager, 'get_text_provider', lambda model: object())
    a = capture(app, owners[0])
    b = ProviderConfigSnapshot(owners[1], a.version, a.values, a.app_id)
    rotated = ProviderConfigSnapshot(a.user_id, a.version+'-next', a.values, a.app_id)
    objects = []
    with app.app_context():
        for s in [a, b, rotated]:
            with provider_snapshot_scope(s):
                objects.append(manager._get_cached_text_provider('same'))
        assert len({id(p) for p in objects}) == 3
        manager.clear_ai_service_cache()


def test_real_provider_factory_consumes_pinned_per_model_credentials(app, owners, monkeypatch):
    import services.ai_providers as providers
    manager.clear_ai_service_cache()
    def fake(**kwargs): return SimpleNamespace(**kwargs)
    monkeypatch.setattr(providers, 'OpenAITextProvider', fake)
    monkeypatch.setattr(providers, 'OpenAIImageProvider', fake)
    a = capture(app, owners[0])
    snapshot = ProviderConfigSnapshot(a.user_id, a.version, {
        **a.values, 'AI_PROVIDER_FORMAT':'openai', 'TEXT_MODEL_SOURCE':'openai',
        'TEXT_API_KEY':'separate-text-key', 'TEXT_API_BASE':'https://example.invalid/v1',
    }, a.app_id)
    with app.app_context():
        service = manager.get_ai_service(snapshot=snapshot)
        assert service.text_provider.api_key == 'separate-text-key'
        assert service.image_provider.api_key == 'snapshot-A-secret'
        assert service.text_model == 'snapshot-A'
        # Rebuilding after cache invalidation still uses the explicitly pinned snapshot.
        retry = manager.get_ai_service(force_new=True, snapshot=snapshot)
        assert retry.text_provider.api_key == service.text_provider.api_key
        assert retry is not service
    manager.clear_ai_service_cache()


def test_public_restart_recovery_fails_both_stages_and_releases_once(app, owners):
    from models import Project, PublicPptGeneration, ApiKey
    from services.credit_service import reserve_credits, get_or_create_account
    with app.app_context():
        project = Project(user_id=owners[0], creation_type='idea'); db.session.add(project); db.session.flush()
        tasks = [Task(user_id=owners[0], project_id=project.id, task_type='TEST', status='PENDING') for _ in range(2)]
        db.session.add_all(tasks); db.session.flush()
        for task in tasks: reserve_credits(user_id=owners[0], amount=25, operation='images', task_id=task.id)
        key, _ = ApiKey.issue(user_id=owners[0], name='recovery-test')
        db.session.add(key); db.session.flush()
        generation = PublicPptGeneration(user_id=owners[0], api_key_id=key.id, project_id=project.id,
            description_task_id=tasks[0].id, image_task_id=tasks[1].id, request_json='{}')
        db.session.add(generation); db.session.commit()
        assert set(fail_interrupted_tasks([generation.id], workers_stopped=True)) == {t.id for t in tasks}
        assert generation.status == project.status == 'FAILED'
        assert get_or_create_account(owners[0]).reserved_balance == 0
        assert fail_interrupted_tasks([generation.id], workers_stopped=True) == []


def test_task_context_propagates_to_nested_pool_and_duplicate_submit_is_rejected(app, owners):
    from services.task_execution import current_task_execution
    ready, proceed = Event(), Event()
    tm = TaskManager(1)
    with app.app_context():
        task = Task(user_id=owners[0], task_type='TEST'); db.session.add(task); db.session.commit()
        snapshot = capture_provider_snapshot(user_id=owners[0])
        control = TaskExecutionContext(task.id, owners[0])
        def worker(_):
            ready.set(); assert proceed.wait(5)
            with ContextThreadPoolExecutor(1) as pool:
                assert pool.submit(current_task_execution).result(5) is control
        future = tm.submit_task(task.id, worker, provider_snapshot=snapshot, execution_context=control)
        assert ready.wait(5)
        with pytest.raises(ValueError, match='already active'):
            tm.submit_task(task.id, worker, provider_snapshot=snapshot)
        proceed.set(); future.result(5)
    tm.shutdown()


def test_explicit_snapshot_keeps_owner_in_cache_outside_flask(app, owners):
    snapshots = [capture(app, owner) for owner in owners]
    keys = []
    for snapshot in snapshots:
        with provider_snapshot_scope(snapshot):
            assert capture_provider_snapshot() is snapshot
            keys.append(manager._config_fingerprint('text', 'same'))
    assert keys[0] != keys[1]


def test_server_managed_routes_still_capture_account_scoped_oauth(app, owners, monkeypatch):
    monkeypatch.setenv('SERVER_MANAGED_AI_CONFIG', 'true')
    monkeypatch.setitem(app.config, 'AI_PROVIDER_FORMAT', 'codex')
    with app.app_context():
        for owner in owners:
            s = Settings.query.filter_by(user_id=owner).one()
            s.openai_oauth_access_token = owner+'-fake-oauth'
        db.session.commit()
        for owner in owners:
            snapshot = capture_provider_snapshot(user_id=owner)
            assert snapshot.values['PROVIDER_OAUTH_TOKEN'] == owner+'-fake-oauth'
            assert snapshot.values['TEXT_MODEL'] == app.config['TEXT_MODEL']

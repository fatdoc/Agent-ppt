#!/usr/bin/env python3
"""Real HTTP acceptance against a temporary DB and fake providers only.

Run via scripts/verify_isolated.py runtime. No existing service is restarted.
"""
import os
import sys
import tempfile
from pathlib import Path


def main():
    if os.getenv('LOAD_DOTENV') != 'false' or os.getenv('BANANA_ISOLATED_VERIFICATION') != '1':
        raise SystemExit('Use scripts/verify_isolated.py runtime')
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Thread, Lock
    from unittest.mock import patch
    import requests
    from werkzeug.serving import make_server
    from flask import g, current_app
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    from app import create_app
    from models import db, User, Settings
    from services.provider_config import active_provider_snapshot
    import services.ai_providers as providers

    with tempfile.TemporaryDirectory(prefix='banana-http-') as tmp:
        os.environ['DATABASE_URL'] = 'sqlite:///' + tmp + '/runtime.db'
        os.environ['AUTH_REQUIRED'] = 'true'
        os.environ['AUTH_COOKIE_SECURE'] = 'false'
        app = create_app({'TESTING': True, 'UPLOAD_FOLDER': tmp+'/uploads'})
        with app.app_context():
            db.create_all()
            for name in ('runtime-A', 'runtime-B'):
                user = User(username=name); user.set_password('isolated-test-password')
                db.session.add(user); db.session.flush()
                db.session.add(Settings(user_id=user.id, text_model=name, api_key=name+'-fake-key'))
            db.session.commit()
        baseline = dict(app.config)
        barrier = None
        observations = []
        lock = Lock()
        def fake_provider(model):
            snapshot = active_provider_snapshot()
            assert snapshot is not None and snapshot.user_id == g.current_user.id
            assert snapshot.values['TEXT_MODEL'] == model
            class Fake:
                def generate_text(self, *args, **kwargs):
                    if barrier is not None:
                        barrier.wait(timeout=10)
                    assert current_app.config['OPENAI_API_KEY'] == model+'-fake-key'
                    assert active_provider_snapshot() is snapshot
                    with lock: observations.append(model)
                    return 'OK'
            return Fake()
        server = make_server('127.0.0.1', 0, app, threaded=True)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            assert requests.get(base+'/health', timeout=5).json()['status'] == 'ok'
            clients = []
            for name in ('runtime-A', 'runtime-B'):
                session = requests.Session(); session.trust_env = False
                response = session.post(base+'/api/auth/login', json={'username': name, 'password': 'isolated-test-password'}, timeout=5)
                assert response.status_code == 200
                session.headers['X-CSRF-Token'] = session.cookies['banana_csrf_token']
                clients.append(session)
            def verify(client):
                response = client.post(base+'/api/settings/verify', timeout=15)
                assert response.status_code == 200 and response.json()['data']['available'], response.status_code
            with patch.object(providers, 'get_text_provider', fake_provider):
                for client in clients*2: verify(client)
                barrier = Barrier(2)
                with ThreadPoolExecutor(2) as pool: list(pool.map(verify, clients))
                barrier = None
            assert observations.count('runtime-A') == 3
            assert observations.count('runtime-B') == 3
            assert dict(app.config) == baseline
            # Real Cookie/CSRF and tenant routes, with no model traffic.
            missing_csrf = clients[0].post(base+'/api/projects', headers={'X-CSRF-Token': ''}, json={'creation_type':'idea'}, timeout=5)
            assert missing_csrf.status_code == 403
            project = clients[0].post(base+'/api/projects', json={'creation_type':'idea','idea_prompt':'offline verification'}, timeout=5)
            assert project.status_code == 201
            project_id = project.json()['data']['project_id']
            assert clients[1].get(base+'/api/projects/'+project_id, timeout=5).status_code == 404
            # Public API key authentication and ownership, no generation submitted.
            issued = clients[0].post(base+'/api/api-keys', json={'name':'offline-verification'}, timeout=5)
            assert issued.status_code == 201
            key = issued.json()['data']['key']
            assert requests.get(base+'/v1/templates', headers={'Authorization':'Bearer '+key}, timeout=5).status_code == 200
            assert requests.get(base+'/v1/templates', timeout=5).status_code == 401
            print('HTTP_ACCEPTANCE: health, A/B sequential=4 concurrent=2, Cookie/CSRF, tenant ownership, Public API Key PASS')
            print('ISOLATION: temporary database/uploads; fake provider only; real service untouched')
        finally:
            server.shutdown(); server.server_close(); server_thread.join(5)
            for client in locals().get('clients', []): client.close()
        with app.app_context():
            db.session.remove(); db.engine.dispose()


if __name__ == '__main__':
    main()

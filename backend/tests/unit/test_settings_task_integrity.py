"""Settings tests must work with SQLite foreign keys enabled."""

from unittest.mock import patch

import pytest
from flask import Flask, g
from sqlalchemy import text

from controllers.settings_controller import run_settings_test, get_test_status
from models import db, Task, User


@pytest.mark.parametrize('test_name', ['mineru-pdf', 'text-model', 'image-model'])
def test_settings_task_without_project_preserves_owner(test_name, tmp_path):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path / "settings.db"}'
    db.init_app(app)
    with app.app_context():
        db.session.execute(text('PRAGMA foreign_keys=ON'))
        db.create_all()
        user = User(username='settings-test-owner')
        user.set_password('test-password')
        db.session.add(user)
        db.session.commit()
        with app.test_request_context(method='POST', json={}):
            g.current_user = user
            with patch('controllers.settings_controller.task_manager.submit_task') as submit:
                response, status = run_settings_test(test_name)
            assert status == 200, response.get_json()
            task = db.session.get(Task, response.get_json()['data']['task_id'])
            assert task.project_id is None
            assert task.user_id == user.id
            assert task.status == 'PENDING'
            assert task.task_type == 'TEST_' + test_name.upper().replace('-', '_')
            submit.assert_called_once()
            result, status = get_test_status(task.id)
            assert status == 200
            assert result.get_json()['data']['status'] == 'PENDING'

"""PPT 翻新后台任务回归测试。"""

from pathlib import Path


class _FileService:
    def get_absolute_path(self, value):
        return value


class _AIService:
    def extract_page_content(self, markdown, language='zh'):
        return {
            'title': markdown.strip().splitlines()[0].lstrip('# '),
            'points': ['要点'],
            'description': '已提取的页面描述',
        }


class _SuccessfulParser:
    def parse_file(self, _path, filename):
        return None, f'# {filename}', None, None, 0

    def extract_header_footer_from_layout(self, _extract_id):
        return ''


class _UnavailableMinerUParser:
    def parse_file(self, _path, _filename):
        return None, None, None, 'Local MinerU request failed: Connection refused', 0

    def extract_header_footer_from_layout(self, _extract_id):
        return ''


def _seed_task(app, page_count):
    from models import db, Page, Project, Task

    project = Project(creation_type='ppt_renovation', status='PROCESSING')
    db.session.add(project)
    db.session.flush()

    for index in range(page_count):
        page = Page(project_id=project.id, order_index=index, status='DRAFT')
        page.set_outline_content({'title': f'Page {index + 1}', 'points': []})
        db.session.add(page)

    task = Task(project_id=project.id, task_type='PPT_RENOVATION', status='PENDING')
    task.set_progress({
        'total': page_count,
        'completed': 0,
        'failed': 0,
        'current_step': 'queued',
    })
    db.session.add(task)
    db.session.commit()

    template_dir = Path(app.config['UPLOAD_FOLDER']) / project.id / 'template'
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / 'original.pdf').write_bytes(b'%PDF test fixture')

    return project.id, task.id


def test_workers_use_page_ids_instead_of_cross_thread_models(client, app, monkeypatch):
    from models import db, Page, Project, Task
    from services.task_manager import process_ppt_renovation_task

    project_id, task_id = _seed_task(app, page_count=6)
    split_paths = [f'/tmp/renovation-page-{index}.pdf' for index in range(6)]
    monkeypatch.setattr('services.task_manager.split_pdf_to_pages', lambda *_args: split_paths)

    process_ppt_renovation_task(
        task_id,
        project_id,
        _AIService(),
        _FileService(),
        _SuccessfulParser(),
        keep_layout=False,
        max_workers=3,
        app=app,
        language='zh',
    )

    db.session.expire_all()
    task = Task.query.get(task_id)
    project = Project.query.get(project_id)
    pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()

    assert task.status == 'COMPLETED'
    assert task.get_progress() == {
        'total': 6,
        'completed': 6,
        'failed': 0,
        'current_step': 'done',
    }
    assert project.status == 'DESCRIPTIONS_GENERATED'
    assert all(page.get_description_content()['text'] == '已提取的页面描述' for page in pages)


def test_mineru_error_fails_task_instead_of_writing_blank_descriptions(client, app, monkeypatch):
    from models import db, Page, Project, Task
    from services.task_manager import process_ppt_renovation_task

    project_id, task_id = _seed_task(app, page_count=3)
    split_paths = [f'/tmp/mineru-unavailable-{index}.pdf' for index in range(3)]
    monkeypatch.setattr('services.task_manager.split_pdf_to_pages', lambda *_args: split_paths)

    process_ppt_renovation_task(
        task_id,
        project_id,
        _AIService(),
        _FileService(),
        _UnavailableMinerUParser(),
        keep_layout=False,
        max_workers=3,
        app=app,
        language='zh',
    )

    db.session.expire_all()
    task = Task.query.get(task_id)
    project = Project.query.get(project_id)
    pages = Page.query.filter_by(project_id=project_id).all()

    assert task.status == 'FAILED'
    assert task.get_progress()['completed'] == 0
    assert task.get_progress()['failed'] == 3
    assert 'MinerU' in task.error_message
    assert 'Connection refused' in task.error_message
    assert project.status == 'DRAFT'
    assert all(page.description_content is None for page in pages)

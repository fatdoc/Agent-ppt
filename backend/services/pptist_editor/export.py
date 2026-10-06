"""Deterministic semantic export. Never construct an AI service or Provider."""
import hashlib,json,os,tempfile
from datetime import datetime
from pathlib import Path
from models import db,Task
from models.editor_document import EditorRevision
from services.semantic_export import AssetStore,PageJob,export_jobs,load_page
from services.task_execution import current_task_execution

def export_revision(task_id, *, project_id, user_id, revision_id, payload_hash, app):
    with app.app_context():
        task=db.session.get(Task,task_id)
        control=current_task_execution()
        if not task or (task.user_id,task.project_id)!=(user_id,project_id):raise ValueError('task scope mismatch')
        row=EditorRevision.query.filter_by(id=revision_id,project_id=project_id).one()
        if hashlib.sha256(row.payload.encode()).hexdigest()!=payload_hash:raise ValueError('immutable snapshot changed')
        pages=[load_page(p) for p in json.loads(row.payload)]
        root=Path(app.config['UPLOAD_FOLDER'])/project_id
        root.mkdir(parents=True,exist_ok=True)
        store=AssetStore(root,user_id=user_id,project_id=project_id)
        task.status='PROCESSING';db.session.commit()
        def checkpoint():
            control.checkpoint()
            db.session.expire(task)
            if task.get_progress().get('cancel_requested'):raise RuntimeError('export cancelled')
        def event(e):
            progress=task.get_progress();progress.update(stage=e['stage'],page_id=e['page_id'])
            task.set_progress(progress);db.session.commit()
        jobs=[PageJob(p.id,p.source,payload_hash,'pptist-semantic-v1',p.revision,lambda p=p:p.model_dump(mode='json'),lambda raw:raw) for p in pages]
        raw,report=export_jobs(jobs,store=store,checkpoint_dir=root/'.editor-checkpoints'/task_id,mode='semantic',on_event=event,check_cancelled=checkpoint)
        # The hidden staging directory is not exposed by the file controller.
        staging=root/'.editor-staging';staging.mkdir(exist_ok=True)
        final_dir=root/'exports';final_dir.mkdir(exist_ok=True)
        name=f'editor-r{row.revision}-{task_id}.pptx'
        temp=None
        try:
            with tempfile.NamedTemporaryFile(dir=staging,suffix='.pptx',delete=False) as f:
                temp=Path(f.name);f.write(raw);f.flush();os.fsync(f.fileno())
            checkpoint()
            os.replace(temp,final_dir/name);temp=None
            progress=task.get_progress();progress.update(download_url=f'/api/projects/{project_id}/editor-document/exports/{task_id}',filename=name,structure=report,completed=len(pages),total=len(pages),render='not_run',client='not_run')
            task.set_progress(progress);task.status='COMPLETED';task.completed_at=datetime.utcnow();db.session.commit()
        finally:
            if temp:temp.unlink(missing_ok=True)

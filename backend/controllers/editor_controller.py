"""Authenticated editor storage. No OCR, no Provider call, no client root paths."""
import json
import os
import tempfile
from io import BytesIO
from pathlib import Path
from flask import Blueprint, request, current_app, send_file
from sqlalchemy.exc import IntegrityError
from models import db, Page as LocalPage
from models.editor_document import EditorDocument, EditorRevision
from utils import success_response, error_response, not_found
from utils.auth import owned_project_or_404, current_user_id, require_auth
from services.semantic_export import AssetStore, load_page
from services.semantic_export.model import digest, Correction
from services.pptist_editor.adapter import PPTistAdapter

editor_bp = Blueprint('editor',__name__,url_prefix='/api/projects/<project_id>')
MAX_BYTES=4*1024*1024
adapter=PPTistAdapter()

def store_for(project_id):
    # project_id already resolved by owned_project_or_404; never from document URI.
    return AssetStore(Path(current_app.config['UPLOAD_FOLDER'])/project_id,user_id=current_user_id(),project_id=project_id)

def revision_row(project_id,revision):
    return EditorRevision.query.filter_by(project_id=project_id,revision=revision).first()

def scoped_adapter(revision):
    return PPTistAdapter(lambda a: f'/api/projects/{a.project_id}/editor-assets/{a.id}?sha256={a.sha256}')

def document_data(row):
    pages=[load_page(p) for p in json.loads(row.payload)]
    result=dict(revision=row.revision,pages=[p.model_dump(mode='json') for p in pages],width=pages[0].width,height=pages[0].height)
    result['asset_options']={p.id:[dict(id=a.id,url=scoped_adapter(row.revision).asset_url(a)) for a in p.assets if a.media_type!='image/svg+xml'] for p in pages}
    try: result['slides']=[scoped_adapter(row.revision).to_editor(p) for p in pages]
    except ValueError as exc: result.update(readonly=True,reason=str(exc))
    if len(json.dumps(result,ensure_ascii=False).encode())>MAX_BYTES: raise ValueError('editor response exceeds 4 MiB')
    return result

def validate_pages(raw,project_id,*,freeze_assets=False):
    if not isinstance(raw,list) or not 1<=len(raw)<=100: raise ValueError('1–100 pages required')
    pages=[load_page(p) for p in raw]
    ids=[p.id for p in pages]
    if len(set(ids))!=len(ids): raise ValueError('duplicate page ID')
    local_pages=LocalPage.query.filter_by(project_id=project_id).order_by(LocalPage.order_index).all()
    local={p.id for p in local_pages}
    if ids != [p.id for p in local_pages]:raise ValueError('semantic page order must match Local Pages')
    assets=store_for(project_id) if any(p.assets for p in pages) else None
    for p in pages:
        if p.project_id!=project_id or p.user_id!=current_user_id() or p.id not in local: raise ValueError('page ownership mismatch')
        if (p.width,p.height)!=(pages[0].width,pages[0].height): raise ValueError('mixed page sizes unsupported')
        if len(p.nodes)>1000: raise ValueError('too many objects')
        if assets:
            for a in p.assets:
                candidate=(assets.root/a.uri).resolve(strict=True)
                if not candidate.is_relative_to(assets.root) or candidate.stat().st_size>20*1024*1024:raise ValueError('asset exceeds limit or escapes project')
            assets.verify(p)
            if freeze_assets:
                target=assets.root/'editor-assets';target.mkdir(exist_ok=True)
                for a in p.assets:
                    ext={'image/png':'.png','image/jpeg':'.jpg','image/svg+xml':'.svg'}[a.media_type]
                    name=a.sha256+ext
                    blob=assets.read(a)
                    # Content-addressed assets never overwrite any older resource.
                    destination=target/name
                    if destination.exists():
                        import hashlib
                        if hashlib.sha256(destination.read_bytes()).hexdigest()!=a.sha256:raise ValueError('immutable asset corrupted')
                    else:
                        with tempfile.NamedTemporaryFile(dir=target,delete=False) as temp:
                            temp.write(blob);temporary=temp.name
                        os.replace(temporary,destination)
                    a.uri='editor-assets/'+name
    return pages

class RevisionConflict(Exception): pass

def write_revision(project_id,base_revision,pages,restored_from=None):
    if type(base_revision) is not int or base_revision<0: raise ValueError('base_revision required')
    next_revision=base_revision+1
    if base_revision==0:
        db.session.add(EditorDocument(project_id=project_id,revision=1))
        try: db.session.flush()
        except IntegrityError as exc:
            db.session.rollback()
            if db.session.get(EditorDocument,project_id): raise RevisionConflict() from exc
            raise
    else:
        count=db.session.query(EditorDocument).filter_by(project_id=project_id,revision=base_revision).update({'revision':next_revision},synchronize_session=False)
        if count!=1: raise RevisionConflict()
    raw=[p.model_dump(mode='json') for p in pages]
    for p in raw: p['revision']=f'editor-r{next_revision}'
    row=EditorRevision(project_id=project_id,revision=next_revision,actor_user_id=current_user_id(),restored_from_revision=restored_from,payload=json.dumps(raw,ensure_ascii=False,allow_nan=False))
    db.session.add(row);db.session.flush()
    document_data(row)  # Reject unrepresentable/oversized response before commit.
    db.session.commit()
    return row

@editor_bp.route('/editor-document/initialize',methods=['POST'])
@editor_bp.route('/editor-document',methods=['GET','PUT'])
@require_auth
def document(project_id):
    if not owned_project_or_404(project_id): return not_found('Project')
    doc=db.session.get(EditorDocument,project_id)
    if request.method=='GET':
        if not doc:return error_response('EDITOR_DOCUMENT_NOT_FOUND','此项目尚无语义文档。图片自动转换尚未实现。',404)
        return success_response(document_data(revision_row(project_id,doc.revision)))
    if len(request.get_data(cache=True))>MAX_BYTES:return error_response('EDITOR_PAYLOAD_TOO_LARGE','文档超过 4 MiB',413)
    try:
        body=request.get_json()
        if not isinstance(body,dict):raise ValueError('JSON object required')
        if request.method=='POST' and doc: return error_response('EDITOR_REVISION_CONFLICT','文档已经初始化',409)
        if request.method=='PUT' and not doc: return error_response('EDITOR_DOCUMENT_NOT_FOUND','先显式初始化结构化语义文档',404)
        base=body.get('base_revision')
        if type(base) is not int:raise ValueError('base_revision required')
        if (doc.revision if doc else 0)!=base:return error_response('EDITOR_REVISION_CONFLICT','文档已由其他窗口保存，请保留草稿并重新加载。',409)
        if doc:
            if set(body)!={'base_revision','slides'}:raise ValueError('only editor slides accepted for existing document')
            originals=[load_page(p) for p in json.loads(revision_row(project_id,base).payload)]
            slides=body['slides']
            if not isinstance(slides,list) or any(not isinstance(s,dict) for s in slides) or [s.get('id') for s in slides]!=[p.id for p in originals]:raise ValueError('page addition, deletion and reorder are not enabled yet')
            pages=[scoped_adapter(base).from_editor(s,base=p) for s,p in zip(slides,originals)]
            for p,old in zip(pages,originals):
                oldnodes={n.id:n for n in old.nodes}
                for n in p.nodes:
                    if n.id in oldnodes and n!=oldnodes[n.id]:
                        p.corrections.append(Correction(revision=f'editor-r{base+1}',object_id=n.id,reason='PPTist manual edit',before_sha256=digest(oldnodes[n.id]),after_sha256=digest(n)))
            pages=validate_pages([p.model_dump(mode='json') for p in pages],project_id)
        else:
            if set(body)!={'base_revision','pages'}:raise ValueError('explicit structured pages required for initialization')
            pages=validate_pages(body['pages'],project_id,freeze_assets=True)
            for p in pages:adapter.to_editor(p)
        row=write_revision(project_id,base,pages)
        return success_response(document_data(row))
    except RevisionConflict:
        db.session.rollback();return error_response('EDITOR_REVISION_CONFLICT','版本冲突，未覆盖服务器文档。',409)
    except OSError:
        db.session.rollback();return error_response('EDITOR_ASSET_UNAVAILABLE','授权素材缺失或无法读取',400)
    except (ValueError,KeyError,TypeError,IndexError) as exc:
        db.session.rollback();return error_response('EDITOR_UNSUPPORTED_CHANGE',str(exc),400)

@editor_bp.route('/editor-document/revisions',methods=['GET'])
@require_auth
def revisions(project_id):
    if not owned_project_or_404(project_id):return not_found('Project')
    rows=EditorRevision.query.filter_by(project_id=project_id).order_by(EditorRevision.revision.desc()).limit(100).all()
    return success_response([dict(revision=r.revision,created_at=r.created_at.isoformat()) for r in rows])

@editor_bp.route('/editor-document/restore',methods=['POST'])
@require_auth
def restore(project_id):
    if not owned_project_or_404(project_id):return not_found('Project')
    body=request.get_json(silent=True) or {}
    if not isinstance(body,dict) or type(body.get('revision')) is not int:return error_response('INVALID_REQUEST','revision required',400)
    row=revision_row(project_id,body['revision'])
    if not row:return not_found('Revision')
    try:
        pages=validate_pages(json.loads(row.payload),project_id)
        result=write_revision(project_id,body.get('base_revision'),pages,restored_from=body['revision'])
        return success_response(document_data(result))
    except RevisionConflict:
        db.session.rollback();return error_response('EDITOR_REVISION_CONFLICT','版本冲突',409)
    except OSError:
        db.session.rollback();return error_response('EDITOR_ASSET_UNAVAILABLE','授权素材缺失或无法读取',400)
    except ValueError as exc:
        db.session.rollback();return error_response('INVALID_REQUEST',str(exc),400)

@editor_bp.route('/editor-assets/<asset_id>',methods=['GET'])
@require_auth
def asset(project_id,asset_id):
    if not owned_project_or_404(project_id):return not_found('Project')
    sha=request.args.get('sha256','')
    if len(sha)!=64:return not_found('Asset')
    rows=EditorRevision.query.filter_by(project_id=project_id).order_by(EditorRevision.revision.desc()).all()
    for row in rows:
        for raw in json.loads(row.payload):
            for a in load_page(raw).assets:
                if a.id==asset_id and a.sha256==sha:
                    try:
                        blob=store_for(project_id).read(a)
                        if len(blob)>20*1024*1024:return error_response('ASSET_TOO_LARGE','Asset exceeds 20 MiB',413)
                        response=send_file(BytesIO(blob),mimetype=a.media_type,conditional=True)
                        response.headers['Content-Security-Policy']="default-src 'none'; sandbox"
                        response.headers['X-Content-Type-Options']='nosniff'
                        return response
                    except (ValueError,OSError):return not_found('Asset')
    return not_found('Asset')

@editor_bp.route('/editor-document/export',methods=['POST'])
@require_auth
def export_document(project_id):
    from hashlib import sha256
    from datetime import datetime
    from time import monotonic
    from models import Task
    from services.task_manager import task_manager
    from services.task_execution import TaskExecutionContext
    from services.provider_config import active_provider_snapshot
    from services.pptist_editor.export import export_revision
    if not owned_project_or_404(project_id):return not_found('Project')
    body=request.get_json(silent=True) or {}
    if not isinstance(body,dict) or type(body.get('revision')) is not int:return error_response('INVALID_REQUEST','revision required',400)
    row=revision_row(project_id,body['revision'])
    if not row:return not_found('Revision')
    # Serialize task admission on the existing document row. Both the lock and
    # pending task insert remain in one transaction; SQLite serializes writers.
    db.session.query(EditorDocument).filter_by(project_id=project_id).update({'revision':EditorDocument.revision},synchronize_session=False)
    active=Task.query.filter_by(project_id=project_id,user_id=current_user_id(),task_type='EXPORT_SEMANTIC_EDITOR').filter(Task.status.in_(['PENDING','PROCESSING'])).first()
    if active:
        db.session.rollback()
        if active.get_progress().get('revision_id')==row.id:return success_response(active.to_dict())
        return error_response('EDITOR_EXPORT_BUSY','该项目已有语义导出任务',409)
    task=Task(user_id=current_user_id(),project_id=project_id,task_type='EXPORT_SEMANTIC_EDITOR',status='PENDING')
    task.set_progress(dict(revision=row.revision,revision_id=row.id,payload_hash=sha256(row.payload.encode()).hexdigest(),credits=0,total=len(json.loads(row.payload)),completed=0))
    db.session.add(task);db.session.commit()
    try:
        task_manager.submit_task(task.id,export_revision,project_id=project_id,user_id=current_user_id(),revision_id=row.id,payload_hash=task.get_progress()['payload_hash'],app=current_app._get_current_object(),provider_snapshot=active_provider_snapshot(),execution_context=TaskExecutionContext(task.id,current_user_id(),project_id,deadline=monotonic()+300))
    except Exception:
        task.status='FAILED';task.error_message='EDITOR_EXPORT_SUBMIT_FAILED';task.completed_at=datetime.utcnow();db.session.commit()
        return error_response('EDITOR_EXPORT_SUBMIT_FAILED','任务提交失败',503)
    return success_response(task.to_dict(),status_code=202)

@editor_bp.route('/editor-document/exports/<task_id>',methods=['GET'])
@require_auth
def download_export(project_id,task_id):
    from models import Task
    if not owned_project_or_404(project_id):return not_found('Project')
    task=Task.query.filter_by(id=task_id,project_id=project_id,user_id=current_user_id(),task_type='EXPORT_SEMANTIC_EDITOR',status='COMPLETED').first()
    if not task:return not_found('Export')
    name=f"editor-r{task.get_progress()['revision']}-{task.id}.pptx"
    path=Path(current_app.config['UPLOAD_FOLDER'])/project_id/'exports'/name
    if not path.is_file():return not_found('Export')
    return send_file(path,as_attachment=True,download_name=name,mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation')

@editor_bp.route('/editor-document/export-tasks/<task_id>',methods=['GET','DELETE'])
@require_auth
def export_task(project_id,task_id):
    from models import Task
    if not owned_project_or_404(project_id):return not_found('Project')
    task=Task.query.filter_by(id=task_id,project_id=project_id,user_id=current_user_id(),task_type='EXPORT_SEMANTIC_EDITOR').first()
    if not task:return not_found('Task')
    if request.method=='DELETE' and task.status in ('PENDING','PROCESSING'):
        progress=task.get_progress();progress['cancel_requested']=True;task.set_progress(progress);db.session.commit()
    return success_response(task.to_dict())

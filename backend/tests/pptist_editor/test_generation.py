import copy
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image, ImageDraw
from models import db, User, Project, Page, Task, CreditAccount, CreditLedger
from models.editor_document import EditorDocument, EditorRevision
from utils.auth import create_auth_token
from services.provider_config import provider_snapshot_scope
from services.task_execution import task_execution_scope
from services.pptist_editor.generation import organize_image, GenerationError


def plan():
    return dict(background='FFFFFF', groups=[dict(id='card', name='卡片', module_id='card')], nodes=[
        dict(id='frame', name='完整底框', kind='shape', box=dict(x=20,y=20,w=380,h=350), layer=0,module_id='card',parent_id='card',shape=dict(geometry='roundRect',fill='EEEEEE')),
        dict(id='body', name='正文', kind='text', box=dict(x=40,y=50,w=340,h=160),layer=1,module_id='card',parent_id='card',text=dict(paragraphs=[dict(runs=[dict(text='可编辑原文',size=24)])])),
        dict(id='photo',name='完整截图',kind='image',box=dict(x=450,y=50,w=250,h=250),layer=2,module_id='photo',picture=dict(role='screenshot')),
    ])


@pytest.fixture
def conversion(client, app, monkeypatch):
    monkeypatch.setenv('AUTH_REQUIRED','true')
    monkeypatch.setenv('CREDIT_ENABLED','true')
    owner=User(username='generation-owner'); owner.set_password('test-only')
    other=User(username='generation-other'); other.set_password('test-only')
    db.session.add_all([owner,other]); db.session.flush()
    project=Project(user_id=owner.id, creation_type='idea'); db.session.add(project); db.session.flush()
    root=Path(app.config['UPLOAD_FOLDER'])/project.id; root.mkdir()
    image=Image.new('RGB',(800,450),'white'); ImageDraw.Draw(image).rectangle((450,50,700,300),fill='green'); image.save(root/'page.png')
    page=Page(project_id=project.id,order_index=0,generated_image_path=f'{project.id}/page.png'); db.session.add(page); db.session.commit()
    calls=[]
    import controllers.editor_generation_controller as controller
    monkeypatch.setattr(controller.task_manager,'submit_task',lambda *a,**kw:calls.append((a,kw)))
    class Vision:
        def _generate_text_from_image(self,prompt,path):
            assert '800 x 450' in prompt
            assert Path(path).is_file()
            return json.dumps(plan(),ensure_ascii=False)
    import services.ai_service_manager as manager
    monkeypatch.setattr(manager,'create_ai_service',lambda:Vision())
    return dict(root=root,owner=owner.id,project=project.id,page=page.id,calls=calls,
                url=f'/api/projects/{project.id}/editable-generation',
                headers={'Authorization':'Bearer '+create_auth_token(owner)},
                other={'Authorization':'Bearer '+create_auth_token(other)})


def run(c):
    args, kwargs=c['calls'][-1]
    snapshot=kwargs.pop('provider_snapshot')
    control=kwargs.pop('execution_context')
    with provider_snapshot_scope(snapshot), task_execution_scope(control): args[1](args[0],**kwargs)
    db.session.expire_all()


def test_image_to_editor_and_download_full_lifecycle(client,conversion):
    c=conversion
    state=client.get(c['url'],headers=c['headers']).json['data']
    assert state['ready'] is False and state['credit_estimate']['amount']==110
    r=client.post(c['url'],json={},headers=c['headers']); assert r.status_code==202,r.json
    tid=r.json['data']['task']['task_id']
    assert c['calls'][0][1]['provider_snapshot'].user_id==c['owner']
    # Duplicate request reuses pending task and its single reservation.
    duplicate=client.post(c['url'],json={},headers=c['headers'])
    assert duplicate.json['data']['task']['task_id']==tid and len(c['calls'])==1
    run(c)
    state=client.get(c['url'],headers=c['headers']).json['data']
    assert state['ready'] and state['task']['status']=='COMPLETED',state
    document=client.get(f'/api/projects/{c["project"]}/editor-document',headers=c['headers'])
    assert document.status_code==200,document.json
    assert document.json['data']['slides'][0]['id']==c['page']
    download=client.get(state['task']['progress']['download_url'],headers=c['headers'])
    assert download.status_code==200
    with ZipFile(BytesIO(download.data)) as deck:
        xml=deck.read('ppt/slides/slide1.xml').decode()
        assert '可编辑原文' in xml and '<p:grpSp>' in xml and '<p:pic>' in xml
    account=db.session.get(CreditAccount,c['owner'])
    assert account.reserved_balance==0 and account.lifetime_spent==110
    # Existing editor content is never re-generated/charged on repeat click.
    assert client.post(c['url'],json={},headers=c['headers']).json['data']['ready']
    assert len(c['calls'])==1 and EditorRevision.query.count()==1
    assert client.get(state['task']['progress']['download_url'],headers=c['other']).status_code==404


def test_auth_sources_and_untrusted_parameters(client,conversion):
    c=conversion
    assert client.get(c['url']).status_code==401
    assert client.post(c['url'],json={},headers=c['other']).status_code==404
    assert client.post(c['url'],json={'user_id':c['owner']},headers=c['headers']).status_code==400
    db.session.get(Page,c['page']).generated_image_path=None; db.session.commit()
    assert client.post(c['url'],json={},headers=c['headers']).status_code==400
    assert not c['calls'] and Task.query.count()==0


def test_failure_does_not_publish_or_charge_and_can_retry(client,conversion,monkeypatch):
    c=conversion
    import services.pptist_editor.generation as generation
    original=generation.extract_page
    monkeypatch.setattr(generation,'extract_page',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('provider secret detail')))
    client.post(c['url'],json={},headers=c['headers']); run(c)
    state=client.get(c['url'],headers=c['headers']).json['data']
    assert not state['ready'] and state['task']['status']=='FAILED'
    assert 'provider secret detail' not in json.dumps(state)
    assert EditorDocument.query.count()==0
    account=db.session.get(CreditAccount,c['owner']); assert account.lifetime_spent==0 and account.reserved_balance==0
    monkeypatch.setattr(generation,'extract_page',original)
    assert client.post(c['url'],json={},headers=c['headers']).status_code==202
    run(c)
    assert client.get(c['url'],headers=c['headers']).json['data']['ready']


def test_changed_source_prevents_publication(client,conversion):
    c=conversion
    client.post(c['url'],json={},headers=c['headers'])
    Image.new('RGB',(800,450),'blue').save(c['root']/'page.png')
    run(c)
    assert EditorDocument.query.count()==0
    state=client.get(c['url'],headers=c['headers']).json['data']; assert state['task']['status']=='FAILED'
    assert db.session.get(CreditAccount,c['owner']).reserved_balance==0


def test_semantic_rejects_fullpage_and_external_paths(conversion):
    c=conversion
    from services.pptist_editor.generation import capture_sources
    source=capture_sources(c['project'])[0]
    with Image.open(c['root']/'page.png') as image:
        invalid=plan(); invalid['nodes'][2]['box']=dict(x=0,y=0,w=800,h=450)
        with pytest.raises(GenerationError): organize_image(invalid,image,source=source,project_id=c['project'],user_id=c['owner'],root=c['root'])
        invalid=plan(); invalid['nodes'][2]['picture']['uri']='../../private.png'
        with pytest.raises(GenerationError): organize_image(invalid,image,source=source,project_id=c['project'],user_id=c['owner'],root=c['root'])


def test_existing_manual_document_not_overwritten(client,conversion):
    c=conversion
    client.post(c['url'],json={},headers=c['headers'])
    db.session.add(EditorDocument(project_id=c['project'],revision=2)); db.session.commit()
    run(c)
    assert db.session.get(EditorDocument,c['project']).revision==2
    assert Task.query.one().status=='FAILED'
    assert db.session.get(CreditAccount,c['owner']).lifetime_spent==0


def test_status_poll_never_loads_provider_keys(client,conversion,monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module,'capture_provider_snapshot',lambda **kw:(_ for _ in ()).throw(AssertionError('status poll must not load Provider')))
    assert client.get(conversion['url'],headers=conversion['headers']).status_code==200


def test_project_delete_blocked_during_generation(client,conversion):
    c=conversion
    client.post(c['url'],json={},headers=c['headers'])
    response=client.delete(f'/api/projects/{c["project"]}',headers=c['headers'])
    assert response.status_code==409
    assert (c['root']/'page.png').is_file() and Task.query.count()==1
    run(c)
    before=[(x.id,x.amount,x.balance_after,x.reserved_after,x.user_id,x.entry_type) for x in CreditLedger.query.order_by(CreditLedger.id).all()]
    scoped_ids={x.id for x in CreditLedger.query.filter_by(project_id=c['project']).all()}
    assert client.delete(f'/api/projects/{c["project"]}',headers=c['headers']).status_code==200
    after=[(x.id,x.amount,x.balance_after,x.reserved_after,x.user_id,x.entry_type) for x in CreditLedger.query.order_by(CreditLedger.id).all()]
    assert before==after
    assert all(x.project_id is None and x.task_id is None and x.legacy_project_id==c['project'] for x in CreditLedger.query.all() if x.id in scoped_ids)
    assert db.session.execute(db.text('PRAGMA foreign_key_check')).all()==[]


def test_all_pages_publish_atomically_and_retry_reuses_good_page(client,conversion,monkeypatch):
    c=conversion
    second=Page(project_id=c['project'],order_index=1,generated_image_path=f'{c["project"]}/page.png')
    db.session.add(second);db.session.commit(); second_id=second.id
    import services.pptist_editor.generation as generation
    original=generation.extract_page; seen=[]; fail=[True]
    def extract(ai,source,**kw):
        seen.append(source['id'])
        if source['id']==second_id and fail[0]:raise GenerationError('第二页转换失败')
        return original(ai,source,**kw)
    monkeypatch.setattr(generation,'extract_page',extract)
    client.post(c['url'],json={},headers=c['headers']);run(c)
    assert EditorDocument.query.count()==0 and EditorRevision.query.count()==0
    assert db.session.get(CreditAccount,c['owner']).reserved_balance==0
    fail[0]=False
    client.post(c['url'],json={},headers=c['headers']);run(c)
    state=client.get(c['url'],headers=c['headers']).json['data'];assert state['ready'],state
    assert seen==[c['page'],second_id,second_id]
    assert len(json.loads(EditorRevision.query.one().payload))==2

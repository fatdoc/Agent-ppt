"""Start disposable editor acceptance server; no real DB/.env/uploads/provider.
Usage: python scripts/verify_pptist_runtime.py --port 5191 --output /tmp/pptist-qa
Stop with Ctrl-C; only this process's temp storage is removed.
"""
import argparse,os,sys,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backend'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=5191);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--image-flow',action='store_true',help='Start with image only; deterministic fake vision, never real model quality verification');args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='banana-pptist-') as tmp:
        # Child re-exec removes inherited secret/provider settings before imports.
        if not os.getenv('PPTIST_ISOLATED'):
            env={k:os.environ[k] for k in ('PATH','TMPDIR') if k in os.environ}
            env.update(PPTIST_ISOLATED='1',LOAD_DOTENV='false',AUTH_REQUIRED='true',AUTH_COOKIE_SECURE='false',DATABASE_URL=f'sqlite:///{tmp}/qa.db',UPLOAD_FOLDER=f'{tmp}/uploads',HOME=tmp,SECRET_KEY='isolated-editor-test-only-not-for-production')
            import subprocess
            return subprocess.call([sys.executable,__file__,'--port',str(args.port),'--output',str(args.output)]+(['--image-flow'] if args.image_flow else []),env=env)
        from app import create_app
        from models import db,User,Project,Page
        from scripts.semantic_export.sample import samples
        from services.semantic_export.model import load_page
        from models.editor_document import EditorDocument,EditorRevision
        app=create_app({'TESTING':True})
        with app.app_context():
            db.create_all()
            user=User(username='editor-test');user.set_password('editor-test-only');db.session.add(user);db.session.flush()
            project=Project(id='pptist-acceptance',user_id=user.id,creation_type='idea',project_title='PPTist 人工测试样例');db.session.add(project);db.session.flush()
            root=Path(app.config['UPLOAD_FOLDER'])/project.id;root.mkdir(parents=True)
            pages=[] if args.image_flow else samples(root)
            raw=[]
            for i,p in enumerate(pages):
                db.session.add(Page(id=p.id,project_id=project.id,order_index=i))
                d=p.model_dump(mode='json');d.update(user_id=user.id,project_id=project.id)
                for a in d['assets']:a.update(user_id=user.id,project_id=project.id)
                raw.append(load_page(d).model_dump(mode='json'))
            if args.image_flow:
                from PIL import Image,ImageDraw
                image=Image.new('RGB',(1280,720),'white');draw=ImageDraw.Draw(image)
                draw.rounded_rectangle((40,80,900,600),radius=20,fill='#EEEEEE')
                draw.text((80,120),'Image flow acceptance',fill='black',font_size=42)
                draw.rectangle((600,200,850,500),fill='#337755');(root/'pages').mkdir();image.save(root/'pages'/'source.png')
                page=Page(project_id=project.id,order_index=0,generated_image_path=project.id+'/pages/source.png',status='COMPLETED')
                page.set_outline_content({'title':'Image flow acceptance','points':['Offline fixture']})
                page.set_description_content({'text':'Image flow acceptance'})
                db.session.add(page)
                response=dict(background='FFFFFF',groups=[dict(id='card',name='Test card',module_id='card')],nodes=[
                    dict(id='frame',name='Card',kind='shape',box=dict(x=40,y=80,w=860,h=520),layer=0,module_id='card',parent_id='card',shape=dict(geometry='roundRect',fill='EEEEEE')),
                    dict(id='title',name='Title',kind='text',box=dict(x=80,y=120,w=500,h=65),layer=1,module_id='card',parent_id='card',text=dict(paragraphs=[dict(runs=[dict(text='Image flow acceptance',size=42)])])),
                    dict(id='picture',name='Image',kind='image',box=dict(x=600,y=200,w=250,h=300),layer=2,module_id='card',parent_id='card',picture=dict(role='photo'))])
                class OfflineVision:
                    def _generate_text_from_image(self,*a,**kw):return json.dumps(response)
                import services.ai_service_manager as manager
                manager.create_ai_service=lambda *a,**kw:OfflineVision()
            else:
                db.session.add(EditorDocument(project_id=project.id,revision=1))
                db.session.add(EditorRevision(project_id=project.id,revision=1,actor_user_id=user.id,payload=json.dumps(raw,ensure_ascii=False)))
            db.session.commit()
        # All outbound network attempts from backend must fail. Local HTTP server
        # accept/send does not call socket.connect.
        import socket
        def blocked(*a,**kw):raise RuntimeError('Outbound network disabled for editor acceptance')
        socket.socket.connect=blocked
        (args.output/'runtime.json').write_text(json.dumps({'port':args.port,'project_id':'pptist-acceptance','temporary':True}))
        from werkzeug.serving import make_server
        server=make_server('127.0.0.1',args.port,app,threaded=True)
        print(f'Isolated PPTist API ready on {args.port}',flush=True)
        try:server.serve_forever()
        finally:server.server_close()
if __name__=='__main__':raise SystemExit(main())

"""Start disposable editor acceptance server; no real DB/.env/uploads/provider.
Usage: python scripts/verify_pptist_runtime.py --port 5191 --output /tmp/pptist-qa
Stop with Ctrl-C; only this process's temp storage is removed.
"""
import argparse,os,sys,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backend'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=5191);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='banana-pptist-') as tmp:
        # Child re-exec removes inherited secret/provider settings before imports.
        if not os.getenv('PPTIST_ISOLATED'):
            env={k:os.environ[k] for k in ('PATH','TMPDIR') if k in os.environ}
            env.update(PPTIST_ISOLATED='1',LOAD_DOTENV='false',AUTH_REQUIRED='true',AUTH_COOKIE_SECURE='false',DATABASE_URL=f'sqlite:///{tmp}/qa.db',UPLOAD_FOLDER=f'{tmp}/uploads',HOME=tmp,SECRET_KEY='isolated-editor-test-only-not-for-production')
            import subprocess
            return subprocess.call([sys.executable,__file__,'--port',str(args.port),'--output',str(args.output)],env=env)
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
            pages=samples(root)
            raw=[]
            for i,p in enumerate(pages):
                db.session.add(Page(id=p.id,project_id=project.id,order_index=i))
                d=p.model_dump(mode='json');d.update(user_id=user.id,project_id=project.id)
                for a in d['assets']:a.update(user_id=user.id,project_id=project.id)
                raw.append(load_page(d).model_dump(mode='json'))
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

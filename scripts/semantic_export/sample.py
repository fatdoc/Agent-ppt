"""Small offline fixture. No credentials, network, application startup or DB.

Usage: python scripts/semantic_export/sample.py --output /tmp/semantic-demo
Optional --reference-dir imports ONE explicitly manual page from the supplied
reference delivery; original assets/output stay outside Git.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from services.semantic_export import AssetStore, export_pages, load_page
from services.semantic_export.model import correct_node


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance(source='fixture', **kwargs):
    return dict(method='manual_fixture', source_ref=source, **kwargs)


def node(id, kind, box, layer, module='page', parent=None, **payload):
    return dict(id=id, name=id, kind=kind, box=dict(zip(('x','y','w','h'), box)), layer=layer, module_id=module, parent_id=parent, provenance=provenance(), **payload)


def text(value, size=24, color='203040', bold=False):
    return dict(paragraphs=[dict(runs=[dict(text=value, size=size, font='Noto Sans CJK SC', color=color, bold=bold)])])


def basic_page(id, nodes, **kwargs):
    return dict(schema_version='1.0', id=id, revision='r1', source=dict(id='fixture',revision='r1',sha256=hashlib.sha256(('manual-fixture-'+id).encode()).hexdigest()), user_id='sample-user', project_id='sample-project', width=1280,height=720,nodes=nodes, **kwargs)


def asset(root, path, id, mime):
    return dict(id=id,uri=str(path.relative_to(root)),sha256=sha(path),media_type=mime,user_id='sample-user',project_id='sample-project',provenance=provenance())


def samples(out):
    assets_dir = out/'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)
    # Existing repository content is only staged to the sample's authorized root.
    screenshot = assets_dir/'software.png'
    shutil.copyfile(ROOT/'frontend/public/images/login-harness-panel.png', screenshot)
    for name in ('monitor.svg', 'monitor.png'):
        shutil.copyfile(Path(__file__).parent/'fixtures'/name, assets_dir/name)
    assets = [asset(out, screenshot, 'software', 'image/png'), asset(out, assets_dir/'monitor.svg','monitor','image/svg+xml'),asset(out,assets_dir/'monitor.png','monitor-png','image/png')]
    nodes = [node('title','text',[60,42,1160,68],0,text=text('语义导出验证：正文、卡片与完整软件截图',40,bold=True)),
             node('card','shape',[60,155,1160,475],1,'content','content-group',shape=dict(geometry='roundRect',fill='F2F5F8')),
             node('icon','svg',[92,190,48,48],2,'content','content-group',picture=dict(asset_id='monitor',fallback_asset_id='monitor-png',role='icon')),
             node('body','text',[92,264,365,210],3,'content','content-group',text=text('标题和正文保留为原生文字。\n卡片底框是一个完整形状。\n界面内的小字随截图保留。',26)),
             node('screenshot','image',[710,190,385*1039/1514,385],4,'content','content-group',picture=dict(asset_id='software',role='screenshot',preserve_whole=True)),
             node('footnote','text',[60,663,1160,28],5,text=text('人工标注输入样例；不代表自动区域识别验收。',18))]
    representative = load_page(basic_page('representative',nodes,assets=assets,groups=[dict(id='content-group',name='正文与软件界面',module_id='content')]))
    table_nodes = [node('table-title','text',[60,42,1160,65],0,text=text('独立业务表格样例',40,bold=True)),
                   node('table-note','text',[60,123,1160,44],1,text=text('以下为虚构验收数据，用于测试原生表格和中文排版。',24)),
                   node('table','table',[60,204,1160,342],2,table=dict(rows=[['检查项','输入类型','结果','备注'],['标题与正文','原生文本','待验收','允许直接改字'],['卡片模块','命名组合','待验收','移动后保持相对位置'],['软件截图','完整图片','待验收','不重复提取小字'],['业务表格','原生表格','待验收','可编辑单元格']],column_weights=[.24,.24,.16,.36],size=24)),
                   node('table-footer','text',[60,620,1160,40],3,text=text('表格独立于截图；示例数据不作为项目成果证明。',20))]
    return [representative,load_page(basic_page('business-table',table_nodes))]


def import_reference(ref, out):
    # Explicit manual fixture conversion, NOT an arbitrary reference-script parser.
    source = json.loads((ref/'source/deck.json').read_text())[20]
    ordered = []
    by_group = {}
    warnings = ['Manual page 21 fixture; reference image-generation illustration, not hardware evidence.', 'Native solid background replaces decorative photographic texture.', 'Reference gradient/alpha simplified explicitly; no whole-page image used.']
    for index, old in enumerate(source['objects']):
        if old.get('group') == '页面装饰':
            continue
        by_group.setdefault(old.get('group','page'), []).append((index,old))
    groups, assets, nodes = [], [], []
    asset_dir = out/'assets'
    asset_dir.mkdir(exist_ok=True, parents=True)
    for gi,(name,items) in enumerate(by_group.items()):
        gid = f'module-{gi}'
        groups.append(dict(id=gid,name=name,module_id=gid))
        for index,old in items:
            id = f'ref-{index}'
            kind = old['kind']
            payload = {}
            if kind == 'text':
                payload['text'] = text(old['text'],old['size'],old.get('color','#FAF8D5').lstrip('#'),old.get('bold',False))
                payload['text']['paragraphs'][0]['align'] = old.get('align','left')
            elif kind == 'shape':
                payload['shape'] = dict(geometry=old.get('geo','roundRect'),fill=old['fill'].split('/')[0].lstrip('#'),stroke=old.get('stroke','none').lstrip('#') if old.get('stroke','none')!='none' else None)
            else:
                path = ref/old['file']
                target = asset_dir/(id+path.suffix)
                shutil.copyfile(path,target)
                assets.append(asset(out,target,id,'image/svg+xml' if kind=='svg' else 'image/png'))
                payload['picture'] = dict(asset_id=id,role='icon' if kind=='svg' else ('screenshot' if 'screenshots' in old['file'] else 'photo'),preserve_whole='screenshots' in old['file'])
                if kind=='svg':
                    # Offline fixture preparation only. Runtime builder requires supplied fallback.
                    import fitz
                    target_png = target.with_suffix('.png')
                    svg_doc = fitz.open(target)
                    svg_doc[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=True).save(target_png)
                    assets.append(asset(out,target_png,id+'-png','image/png'))
                    payload['picture']['fallback_asset_id'] = id+'-png'
            n=node(id,kind,old['box'],len(nodes),gid,gid,**payload)
            n['name']=old.get('name',id)
            n['provenance']=provenance('reference-p21',source_box=dict(zip(('x','y','w','h'),old.get('source_box',old['box']))))
            nodes.append(n)
    p=basic_page('reference-p21',nodes,assets=assets,groups=groups,background='113D2E',warnings=warnings)
    p['source']=dict(id='reference-p21',revision='reference-delivery',sha256=sha(ref/'reference/21.png'))
    # Explicitly regroup disjoint cards into contiguous paint runs in fixture;
    # boxes don't overlap unrelated nodes, verified visually. Core never reorders.
    page=load_page(p)
    title=next(n for n in page.nodes if n.kind=='text' and 'MQTT' in n.text.paragraphs[0].runs[0].text).model_copy(deep=True)
    title.box.w=1160
    title.text.paragraphs[0].runs[0].size=52
    title.provenance.method='manual_correction'
    return correct_node(page,title.id,title,'r2','Rendered title wrapped over card. Widened native text box and reduced title font; wording unchanged.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reference-dir',type=Path)
    args=parser.parse_args()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    pages=samples(out)
    if args.reference_dir:
        pages=[import_reference(args.reference_dir,out),pages[1]]
        shutil.copyfile(args.reference_dir/'reference/21.png',out/'reference-1.png')
    for p in pages:
        (out/(p.id+'.json')).write_text(p.model_dump_json(indent=2))
    store=AssetStore(out,user_id='sample-user',project_id='sample-project')
    events=[]
    raw,report=export_pages(pages,store=store,checkpoint_dir=out/'.checkpoints',mode='semantic',on_event=events.append)
    (out/'semantic-phase1.pptx').write_bytes(raw)
    (out/'structure-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (out/'events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2))
    print(json.dumps(dict(output=str(out/'semantic-phase1.pptx'),sha256=hashlib.sha256(raw).hexdigest(),report=report),ensure_ascii=False))


if __name__ == '__main__':
    main()

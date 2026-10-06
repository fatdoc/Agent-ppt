"""Inspect an externally rendered PDF; does not install/choose office software.

Usage: python scripts/semantic_export/render_check.py OUTPUT_DIR
Run a trusted LibreOffice/PowerPoint PDF export first. Output includes independent
raster previews, side-by-side comparison, text coverage and bounds findings.
"""
import argparse
import json
import html
import re
from pathlib import Path
import fitz
from PIL import Image


def inspect(out):
    pdf=fitz.open(out/'semantic-phase1.pdf')
    structure=json.loads((out/'structure-report.json').read_text())
    assert len(pdf)==len(structure)
    findings=[]
    previews=[]
    for i,report in enumerate(structure):
        page=json.loads((out/(report['page_id']+'.json')).read_text())
        p=pdf[i]
        rendered=p.get_text()
        normalized=lambda s:re.sub(r'\s+','',s)
        for node in page['nodes']:
            values=[]
            if node['text']:
                values=[''.join(r['text'] for r in para['runs']) for para in node['text']['paragraphs']]
            if node['table']:
                values=[v for row in node['table']['rows'] for v in row]
            for value in values:
                if node['text']:
                    b=node['box'];scale=p.rect.width/page['width']
                    rect=fitz.Rect(b['x']*scale-4.5,b['y']*scale-4.5,(b['x']+b['w'])*scale+4.5,(b['y']+b['h'])*scale+4.5)
                    hits=p.search_for(value)
                    for hit in hits:
                        if not rect.contains(hit):
                            findings.append(dict(page=i+1,object=node['id'],issue='rendered text outside object box',text=value))
                if normalized(value) not in normalized(rendered):
                    findings.append(dict(page=i+1,object=node['id'],issue='rendered text missing',text=value))
        for word in p.get_text('words'):
            if word[0]<-.5 or word[1]<-.5 or word[2]>p.rect.width+.5 or word[3]>p.rect.height+.5:
                findings.append(dict(page=i+1,issue='rendered word outside page',text=word[4]))
        png=out/f'render-{i+1}.png'
        p.get_pixmap(matrix=fitz.Matrix(page['width']/p.rect.width,page['width']/p.rect.width)).save(png)
        previews.append(png.name)
        reference=out/f'reference-{i+1}.png'
        if reference.exists():
            a=Image.open(reference).convert('RGB').resize((int(page['width']),int(page['height'])))
            b=Image.open(png).convert('RGB')
            comparison=Image.new('RGB',(a.width+b.width+20,max(a.height,b.height)), 'white')
            comparison.paste(a,(0,0));comparison.paste(b,(a.width+20,0))
            comparison.save(out/f'comparison-{i+1}.png')
    (out/'render-report.json').write_text(json.dumps(dict(renderer='externally rendered PDF',pages=len(pdf),text_and_bounds_findings=findings,visual_review='required separately',client_operations='not tested'),ensure_ascii=False,indent=2))
    body='<meta charset="utf-8"><title>Semantic export review</title><style>body{font-family:system-ui;margin:24px;background:#eee}img{width:100%;margin-bottom:24px}section{background:white;padding:20px}</style><h1>语义导出阶段一验证</h1><p>结构、渲染与客户端操作为独立验收。左侧为原视觉稿，右侧为原生对象重构；背景简化已明确记录。</p>'
    for i,png in enumerate(previews,1):
        name=f'comparison-{i}.png' if (out/f'comparison-{i}.png').exists() else png
        body+=f'<section><h2>第 {i} 页</h2><img src="{html.escape(name)}"></section>'
    (out/'review.html').write_text(body)
    print(json.dumps(findings,ensure_ascii=False,indent=2))
    return findings


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path)
    raise SystemExit(bool(inspect(parser.parse_args().output)))

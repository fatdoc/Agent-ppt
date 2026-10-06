"""PPTist 82ecf1 adapter. Semantic Page is authoritative; editor JSON is disposable.

Unknown visual changes fail closed. Never trust client provenance or asset URLs.
"""
from copy import deepcopy
from html import escape
from html.parser import HTMLParser
import re
from services.semantic_export.model import Page, load_page, digest

PATHS = {
    'rect': 'M 0 0 L 100 0 L 100 100 L 0 100 Z',
    'roundRect': 'M 8 0 L 92 0 Q 100 0 100 8 L 100 92 Q 100 100 92 100 L 8 100 Q 0 100 0 92 L 0 8 Q 0 0 8 0 Z',
    'ellipse': 'M 0 50 A 50 50 0 1 0 100 50 A 50 50 0 1 0 0 50 Z',
    'rightArrow': 'M 0 25 L 60 25 L 60 0 L 100 50 L 60 100 L 60 75 L 0 75 Z',
}


def color(value):
    if not isinstance(value, str): raise ValueError('invalid color')
    if re.fullmatch(r'#[a-fA-F0-9]{6}', value): return value[1:].upper()
    rgb = re.fullmatch(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', value)
    if rgb and all(int(v) <= 255 for v in rgb.groups()): return ''.join(f'{int(v):02X}' for v in rgb.groups())
    raise ValueError('only opaque RGB colors supported')


def html_text(text):
    result = []
    for p in text.paragraphs:
        runs = []
        for r in p.runs:
            if not re.fullmatch(r'[\w ,\"\'-]{1,150}',r.font): raise ValueError('unsupported font name')
            style = f'font-size: {r.size}px; font-family: {r.font}; color: #{r.color}; font-weight: {"bold" if r.bold else "normal"}; font-style: {"italic" if r.italic else "normal"}'
            runs.append(f'<span style="{escape(style, quote=True)}">{escape(r.text).replace(chr(10), "<br>")}</span>')
        result.append(f'<p style="text-align: {p.align};">{"".join(runs)}</p>')
    return ''.join(result)


class SafeText(HTMLParser):
    """Parse only supported rich text. No arbitrary HTML survives into Page."""
    def __init__(self, defaults, line, space):
        super().__init__(convert_charrefs=True)
        self.defaults = defaults
        self.stack = []
        self.paragraphs = []
        self.current = None
        self.line, self.space = line, space

    def handle_starttag(self, tag, attrs):
        if tag not in ('p', 'span', 'strong', 'b', 'em', 'i', 'br'): raise ValueError('unsupported rich text tag: '+tag)
        if tag == 'br':
            self.handle_data('\n')
            return
        attrs = dict(attrs)
        if set(attrs)-{'style'}: raise ValueError('unsupported rich text attributes')
        style = dict(self.stack[-1][1] if self.stack else self.defaults)
        align = 'left'
        for item in attrs.get('style','').split(';'):
            if not item.strip(): continue
            if ':' not in item: raise ValueError('invalid rich text style')
            key, val = (v.strip() for v in item.split(':',1))
            if key == 'font-size' and re.fullmatch(r'[\d.]+px',val): style['size'] = float(val[:-2])
            elif key == 'font-family' and re.fullmatch(r'[\w ,"\'-]{1,150}',val): style['font'] = val.strip('"\'')
            elif key == 'color': style['color'] = color(val)
            elif key == 'font-weight' and val in ('bold','normal','400','700'): style['bold'] = val in ('bold','700')
            elif key == 'font-style' and val in ('italic','normal'): style['italic'] = val == 'italic'
            elif key == 'text-align' and val in ('left','center','right'): align = val
            else: raise ValueError('unsupported rich text style: '+key)
        if tag in ('strong','b'): style['bold'] = True
        if tag in ('em','i'): style['italic'] = True
        if tag == 'p':
            if self.current is not None: raise ValueError('nested paragraph')
            self.current = dict(runs=[],align=align,line_spacing=self.line,space_after=self.space)
        self.stack.append((tag,style))

    def handle_endtag(self, tag):
        if tag == 'br': return
        if not self.stack or self.stack[-1][0] != tag: raise ValueError('unbalanced rich text')
        if tag == 'p':
            if not self.current['runs']: self.current['runs'] = [dict(self.defaults,text='')]
            self.paragraphs.append(self.current)
            self.current = None
        self.stack.pop()

    def handle_data(self, data):
        if self.current is None:
            if data.strip(): raise ValueError('text outside paragraph')
            return
        run = dict(self.stack[-1][1] if self.stack else self.defaults, text=data)
        prior = self.current['runs'][-1] if self.current['runs'] else None
        if prior and {k:v for k,v in prior.items() if k!='text'} == {k:v for k,v in run.items() if k!='text'}: prior['text'] += data
        else: self.current['runs'].append(run)

    def handle_comment(self, data): raise ValueError('HTML comments unsupported')
    def handle_decl(self, decl): raise ValueError('HTML declarations unsupported')


def same_except(actual, expected, allowed):
    if {k:v for k,v in actual.items() if k not in allowed} != {k:v for k,v in expected.items() if k not in allowed}:
        raise ValueError('unsupported editor property changed; undo the operation')


class PPTistAdapter:
    def __init__(self, asset_url=None):
        # URL resolver must be constructed by authorized server code.
        self.asset_url = asset_url or (lambda a: f'/api/projects/{a.project_id}/editor-assets/{a.id}')

    def to_editor(self, page: Page) -> dict:
        if any(g.parent_id for g in page.groups): raise ValueError('nested groups are not editable in PPTist MVP')
        assets = {a.id:a for a in page.assets}
        elements = []
        for n in sorted(page.nodes,key=lambda n:n.layer):
            e = dict(id=n.id,name=n.name,left=n.box.x,top=n.box.y,width=n.box.w,height=n.box.h,rotate=n.rotation)
            if n.parent_id: e['groupId'] = n.parent_id
            if n.text:
                paragraphs = n.text.paragraphs
                if len({(p.line_spacing,p.space_after) for p in paragraphs}) > 1: raise ValueError('mixed paragraph spacing unsupported by PPTist')
                e.update(type='text',content=html_text(n.text),defaultFontName=paragraphs[0].runs[0].font,defaultColor='#'+paragraphs[0].runs[0].color,lineHeight=paragraphs[0].line_spacing,paragraphSpace=paragraphs[0].space_after,inset=[0,0,0,0],fixedHeight=True)
            elif n.shape:
                s = n.shape
                e.update(type='shape',path=PATHS[s.geometry],viewBox=[100,100],fixedRatio=False,fill='#'+s.fill,outline=dict(color='#'+(s.stroke or s.fill),width=s.stroke_width if s.stroke else 0,style='solid'))
            elif n.picture:
                p = n.picture
                e.update(type='image',src=self.asset_url(assets[p.asset_id]),fixedRatio=True,clip=dict(shape='rect',range=[[p.crop.left*100,p.crop.top*100],[(1-p.crop.right)*100,(1-p.crop.bottom)*100]]))
            elif n.table:
                t = n.table
                e.update(type='table',outline=dict(color='#FFFFFF',width=1,style='solid'),colWidths=[v/sum(t.column_weights) for v in t.column_weights],cellMinHeight=n.box.h/len(t.rows),data=[[dict(id=f'{n.id}_{ri}_{ci}',text=val,colspan=1,rowspan=1,style=dict(fontname=t.font,fontsize=t.size,color='#'+(t.header_color if ri==0 else t.text_color),backcolor='#'+(t.header_fill if ri==0 else t.body_fill))) for ci,val in enumerate(row)] for ri,row in enumerate(t.rows)])
            elements.append(e)
        return dict(id=page.id,background=dict(type='solid',color='#'+page.background),elements=elements)

    def from_editor(self, data: dict, *, base: Page) -> Page:
        if not isinstance(data,dict):raise ValueError('editor slide must be an object')
        expected = self.to_editor(base)
        same_except(data,expected,{'elements','background'})
        if set(data.get('background',{}))!={'type','color'} or data['background']['type']!='solid':raise ValueError('only solid page backgrounds supported')
        if not isinstance(data.get('elements'),list) or not 1 <= len(data['elements']) <= 1000: raise ValueError('invalid object count')
        old = {e['id']:e for e in expected['elements']}
        nodes = {n.id:n.model_dump(mode='json') for n in base.nodes}
        if any(not isinstance(e,dict) or not isinstance(e.get('id'),str) for e in data['elements']):raise ValueError('invalid editor object')
        ids = [e.get('id') for e in data['elements']]
        if len(ids)!=len(set(ids)): raise ValueError('duplicate object ID')
        if set(ids)-set(old): raise ValueError('new/copied objects need an explicit semantic origin; unsupported in this batch')
        result = base.model_dump(mode='json')
        result['background']=color(data['background']['color'])
        result['nodes'] = []
        for index,e in enumerate(data['elements']):
            n = deepcopy(nodes[e['id']])
            original = old[e['id']]
            mutable = {'left','top','width','height','rotate','groupId'}
            if n['kind']=='text': mutable |= {'content','lineHeight','paragraphSpace'}
            if n['kind']=='shape': mutable |= {'fill','outline'}
            if n['kind'] in ('image','svg'): mutable |= {'clip','src'}
            if n['kind']=='table': mutable |= {'data','colWidths','cellMinHeight'}
            same_except(e,original,mutable)
            n['box'] = dict(x=e['left'],y=e['top'],w=e['width'],h=e['height'])
            n['rotation'] = e['rotate']
            # Retain exact layer values unless ordering/deletion changed.
            if ids != [v['id'] for v in expected['elements']]: n['layer']=index
            n['parent_id'] = e.get('groupId')
            if n['text'] and any(e.get(k)!=original.get(k) for k in ('content','lineHeight','paragraphSpace')):
                defaults = deepcopy(n['text']['paragraphs'][0]['runs'][0]); defaults.pop('text')
                parser = SafeText(defaults,e['lineHeight'],e['paragraphSpace'])
                parser.feed(e['content']); parser.close()
                if parser.stack or not parser.paragraphs: raise ValueError('incomplete rich text')
                baseline_parser=SafeText(defaults,original['lineHeight'],original['paragraphSpace'])
                baseline_parser.feed(original['content']);baseline_parser.close()
                if parser.paragraphs != baseline_parser.paragraphs:
                    n['text']['paragraphs'] = parser.paragraphs
            if n['shape']:
                n['shape']['fill']=color(e['fill'])
                outline=e['outline']
                if set(outline)!={'color','width','style'} or outline['style']!='solid': raise ValueError('unsupported outline')
                if outline != original['outline']:
                    n['shape'].update(stroke=color(outline['color']),stroke_width=outline['width'])
            if n['picture']:
                if e['src'] != original['src']:
                    matches=[a for a in base.assets if self.asset_url(a)==e['src']]
                    if len(matches)!=1 or n['kind']=='svg' or matches[0].media_type=='image/svg+xml': raise ValueError('replacement must be an authorized raster asset')
                    n['picture']['asset_id']=matches[0].id
                if e['clip'] != original['clip']:
                    if set(e['clip'])!={'range','shape'} or e['clip']['shape']!='rect': raise ValueError('rectangular crop required')
                    (l,t),(r,b)=e['clip']['range']
                    n['picture']['crop']=dict(left=l/100,top=t/100,right=1-r/100,bottom=1-b/100)
            if n['table']:
                rows=e['data']
                if e['cellMinHeight']!=original['cellMinHeight'] and abs(e['cellMinHeight']*len(rows)-e['height'])>.01:raise ValueError('independent row heights unsupported')
                if len(rows)!=len(original['data']) or any(len(r)!=len(original['data'][0]) for r in rows): raise ValueError('table row/column insertion unsupported')
                for ri,row in enumerate(rows):
                    for ci,cell in enumerate(row): same_except(cell,original['data'][ri][ci],{'text'})
                n['table']['rows']=[[c['text'] for c in row] for row in rows]
                if e['colWidths']!=original['colWidths']: n['table']['column_weights']=e['colWidths']
            result['nodes'].append(n)
        # Reuse existing group metadata, allow ungroup and new identity groups only
        # within one semantic module, never invent cross-module ownership.
        used={n['parent_id'] for n in result['nodes'] if n['parent_id']}
        result['groups']=[g for g in result['groups'] if g['id'] in used]
        known={g['id'] for g in result['groups']}
        for gid in used-known:
            modules={n['module_id'] for n in result['nodes'] if n['parent_id']==gid}
            if len(modules)!=1: raise ValueError('group crosses semantic modules')
            result['groups'].append(dict(id=gid,name='编辑组合',module_id=modules.pop(),parent_id=None))
        page=load_page(result)
        # Preserve original ordering in a no-op roundtrip (schema nodes need not be sorted).
        if data==expected: return base.model_copy(deep=True)
        return page

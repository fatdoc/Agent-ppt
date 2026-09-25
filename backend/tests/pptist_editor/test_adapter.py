import copy
import pytest
from services.pptist_editor.adapter import PPTistAdapter
from scripts.semantic_export.sample import samples

@pytest.fixture
def data(tmp_path):
    return PPTistAdapter(), samples(tmp_path)

def test_exact_roundtrip(data):
    adapter,pages=data
    for page in pages:
        assert adapter.from_editor(adapter.to_editor(page),base=page)==page

def test_text_geometry_and_metadata(data):
    a,pages=data; p=pages[0]; e=a.to_editor(p)
    e['elements'][0]['content']=e['elements'][0]['content'].replace('语义导出验证','中文修改验证')
    e['elements'][0]['top']+=1
    result=a.from_editor(e,base=p)
    assert result.nodes[0].text.paragraphs[0].runs[0].text.startswith('中文修改验证')
    assert result.source==p.source and result.assets==p.assets
    assert result.nodes[0].provenance==p.nodes[0].provenance

@pytest.mark.parametrize('html',[
    '<p><img src=x onerror=alert(1)></p>', '<p onclick="x()">a</p>',
    '<p><span style="background:url(https://evil)">a</span></p>',
    '<p><script>alert(1)</script></p>', '<p><a href="javascript:x()">a</a></p>',
    '<p><span style="font-family:a;position:fixed">x</span></p>',
])
def test_rich_text_rejects_active_or_lossy_html(data,html):
    a,pages=data; p=pages[0]; e=a.to_editor(p); e['elements'][0]['content']=html
    with pytest.raises(ValueError): a.from_editor(e,base=p)

@pytest.mark.parametrize('field,value',[('shadow',{'blur':4}),('link',{'target':'https://evil'}),('type','video')])
def test_unsupported_changes(data,field,value):
    a,pages=data; p=pages[0]; e=a.to_editor(p); e['elements'][0][field]=value
    with pytest.raises(ValueError): a.from_editor(e,base=p)

def test_table_edit_and_merge_rejected(data):
    a,pages=data; p=pages[1]; e=a.to_editor(p)
    e['elements'][2]['data'][1][2]['text']='已验证'
    assert a.from_editor(e,base=p).nodes[2].table.rows[1][2]=='已验证'
    e['elements'][2]['data'][1][2]['colspan']=2
    with pytest.raises(ValueError): a.from_editor(e,base=p)

def test_screenshot_crop_and_external_image_rejected(data):
    a,pages=data; p=pages[0]; e=a.to_editor(p)
    e['elements'][4]['clip']['range'][0][0]=10
    with pytest.raises(ValueError): a.from_editor(e,base=p)
    e=a.to_editor(p);e['elements'][4]['src']='https://evil/image.png'
    with pytest.raises(ValueError): a.from_editor(e,base=p)

def test_duplicate_copy_delete_and_ungroup(data):
    a,pages=data; p=pages[0]; e=a.to_editor(p)
    e['elements'].append(copy.deepcopy(e['elements'][0]))
    with pytest.raises(ValueError): a.from_editor(e,base=p)
    e['elements'][-1]['id']='new'
    with pytest.raises(ValueError): a.from_editor(e,base=p)
    e=a.to_editor(p);e['elements'].pop()
    assert len(a.from_editor(e,base=p).nodes)==5
    e=a.to_editor(p)
    for obj in e['elements']: obj.pop('groupId',None)
    assert not a.from_editor(e,base=p).groups

def test_nested_group_rejected_without_flattening(data):
    from services.semantic_export.model import load_page
    a,pages=data;raw=pages[0].model_dump(mode='json')
    raw['groups'].append(dict(id='inner',name='inner',module_id='content',parent_id='content-group'))
    raw['nodes'][2]['parent_id']='inner'
    p=load_page(raw)
    with pytest.raises(ValueError,match='nested groups'):a.to_editor(p)
    assert p.nodes[2].parent_id=='inner'

def test_font_style_injection_rejected_and_soft_break_preserved(data):
    from services.semantic_export.model import load_page
    a,pages=data;p=pages[0];e=a.to_editor(p)
    assert '<br>' in e['elements'][3]['content']
    assert a.from_editor(e,base=p).nodes[3].text==p.nodes[3].text
    raw=p.model_dump(mode='json');raw['nodes'][0]['text']['paragraphs'][0]['runs'][0]['font']='x; position:fixed'
    with pytest.raises(ValueError,match='font'):a.to_editor(load_page(raw))

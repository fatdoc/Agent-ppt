import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image
from services.pptist_editor.recognition import parse_response, normalize_plan, RecognitionError
from services.pptist_editor.generation import validate_response, GenerationError


def minimal():
    return {'background':'FFFFFF','groups':[], 'nodes':[dict(
        id='body',name='正文',kind='text',module_id='body',layer=0,
        box=dict(x=20,y=20,w=300,h=100),
        text=dict(paragraphs=[dict(runs=[dict(text='逐字保留\n第二行',color='203040')])]))]}


@pytest.mark.parametrize('raw', ['not JSON', '{"nodes":', '{"a":1,"a":2}', '{"x":NaN}', '```json\n{}\n``` trailing', '[]'])
def test_malformed_response_rejected_without_guessing(raw):
    with pytest.raises(RecognitionError):normalize_plan(parse_response(raw))


def test_normalization_does_not_mutate_input_or_drop_unknown_fields():
    value=minimal();original=copy.deepcopy(value)
    result,_=normalize_plan(value)
    assert value==original and result==original
    value['nodes'][0]['box']['width']=999
    with pytest.raises(RecognitionError,match='冲突'):normalize_plan(value)
    value=minimal();value['nodes'][0]['untrusted_path']='../../secret'
    result,_=normalize_plan(value)
    assert result['nodes'][0]['untrusted_path']=='../../secret' # Must be rejected, never silently discarded.


@pytest.mark.parametrize('case', ['outside','rgba','unknown','duplicate_layer','broken_group','fullpage','overlap','nested'])
def test_safety_and_visual_constraints_still_fail(case,tmp_path):
    plan=minimal();node=plan['nodes'][0]
    if case=='outside':node['box']['x']=790
    elif case=='rgba':plan['background']='rgba(255,255,255,0.3)'
    elif case=='unknown':node['external_url']='https://invalid.test/image.png'
    elif case=='duplicate_layer':
        extra=copy.deepcopy(node);extra['id']='other';plan['nodes'].append(extra)
    elif case=='broken_group':node['parent_id']='missing'
    elif case=='nested':
        plan['groups']=[dict(id='outer',name='outer',module_id='body'),dict(id='inner',name='inner',module_id='body',parent_id='outer')]
        node['parent_id']='inner'
    else:
        box=dict(x=0,y=0,w=800,h=450) if case=='fullpage' else dict(x=20,y=20,w=300,h=100)
        plan['nodes'].append(dict(id='pic',name='截图',kind='image',module_id='pic',layer=1,box=box,picture=dict(role='screenshot')))
    with Image.new('RGB',(800,450),'white') as image:
        with pytest.raises(GenerationError):
            validate_response(json.dumps(plan),image,source={'id':'page','sha256':'a'*64},project_id='project',user_id='user',root=tmp_path)


def test_offline_single_page_replay_builds_native_pptx_without_app(tmp_path):
    image=tmp_path/'page.png';Image.new('RGB',(800,450),'white').save(image)
    response=tmp_path/'response.json';response.write_text(json.dumps(minimal()))
    root=Path(__file__).resolve().parents[3]
    output=tmp_path/'result'
    env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':str(tmp_path),'LOAD_DOTENV':'false'}
    result=subprocess.run([sys.executable,str(root/'scripts/validate_editor_page.py'),'--image',str(image),'--response',str(response),'--output',str(output)],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads((output/'result.json').read_text())['provider_calls']==0
    assert (output/'page.pptx').is_file()
    again=subprocess.run([sys.executable,str(root/'scripts/validate_editor_page.py'),'--image',str(image),'--response',str(response),'--output',str(output)],env=env,capture_output=True,text=True)
    assert again.returncode!=0 # Never overwrite an operator's existing artifacts.

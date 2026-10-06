"""Build explicitly manual dev fixture assets. Output is ignored by Git."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backend'))
from scripts.semantic_export.sample import samples
from services.pptist_editor.adapter import PPTistAdapter
out=ROOT/'frontend/public/editor-fixture';out.mkdir(parents=True,exist_ok=True)
pages=samples(out)
a=PPTistAdapter(lambda asset:'/editor-fixture/'+asset.uri)
(out/'document.json').write_text(json.dumps(dict(revision=0,fixture=True,width=pages[0].width,height=pages[0].height,slides=[a.to_editor(p) for p in pages]),ensure_ascii=False))
print(out)

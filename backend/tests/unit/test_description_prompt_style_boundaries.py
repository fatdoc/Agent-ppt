from types import SimpleNamespace

from services.prompts import get_all_descriptions_stream_prompt, get_page_description_prompt


def _context():
    return SimpleNamespace(
        idea_prompt=None,
        outline_text="第一页：封面\n第二页：方案",
        description_text=None,
        creation_type="outline",
        description_requirements=None,
        reference_files_content=[],
    )


def test_page_description_prompt_keeps_global_style_out_of_descriptions():
    prompt = get_page_description_prompt(
        project_context=_context(),
        outline=[{"title": "封面", "points": ["主题"]}],
        page_outline={"title": "封面", "points": ["主题"]},
        page_index=1,
        language="zh",
    )

    assert "内容、信息层级、布局、图表、素材" in prompt
    assert "不要在页面描述中重新指定整体配色、视觉风格、材质风格" in prompt
    assert "单页特殊风格" in prompt


def test_stream_description_prompt_keeps_global_style_out_of_descriptions():
    prompt = get_all_descriptions_stream_prompt(
        project_context=_context(),
        outline=[{"title": "封面", "points": ["主题"]}],
        flat_pages=[{"title": "封面", "points": ["主题"]}],
        language="zh",
    )

    assert "内容、信息层级、布局、图表、素材" in prompt
    assert "不要在页面描述中重新指定整体配色、视觉风格、材质风格" in prompt
    assert "单页特殊风格" in prompt

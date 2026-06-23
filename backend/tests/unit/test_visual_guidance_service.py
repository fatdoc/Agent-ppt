"""Tests for visual guidance priority and style override rules."""
from types import SimpleNamespace


def test_template_first_keeps_global_style_over_page_style():
    from services.visual_guidance_service import VisualGuidanceService

    project = SimpleNamespace(
        template_style="黑白极简商务风",
        extra_requirements="使用公司标准页脚",
    )
    service = VisualGuidanceService()

    guidance = service.build_visual_guidance(
        project=project,
        page_desc="页面使用粉色渐变、可爱插画、活泼风格。",
        has_template_image=True,
        has_blueprint_page=False,
    )

    assert guidance["style_priority"] == "template_first"
    assert "单张风格模板图" in guidance["global_visual_system"]
    assert "黑白极简商务风" in guidance["global_visual_system"]
    assert "页面描述中的普通风格词" not in guidance["global_visual_system"]


def test_explicit_page_override_keyword_allows_override():
    from services.visual_guidance_service import VisualGuidanceService

    project = SimpleNamespace(template_style="黑白极简商务风", extra_requirements=None)
    service = VisualGuidanceService()

    guidance = service.build_visual_guidance(
        project=project,
        page_desc="本页特殊风格：使用粉色渐变和可爱插画。",
        has_template_image=True,
        has_blueprint_page=False,
    )

    assert guidance["style_priority"] == "template_first"
    assert "本页特殊风格" in guidance["page_visual_notes"]


def test_blueprint_priority_beats_template_style():
    from services.visual_guidance_service import VisualGuidanceService

    project = SimpleNamespace(template_style="浅色手绘风", extra_requirements="减少文字")
    service = VisualGuidanceService()

    guidance = service.build_visual_guidance(
        project=project,
        page_desc="页面描述要求使用橙色复古风。",
        has_template_image=True,
        has_blueprint_page=True,
    )

    assert guidance["style_priority"] == "blueprint_first"
    assert guidance["reference_images"]["blueprint_layout_reference"] == "primary"
    assert guidance["reference_images"]["style_reference"] == "supplemental"
    assert "PPT 蓝图对应页截图" in guidance["global_visual_system"]

"""Test that image generation prompt uses the correct aspect ratio."""
from services.prompts import get_image_generation_prompt


class TestImagePromptAspectRatio:
    def test_default_ratio_is_16_9(self):
        prompt = get_image_generation_prompt(
            page_desc="Test page",
            outline_text="Test outline",
            current_section="Section 1",
        )
        assert "16:9比例" in prompt

    def test_custom_ratio_4_3(self):
        prompt = get_image_generation_prompt(
            page_desc="Test page",
            outline_text="Test outline",
            current_section="Section 1",
            aspect_ratio="4:3",
        )
        assert "4:3比例" in prompt
        assert "16:9比例" not in prompt

    def test_custom_ratio_1_1(self):
        prompt = get_image_generation_prompt(
            page_desc="Test page",
            outline_text="Test outline",
            current_section="Section 1",
            aspect_ratio="1:1",
        )
        assert "1:1比例" in prompt
        assert "16:9比例" not in prompt

    def test_visual_guidance_uses_layered_prompt_blocks(self):
        prompt = get_image_generation_prompt(
            page_desc="页面内容",
            outline_text="Test outline",
            current_section="Section 1",
            visual_guidance={
                "global_visual_system": "全局视觉系统",
                "page_visual_notes": "页面局部视觉说明",
            },
        )

        assert "<global_visual_system>" in prompt
        assert "全局视觉系统" in prompt
        assert "<page_content>" in prompt
        assert "页面内容" in prompt
        assert "<page_layout_notes>" in prompt
        assert "页面局部视觉说明" in prompt
        assert "<style_conflict_rule>" not in prompt
        assert "页面描述中的普通风格词" not in prompt

    def test_image_prompt_prefers_sparse_slide_text_over_rendering_every_word(self):
        prompt = get_image_generation_prompt(
            page_desc="页面标题：闭环自动调控。页面要点：采集、判断、控制。",
            outline_text="Test outline",
            current_section="Section 1",
        )

        assert "不重不漏" not in prompt
        assert "只呈现演示所需的核心文字" in prompt
        assert "不得把提示词中的页面角色" in prompt

"""Visual guidance for image generation."""
from __future__ import annotations


class VisualGuidanceService:
    """Build structured visual guidance for PPT page image prompts."""

    def build_visual_guidance(
        self,
        project,
        page_desc: str,
        has_template_image: bool,
        has_blueprint_page: bool,
        style_policy: str = "template_first",
    ) -> dict:
        template_style = (getattr(project, "template_style", None) or "").strip()
        extra_requirements = (getattr(project, "extra_requirements", None) or "").strip()

        if has_blueprint_page:
            style_priority = "blueprint_first"
            global_visual_parts = [
                "PPT 蓝图对应页截图是最高优先级的结构、版式、信息密度和页面级风格参考。",
                "借用蓝图的页面角色、布局节奏和视觉系统，但禁止复用蓝图中的具体文字、数字、品牌或案例。",
            ]
            if has_template_image:
                global_visual_parts.append("单张风格模板图只能作为补充，不能覆盖 PPT 蓝图结构。")
            reference_images = {
                "blueprint_layout_reference": "primary",
                "style_reference": "supplemental" if has_template_image else None,
                "material_references": [],
            }
        elif has_template_image:
            style_priority = "template_first"
            global_visual_parts = [
                "单张风格模板图是全局风格参考。",
                "请保持模板图的色彩体系、设计语言、字体气质和整体视觉秩序。",
            ]
            reference_images = {
                "blueprint_layout_reference": None,
                "style_reference": "primary",
                "material_references": [],
            }
        elif template_style:
            style_priority = "template_first"
            global_visual_parts = [
                "项目级 template_style 是全局视觉系统。",
            ]
            reference_images = {
                "blueprint_layout_reference": None,
                "style_reference": "text",
                "material_references": [],
            }
        else:
            style_priority = "page_first"
            global_visual_parts = [
                "没有模板图或项目级风格描述，本页页面描述可决定主要视觉风格。",
            ]
            reference_images = {
                "blueprint_layout_reference": None,
                "style_reference": None,
                "material_references": [],
            }

        if template_style:
            global_visual_parts.append(f"项目级风格描述：{template_style}")
        if extra_requirements:
            global_visual_parts.append(f"用户额外要求：{extra_requirements}")

        return {
            "global_visual_system": "\n".join(global_visual_parts),
            "page_visual_notes": page_desc or "",
            "reference_images": reference_images,
            "style_priority": style_priority,
        }

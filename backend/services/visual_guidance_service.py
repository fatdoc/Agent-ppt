"""Visual guidance for image generation."""
from __future__ import annotations


class VisualGuidanceService:
    """Build structured visual guidance for PPT page image prompts."""

    _COMPETITION_NAMES = {
        "wvcc": "世界职业院校技能大赛",
        "challenge-cup": "挑战杯",
        "innovation-competition": "中国国际大学生创新大赛",
        "career-planning": "全国大学生职业规划大赛",
        "teaching-ability": "职业院校技能大赛教学能力比赛",
        "custom": "自定义赛事",
    }
    _TRACK_NAMES = {
        "electronic-information": "电子信息",
        "equipment-manufacturing": "装备制造",
        "agriculture": "农林牧渔",
        "healthcare": "医药卫生",
        "eldercare": "康养服务",
        "modern-agriculture": "现代农业",
        "ai-application": "人工智能应用",
        "other": "其他",
        "custom": "自定义赛道",
    }
    _THEME_NAMES = {
        "smart-manufacturing": "智能制造与产业升级",
        "smart-agriculture": "智慧农业与乡村振兴",
        "smart-eldercare": "智慧养老与健康服务",
        "ai-industry": "人工智能赋能产业应用",
        "custom": "自定义主题",
    }

    def build_asset_context(
        self,
        project,
        *,
        section: str = "",
        page_purpose: str = "",
        image_usage: str = "PPT 页面视觉素材",
    ) -> str:
        """Build trusted project context shared by page and standalone material generation."""
        context = project.get_platform_context() if project and hasattr(project, "get_platform_context") else {}
        context = context if isinstance(context, dict) else {}
        competition_id = context.get("competitionId")
        track_id = context.get("trackId")
        theme_id = context.get("themeId")
        custom_theme = context.get("customTheme")
        style = context.get("style") or (getattr(project, "template_style", None) if project else None)
        parts = [
            f"赛事：{self._COMPETITION_NAMES.get(competition_id, competition_id or '通用项目')}",
            f"赛道：{self._TRACK_NAMES.get(track_id, track_id or '未指定')}",
            f"大赛主题：{custom_theme or self._THEME_NAMES.get(theme_id, theme_id or '未指定')}",
            f"当前章节：{section or context.get('currentSectionId') or '未指定'}",
            f"当前页面目的：{page_purpose or '服务当前页面信息表达'}",
            f"视觉风格：{style or '遵循项目统一视觉系统'}",
            f"图片用途：{image_usage}",
        ]
        if competition_id == "wvcc":
            parts.append("评分语境：技能水平、职业素养、应用价值、团队合作、创新创意；只呈现有项目材料支撑的证据。")
        return "\n".join(parts)

    def build_visual_guidance(
        self,
        project,
        page_desc: str,
        has_template_image: bool,
        has_blueprint_page: bool,
        style_policy: str = "template_first",
        page_data: dict | None = None,
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
        page_data = page_data or {}
        page_title = page_data.get("title") or ""
        global_visual_parts.append(
            "项目业务上下文（生成内容必须与这些字段一致）：\n"
            + self.build_asset_context(
                project,
                section=page_data.get("part") or "",
                page_purpose=page_data.get("purpose") or page_title,
                image_usage="当前 PPT 页的主视觉、图表或项目证据配图",
            )
        )

        return {
            "global_visual_system": "\n".join(global_visual_parts),
            "page_visual_notes": page_desc or "",
            "reference_images": reference_images,
            "style_priority": style_priority,
        }

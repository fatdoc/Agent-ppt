"""Visual guidance for image generation."""
from __future__ import annotations

import json

from models import PageVisualPlan


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
        visual_strategy = (getattr(project, "visual_strategy", None) or "native").strip()
        if visual_strategy == "external_skill":
            return self._build_external_skill_guidance(project, page_desc)

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

        guidance = {
            "global_visual_system": "\n".join(global_visual_parts),
            "page_visual_notes": page_desc or "",
            "reference_images": reference_images,
            "style_priority": style_priority,
        }
        return self._with_harness_generation_guidance(project, page_desc, guidance)

    def _build_external_skill_guidance(self, project, page_desc: str) -> dict:
        skill_id = (getattr(project, "external_style_skill_id", None) or "").strip()
        payload = self._get_external_style_payload(project)
        extra_requirements = (getattr(project, "extra_requirements", None) or "").strip()

        global_visual_parts = [
            "外部风格 Skill 是唯一的全局视觉系统。",
            "忽略项目原有模板图、template_style、PPT 蓝图风格和页面描述中的全局风格词；页面描述仅用于内容、信息层级、布局和素材需求。",
        ]
        if skill_id:
            global_visual_parts.append(f"外部风格 Skill ID：{skill_id}")
        payload_text = self._format_external_payload(payload)
        if payload_text:
            global_visual_parts.append(f"外部风格 Skill 输出：\n{payload_text}")
        if extra_requirements:
            global_visual_parts.append(f"用户额外要求（非风格类内容仍需遵循）：{extra_requirements}")

        return {
            "global_visual_system": "\n".join(global_visual_parts),
            "page_visual_notes": page_desc or "",
            "reference_images": {
                "blueprint_layout_reference": None,
                "style_reference": "external_skill",
                "material_references": [],
            },
            "style_priority": "external_skill_first",
        }

    def _with_harness_generation_guidance(self, project, page_desc: str, guidance: dict) -> dict:
        generation_mode = (getattr(project, "generation_mode", None) or "fast").strip()
        harness_template = (getattr(project, "harness_template", None) or "").strip()
        if generation_mode != "harness" or harness_template != "paper_operators":
            return guidance

        visual_plan = self._find_visual_plan_for_page(project, page_desc)
        global_visual_parts = [guidance.get("global_visual_system", "")]
        global_visual_parts.append(
            "Harness 模板 paper-operators 只作为生成流程和页面组织参考，不覆盖模板图、文字风格、PPT 蓝图或用户指定的视觉方案。"
        )
        if visual_plan:
            plan = visual_plan.get_plan()
            global_visual_parts.append("当前页 Harness PageVisualPlan（用于信息组织、构图校验和可读性约束）：")
            global_visual_parts.append(json.dumps(plan, ensure_ascii=False, indent=2))
            if plan.get("visual_prompt"):
                global_visual_parts.append(f"当前页 Harness 生成建议：\n{plan['visual_prompt']}")
        else:
            global_visual_parts.append(
                "未找到当前页 PageVisualPlan 时，仅按 paper-operators 的流程思想检查页面：先明确读者收获，再确定信息层级、构图、标签和可读性。不要强制加入纸片人或固定画风。"
            )

        next_guidance = dict(guidance)
        next_guidance["global_visual_system"] = "\n".join(part for part in global_visual_parts if part)
        return next_guidance

    def _find_visual_plan_for_page(self, project, page_desc: str):
        for page in getattr(project, "pages", []) or []:
            desc = page.get_description_content() or {}
            desc_text = desc.get("text", "") if isinstance(desc, dict) else ""
            if desc_text and desc_text in page_desc:
                return (
                    PageVisualPlan.query
                    .filter_by(project_id=project.id, page_id=page.id)
                    .order_by(PageVisualPlan.version_number.desc(), PageVisualPlan.updated_at.desc())
                    .first()
                )
        return None

    def _get_external_style_payload(self, project):
        getter = getattr(project, "get_external_style_payload", None)
        if callable(getter):
            return getter()
        payload = getattr(project, "external_style_payload", None)
        if not payload:
            return None
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return payload
        return payload

    def _format_external_payload(self, payload) -> str:
        if payload is None:
            return ""
        if isinstance(payload, str):
            return payload.strip()
        if isinstance(payload, dict):
            preferred_keys = (
                "global_visual_system",
                "visual_system",
                "style_prompt",
                "prompt",
                "description",
            )
            parts = []
            for key in preferred_keys:
                value = payload.get(key)
                if value:
                    parts.append(str(value).strip())
            remaining = {
                key: value
                for key, value in payload.items()
                if key not in preferred_keys and value not in (None, "", [], {})
            }
            if remaining:
                parts.append(json.dumps(remaining, ensure_ascii=False, indent=2))
            return "\n".join(part for part in parts if part)
        return json.dumps(payload, ensure_ascii=False, indent=2)

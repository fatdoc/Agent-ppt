"""Visual guidance for image generation."""
from __future__ import annotations

import json

from models import PageVisualPlan
from services.harness_generation_service import get_project_scenario_pack
from services.harness_skills import GENERIC_FORBIDDEN_PATTERNS, IMAGE_QUALITY_CONSTRAINTS


_PAGE_VISUAL_OVERRIDE_MARKERS = ("本页特殊风格", "本页风格覆写", "本页视觉覆写")


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
            guidance = self._build_external_skill_guidance(project, page_desc)
            return self._with_harness_generation_guidance(
                project,
                page_desc,
                guidance,
                visual_overridden=True,
                override_source="外部风格 Skill",
            )

        template_style = (getattr(project, "template_style", None) or "").strip()
        extra_requirements = (getattr(project, "extra_requirements", None) or "").strip()
        harness_pack = get_project_scenario_pack(project)

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
        elif harness_pack is not None:
            style_priority = "harness_pack_first"
            global_visual_parts = [
                f"用户未指定模板图或风格描述，Harness 场景包「{harness_pack.name}」的默认视觉系统是全局视觉参考。",
            ]
            reference_images = {
                "blueprint_layout_reference": None,
                "style_reference": "harness_pack",
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
            "page_visual_notes": self._page_visual_notes(page_desc),
            "reference_images": reference_images,
            "style_priority": style_priority,
        }

        visual_overridden = bool(has_template_image or has_blueprint_page)
        override_source = None
        if has_blueprint_page:
            override_source = "PPT 蓝图"
        elif has_template_image:
            override_source = "用户模板图"
        return self._with_harness_generation_guidance(
            project,
            page_desc,
            guidance,
            visual_overridden=visual_overridden,
            override_source=override_source,
            user_style_text=template_style,
        )

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
            "page_visual_notes": self._page_visual_notes(page_desc),
            "reference_images": {
                "blueprint_layout_reference": None,
                "style_reference": "external_skill",
                "material_references": [],
            },
            "style_priority": "external_skill_first",
        }

    def _with_harness_generation_guidance(
        self,
        project,
        page_desc: str,
        guidance: dict,
        *,
        visual_overridden: bool = False,
        override_source: str | None = None,
        user_style_text: str = "",
    ) -> dict:
        """Inject Harness scenario pack guidance.

        结构层（页面角色、构图骨架、标签、可读性）对所有视觉来源注入；
        默认视觉层只在用户未显式指定视觉来源时注入；
        用户给出任何风格文字时，场景包默认视觉完整退位，不做风格混合；
        质量约束对所有 Harness 项目无条件注入。
        """
        pack = get_project_scenario_pack(project)
        if pack is None:
            return guidance

        global_visual_parts = [guidance.get("global_visual_system", "")]
        global_visual_parts.append(
            f"Harness 场景包「{pack.name}」提供页面组织、构图骨架和可读性校验，对任何视觉来源都必须生效。"
        )

        style_replaced = visual_overridden or bool(user_style_text)
        if style_replaced:
            source = override_source or ("用户风格描述" if user_style_text else "用户指定的视觉来源")
            global_visual_parts.append(
                f"视觉层以{source}为准，场景包默认视觉整体退位且禁止混合；只保留下述结构性指导。"
            )

        visual_plan = self._find_visual_plan_for_page(project, page_desc)
        if visual_plan:
            plan = visual_plan.get_plan()
            structure_view = self._structure_view(
                plan,
                include_pack_negatives=not style_replaced,
                pack_id=pack.pack_id,
                page_desc=page_desc,
            )
            global_visual_parts.append("当前页 Harness 结构计划（信息组织、构图骨架和可读性约束）：")
            global_visual_parts.append(json.dumps(structure_view, ensure_ascii=False, indent=2))
            structure_prompt = plan.get("structure_prompt") or ""
            style_prompt = plan.get("style_prompt") or ""
            if not structure_prompt and not style_prompt:
                # 旧版计划只有合并的 visual_prompt；无覆写时按原行为整体注入。
                if not style_replaced and plan.get("visual_prompt"):
                    global_visual_parts.append(f"当前页 Harness 生成建议：\n{plan['visual_prompt']}")
            else:
                if structure_prompt:
                    global_visual_parts.append(f"当前页结构指令：\n{structure_prompt}")
                if style_prompt and not style_replaced:
                    global_visual_parts.append(f"当前页默认视觉指令：\n{style_prompt}")
            if plan.get("material_status") == "concept_placeholder":
                global_visual_parts.append(
                    "本页产品图为 AI 概念渲染占位：保持中性概念形态，禁止真实品牌名、logo 或可误认为实拍的标注。"
                )
        else:
            global_visual_parts.append(
                "未找到当前页结构计划时，仍按场景包的流程思想检查页面：先明确读者收获，再确定信息层级、构图、标签和可读性。"
            )

        global_visual_parts.append("成图质量硬约束（必须全部满足）：")
        global_visual_parts.extend(f"- {item}" for item in IMAGE_QUALITY_CONSTRAINTS)

        next_guidance = dict(guidance)
        next_guidance["global_visual_system"] = "\n".join(part for part in global_visual_parts if part)
        return next_guidance

    @staticmethod
    def _structure_view(
        plan: dict,
        *,
        include_pack_negatives: bool,
        pack_id: str | None = None,
        page_desc: str = "",
    ) -> dict:
        structure_keys = (
            "page_role",
            "page_role_name",
            "asset_role",
            "asset_role_name",
            "relationship_type",
            "relationship_type_name",
            "composition_mode",
            "composition_mode_name",
            "source_anchor",
            "reader_takeaway",
            "composition",
            "labels",
            "truth_constraints",
            "data_contract",
            "throughline",
            "variation_axes",
            "material_status",
            "operator_required",
            "operator_family",
            "scoring_dimension",
            "member_index",
            "member_role",
            "skill_point_index",
            "metaphor_world",
        )
        view = {key: plan[key] for key in structure_keys if plan.get(key) not in (None, "", [])}
        negatives = plan.get("negative_prompts") or []
        if not include_pack_negatives:
            # 视觉被覆写时，只保留与画风无关的通用负面约束，避免与用户视觉冲突。
            negatives = [item for item in negatives if item in GENERIC_FORBIDDEN_PATTERNS]
        if negatives:
            view["negative_prompts"] = negatives
        return view

    @staticmethod
    def _page_visual_notes(page_desc: str) -> str:
        """Avoid duplicating all page content into the layout-notes block.

        Only an explicit page-level visual override belongs here; normal page text
        already appears once in <page_content>.
        """
        text = (page_desc or "").strip()
        if any(marker in text for marker in _PAGE_VISUAL_OVERRIDE_MARKERS):
            return text
        return ""

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

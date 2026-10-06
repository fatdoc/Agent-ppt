"""Harness scenario pack framework.

产品层：一个场景包（ScenarioPack）默认绑定「结构 Skill + 默认视觉 Skill」。
架构层：两层解耦——
- StructureSkill 负责页面角色、叙事组织、构图骨架、素材策略和校验规则，
  对任何视觉来源（默认视觉 / 模板图 / 风格文字 / 外部风格 Skill）都必须生效；
- VisualStyleSkill 负责色板、材质、画风、字体气质和装饰语言，
  仅在用户未显式指定视觉来源时作为默认视觉系统生效。
"""
from __future__ import annotations

import os
from typing import Any

# Harness / Agent 模式页数上限，仅作防滥用安全阀，默认 80。
HARNESS_MAX_PAGE_COUNT = max(1, int(os.getenv("HARNESS_MAX_PAGE_COUNT", "80")))


# 成图质量硬约束：对所有场景包、所有视觉来源统一注入，属于交付底线而非风格。
IMAGE_QUALITY_CONSTRAINTS = [
    "成品必须是可直接交付的 4K 高分辨率 PPT 页面：边缘锐利、无噪点、无模糊区域、无压缩伪影、无低分辨率拉伸感。",
    "画面中的所有文字必须真实可读、笔画完整、拼写正确；禁止乱码、伪文字、含混笔画和扭曲字形；无法保证可读的文字宁可不画。",
    "构图保留安全边距，任何文字和关键元素不得贴边或被裁切；留白克制而有秩序。",
    "全画面光影方向一致、阴影自然；色彩严格遵循声明的色板，禁止脏色、偏色和无意义的过饱和。",
    "若出现人物或角色，身体结构与比例必须正确，禁止畸形手指、错位五官、断裂或多余肢体。",
    "禁止水印、签名、无关 logo 和边框装饰残影。",
]


# 与画风无关的通用负面约束，所有场景包共享。
GENERIC_FORBIDDEN_PATTERNS = [
    "PPT 模板感",
    "库存图标堆砌",
    "无意义装饰箭头",
    "密集伪文字",
    "与内容无关的装饰元素",
]


HARNESS_CORE_OUTLINE_INSTRUCTION = """
Harness 高质量模式已启用。
大纲阶段必须先理解交付对象、读者、证据链和页面角色，再组织页面顺序。
每一页都要有清晰 reader takeaway：读者看完这一页应该带走什么判断。
每页需可命名 asset role（内容论证/故事卡/数据叙事/封面收束/参考科普）与核心关系类型。
避免只堆主题词；优先形成“问题/证据/机制/取舍/结论/行动”的可校验叙事链。
含数字的页面必须可追溯到输入材料，禁止编造精确数据。
场景包只约束页面组织与生成流程，不要把具体画风词汇写进大纲。
"""


HARNESS_CORE_DESCRIPTION_INSTRUCTION = """
Harness 高质量模式已启用。
逐页描述阶段必须补足：页面主张、读者收获、信息层级、构图意图、关系类型、构图模式、素材/图表需求和可读性校验。
如果页面适合后续生成 PageVisualPlan，请明确 source anchor、reader takeaway、visual_focus、layout_intent、truth_constraints（如有数字）。
场景包在这里是页面组织与校验流程，不覆盖用户选择的模板图、文字风格或视觉方案。
"""


class StructureSkill:
    """页面组织能力：角色系统、叙事结构、构图骨架、素材策略、校验规则。

    输出必须与画风无关，保证在任何视觉来源下都可复用。
    """

    structure_id = "generic"
    name = "通用结构"

    def outline_instruction_extra(self) -> str:
        return ""

    def description_instruction_extra(self) -> str:
        return ""

    def deck_plan_hint(self) -> str:
        """Agent 模式生成 DeckPlan 时附加的叙事组织提示。"""
        return ""

    def build_structure(self, slide: dict[str, Any], *, page_id: str, order_index: int | None = None) -> dict[str, Any]:
        """返回风格无关的页面结构计划。

        约定字段：page_role / page_role_name / source_anchor / reader_takeaway /
        composition / labels / structure_prompt，可附带场景包专属扩展字段
        （如 operator_required、material_status），扩展字段会被铺到 plan 顶层。
        """
        raise NotImplementedError

    @staticmethod
    def source_anchor_for(slide: dict[str, Any]) -> str:
        main_message = slide.get("main_message") or slide.get("title") or ""
        points = slide.get("content_points") or []
        joined_points = "；".join(str(item) for item in points[:3])
        return str(main_message or joined_points or slide.get("title") or "").strip()

    @staticmethod
    def labels_for_slide(slide: dict[str, Any], *, limit: int = 6) -> list[str]:
        labels: list[str] = []
        title = slide.get("title") or ""
        main_message = slide.get("main_message") or ""
        points = slide.get("content_points") or []
        for raw in [title, *points, main_message]:
            text = str(raw).strip()
            if not text:
                continue
            label = text.replace("：", " ").replace(":", " ").split()[0][:6]
            if label and label not in labels:
                labels.append(label)
            if len(labels) >= limit:
                break
        return labels or ["主题", "路径", "结果"]


class VisualStyleSkill:
    """默认视觉系统：色板、材质、画风、字体气质、装饰语言。

    仅当用户未上传模板图、未填写风格文字、未启用外部风格 Skill 时作为全局视觉。
    """

    style_id = "generic"
    name = "通用视觉"

    def visual_fields(self, style_hint: str | None = None) -> dict[str, Any]:
        """返回 DeckVisualSystem 的视觉字段（color_palette / typography /
        illustration_style / background_style / label_density 等）。"""
        raise NotImplementedError

    def forbidden_patterns(self) -> list[str]:
        return []

    def consistency_rules(self) -> list[str]:
        return []

    def style_prompt(self, structure: dict[str, Any], style_hint: str | None = None) -> str:
        """把结构计划渲染成本视觉体系下的画风指令。"""
        raise NotImplementedError


class ScenarioPack:
    """场景包：产品层的打包单位，默认绑定结构与视觉，底层保持两层可独立消费。"""

    def __init__(self, pack_id: str, name: str, description: str, structure: StructureSkill, default_visual: VisualStyleSkill):
        self.pack_id = pack_id
        self.name = name
        self.description = description
        self.structure = structure
        self.default_visual = default_visual

    def outline_instruction(self) -> str:
        parts = [HARNESS_CORE_OUTLINE_INSTRUCTION.strip(), f"当前场景包：{self.name}（{self.pack_id}）。"]
        extra = self.structure.outline_instruction_extra().strip()
        if extra:
            parts.append(extra)
        return "\n".join(parts)

    def description_instruction(self) -> str:
        parts = [HARNESS_CORE_DESCRIPTION_INSTRUCTION.strip(), f"当前场景包：{self.name}（{self.pack_id}）。"]
        extra = self.structure.description_instruction_extra().strip()
        if extra:
            parts.append(extra)
        return "\n".join(parts)

    def deck_plan_hint(self) -> str:
        return self.structure.deck_plan_hint()

    def deck_visual_system(
        self,
        topic: str,
        audience: str,
        style: str | None = None,
        *,
        use_default_visual: bool = True,
    ) -> dict[str, Any]:
        if use_default_visual:
            fields = self.default_visual.visual_fields(style)
            default_intent = fields.pop("default_style_intent", self.name)
            forbidden_patterns = [*GENERIC_FORBIDDEN_PATTERNS, *self.default_visual.forbidden_patterns()]
            consistency_rules = list(self.default_visual.consistency_rules())
        else:
            # Keep a schema-valid visual system for planning, but contribute no
            # palette, typography, background, illustration language, motif, or
            # pack-specific style negatives when the user owns the visual layer.
            fields = {
                "color_palette": "由用户视觉来源决定；Harness 不指定或修改色彩。",
                "typography": "由用户视觉来源决定；Harness 仅要求文字清晰可读。",
                "illustration_style": "由用户视觉来源决定；Harness 仅约束内容真实性与构图关系。",
                "background_style": "由用户视觉来源决定；Harness 不增加背景或装饰语言。",
                "label_density": "按内容与用户视觉来源控制，避免文字墙。",
                "signature_element": "无；Harness 不增加视觉母题。",
            }
            default_intent = "用户视觉来源"
            forbidden_patterns = list(GENERIC_FORBIDDEN_PATTERNS)
            consistency_rules = [
                "全篇视觉表现仅遵循用户指定的模板、风格文字、蓝图或外部风格 Skill。",
                "Harness 只保留页面角色、信息层级、构图关系、真实性和交付质量约束。",
            ]
        system = {
            "strategy_id": self.pack_id,
            "name": self.name,
            "topic": topic,
            "audience": audience,
            "style_intent": (style or "").strip() or default_intent,
            "harness_default_visual_enabled": use_default_visual,
            **fields,
            "quality_constraints": list(IMAGE_QUALITY_CONSTRAINTS),
            "forbidden_patterns": forbidden_patterns,
            "consistency_rules": consistency_rules,
        }
        return system

    def build_page_plan(self, slide: dict[str, Any], visual_system: dict[str, Any], *, page_id: str, order_index: int | None = None) -> dict[str, Any]:
        structure = self.structure.build_structure(slide, page_id=page_id, order_index=order_index)
        return self._finalize_page_plan(structure, slide, visual_system, page_id=page_id)

    def build_deck_page_plans(
        self,
        slides: list[dict[str, Any]],
        visual_system: dict[str, Any],
        *,
        topic: str = "",
        page_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Build all page plans and apply deck-level series continuity."""
        from services.harness_skills.quality import apply_series_continuity

        plans: list[dict[str, Any]] = []
        for index, slide in enumerate(slides):
            page_id = (page_ids[index] if page_ids and index < len(page_ids) else None) or str(
                slide.get("slide_id") or f"page-{index + 1}"
            )
            structure = self.structure.build_structure(slide, page_id=page_id, order_index=index)
            plans.append(self._finalize_page_plan(structure, slide, visual_system, page_id=page_id))
        return apply_series_continuity(
            plans,
            pack_id=self.pack_id,
            topic=topic or visual_system.get("topic", ""),
            include_visual=bool(visual_system.get("harness_default_visual_enabled", True)),
        )

    def _finalize_page_plan(
        self,
        structure: dict[str, Any],
        slide: dict[str, Any],
        visual_system: dict[str, Any],
        *,
        page_id: str,
    ) -> dict[str, Any]:
        use_default_visual = bool(visual_system.get("harness_default_visual_enabled", True))
        style_hint = (visual_system.get("style_intent") or "").strip() or None
        structure_prompt = structure.get("structure_prompt", "")
        style_prompt = self.default_visual.style_prompt(structure, style_hint) if use_default_visual else ""
        truth_line = ""
        if structure.get("truth_constraints"):
            truth_line = "数值与标签真实约束：" + "；".join(structure["truth_constraints"][:4]) + "。"
        visual_prompt = "\n".join(part for part in [
            structure_prompt,
            style_prompt,
            truth_line,
            "画质要求：4K 成品级，文字必须真实可读，无伪影、无乱码、无畸形结构。",
        ] if part)
        return {
            "page_id": page_id,
            "strategy_id": self.pack_id,
            **structure,
            "negative_prompts": list(visual_system.get("forbidden_patterns", [])),
            "structure_prompt": structure_prompt,
            "style_prompt": style_prompt,
            "visual_prompt": visual_prompt,
        }

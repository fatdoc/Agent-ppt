"""Paper Operators / 纸片人场景包：隐喻执行者叙事 + 纸模舞台默认视觉。"""
from __future__ import annotations

from typing import Any

from services.harness_skills.base import ScenarioPack, StructureSkill, VisualStyleSkill
from services.harness_skills.operators import (
    PAPER_OPERATOR_FAMILIES,
    choose_operator_for_relationship,
    operator_required_for,
)
from services.harness_skills.quality import enrich_structure_plan, infer_relationship


class PaperOperatorsStructure(StructureSkill):
    structure_id = "paper_operators"
    name = "隐喻执行者叙事"

    def outline_instruction_extra(self) -> str:
        return (
            "每一页先确定 source anchor 和 reader takeaway，再命名本页核心关系类型，"
            "最后判断是否需要隐喻执行者；执行者是理解工具，不是装饰。"
        )

    def description_instruction_extra(self) -> str:
        return "描述中请明确本页的核心关系或机制、构图模式（单节拍/多节拍/对照），方便选择执行者与隐喻场景。"

    def deck_plan_hint(self) -> str:
        return "每页应有一个可被“亲手执行”的核心动作或关系；整套 Deck 共享路径蓝母题，但页间 camera/props/accent 至少变化两轴。"

    def build_structure(self, slide: dict[str, Any], *, page_id: str, order_index: int | None = None) -> dict[str, Any]:
        title = slide.get("title") or "Untitled"
        main_message = slide.get("main_message") or ""
        source_anchor = self.source_anchor_for(slide) or title
        page_role = "cover" if order_index == 0 else "metaphor_stage"

        # Pre-route for relationship-first selection
        asset_role = "slide_center" if order_index == 0 else "content_figure"
        relationship_type = infer_relationship(slide, asset_role=asset_role)
        from services.harness_skills.quality import choose_composition_mode

        composition_mode = choose_composition_mode(
            asset_role=asset_role,
            relationship_type=relationship_type,
            slide=slide,
            order_index=order_index,
        )
        operator = choose_operator_for_relationship(relationship_type, slide)
        needs_operator = operator_required_for(
            asset_role=asset_role,
            relationship_type=relationship_type,
            source_anchor=source_anchor,
            composition_mode=composition_mode,
        )
        metaphor_world = self._choose_metaphor_world(source_anchor, title, relationship_type)
        labels = self.labels_for_slide(slide)
        composition = self._composition_for_mode(
            composition_mode, title, operator, needs_operator, relationship_type,
        )
        structure_prompt = (
            f"页面标题：{title}。核心信息：{main_message}。读者看完应理解：{source_anchor}。"
            f"关系类型：{relationship_type}。隐喻场景：{metaphor_world}。构图：{composition}"
            f"执行者：{'需要 ' + operator['name'] + '，必须亲手完成核心动作。' if needs_operator else '不强制出现；若出现必须增强理解。'}"
            f"中文标签：{'、'.join(labels)}。"
        )
        plan = {
            "page_role": page_role,
            "page_role_name": "封面页" if order_index == 0 else "隐喻舞台页",
            "source_anchor": source_anchor,
            "reader_takeaway": source_anchor,
            "relationship_type": relationship_type,
            "composition_mode": composition_mode,
            "operator_required": needs_operator,
            "operator_family": operator["name"] if needs_operator else "None",
            "core_action": operator["function"] if needs_operator else "",
            "metaphor_world": metaphor_world,
            "composition": composition,
            "labels": labels,
            "structure_prompt": structure_prompt,
        }
        return enrich_structure_plan(plan, pack_id="paper_operators", slide=slide, order_index=order_index)

    def _composition_for_mode(
        self,
        composition_mode: str,
        title: str,
        operator: dict[str, str],
        needs_operator: bool,
        relationship_type: str,
    ) -> str:
        op_line = (
            f"一个执行者（{operator['name']}）亲手完成核心动作（{operator['function']}）；"
            if needs_operator
            else "不强制放置执行者；"
        )
        if composition_mode == "cover_minimal":
            return f"极简封面：大标题“{title}”，留白充足，不放置纸片人。"
        if composition_mode == "comparison":
            return f"左右对照布局呈现「{title}」的对比关系；{op_line}标签贴在对照对象上。"
        if composition_mode == "multi_beat":
            return (
                f"单页多节拍：在同一纸模场景中呈现「{title}」的 2-4 个阶段/节拍；"
                f"{op_line}用路径或分层区分各节拍，保留安静留白。"
            )
        return (
            f"左侧放置「{title}」的核心信息卡，中部呈现 {relationship_type} 关系，右侧形成结果区；"
            f"{op_line}所有标签贴在对象表面或路径节点上。"
        )

    def _choose_metaphor_world(self, text: str, title: str, relationship_type: str) -> str:
        combined = f"{title} {text}"
        if relationship_type == "sequence_handoff":
            return "接力工作台：交接托盘、路径段、阶段标记"
        if relationship_type in ("contrast", "tradeoff"):
            return "对照托盘：分栏卡、天平、对照框"
        if any(token in combined for token in ("艺术", "审美", "设计", "作品")):
            return "画廊工作台：画框、光卡、色票、留白和小型展台"
        if any(token in combined for token in ("情绪", "关系", "边界", "生活")):
            return "软边界房间：屏风、天气卡、空椅子、折叠便签"
        if any(token in combined for token in ("历史", "文化", "研究", "证据")):
            return "档案桌：索引卡、抽屉、时间线、证据标签"
        if any(token in combined for token in ("产品", "AI", "系统", "流程", "增长")):
            return "高空小镇/路线桌：载体路径、检查点、模块化组件"
        return "高空工作台：信息卡、路径、托盘、结果区"


class PaperCraftVisual(VisualStyleSkill):
    style_id = "paper_craft"
    name = "纸模舞台"

    def visual_fields(self, style_hint: str | None = None) -> dict[str, Any]:
        return {
            "default_style_intent": "中文优先的纸模舞台正文配图",
            "color_palette": "暖白纸张、炭黑线条、安静灰、路径蓝；证据琥珀、风险珊瑚、增长薄荷按语义使用。",
            "typography": "中文短标签优先，2-6 字为主；使用纸标签、吊牌、牌匾、路线牌或缝线卡片承载文字。",
            "illustration_style": "16:9 高空视角纸模舞台，折纸物件、柔和阴影、克制留白、编辑型构图。",
            "background_style": "暖白纸面、轻微纸纹、干净桌面或微缩纸模空间，避免模板背景噪音。",
            "label_density": "简单页 3-6 个短标签；复杂页最多 8-10 个，按路径、状态或对象分组。",
            "signature_element": "无脸折纸小人（纸片人）",
            "signature_element_density": "默认每页最多一个纸片人；只有 operator inclusion test 通过时才使用。",
            "operator_families": [item["name"] for item in PAPER_OPERATOR_FAMILIES],
            "throughline_motif": "路径蓝丝带贯穿全稿",
        }

    def forbidden_patterns(self) -> list[str]:
        return ["机器人头", "发光 AI 大脑", "黑色小怪物", "白点眼睛", "细腿", "表情脸", "可爱贴纸", "通用办公室人物"]

    def consistency_rules(self) -> list[str]:
        return [
            "整套 PPT 使用同一纸张材质、路径蓝、标签样式和留白比例。",
            "每页先确定 source anchor、relationship 和 reader takeaway，再决定是否需要纸片人。",
            "纸片人必须执行核心动作，不能站立展示或装饰。",
            "页间至少变化 camera/focal/props/accent 两轴，避免模板锁定。",
            "非工程主题应使用对应领域物件，不强行套节点、漏斗、仪表盘。",
        ]

    def style_prompt(self, structure: dict[str, Any], style_hint: str | None = None) -> str:
        operator_required = bool(structure.get("operator_required"))
        operator_line = (
            f"执行者渲染为无脸折纸小人（{structure.get('operator_family')}），亲手完成核心动作。"
            if operator_required
            else "本页不强制出现纸片人；若出现必须是无脸折纸小人且能增强理解。"
        )
        hint_line = f"风格意图：{style_hint}。" if style_hint else ""
        truth_line = ""
        if structure.get("truth_constraints"):
            truth_line = "真实约束：" + "；".join(structure["truth_constraints"][:3]) + "。"
        return (
            "视觉体系：Paper Operators / 纸片人。16:9 高空视角纸模舞台，折纸物件、路径蓝、克制留白。"
            f"{operator_line}{hint_line}{truth_line}"
            "禁止机器人头、发光 AI 大脑、黑色小怪物、表情脸、可爱贴纸、漂浮文字。"
        )


def build_pack() -> ScenarioPack:
    return ScenarioPack(
        pack_id="paper_operators",
        name="Paper Operators / 纸片人",
        description="隐喻执行者叙事：关系优先、Swap Test 质检，默认纸模舞台视觉。",
        structure=PaperOperatorsStructure(),
        default_visual=PaperCraftVisual(),
    )

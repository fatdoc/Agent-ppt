"""咨询汇报场景包：金字塔原理叙事 + 深蓝灰咨询版式默认视觉。"""
from __future__ import annotations

import re
from typing import Any

from services.harness_skills.base import ScenarioPack, StructureSkill, VisualStyleSkill
from services.harness_skills.quality import enrich_structure_plan


PAGE_ROLES = {
    "cover": "封面页",
    "executive_summary": "核心结论页",
    "evidence_chart": "论据图表页",
    "big_number": "关键数字页",
    "risk_tradeoff": "风险取舍页",
    "action_plan": "行动计划页",
    "section_divider": "章节页",
}

_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:%|亿|万|倍|percent)")


class ConsultingReportStructure(StructureSkill):
    structure_id = "consulting_report"
    name = "金字塔汇报叙事"

    def outline_instruction_extra(self) -> str:
        return (
            "按金字塔原理组织页面：先给核心结论，再逐层展开论据；每页标题必须是一个完整的结论句"
            "（如“华东市场增速是整体的 2.3 倍”），不能是主题词（如“市场分析”）；"
            "结尾必须落到风险取舍和行动计划。"
        )

    def description_instruction_extra(self) -> str:
        return (
            "每页描述必须写明：本页结论句、支撑该结论的图表或数字类型（对比柱状、趋势线、占比、瀑布等）、"
            "以及图表旁的一句 takeaway 标注；数字必须可追溯到输入材料，禁止编造精确数据。"
        )

    def deck_plan_hint(self) -> str:
        return (
            "页面角色应覆盖：封面、核心结论（executive summary）、论据图表页（每个论据一页）、"
            "关键数字页、风险与取舍、行动计划；每页标题必须是完整结论句，全篇先结论后论据。"
        )

    def build_structure(self, slide: dict[str, Any], *, page_id: str, order_index: int | None = None) -> dict[str, Any]:
        title = slide.get("title") or "Untitled"
        main_message = slide.get("main_message") or ""
        source_anchor = self.source_anchor_for(slide) or title
        role = self._choose_role(slide, order_index)
        labels = self.labels_for_slide(slide, limit=6)
        composition = self._composition_for_role(role, title)
        conclusion_line = ""
        if role not in ("cover", "section_divider"):
            conclusion_line = "页面标题必须呈现为完整的结论句，读者只看标题就能得到本页判断。"
        structure_prompt = (
            f"页面角色：{PAGE_ROLES[role]}。页面标题：{title}。核心结论：{main_message or source_anchor}。"
            f"{conclusion_line}构图：{composition}"
            f"信息要点：{'、'.join(labels)}。"
            "图表必须有清晰的坐标与单位，图表旁必须有一句 takeaway 标注；先结论后论据，层级分明。"
        )
        plan = {
            "page_role": role,
            "page_role_name": PAGE_ROLES[role],
            "source_anchor": source_anchor,
            "reader_takeaway": source_anchor,
            "composition": composition,
            "labels": labels,
            "structure_prompt": structure_prompt,
        }
        return enrich_structure_plan(plan, pack_id="consulting_report", slide=slide, order_index=order_index)

    def _choose_role(self, slide: dict[str, Any], order_index: int | None) -> str:
        combined = " ".join([
            str(slide.get("title") or ""),
            str(slide.get("main_message") or ""),
            "；".join(str(item) for item in (slide.get("content_points") or [])),
        ])
        if order_index == 0:
            return "cover"
        if any(token in combined for token in ("风险", "取舍", "权衡", "挑战", "应对")):
            return "risk_tradeoff"
        if any(token in combined for token in ("行动", "计划", "下一步", "排期", "路线图", "落地")):
            return "action_plan"
        if any(token in combined for token in ("结论", "建议", "总结", "核心判断", "executive")):
            return "executive_summary"
        if _NUMBER_PATTERN.search(combined) and len(combined) < 80:
            return "big_number"
        if any(token in combined for token in ("第一部分", "第二部分", "章节", "part")):
            return "section_divider"
        return "evidence_chart"

    def _composition_for_role(self, role: str, title: str) -> str:
        if role == "cover":
            return f"简洁封面：大标题“{title}”，副标题标注汇报对象与日期，底部细线分隔署名区。"
        if role == "executive_summary":
            return "顶部结论句大标题，主体用 2-4 个编号论点卡片支撑结论，每个论点一行加粗判断加一句依据。"
        if role == "big_number":
            return "一个超大关键数字占据画面中心，上方结论句标题，数字下方一行注明口径与来源，其余留白。"
        if role == "risk_tradeoff":
            return "左右或矩阵布局呈现选项与代价，每个选项标注收益与风险，底部给出推荐立场。"
        if role == "action_plan":
            return "横向时间轴或表格呈现行动项：负责人、里程碑、时间点清晰可读，首行是本页结论句。"
        if role == "section_divider":
            return f"章节编号与标题“{title}”左对齐大字排版，右侧留白，底部一行本章导语。"
        return "顶部结论句标题，主体一张主导图表（占约六成版面），图表旁一句 takeaway 标注，底部注明数据口径。"


class ExecutiveSlateVisual(VisualStyleSkill):
    style_id = "executive_slate"
    name = "深蓝灰咨询版式"

    def visual_fields(self, style_hint: str | None = None) -> dict[str, Any]:
        return {
            "default_style_intent": "高管咨询汇报风：结论先行、图表主导、克制专业",
            "color_palette": "深蓝灰主色（如石板蓝 #1F2A3A 系）、白与浅灰底、橙色作为唯一强调色标注关键数据与 takeaway。",
            "typography": "标题为完整结论句、字重厚实；正文极简；关键数字使用超大字号；全篇字体族统一。",
            "illustration_style": "图表主导：干净的柱状、趋势线、占比、瀑布图，细网格线、清晰坐标与单位；无装饰性插画。",
            "background_style": "白或浅灰底配深蓝灰导航条/页眉，或整页深蓝灰底反白排版；无纹理与装饰。",
            "label_density": "每页一个结论加不超过 5 个支撑要点；图表标注完整但克制。",
            "signature_element": "橙色 takeaway 标注与超大关键数字",
        }

    def forbidden_patterns(self) -> list[str]:
        return ["彩虹配色图表", "3D 立体图表", "剪贴画", "渐变彩色块堆叠", "夸张图标"]

    def consistency_rules(self) -> list[str]:
        return [
            "全篇只使用深蓝灰 + 橙色一套配色，橙色只用于关键数据和 takeaway。",
            "所有图表使用同一坐标风格、同一网格密度、同一标注方式。",
            "每页标题都是结论句，版式位置固定，形成稳定的阅读动线。",
            "数据必须标注口径或来源，禁止无出处的精确数字；data_contract 中的数值不可编造。",
            "页间至少变化 focal/props/accent 两轴，避免每页同一图表模板。",
        ]

    def style_prompt(self, structure: dict[str, Any], style_hint: str | None = None) -> str:
        hint_line = f"风格意图：{style_hint}。" if style_hint else ""
        return (
            "视觉体系：高管咨询汇报风。深蓝灰主色、白/浅灰底、橙色唯一强调色；"
            "图表干净专业（细网格、清晰坐标、完整单位），关键数字超大呈现，装饰元素接近于零，信息层级森严。"
            f"{hint_line}"
            "禁止彩虹配色、3D 图表、剪贴画和夸张图标。"
        )


def build_pack() -> ScenarioPack:
    return ScenarioPack(
        pack_id="consulting_report",
        name="咨询汇报",
        description="金字塔汇报叙事：结论先行、图表主导，标题即结论句，默认深蓝灰咨询版式与橙色强调。",
        structure=ConsultingReportStructure(),
        default_visual=ExecutiveSlateVisual(),
    )

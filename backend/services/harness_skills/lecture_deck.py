"""课程讲义场景包：教学叙事结构 + 讲义板书默认视觉。"""
from __future__ import annotations

from typing import Any

from services.harness_skills.base import ScenarioPack, StructureSkill, VisualStyleSkill
from services.harness_skills.quality import enrich_structure_plan


PAGE_ROLES = {
    "cover": "课程封面页",
    "agenda": "课程导览页",
    "chapter_divider": "章节页",
    "concept": "概念讲解页",
    "worked_example": "例题演算页",
    "comparison": "对比辨析页",
    "recap": "小结回顾页",
}


class LectureDeckStructure(StructureSkill):
    structure_id = "lecture_deck"
    name = "教学叙事结构"

    def outline_instruction_extra(self) -> str:
        return (
            "按教学节奏组织页面：学习目标 → 概念展开 → 例题/练习巩固 → 小结回顾；"
            "每个章节单元应以明确的学习目标开始、以小结收尾；概念页之后尽量安排例题或应用页帮助巩固。"
        )

    def description_instruction_extra(self) -> str:
        return (
            "概念页要写清定义、直观解释和一个帮助理解的图示需求；例题页必须包含题干和分步解法；"
            "术语首次出现时给一句白话定义；允许比常规 PPT 更高的信息密度，但必须分层呈现。"
        )

    def deck_plan_hint(self) -> str:
        return (
            "页面角色应覆盖：课程封面、学习目标/导览、章节页、概念讲解页、例题演算页、对比辨析页、小结回顾页；"
            "遵循“目标→展开→巩固→回顾”的教学闭环，每 4-6 页出现一次小结或练习。"
        )

    def build_structure(self, slide: dict[str, Any], *, page_id: str, order_index: int | None = None) -> dict[str, Any]:
        title = slide.get("title") or "Untitled"
        main_message = slide.get("main_message") or ""
        source_anchor = self.source_anchor_for(slide) or title
        role = self._choose_role(slide, order_index)
        labels = self.labels_for_slide(slide, limit=8)
        composition = self._composition_for_role(role, title)
        structure_prompt = (
            f"页面角色：{PAGE_ROLES[role]}。页面标题：{title}。核心信息：{main_message}。"
            f"学生看完应掌握：{source_anchor}。构图：{composition}"
            f"标签与要点：{'、'.join(labels)}。"
            "信息可以比常规 PPT 更密，但必须有清晰的层级：标题区、讲解区、图示区、要点区各司其职。"
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
        return enrich_structure_plan(plan, pack_id="lecture_deck", slide=slide, order_index=order_index)

    def _choose_role(self, slide: dict[str, Any], order_index: int | None) -> str:
        combined = " ".join([
            str(slide.get("title") or ""),
            str(slide.get("main_message") or ""),
            "；".join(str(item) for item in (slide.get("content_points") or [])),
        ])
        if order_index == 0:
            return "cover"
        if any(token in combined for token in ("目录", "导览", "学习目标", "课程安排", "agenda")):
            return "agenda"
        if any(token in combined for token in ("例题", "练习", "习题", "演算", "案例分析")):
            return "worked_example"
        if any(token in combined for token in ("对比", "区别", "异同", "vs", "辨析")):
            return "comparison"
        if any(token in combined for token in ("小结", "总结", "回顾", "复习", "要点回顾")):
            return "recap"
        if any(token in combined for token in ("第一章", "第二章", "第三章", "章节", "单元", "part")):
            return "chapter_divider"
        return "concept"

    def _composition_for_role(self, role: str, title: str) -> str:
        if role == "cover":
            return f"居中大标题“{title}”，副标题标注课程对象与讲者，底部留出课程信息条。"
        if role == "agenda":
            return "纵向编号列表呈现学习目标或课程结构，每项配一个小图示，右侧留白。"
        if role == "chapter_divider":
            return f"超大章节编号与标题“{title}”占据主体，配一句本章导语，弱化其他元素。"
        if role == "worked_example":
            return "上方题干区（完整题目文字），中部分步解法区（步骤编号清晰），底部答案框醒目标出。"
        if role == "comparison":
            return "左右两栏对照布局，顶部各自命名，中部逐行对比属性，底部给出一句选择建议。"
        if role == "recap":
            return "网格或清单式回顾本单元要点，每项一个关键词加一句话，右下角提示下一步学习内容。"
        return "标题区给出概念名，主体分为定义区（一句白话定义）、图示区（一个直观示意图）和要点区（分层列出）。"


class ChalkboardHandoutVisual(VisualStyleSkill):
    style_id = "chalkboard_handout"
    name = "讲义板书"

    def visual_fields(self, style_hint: str | None = None) -> dict[str, Any]:
        return {
            "default_style_intent": "清晰易读的课程讲义配图，兼具板书感与印刷讲义的秩序",
            "color_palette": "米白或纯白底、靛蓝主色、炭灰正文；重点用橙红色手写批注色标出，图示可用浅蓝、浅绿色块区分。",
            "typography": "标题清晰厚重，正文规整易读；重点术语用下划线或高亮块标注，允许少量手写体批注。",
            "illustration_style": "简洁的教学示意图：几何图形、坐标系、流程框图、手绘风格箭头，一切图示服务于理解。",
            "background_style": "干净的讲义纸面或淡色板书背景，可有轻微网格或横线纹理，无装饰噪音。",
            "label_density": "允许中高信息密度：概念页 6-10 个标签要点，例题页完整呈现题干与步骤文字。",
        }

    def forbidden_patterns(self) -> list[str]:
        return ["卡通吉祥物", "幼儿园贴纸风", "赛博发光特效", "拥挤无层级的文字墙"]

    def consistency_rules(self) -> list[str]:
        return [
            "整套课件使用统一的底色、主色和批注色，章节页风格一致。",
            "同类页面角色（概念页/例题页/小结页）保持相同的布局骨架，方便学生建立阅读习惯。",
            "图示风格全程统一：同一种线条粗细、同一种箭头样式。",
            "重点标注色只用于真正的重点，每页不超过三处。",
        ]

    def style_prompt(self, structure: dict[str, Any], style_hint: str | None = None) -> str:
        hint_line = f"风格意图：{style_hint}。" if style_hint else ""
        return (
            "视觉体系：课程讲义板书风。米白/纯白底面，靛蓝主色、炭灰正文，重点用橙红批注色标出；"
            "教学示意图用简洁几何图形与手绘感箭头，板书与印刷讲义气质并存，秩序感强。"
            f"{hint_line}"
            "禁止卡通吉祥物、发光特效和文字墙；信息密度可以高，但层级必须一眼可读。"
        )


def build_pack() -> ScenarioPack:
    return ScenarioPack(
        pack_id="lecture_deck",
        name="课程讲义",
        description="教学叙事结构：目标→概念→例题→小结的教学闭环，默认讲义板书视觉，允许更高信息密度。",
        structure=LectureDeckStructure(),
        default_visual=ChalkboardHandoutVisual(),
    )

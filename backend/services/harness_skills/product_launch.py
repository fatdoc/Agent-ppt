"""产品发布会场景包：产品叙事结构 + 深色舞台默认视觉，产品图为主视觉。"""
from __future__ import annotations

import re
from typing import Any

from services.harness_skills.base import ScenarioPack, StructureSkill, VisualStyleSkill
from services.harness_skills.quality import enrich_structure_plan


PAGE_ROLES = {
    "teaser": "悬念开场页",
    "hero_product": "产品主视觉页",
    "feature": "特性亮点页",
    "specs": "参数规格页",
    "pricing": "价格发布页",
    "cta": "行动号召页",
}

# 需要产品图作为主视觉的页面角色。
PRODUCT_IMAGE_ROLES = {"hero_product", "feature"}

_MATERIAL_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]+\)|https?://\S+\.(?:png|jpe?g|webp|gif)", re.IGNORECASE)


def _has_material_images(slide: dict[str, Any]) -> bool:
    text = str(slide.get("description_text") or "")
    return bool(_MATERIAL_IMAGE_PATTERN.search(text))


class ProductLaunchStructure(StructureSkill):
    structure_id = "product_launch"
    name = "产品发布叙事"

    def outline_instruction_extra(self) -> str:
        return (
            "按发布会叙事组织页面：痛点悬念 → 产品揭幕 → 特性逐一递进 → 参数规格 → 价格与发布信息 → 行动号召；"
            "每页只讲一个主张，文字极少（大标题 + 一句副文案），把版面留给产品本身。"
        )

    def description_instruction_extra(self) -> str:
        return (
            "描述中必须写明本页产品图的需求：展示角度、局部特写还是整机；如果用户已提供产品素材图，"
            "必须在描述中引用对应素材；没有素材时明确标注需要概念渲染图占位。"
        )

    def deck_plan_hint(self) -> str:
        return (
            "页面角色应覆盖：悬念开场、产品主视觉揭幕、特性亮点（每个特性一页）、参数规格、价格发布、行动号召；"
            "每页一个主张，标题要短而有力，像发布会讲稿的一句话。"
        )

    def build_structure(self, slide: dict[str, Any], *, page_id: str, order_index: int | None = None) -> dict[str, Any]:
        title = slide.get("title") or "Untitled"
        main_message = slide.get("main_message") or ""
        source_anchor = self.source_anchor_for(slide) or title
        role = self._choose_role(slide, order_index)
        labels = self.labels_for_slide(slide, limit=4)
        has_materials = _has_material_images(slide)
        needs_product_image = role in PRODUCT_IMAGE_ROLES
        material_status = None
        if needs_product_image:
            material_status = "real" if has_materials else "concept_placeholder"
        composition = self._composition_for_role(role, title)
        material_line = ""
        if material_status == "real":
            material_line = "本页必须使用用户提供的产品素材图作为主视觉，产品占据约六成版面，不得用生成图替代真实产品。"
        elif material_status == "concept_placeholder":
            material_line = (
                "本页暂无真实产品图，使用 AI 概念渲染图占位：产品形态保持中性概念感，"
                "禁止出现真实品牌名、logo 或可被误认为实拍的宣传标注；该页已标记为概念图，待用户提供素材后替换。"
            )
        structure_prompt = (
            f"页面角色：{PAGE_ROLES[role]}。页面标题：{title}。核心主张：{main_message or source_anchor}。"
            f"构图：{composition}{material_line}"
            f"文案元素：{'、'.join(labels)}。"
            "每页只允许一个主张，副文案不超过一句话，其余信息全部让位给视觉。"
        )
        plan = {
            "page_role": role,
            "page_role_name": PAGE_ROLES[role],
            "source_anchor": source_anchor,
            "reader_takeaway": source_anchor,
            "material_status": material_status,
            "composition": composition,
            "labels": labels,
            "structure_prompt": structure_prompt,
        }
        return enrich_structure_plan(plan, pack_id="product_launch", slide=slide, order_index=order_index)

    def _choose_role(self, slide: dict[str, Any], order_index: int | None) -> str:
        combined = " ".join([
            str(slide.get("title") or ""),
            str(slide.get("main_message") or ""),
            "；".join(str(item) for item in (slide.get("content_points") or [])),
        ])
        if any(token in combined for token in ("价格", "售价", "定价", "¥", "$", "预售")):
            return "pricing"
        if any(token in combined for token in ("参数", "规格", "配置", "尺寸", "续航", "性能对比")):
            return "specs"
        if any(token in combined for token in ("购买", "预约", "行动", "立即", "扫码", "官网")):
            return "cta"
        if order_index == 0:
            return "teaser"
        if order_index == 1 or any(token in combined for token in ("揭幕", "登场", "全新", "介绍", "亮相")):
            return "hero_product"
        return "feature"

    def _composition_for_role(self, role: str, title: str) -> str:
        if role == "teaser":
            return f"近乎全黑的画面中央一句悬念标题“{title}”，可有产品剪影或一束微光，其余全部留黑。"
        if role == "hero_product":
            return "产品居中悬浮，占据约六成版面，顶部或底部一行大标题，一句副文案，无其他元素。"
        if role == "feature":
            return "产品局部特写占据画面主体（约六成版面），一侧用大字标出该特性名称与一句说明。"
        if role == "specs":
            return "产品置于一侧，另一侧用极简表格或参数列点呈现规格，行距宽松、数字醒目。"
        if role == "pricing":
            return "超大价格数字居中，上方产品小图或名称，下方一行发布/开售信息。"
        return "居中大标题给出行动指令，配二维码或渠道信息，底部留出产品家族小图。"


class DarkStageVisual(VisualStyleSkill):
    style_id = "dark_stage"
    name = "深色发布舞台"

    def visual_fields(self, style_hint: str | None = None) -> dict[str, Any]:
        return {
            "default_style_intent": "科技产品发布会 keynote 风格，产品即主角",
            "color_palette": "近黑深灰渐变底、纯白大标题、单一品牌强调色（默认电光蓝）点缀；价格页可用暖金色数字。",
            "typography": "超大号极粗标题字、极简副文案；数字使用大字号等宽感排版；文字总量极少。",
            "illustration_style": "产品摄影级渲染：柔和棚拍光、克制反射、真实材质质感；无插画元素。",
            "background_style": "深色舞台背景，中央聚光或柔光晕，轻微渐变，无纹理噪音。",
            "label_density": "每页文案不超过 4 个元素：一个大标题、一句副文案、必要的参数或价格。",
            "signature_element": "居中悬浮的产品主视觉",
        }

    def forbidden_patterns(self) -> list[str]:
        return ["杂乱背景", "多产品堆叠", "花哨光效", "廉价 3D 渲染感", "白底电商图风格"]

    def consistency_rules(self) -> list[str]:
        return [
            "整场发布会保持同一深色底、同一强调色和同一打光方向。",
            "产品是唯一主角：真实素材图优先，概念渲染图必须与素材图光影风格一致。",
            "同一产品在不同页面的形态、颜色、比例必须一致。",
            "文字永远压在留白区，禁止压在产品主体上。",
        ]

    def style_prompt(self, structure: dict[str, Any], style_hint: str | None = None) -> str:
        hint_line = f"风格意图：{style_hint}。" if style_hint else ""
        concept_line = ""
        if structure.get("material_status") == "concept_placeholder":
            concept_line = "产品为概念渲染：保持中性设计语言，禁止真实品牌标识，光影与整场发布会一致。"
        return (
            "视觉体系：深色发布会舞台（keynote 风）。近黑渐变背景、中央聚光，产品以摄影级质感居中呈现；"
            "纯白超大标题、极少文字、单一强调色点缀。"
            f"{concept_line}{hint_line}"
            "禁止杂乱背景、花哨光效、廉价渲染感和白底电商图风格。"
        )


def build_pack() -> ScenarioPack:
    return ScenarioPack(
        pack_id="product_launch",
        name="产品发布会",
        description="产品发布叙事：悬念→揭幕→特性→参数→价格→行动，产品图占主视觉，默认深色舞台视觉。",
        structure=ProductLaunchStructure(),
        default_visual=DarkStageVisual(),
    )

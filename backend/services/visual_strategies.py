"""Built-in visual strategies for Agent Mode and image guidance."""
from __future__ import annotations

from typing import Any


PAPER_OPERATOR_FAMILIES = [
    "Thread Runner / 牵线员",
    "Lens Keeper / 检视员",
    "Gate Builder / 闸门员",
    "Frame Setter / 装框员",
    "Color Tuner / 调色员",
    "Light Catcher / 捕光员",
    "Archive Tender / 档案员",
    "Care Folder / 照料员",
    "Boundary Keeper / 边界员",
    "Weather Reader / 读天气的人",
    "Stack Mason / 搭层员",
    "Residue Sweeper / 残留清理员",
    "Tradeoff Weigher / 权衡员",
]


class PaperOperatorsStrategy:
    strategy_id = "paper_operators"

    def deck_visual_system(self, topic: str, audience: str, style: str | None = None) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": "Paper Operators / 纸片人",
            "topic": topic,
            "audience": audience,
            "style_intent": style or "中文优先的纸模舞台正文配图",
            "color_palette": "暖白纸张、炭黑线条、安静灰、路径蓝；仅在语义需要时使用证据琥珀、风险珊瑚、增长薄荷。",
            "typography": "中文短标签优先，2-6 字为主；使用纸标签、吊牌、牌匾、路线牌或缝线卡片承载文字。",
            "illustration_style": "16:9 高空视角纸模舞台，折纸物件、柔和阴影、克制留白、编辑型构图。",
            "paper_operator_density": "默认每页最多一个纸片人；只有 operator inclusion test 通过时才使用，不硬塞。",
            "chinese_label_density": "简单页 3-6 个短标签；复杂页最多 8-10 个，按路径、状态或对象分组。",
            "background_style": "暖白纸面、轻微纸纹、干净桌面或微缩纸模空间，避免模板背景噪音。",
            "operator_families": PAPER_OPERATOR_FAMILIES,
            "forbidden_patterns": [
                "PPT 模板感", "库存图标", "机器人头", "发光 AI 大脑", "黑色小怪物",
                "白点眼睛", "细腿", "表情脸", "可爱贴纸", "通用办公室人物", "无意义流程箭头",
            ],
            "consistency_rules": [
                "整套 PPT 使用同一纸张材质、路径蓝、标签样式和留白比例。",
                "每页先确定 source anchor 和 reader takeaway，再决定是否需要纸片人。",
                "纸片人必须执行核心动作，不能站立展示或装饰。",
                "非工程主题应使用对应领域物件，不强行套节点、漏斗、仪表盘。",
            ],
        }

    def build_page_plan(self, slide: dict[str, Any], visual_system: dict[str, Any], *, page_id: str) -> dict[str, Any]:
        main_message = slide.get("main_message") or slide.get("title") or ""
        title = slide.get("title") or "Untitled"
        points = slide.get("content_points") or []
        joined_points = "；".join(str(item) for item in points[:3])
        source_anchor = main_message or joined_points or title
        operator_required = len(source_anchor) > 12 or any(token in source_anchor for token in ("关系", "路径", "变化", "边界", "权衡", "证据", "系统", "流程", "转变"))
        operator_family = self._choose_operator_family(source_anchor, title)
        metaphor_world = self._choose_metaphor_world(source_anchor, title)
        labels = self._labels_for_slide(title, main_message, points)
        composition = (
            f"16:9 高空纸模舞台。左侧放置“{title}”的核心信息卡，中部用纸质物件呈现关键关系，"
            f"右侧形成清晰结果区。{'一个无脸折纸小人亲手执行核心动作，' if operator_required else '不强制放置纸片人，'}"
            "所有标签贴在物件表面或路径节点上，保留安静留白。"
        )
        visual_prompt = (
            "生成一张 Banana Slides PPT 页面图，Paper Operators / 纸片人风格。"
            f"页面标题：{title}。核心信息：{main_message}。"
            f"读者看完应理解：{source_anchor}。"
            f"视觉世界：{metaphor_world}。构图：{composition}。"
            f"纸片人：{'需要，选择 ' + operator_family + '，必须亲手完成核心动作。' if operator_required else '不强制出现，若出现必须能增强理解。'}"
            f"中文标签：{ '、'.join(labels) }。"
            "使用暖白纸张、炭黑线条、路径蓝、轻微纸纹、柔和阴影。"
            "禁止 PPT 模板感、库存图标、机器人头、发光 AI 大脑、黑色小怪物、表情脸、可爱贴纸、漂浮文字、密集伪文字。"
        )
        return {
            "page_id": page_id,
            "strategy_id": self.strategy_id,
            "source_anchor": source_anchor,
            "reader_takeaway": source_anchor,
            "operator_required": operator_required,
            "operator_family": operator_family if operator_required else "None",
            "metaphor_world": metaphor_world,
            "composition": composition,
            "labels": labels,
            "negative_prompts": visual_system.get("forbidden_patterns", []),
            "visual_prompt": visual_prompt,
        }

    def _choose_operator_family(self, text: str, title: str) -> str:
        combined = f"{title} {text}"
        if any(token in combined for token in ("权衡", "成本", "优先级", "取舍")):
            return "Tradeoff Weigher / 权衡员"
        if any(token in combined for token in ("边界", "风险", "准入", "过滤")):
            return "Gate Builder / 闸门员"
        if any(token in combined for token in ("证据", "检验", "质量", "观察")):
            return "Lens Keeper / 检视员"
        if any(token in combined for token in ("情绪", "关系", "生活", "照顾")):
            return "Care Folder / 照料员"
        return "Thread Runner / 牵线员"

    def _choose_metaphor_world(self, text: str, title: str) -> str:
        combined = f"{title} {text}"
        if any(token in combined for token in ("艺术", "审美", "设计", "作品")):
            return "画廊工作台：画框、光卡、色票、留白和小型展台"
        if any(token in combined for token in ("情绪", "关系", "边界", "生活")):
            return "软边界房间：纸屏风、天气卡、空椅子、折叠便签"
        if any(token in combined for token in ("历史", "文化", "研究", "证据")):
            return "档案桌：索引卡、抽屉、时间线、证据标签"
        if any(token in combined for token in ("产品", "AI", "系统", "流程", "增长")):
            return "高空纸片小镇/路线桌：蓝色载体路径、检查点、纸质模块"
        return "高空纸模工作台：信息卡、路径、托盘、结果区"

    def _labels_for_slide(self, title: str, main_message: str, points: list[Any]) -> list[str]:
        labels = []
        for raw in [title, *points, main_message]:
            text = str(raw).strip()
            if not text:
                continue
            label = text.replace("：", " ").replace(":", " ").split()[0][:6]
            if label and label not in labels:
                labels.append(label)
            if len(labels) >= 6:
                break
        return labels or ["主题", "路径", "结果"]


def get_visual_strategy(strategy_id: str):
    if strategy_id == "paper_operators":
        return PaperOperatorsStrategy()
    return PaperOperatorsStrategy() if strategy_id == "external_skill" else None

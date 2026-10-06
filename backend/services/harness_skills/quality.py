"""Shared Harness quality layer — asset routing, relationships, truth, Swap Test, deck continuity.

Applies to every scenario pack (paper_operators, consulting_report, lecture_deck, product_launch).
"""
from __future__ import annotations

import re
from typing import Any

# --- Asset routing (5 roles, cross-pack) ---

ASSET_ROLES: dict[str, str] = {
    "content_figure": "内容论证页",
    "story_card": "故事/案例卡",
    "data_story": "数据叙事页",
    "slide_center": "封面/章节/收束页",
    "reference_explainer": "参考型科普页",
}

# --- Relationship grammar (12 families) ---

RELATIONSHIP_TYPES: dict[str, str] = {
    "connection": "连接",
    "sequence_handoff": "顺序·交接",
    "dependency": "依赖",
    "causality": "因果·触发",
    "feedback": "反馈环",
    "contrast": "对比·对立",
    "tradeoff": "权衡·取舍",
    "hierarchy": "层级·包含",
    "transformation": "转化·状态迁移",
    "boundary": "边界·过滤·门槛",
    "divergence": "分流·汇聚",
    "tension": "张力·均衡",
}

COMPOSITION_MODES: dict[str, str] = {
    "single_beat": "单节拍",
    "multi_beat": "单页多节拍",
    "comparison": "对照构图",
    "cover_minimal": "极简封面/收束",
}

# Generic topic-only anchors that fail Swap Test.
_GENERIC_ANCHOR_TOKENS = frozenset({
    "核心洞察", "问题背景", "方案设计", "价值证明", "总结", "封面",
    "市场分析", "产品介绍", "核心观点", "主要内容", "关键路径",
})

_NUMBER_PATTERN = re.compile(
    r"\d+/\d+|\d{4}年|\d+(?:\.\d+)?\s*(?:%|亿|万|倍|percent|x|X|倍速)?",
    re.IGNORECASE,
)
_PERCENT_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*%")
_UNIT_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:亿|万|倍|x|X)")

# Pack-specific page_role → asset_role
_PACK_ASSET_ROLE_MAP: dict[str, dict[str, str]] = {
    "paper_operators": {
        "metaphor_stage": "content_figure",
        "cover": "slide_center",
        "section": "slide_center",
        "conclusion": "slide_center",
    },
    "consulting_report": {
        "cover": "slide_center",
        "section_divider": "slide_center",
        "executive_summary": "content_figure",
        "evidence_chart": "data_story",
        "big_number": "data_story",
        "risk_tradeoff": "content_figure",
        "action_plan": "content_figure",
    },
    "lecture_deck": {
        "cover": "slide_center",
        "agenda": "slide_center",
        "chapter_divider": "slide_center",
        "concept": "reference_explainer",
        "worked_example": "content_figure",
        "comparison": "content_figure",
        "recap": "slide_center",
    },
    "product_launch": {
        "teaser": "slide_center",
        "hero_product": "slide_center",
        "feature": "content_figure",
        "specs": "data_story",
        "pricing": "data_story",
        "cta": "slide_center",
    },
}

_STORY_TOKENS = ("故事", "案例", "传记", "人物", "转折", "冲突", "经历", "叙事")
_REFERENCE_TOKENS = ("历史", "科学", "机制", "原理", "定义", "物种", "文物", "年代", "公式")
_DATA_TOKENS = ("图表", "数据", "指标", "增速", "占比", "排名", "benchmark", "同比", "环比")


def route_asset_role(
    *,
    pack_id: str,
    page_role: str,
    slide: dict[str, Any],
    order_index: int | None = None,
) -> str:
    """Pick one of five asset roles before structure composition."""
    combined = _slide_text(slide)
    mapped = _PACK_ASSET_ROLE_MAP.get(pack_id, {}).get(page_role)
    if mapped:
        if mapped == "content_figure" and _has_numbers(combined):
            return "data_story"
        if mapped == "content_figure" and any(token in combined for token in _STORY_TOKENS):
            return "story_card"
        if mapped == "content_figure" and any(token in combined for token in _REFERENCE_TOKENS):
            return "reference_explainer"
        return mapped

    if order_index == 0 or any(token in combined for token in ("封面", "章节", "总结", "收束", "cta")):
        return "slide_center"
    if _has_numbers(combined) or any(token in combined for token in _DATA_TOKENS):
        return "data_story"
    if any(token in combined for token in _STORY_TOKENS):
        return "story_card"
    if any(token in combined for token in _REFERENCE_TOKENS):
        return "reference_explainer"
    return "content_figure"


def infer_relationship(slide: dict[str, Any], *, asset_role: str) -> str:
    """Relationship-first: name the relation before choosing operators or layout."""
    combined = _slide_text(slide)
    if asset_role in ("slide_center",):
        return "hierarchy"
    if any(token in combined for token in ("对比", "vs", "异同", "前后", "相反", "对立")):
        return "contrast"
    if any(token in combined for token in ("权衡", "取舍", "成本", "优先级", "tradeoff")):
        return "tradeoff"
    if any(token in combined for token in ("依赖", "前提", "基于", "离不开")):
        return "dependency"
    if any(token in combined for token in ("因果", "导致", "触发", "因此", "因为")):
        return "causality"
    if any(token in combined for token in ("反馈", "循环", "闭环", "回路")):
        return "feedback"
    if any(token in combined for token in ("边界", "过滤", "准入", "门槛", "风险")):
        return "boundary"
    if any(token in combined for token in ("转化", "迁移", "变成", "演进", "状态")):
        return "transformation"
    if any(token in combined for token in ("层级", "体系", "架构", "包含", "分层")):
        return "hierarchy"
    if any(token in combined for token in ("分流", "汇聚", "分支", "合并", "并行")):
        return "divergence"
    if any(token in combined for token in ("张力", "平衡", "拉扯", "均衡", "谈判")):
        return "tension"
    if any(token in combined for token in ("交接", "接力", "顺序", "阶段", "步骤", "流程")):
        return "sequence_handoff"
    return "connection"


def choose_composition_mode(
    *,
    asset_role: str,
    relationship_type: str,
    slide: dict[str, Any],
    order_index: int | None = None,
) -> str:
    combined = _slide_text(slide)
    if asset_role == "slide_center" or order_index == 0:
        return "cover_minimal"
    if relationship_type == "contrast" or asset_role == "story_card" and any(
        token in combined for token in ("对比", "前后")
    ):
        return "comparison"
    if any(token in combined for token in ("四步", "三阶段", "历程", "时间线", "战役", "多次", "节拍")):
        return "multi_beat"
    if asset_role == "data_story" and _has_numbers(combined):
        return "single_beat"
    return "single_beat"


def build_truth_constraints(slide: dict[str, Any]) -> list[str]:
    """Exact labels/numbers that must not be invented by the image model."""
    constraints: list[str] = []
    combined = _slide_text(slide)
    title = str(slide.get("title") or "").strip()
    if title and len(title) <= 80:
        constraints.append(f"标题/结论句必须可读且准确：{title}")
    for match in _meaningful_number_matches(combined):
        value = match.group(0).strip()
        constraint = f"数值必须准确呈现：{value}"
        if value and constraint not in constraints:
            constraints.append(constraint)
    for point in slide.get("content_points") or []:
        text = str(point).strip()
        if _has_numbers(text):
            constraints.append(f"要点数字不可编造：{text[:60]}")
    return constraints[:8]


def build_data_contract(slide: dict[str, Any], *, asset_role: str) -> dict[str, Any] | None:
    combined = _slide_text(slide)
    if asset_role != "data_story" and not _has_numbers(combined):
        return None
    exact_values: list[str] = []
    for match in _meaningful_number_matches(combined):
        value = match.group(0).strip()
        if value and value not in exact_values:
            exact_values.append(value)
    if not exact_values:
        return None
    return {
        "exact_values": exact_values[:10],
        "forbid_invented_axes": True,
        "forbid_invented_categories": True,
        "require_source_note": bool(_PERCENT_PATTERN.search(combined) or _UNIT_NUMBER_PATTERN.search(combined)),
    }


def enrich_structure_plan(
    plan: dict[str, Any],
    *,
    pack_id: str,
    slide: dict[str, Any],
    order_index: int | None = None,
) -> dict[str, Any]:
    """Inject cross-pack quality fields into a pack-specific structure plan."""
    page_role = str(plan.get("page_role") or "content")
    asset_role = route_asset_role(pack_id=pack_id, page_role=page_role, slide=slide, order_index=order_index)
    relationship_type = infer_relationship(slide, asset_role=asset_role)
    composition_mode = choose_composition_mode(
        asset_role=asset_role,
        relationship_type=relationship_type,
        slide=slide,
        order_index=order_index,
    )
    truth_constraints = build_truth_constraints(slide)
    data_contract = build_data_contract(slide, asset_role=asset_role)

    plan["asset_role"] = asset_role
    plan["asset_role_name"] = ASSET_ROLES[asset_role]
    plan["relationship_type"] = relationship_type
    plan["relationship_type_name"] = RELATIONSHIP_TYPES[relationship_type]
    plan["composition_mode"] = composition_mode
    plan["composition_mode_name"] = COMPOSITION_MODES[composition_mode]
    if truth_constraints:
        plan["truth_constraints"] = truth_constraints
    if data_contract:
        plan["data_contract"] = data_contract

    extra_lines: list[str] = []
    extra_lines.append(
        f"资产角色：{ASSET_ROLES[asset_role]}；关系类型：{RELATIONSHIP_TYPES[relationship_type]}；"
        f"构图模式：{COMPOSITION_MODES[composition_mode]}。"
    )
    if truth_constraints:
        extra_lines.append("真实约束：" + "；".join(truth_constraints[:4]) + "。")
    if data_contract:
        extra_lines.append(
            "数据契约：仅允许出现这些数值 "
            + "、".join(data_contract["exact_values"][:6])
            + "；禁止编造坐标轴、类别或额外数字。"
        )
    if extra_lines:
        plan["structure_prompt"] = (plan.get("structure_prompt") or "").rstrip() + "".join(extra_lines)
    return plan


def apply_series_continuity(
    plans: list[dict[str, Any]],
    *,
    pack_id: str,
    topic: str,
    include_visual: bool = True,
) -> list[dict[str, Any]]:
    """Deck-level throughline + inter-page variation axes (series-and-chaining)."""
    if not plans:
        return plans

    if not include_visual:
        # Style-neutral plans only describe content continuity; they never add
        # a pack palette, motif, label container, or other visual axis.
        throughline = {
            "content_anchor": "沿用项目大纲中的事实、任务与证据链",
            "topic": topic[:120],
        }
    else:
        throughline = {
            "motif": _throughline_motif(pack_id),
            "palette_base": _throughline_palette(pack_id),
            "label_style": "短标签、贴对象表面",
            "topic": topic[:120],
        }
    prev_signature: tuple[str, str, str] | None = None

    for index, plan in enumerate(plans):
        signature = (
            str(plan.get("asset_role") or ""),
            str(plan.get("relationship_type") or ""),
            str(plan.get("composition_mode") or ""),
        )
        variation_axes = (
            ["information_hierarchy", "evidence_placement"]
            if not include_visual
            else _variation_axes(index, plan, prev_signature, signature)
        )
        plan["series_position"] = index + 1
        plan["series_total"] = len(plans)
        plan["throughline"] = throughline
        plan["variation_axes"] = variation_axes
        if index == len(plans) - 1 and len(plans) > 2:
            if not include_visual:
                plan["throughline_payoff"] = f"回收整套 {topic[:40]} 的事实、任务与证据链。"
            else:
                plan["throughline_payoff"] = f"回收母题「{throughline['motif']}」，形成整套 {topic[:40]} 的收束。"
        prev_signature = signature

        if include_visual:
            continuity_line = (
                f"系列位置：第 {index + 1}/{len(plans)} 页；"
                f"共享母题：{throughline['motif']}；"
                f"本页变化轴：{', '.join(variation_axes)}。"
            )
            plan["structure_prompt"] = (plan.get("structure_prompt") or "").rstrip() + continuity_line
            if plan.get("visual_prompt"):
                plan["visual_prompt"] = plan["visual_prompt"].rstrip() + " " + continuity_line
    return plans


def swap_test_issues(plan: dict[str, Any], *, previous_plan: dict[str, Any] | None = None) -> list[tuple[str, str, str | None]]:
    """Soft QA warnings — Swap Test and template-lock detection. Returns (severity, message, field)."""
    issues: list[tuple[str, str, str | None]] = []
    anchor = str(plan.get("source_anchor") or "").strip()
    takeaway = str(plan.get("reader_takeaway") or "").strip()

    if not anchor or len(anchor) < 8:
        issues.append(("warning", "Swap Test：source_anchor 过短，页面可能无法锁定到具体内容", "source_anchor"))
    elif anchor in _GENERIC_ANCHOR_TOKENS or takeaway in _GENERIC_ANCHOR_TOKENS:
        issues.append(("warning", "Swap Test：source_anchor/reader_takeaway 过于泛化，换页后仍可套用", "source_anchor"))

    title = str(plan.get("title") or plan.get("page_role_name") or "")
    if title and anchor == title and len(anchor) < 12:
        issues.append(("warning", "Swap Test：source_anchor 仅重复标题，缺少内容特异性", "source_anchor"))

    if plan.get("operator_required") and plan.get("operator_family") not in (None, "None"):
        composition = str(plan.get("composition") or "")
        action_tokens = ("执行", "亲手", "操作", "连接", "过滤", "权衡", "检验", "搭建", "整理")
        if not any(token in composition for token in action_tokens):
            issues.append(("warning", "Swap Test：operator_required 但构图缺少可执行动作描述", "composition"))

    if previous_plan:
        same_asset = plan.get("asset_role") == previous_plan.get("asset_role")
        same_rel = plan.get("relationship_type") == previous_plan.get("relationship_type")
        same_comp = plan.get("composition_mode") == previous_plan.get("composition_mode")
        if same_asset and same_rel and same_comp:
            issues.append((
                "warning",
                "Swap Test：与上一页 asset_role/relationship/composition_mode 完全相同，存在模板锁定风险",
                "composition_mode",
            ))

    data_contract = plan.get("data_contract")
    if isinstance(data_contract, dict) and data_contract.get("exact_values"):
        if not plan.get("truth_constraints"):
            issues.append(("warning", "含 data_contract 但缺少 truth_constraints，数值真实性风险", "truth_constraints"))

    return issues


def deck_continuity_issues(plans: list[dict[str, Any]]) -> list[tuple[str, str, str | None]]:
    issues: list[tuple[str, str, str | None]] = []
    if len(plans) < 2:
        return issues

    signatures = [
        (p.get("asset_role"), p.get("relationship_type"), p.get("composition_mode"))
        for p in plans
        if p.get("asset_role") not in ("slide_center",)
    ]
    if len(signatures) >= 3:
        from collections import Counter
        most_common, count = Counter(signatures).most_common(1)[0]
        if count >= max(2, len(signatures) // 2):
            issues.append((
                "warning",
                f"Deck 连续性：{count} 页共享相同 asset/relationship/composition 签名，整套可能同质化",
                "deck.continuity",
            ))

    variation_counts = sum(1 for p in plans[1:] if len(p.get("variation_axes") or []) >= 2)
    if len(plans) >= 4 and variation_counts < len(plans) // 3:
        issues.append((
            "warning",
            "Deck 连续性：页间变化轴不足，建议增加 camera/focal/props/accent 分化",
            "deck.variation_axes",
        ))
    return issues


def _slide_text(slide: dict[str, Any]) -> str:
    return " ".join([
        str(slide.get("title") or ""),
        str(slide.get("main_message") or ""),
        str(slide.get("description_text") or ""),
        "；".join(str(item) for item in (slide.get("content_points") or [])),
    ])


def _has_numbers(text: str) -> bool:
    return any(True for _ in _meaningful_number_matches(text))


def _meaningful_number_matches(text: str):
    """Yield data-like numbers while excluding alphanumeric model identifiers.

    Examples excluded from a data contract: ESP32-S3, YOLOv8, 3D, mAP50-95.
    Standalone measurements such as 60%, 2.3 倍 or 2026年 remain eligible.
    """
    for match in _NUMBER_PATTERN.finditer(text or ""):
        if _number_is_part_of_identifier(text, match.start(), match.end()):
            continue
        yield match


def _number_is_part_of_identifier(text: str, start: int, end: int) -> bool:
    token_chars = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.+")
    left = start
    right = end
    while left > 0 and text[left - 1] in token_chars:
        left -= 1
    while right < len(text) and text[right] in token_chars:
        right += 1
    token = text[left:right]
    return bool(re.search(r"[A-Za-z]", token) and re.search(r"\d", token))


def _throughline_motif(pack_id: str) -> str:
    return {
        "paper_operators": "路径蓝丝带",
        "consulting_report": "橙色 takeaway 标注",
        "lecture_deck": "靛蓝重点批注",
        "product_launch": "中央产品聚光",
    }.get(pack_id, "统一阅读动线")


def _throughline_palette(pack_id: str) -> str:
    return {
        "paper_operators": "暖白纸面 + 路径蓝",
        "consulting_report": "深蓝灰 + 橙色强调",
        "lecture_deck": "米白底 + 靛蓝主色",
        "product_launch": "深灰舞台 + 电光蓝点缀",
    }.get(pack_id, "全稿统一色板")


def _variation_axes(
    index: int,
    plan: dict[str, Any],
    prev_signature: tuple[str, str, str] | None,
    signature: tuple[str, str, str],
) -> list[str]:
    axes_pool = ["camera", "focal_placement", "props_cluster", "palette_accent", "operator_pose", "label_container"]
    chosen: list[str] = []
    if index % 2 == 0:
        chosen.append("camera")
    if plan.get("composition_mode") == "multi_beat":
        chosen.append("focal_placement")
    if plan.get("asset_role") == "data_story":
        chosen.append("props_cluster")
    if plan.get("relationship_type") in ("contrast", "tradeoff"):
        chosen.append("palette_accent")
    if prev_signature and signature == prev_signature:
        chosen.extend(["camera", "focal_placement", "props_cluster"])
    # dedupe preserving order
    seen: set[str] = set()
    result = []
    for axis in chosen:
        if axis not in seen:
            seen.add(axis)
            result.append(axis)
    if len(result) < 2:
        for axis in axes_pool:
            if axis not in seen:
                result.append(axis)
            if len(result) >= 2:
                break
    return result[:4]

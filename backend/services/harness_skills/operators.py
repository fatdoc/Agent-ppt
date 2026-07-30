"""Paper Operators library — relationship-first selection (upstream paper-operators v2)."""
from __future__ import annotations

from typing import Any

PAPER_OPERATOR_FAMILIES: list[dict[str, str]] = [
    {"id": "thread_runner", "name": "Thread Runner / 牵线员", "function": "亲手把两个对象连接起来，表达关系、依赖或传导路径"},
    {"id": "lens_keeper", "name": "Lens Keeper / 检视员", "function": "举起放大镜或检具，检查证据、质量或细节"},
    {"id": "gate_builder", "name": "Gate Builder / 闸门员", "function": "搭建或看守一道闸门，表达准入、过滤或边界"},
    {"id": "frame_setter", "name": "Frame Setter / 装框员", "function": "为对象装上边框或定位，表达定义、范围或聚焦"},
    {"id": "color_tuner", "name": "Color Tuner / 调色员", "function": "调整色票或旋钮，表达参数调节与权重分配"},
    {"id": "light_catcher", "name": "Light Catcher / 捕光员", "function": "捕捉或引导一束光，表达洞察、发现或亮点"},
    {"id": "archive_tender", "name": "Archive Tender / 档案员", "function": "整理索引卡与抽屉，表达沉淀、归档与检索"},
    {"id": "care_folder", "name": "Care Folder / 照料员", "function": "照料、折叠或安放物件，表达关系维护与照顾"},
    {"id": "boundary_keeper", "name": "Boundary Keeper / 边界员", "function": "拉起边界线或屏风，表达界限、隔离与保护"},
    {"id": "weather_reader", "name": "Weather Reader / 读天气的人", "function": "读取天气卡或风向标，表达趋势、环境与不确定性"},
    {"id": "stack_mason", "name": "Stack Mason / 搭层员", "function": "垒起分层结构，表达层级、堆叠与体系"},
    {"id": "residue_sweeper", "name": "Residue Sweeper / 残留清理员", "function": "清扫残留物，表达清理、纠偏与收尾"},
    {"id": "tradeoff_weigher", "name": "Tradeoff Weigher / 权衡员", "function": "操作天平砝码，表达取舍、成本与优先级"},
    # Relationship operators (v2)
    {"id": "bridge_relay", "name": "Bridge Relay / 接力员", "function": "在间隙间传递或交接对象，表达顺序交接与责任转移"},
    {"id": "mirror_comparator", "name": "Mirror Comparator / 对照员", "function": "并排对照两个对象，表达对比、前后或 A/B 差异"},
    {"id": "weaver", "name": "Weaver / 编织员", "function": "编织多条路径，表达分流、汇聚或交织关系"},
    {"id": "anchor_pin", "name": "Anchor Pin / 定位员", "function": "固定基准点或不变量，表达依赖锚点与定位"},
    {"id": "cartographer", "name": "Cartographer / 制图员", "function": "在纸模地形上标注路线，表达系统地形与选项地图"},
    {"id": "valve_keeper", "name": "Valve Keeper / 阀门员", "function": "调节流量或开度，表达速率、阈值与反馈调节"},
    {"id": "mediator", "name": "Mediator / 调停员", "function": "在两种力量间维持张力平衡，表达谈判与均衡"},
    {"id": "pulse_reader", "name": "Pulse Reader / 测脉员", "function": "读取信号或指标脉动，表达反馈、健康度与早期预警"},
]

RELATIONSHIP_OPERATOR_MAP: dict[str, str] = {
    "connection": "thread_runner",
    "sequence_handoff": "bridge_relay",
    "dependency": "stack_mason",
    "causality": "gate_builder",
    "feedback": "pulse_reader",
    "contrast": "mirror_comparator",
    "tradeoff": "tradeoff_weigher",
    "hierarchy": "stack_mason",
    "transformation": "gate_builder",
    "boundary": "boundary_keeper",
    "divergence": "weaver",
    "tension": "mediator",
}

_BY_ID = {item["id"]: item for item in PAPER_OPERATOR_FAMILIES}


def choose_operator_for_relationship(relationship_type: str, slide: dict[str, Any]) -> dict[str, str]:
    """Relationship-first operator selection with domain tie-breakers."""
    combined = " ".join([
        str(slide.get("title") or ""),
        str(slide.get("main_message") or ""),
        "；".join(str(item) for item in (slide.get("content_points") or [])),
    ])
    operator_id = RELATIONSHIP_OPERATOR_MAP.get(relationship_type, "thread_runner")

    if relationship_type == "dependency" and any(token in combined for token in ("基准", "锚点", "不变")):
        operator_id = "anchor_pin"
    if relationship_type == "dependency" and any(token in combined for token in ("地图", "路线", "选项")):
        operator_id = "cartographer"
    if relationship_type == "feedback" and any(token in combined for token in ("阀门", "调节", "速率")):
        operator_id = "valve_keeper"
    if relationship_type == "hierarchy" and any(token in combined for token in ("地图", "地形", "系统")):
        operator_id = "cartographer"
    if any(token in combined for token in ("证据", "检验", "质量", "观察")):
        return _BY_ID["lens_keeper"]
    if any(token in combined for token in ("艺术", "审美", "画框", "作品")):
        return _BY_ID["frame_setter"]
    if any(token in combined for token in ("情绪", "关系", "照顾", "生活")):
        return _BY_ID["care_folder"]
    if any(token in combined for token in ("历史", "档案", "研究")):
        return _BY_ID["archive_tender"]

    return _BY_ID.get(operator_id, _BY_ID["thread_runner"])


def operator_required_for(
    *,
    asset_role: str,
    relationship_type: str,
    source_anchor: str,
    composition_mode: str,
) -> bool:
    if asset_role in ("slide_center",):
        return False
    if composition_mode == "cover_minimal":
        return False
    if len(source_anchor) > 12:
        return True
    if relationship_type in ("contrast", "tradeoff", "boundary", "dependency", "sequence_handoff"):
        return True
    return any(
        token in source_anchor
        for token in ("关系", "路径", "变化", "边界", "权衡", "证据", "系统", "流程", "转变", "依赖")
    )

"""Tests for Harness quality layer (Phase 1 + Phase 2)."""
from services.agent_mode_schemas import hard_qa_deck_page_plans, hard_qa_page_visual_plan
from services.harness_skills import get_scenario_pack
from services.harness_skills.operators import choose_operator_for_relationship
from services.harness_skills.quality import (
    build_data_contract,
    enrich_structure_plan,
    infer_relationship,
    route_asset_role,
    swap_test_issues,
)


def test_infer_relationship_tradeoff():
    slide = {"title": "成本与收益权衡", "main_message": "需要在成本与体验间取舍", "content_points": ["成本", "体验"]}
    assert infer_relationship(slide, asset_role="content_figure") == "tradeoff"


def test_choose_operator_for_relationship_contrast():
    slide = {"title": "A vs B 对比", "main_message": "两种方案差异", "content_points": []}
    op = choose_operator_for_relationship("contrast", slide)
    assert op["id"] == "mirror_comparator"


def test_route_asset_role_data_story_for_numbers():
    slide = {"title": "华东增速 2.3 倍", "main_message": "华东市场增速是整体的 2.3 倍", "content_points": []}
    role = route_asset_role(pack_id="consulting_report", page_role="evidence_chart", slide=slide)
    assert role == "data_story"


def test_build_data_contract_extracts_values():
    slide = {"title": "营收增长 12%", "main_message": "Q3 营收 1.2 亿", "content_points": []}
    contract = build_data_contract(slide, asset_role="data_story")
    assert contract is not None
    assert contract["forbid_invented_axes"] is True
    assert any("12" in v or "1.2" in v for v in contract["exact_values"])


def test_build_data_contract_ignores_model_identifiers_but_keeps_real_metrics():
    slide = {
        "title": "ESP32-S3、YOLOv8 与 3D 视觉",
        "main_message": "模型 mAP50-95 达到 60%",
        "content_points": ["硬件与算法协同"],
    }
    contract = build_data_contract(slide, asset_role="data_story")

    assert contract is not None
    assert contract["exact_values"] == ["60%"]
    assert all(value not in contract["exact_values"] for value in ("32", "3", "8", "50", "95"))


def test_all_packs_emit_harness_quality_fields():
    slide = {
        "title": "华东市场增速是整体的 2.3 倍",
        "main_message": "华东应作为下季度投放重点",
        "content_points": ["增速对比", "投放建议"],
    }
    for pack_id in ("paper_operators", "consulting_report", "lecture_deck", "product_launch"):
        pack = get_scenario_pack(pack_id)
        system = pack.deck_visual_system("主题", "受众")
        plan = pack.build_page_plan(slide, system, page_id="p1", order_index=2)
        assert plan.get("asset_role"), pack_id
        assert plan.get("relationship_type"), pack_id
        assert plan.get("composition_mode"), pack_id
        assert plan.get("truth_constraints"), pack_id


def test_paper_operators_relationship_first_operator():
    pack = get_scenario_pack("paper_operators")
    system = pack.deck_visual_system("主题", "受众")
    plan = pack.build_page_plan(
        {"title": "方案 A vs B 对比", "main_message": "两种路径的取舍", "content_points": ["对比", "差异"]},
        system,
        page_id="p1",
        order_index=2,
    )
    assert plan["relationship_type"] == "contrast"
    assert "对照员" in plan.get("operator_family", "") or plan["operator_required"]


def test_deck_continuity_adds_throughline():
    pack = get_scenario_pack("paper_operators")
    system = pack.deck_visual_system("AI 教育", "投资人")
    slides = [
        {"title": "封面", "main_message": "AI 教育机会", "content_points": ["市场"]},
        {"title": "核心机制", "main_message": "系统依赖数据反馈闭环", "content_points": ["反馈", "闭环"]},
        {"title": "增长路径", "main_message": "华东市场增速是整体的 2.3 倍", "content_points": ["增速"]},
    ]
    plans = pack.build_deck_page_plans(slides, system, topic="AI 教育")
    assert all(p.get("throughline") for p in plans)
    assert plans[0]["series_position"] == 1
    assert plans[-1].get("throughline_payoff")


def test_swap_test_flags_generic_anchor():
    plan = {
        "source_anchor": "核心洞察",
        "reader_takeaway": "核心洞察",
        "composition": "布局",
        "operator_required": False,
    }
    issues = swap_test_issues(plan)
    assert any("Swap Test" in msg for _, msg, _ in issues)


def test_hard_qa_deck_page_plans_runs():
    pack = get_scenario_pack("consulting_report")
    system = pack.deck_visual_system("季度汇报", "高管")
    slides = [
        {"title": "封面", "main_message": "2026 Q1 业务回顾", "content_points": ["汇报"]},
        {"title": "华东市场增速是整体的 2.3 倍", "main_message": "华东应重点投放", "content_points": ["2.3 倍"]},
    ]
    plans = pack.build_deck_page_plans(slides, system, topic="季度汇报")
    result = hard_qa_deck_page_plans(plans)
    assert isinstance(result.passed, bool)
    assert result.issues is not None


def test_enrich_structure_plan_injects_fields():
    plan = enrich_structure_plan(
        {"page_role": "evidence_chart", "structure_prompt": "test", "source_anchor": "华东市场增速是整体的 2.3 倍", "reader_takeaway": "华东应重点投放"},
        pack_id="consulting_report",
        slide={"title": "华东市场增速是整体的 2.3 倍", "main_message": "华东应重点投放", "content_points": ["2.3 倍"]},
        order_index=2,
    )
    assert plan["asset_role"] == "data_story"
    assert plan.get("data_contract")

from services.agent_mode_schemas import (
    SchemaValidationError,
    validate_deck_plan,
    validate_deck_visual_system,
    validate_page_visual_plan,
)
from services.harness_skills import get_scenario_pack, list_scenario_pack_ids


def test_validate_deck_plan_rejects_wrong_page_count():
    plan = {
        "title": "AI 教育",
        "audience": "投资人",
        "goal": "说明价值",
        "slides": [
            {
                "slide_id": "slide-1",
                "title": "封面",
                "main_message": "说明 AI 教育机会",
                "content_points": ["市场", "产品"],
            }
        ],
    }

    try:
        validate_deck_plan(plan, requested_page_count=2)
    except SchemaValidationError as exc:
        assert "slides count" in str(exc)
    else:
        raise AssertionError("expected SchemaValidationError")


def test_page_visual_plan_rejects_too_many_labels():
    plan = {
        "page_id": "p1",
        "strategy_id": "paper_operators",
        "source_anchor": "核心判断",
        "reader_takeaway": "读者理解核心判断",
        "composition": "高空纸模舞台",
        "labels": [str(i) for i in range(11)],
        "negative_prompts": [],
        "visual_prompt": "生成图像",
    }

    try:
        validate_page_visual_plan(plan, {"p1"})
    except SchemaValidationError as exc:
        assert "labels" in str(exc)
    else:
        raise AssertionError("expected SchemaValidationError")


def test_page_visual_plan_accepts_generic_plan_without_pack_fields():
    plan = {
        "page_id": "p1",
        "strategy_id": "consulting_report",
        "source_anchor": "华东市场增速是整体的 2.3 倍",
        "reader_takeaway": "华东应作为下季度投放重点",
        "composition": "顶部结论句标题，主体一张主导图表",
        "labels": ["华东", "增速"],
        "negative_prompts": [],
        "visual_prompt": "生成图像",
    }

    validated = validate_page_visual_plan(plan, {"p1"})
    assert validated["page_role"] == "content"
    assert validated["structure_prompt"] == ""
    assert "operator_required" not in validated


def test_page_visual_plan_rejects_invalid_material_status():
    plan = {
        "page_id": "p1",
        "strategy_id": "product_launch",
        "source_anchor": "产品揭幕",
        "reader_takeaway": "记住产品形态",
        "composition": "产品居中悬浮",
        "labels": ["新品"],
        "negative_prompts": [],
        "visual_prompt": "生成图像",
        "material_status": "fake",
    }

    try:
        validate_page_visual_plan(plan, {"p1"})
    except SchemaValidationError as exc:
        assert "material_status" in str(exc)
    else:
        raise AssertionError("expected SchemaValidationError")


def test_all_scenario_packs_produce_valid_plans():
    slide = {
        "title": "核心洞察",
        "main_message": "系统的边界决定了权衡方式",
        "content_points": ["边界", "权衡", "证据"],
    }
    for pack_id in list_scenario_pack_ids():
        pack = get_scenario_pack(pack_id)
        system = pack.deck_visual_system("主题", "受众", None)
        system = validate_deck_visual_system(system)
        assert system["quality_constraints"], pack_id
        plan = pack.build_page_plan(slide, system, page_id="p1", order_index=2)
        plan = validate_page_visual_plan(plan, {"p1"})
        assert plan["structure_prompt"], pack_id
        assert plan["style_prompt"], pack_id
        assert plan["visual_prompt"], pack_id
        assert plan["strategy_id"] == pack_id


def test_paper_operators_can_skip_operator_for_simple_slide():
    pack = get_scenario_pack("paper_operators")
    system = pack.deck_visual_system("主题", "受众")
    plan = pack.build_page_plan(
        {
            "title": "封面",
            "main_message": "欢迎",
            "content_points": ["主题"],
        },
        system,
        page_id="p1",
        order_index=0,
    )

    assert plan["strategy_id"] == "paper_operators"
    assert plan["operator_required"] is False


def test_product_launch_marks_concept_placeholder_without_materials():
    pack = get_scenario_pack("product_launch")
    system = pack.deck_visual_system("新品发布", "消费者")
    hero = pack.build_page_plan(
        {"title": "全新登场", "main_message": "产品揭幕", "content_points": ["亮相"]},
        system,
        page_id="p1",
        order_index=1,
    )
    assert hero["page_role"] == "hero_product"
    assert hero["material_status"] == "concept_placeholder"
    assert "概念渲染" in hero["structure_prompt"]

    hero_real = pack.build_page_plan(
        {
            "title": "全新登场",
            "main_message": "产品揭幕",
            "content_points": ["亮相"],
            "description_text": "主视觉 ![产品](https://cdn.example.com/p.png)",
        },
        system,
        page_id="p1",
        order_index=1,
    )
    assert hero_real["material_status"] == "real"


def test_consulting_report_infers_roles():
    pack = get_scenario_pack("consulting_report")
    system = pack.deck_visual_system("季度汇报", "高管")
    risk = pack.build_page_plan(
        {"title": "风险与应对", "main_message": "主要风险在供应链", "content_points": ["风险"]},
        system,
        page_id="p1",
        order_index=3,
    )
    assert risk["page_role"] == "risk_tradeoff"

    action = pack.build_page_plan(
        {"title": "下一步行动计划", "main_message": "三周内完成试点", "content_points": ["排期"]},
        system,
        page_id="p1",
        order_index=4,
    )
    assert action["page_role"] == "action_plan"


def test_lecture_deck_infers_roles():
    pack = get_scenario_pack("lecture_deck")
    system = pack.deck_visual_system("线性代数", "本科生")
    example = pack.build_page_plan(
        {"title": "例题：矩阵求逆", "main_message": "掌握求逆步骤", "content_points": ["题干", "步骤"]},
        system,
        page_id="p1",
        order_index=3,
    )
    assert example["page_role"] == "worked_example"
    assert "题干" in example["structure_prompt"]

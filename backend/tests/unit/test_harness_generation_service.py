from types import SimpleNamespace


def test_harness_mode_enhances_outline_and_description_context():
    from services.harness_generation_service import enhance_project_context

    project = SimpleNamespace(
        generation_mode="harness",
        harness_template="paper_operators",
    )
    context = SimpleNamespace(
        outline_requirements="保留用户原始大纲要求",
        description_requirements="保留用户原始描述要求",
    )

    enhanced = enhance_project_context(project, context)

    assert "保留用户原始大纲要求" in enhanced.outline_requirements
    assert "Harness 高质量模式已启用" in enhanced.outline_requirements
    assert "读者看完这一页应该带走什么判断" in enhanced.outline_requirements
    assert "保留用户原始描述要求" in enhanced.description_requirements
    assert "source anchor" in enhanced.description_requirements
    assert "不覆盖用户选择的模板图" in enhanced.description_requirements


def test_fast_mode_does_not_enhance_context():
    from services.harness_generation_service import enhance_project_context

    project = SimpleNamespace(
        generation_mode="fast",
        harness_template=None,
    )
    context = SimpleNamespace(
        outline_requirements="原始大纲要求",
        description_requirements="原始描述要求",
    )

    enhanced = enhance_project_context(project, context)

    assert enhanced.outline_requirements == "原始大纲要求"
    assert enhanced.description_requirements == "原始描述要求"


def test_harness_mode_creates_page_visual_plans(client):
    from models import DeckVersion, Page, PageVisualPlan, Project, db
    from services.harness_generation_service import ensure_page_visual_plans

    project = Project(
        creation_type="idea",
        idea_prompt="AI 教育产品路演",
        generation_mode="harness",
        harness_template="paper_operators",
        visual_strategy="native",
        template_style="稳重科技风",
        status="DRAFT",
    )
    db.session.add(project)
    db.session.flush()

    page = Page(project_id=project.id, order_index=0, status="DESCRIPTION_GENERATED")
    page.set_outline_content({"title": "核心价值", "points": ["降低备课成本", "提升学习反馈"]})
    page.set_description_content({"text": "说明 AI 教育产品如何把备课、练习和反馈串成闭环。"})
    db.session.add(page)
    db.session.flush()

    ensure_page_visual_plans(project, [page])
    db.session.commit()

    deck = DeckVersion.query.filter_by(project_id=project.id).first()
    visual_plan = PageVisualPlan.query.filter_by(project_id=project.id, page_id=page.id).first()

    assert deck is not None
    assert deck.status == "generated_from_harness_mode"
    assert visual_plan is not None
    assert visual_plan.strategy_id == "paper_operators"
    assert visual_plan.get_plan()["reader_takeaway"]

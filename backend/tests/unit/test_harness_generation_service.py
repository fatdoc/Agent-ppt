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


def test_harness_mode_uses_pack_specific_instructions():
    from services.harness_generation_service import enhance_project_context

    project = SimpleNamespace(
        generation_mode="harness",
        harness_template="consulting_report",
    )
    context = SimpleNamespace(outline_requirements="", description_requirements="")

    enhanced = enhance_project_context(project, context)

    assert "咨询汇报" in enhanced.outline_requirements
    assert "金字塔原理" in enhanced.outline_requirements
    assert "结论句" in enhanced.outline_requirements


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


def test_unknown_harness_template_is_not_harness_project():
    from services.harness_generation_service import is_harness_project

    project = SimpleNamespace(generation_mode="harness", harness_template="not_a_pack")
    assert is_harness_project(project) is False

    hyphen_project = SimpleNamespace(generation_mode="harness", harness_template="paper-operators")
    assert is_harness_project(hyphen_project) is True


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
    plan = visual_plan.get_plan()
    assert plan["reader_takeaway"]
    assert plan["structure_prompt"]
    assert plan["style_prompt"] == ""
    assert plan["throughline"].get("palette_base") is None


def test_harness_mode_creates_plans_for_other_packs(client):
    from models import Page, PageVisualPlan, Project, db
    from services.harness_generation_service import ensure_page_visual_plans

    project = Project(
        creation_type="idea",
        idea_prompt="季度业务汇报",
        generation_mode="harness",
        harness_template="consulting_report",
        visual_strategy="native",
        status="DRAFT",
    )
    db.session.add(project)
    db.session.flush()

    page = Page(project_id=project.id, order_index=0, status="DESCRIPTION_GENERATED")
    page.set_outline_content({"title": "华东市场增速是整体的 2.3 倍", "points": ["增速对比", "投放建议"]})
    page.set_description_content({"text": "用对比图表说明华东市场增速显著高于整体。"})
    db.session.add(page)
    db.session.flush()

    ensure_page_visual_plans(project, [page])
    db.session.commit()

    visual_plan = PageVisualPlan.query.filter_by(project_id=project.id, page_id=page.id).first()
    assert visual_plan is not None
    assert visual_plan.strategy_id == "consulting_report"
    plan = visual_plan.get_plan()
    assert "结论句" in plan["structure_prompt"] or plan["page_role"] == "cover"
    assert "咨询" in plan["style_prompt"] or "深蓝灰" in plan["style_prompt"]


def _make_harness_project_with_plan(db, Project, Page, template_style=None, visual_strategy="native"):
    from services.harness_generation_service import ensure_page_visual_plans

    project = Project(
        creation_type="idea",
        idea_prompt="AI 教育产品路演",
        generation_mode="harness",
        harness_template="paper_operators",
        visual_strategy=visual_strategy,
        template_style=template_style,
        status="DRAFT",
    )
    db.session.add(project)
    db.session.flush()

    page = Page(project_id=project.id, order_index=0, status="DESCRIPTION_GENERATED")
    page.set_outline_content({"title": "核心价值", "points": ["降低备课成本"]})
    page.set_description_content({"text": "说明 AI 教育产品如何把备课、练习和反馈串成闭环。"})
    db.session.add(page)
    db.session.flush()

    ensure_page_visual_plans(project, [page])
    db.session.commit()
    return project, page


def test_visual_guidance_uses_pack_default_visual_without_overrides(client):
    from models import Page, Project, db
    from services.visual_guidance_service import VisualGuidanceService

    project, page = _make_harness_project_with_plan(db, Project, Page)
    desc = page.get_description_content()["text"]

    guidance = VisualGuidanceService().build_visual_guidance(
        project=project,
        page_desc=desc,
        has_template_image=False,
        has_blueprint_page=False,
    )

    system = guidance["global_visual_system"]
    assert guidance["style_priority"] == "harness_pack_first"
    assert "默认视觉系统是全局视觉参考" in system
    assert "当前页结构指令" in system
    assert "当前页默认视觉指令" in system
    assert "纸模舞台" in system
    assert "成图质量硬约束" in system
    assert "4K 高分辨率" in system


def test_visual_guidance_retires_pack_visual_when_template_image_present(client):
    from models import Page, Project, db
    from services.visual_guidance_service import VisualGuidanceService

    project, page = _make_harness_project_with_plan(db, Project, Page)
    desc = page.get_description_content()["text"]

    guidance = VisualGuidanceService().build_visual_guidance(
        project=project,
        page_desc=desc,
        has_template_image=True,
        has_blueprint_page=False,
    )

    system = guidance["global_visual_system"]
    assert guidance["style_priority"] == "template_first"
    assert "场景包默认视觉整体退位" in system
    assert "当前页结构指令" in system
    assert "当前页默认视觉指令" not in system
    assert "成图质量硬约束" in system


def test_visual_guidance_keeps_structure_for_external_skill(client):
    from models import Page, Project, db
    from services.visual_guidance_service import VisualGuidanceService

    project, page = _make_harness_project_with_plan(db, Project, Page, visual_strategy="external_skill")
    project.external_style_skill_id = "my-skill"
    db.session.commit()
    desc = page.get_description_content()["text"]

    guidance = VisualGuidanceService().build_visual_guidance(
        project=project,
        page_desc=desc,
        has_template_image=False,
        has_blueprint_page=False,
    )

    system = guidance["global_visual_system"]
    assert guidance["style_priority"] == "external_skill_first"
    assert "外部风格 Skill 是唯一的全局视觉系统" in system
    assert "当前页结构指令" in system
    assert "当前页默认视觉指令" not in system
    assert "成图质量硬约束" in system


def test_visual_guidance_user_style_text_replaces_pack_visual(client):
    from models import Page, Project, db
    from services.visual_guidance_service import VisualGuidanceService

    project, page = _make_harness_project_with_plan(db, Project, Page, template_style="黑金发布会风格")
    desc = page.get_description_content()["text"]

    guidance = VisualGuidanceService().build_visual_guidance(
        project=project,
        page_desc=desc,
        has_template_image=False,
        has_blueprint_page=False,
    )

    system = guidance["global_visual_system"]
    assert "项目级风格描述：黑金发布会风格" in system
    assert "场景包默认视觉整体退位且禁止混合" in system
    assert "当前页默认视觉指令" not in system
    assert "纸模舞台" not in system
    assert "成图质量硬约束" in system

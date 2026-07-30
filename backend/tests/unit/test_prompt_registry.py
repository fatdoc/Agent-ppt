from pathlib import Path

import pytest

from services.prompt_registry import PromptRegistry, prompt_registry
from services.ai_service import ProjectContext
from services.prompts import get_outline_generation_prompt


def test_prompt_registry_loads_yaml_templates():
    templates = prompt_registry._load_templates()

    assert "outline.generation" in templates
    assert "outline.competition_precise_generation" in templates
    assert "ppt_to_ppt.generation" in templates
    assert "settings.image_model_test" in templates


def test_prompt_registry_renders_variables(tmp_path: Path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "demo.yaml").write_text(
        "prompts:\n"
        "  demo.prompt:\n"
        "    template: 'Hello {{ name }}.'\n",
        encoding="utf-8",
    )

    registry = PromptRegistry(prompts_dir)

    assert registry.render("demo.prompt", name="Banana") == "Hello Banana."


def test_prompt_registry_reports_missing_variables(tmp_path: Path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "demo.yaml").write_text(
        "prompts:\n"
        "  demo.prompt:\n"
        "    template: 'Hello {{ name }}.'\n",
        encoding="utf-8",
    )

    registry = PromptRegistry(prompts_dir)

    with pytest.raises(KeyError, match="missing variables: name"):
        registry.render("demo.prompt")


def test_precise_competition_outline_prompt_uses_enhanced_template():
    context = ProjectContext({
        "creation_type": "no_think",
        "idea_prompt": "职业教育争夺赛 PPT 生成需求",
        "competition_project_spec": {
            "project_positioning": {
                "project_name": "智慧养老守护系统",
                "track": "人工智能",
                "real_scene": "养老院护理站",
                "service_object": "老人和护理员",
                "final_deliverable": "跌倒风险评估系统和护理记录表",
                "one_sentence_intro": "完成跌倒风险识别、护理干预和记录复核",
            },
            "problem_definition": {
                "pain_points": ["夜间跌倒风险高", "护理记录不及时"],
                "project_goal": "完成风险评估、护理干预和记录复核的现场展示",
            },
            "team_roles": [
                {
                    "member": "A",
                    "role": "风险评估员",
                    "responsibility": "采集老人状态并评估风险",
                    "onsite_action": "现场采集并说明评估依据",
                },
            ],
            "skill_modules": [
                {
                    "skill_name": "风险评估",
                    "responsible_role": "A",
                    "verification_method": "评估记录表",
                    "onsite_demo_action": "现场完成风险评估",
                },
            ],
            "result_validation": {
                "deliverables": ["评估表", "护理记录表"],
                "evidence_materials": ["测试记录", "评分材料"],
            },
            "value_innovation": {
                "practical_value": "可用于养老照护课程训练",
                "innovation_points": ["形成评估-干预-复核闭环"],
            },
        },
    })

    prompt = get_outline_generation_prompt(context, language="zh")

    assert "四名选手现场操作、团队分工展示、技能证据呈现" in prompt
    assert "默认生成 39 页" in prompt
    assert "四名选手轮值技能展示" in prompt
    assert "17–33 页" in prompt
    assert "项目名称：智慧养老守护系统" in prompt
    assert "* A 风险评估员：采集老人状态并评估风险；现场动作：现场采集并说明评估依据" in prompt
    assert "优先使用 parts 结构" in prompt
    assert "请使用全中文输出" in prompt

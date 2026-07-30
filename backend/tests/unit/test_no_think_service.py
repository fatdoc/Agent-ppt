"""Tests for NoThinkService option normalization."""


def test_no_think_options_from_dict_normalizes_known_fields():
    from services.no_think_service import NoThinkOptions

    options = NoThinkOptions.from_dict({
        "project_name": "智慧养老守护系统",
        "industry_or_track": "人工智能",
        "real_scene": "养老院",
        "target_user": "老人和护理员",
        "team_task_description": "四名学生分别负责评估、护理、记录和成果展示",
    })

    assert options.project_name == "智慧养老守护系统"
    assert options.industry_or_track == "人工智能"
    assert options.real_scene == "养老院"
    assert options.target_user == "老人和护理员"
    assert options.team_task_description == "四名学生分别负责评估、护理、记录和成果展示"


def test_normalize_prompt_combines_sparse_input_and_options():
    from services.no_think_service import NoThinkOptions, NoThinkService

    options = NoThinkOptions(
        project_name="智慧养老守护系统",
        industry_or_track="人工智能",
        real_scene="养老院",
        target_user="老人和护理员",
        team_task_description="四名学生分别负责评估、护理、记录和成果展示",
    )

    prompt = NoThinkService().normalize_prompt("解决老人跌倒风险", options)

    assert "职业教育争夺赛 PPT 生成需求" in prompt
    assert "世界职业院校技能大赛/争夺赛" in prompt
    assert "项目想法/项目简介：解决老人跌倒风险" in prompt
    assert "项目名称：智慧养老守护系统" in prompt
    assert "赛道/专业方向：人工智能" in prompt
    assert "真实场景：养老院" in prompt
    assert "服务对象/使用对象：老人和护理员" in prompt
    assert "四名选手分工：四名学生分别负责评估、护理、记录和成果展示" in prompt

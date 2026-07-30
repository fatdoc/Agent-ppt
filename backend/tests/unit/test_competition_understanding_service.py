from services.competition_understanding_service import CompetitionUnderstandingService


def test_build_from_raw_text_extracts_vocational_competition_spec():
    service = CompetitionUnderstandingService()

    result = service.build_from_raw_text(
        """
        项目名称：智慧养老守护系统
        赛道：人工智能
        真实场景：养老院护理站
        服务对象：老人和护理员
        最终成果形态：跌倒风险评估系统和护理记录表
        痛点：老人夜间跌倒风险高；护理记录不及时
        项目目标：完成风险评估、护理干预和记录复核的现场展示
        A：风险评估，现场采集老人状态并评估
        B：护理干预，现场干预并处置异常
        C：记录归档，现场记录并归档
        D：成果复核，现场复核评分材料
        技能模块：风险评估；护理干预；记录归档；成果复核
        成果清单：评估表；护理记录表；演示清单
        证据材料：测试记录；评分材料；用户反馈
        实用性：可用于养老照护课程训练和岗位现场展示
        """
    )

    spec = result.spec

    assert spec["competition_context"]["competition_name"] == "世界职业院校技能大赛/争夺赛"
    assert spec["project_positioning"]["project_name"] == "智慧养老守护系统"
    assert spec["project_positioning"]["real_scene"] == "养老院护理站"
    assert spec["project_positioning"]["service_object"] == "老人和护理员"
    assert spec["team_roles"][0]["role"] == "风险评估"
    assert len(spec["skill_modules"]) == 4
    assert result.input_quality in {"ready", "needs_review"}


def test_build_from_structured_input_reports_missing_fields():
    service = CompetitionUnderstandingService()

    result = service.build_from_structured_input({
        "project_positioning": {
            "project_name": "温室大棚巡检项目",
            "track": "现代农业",
        },
    })

    assert "project_positioning.real_scene" in result.missing_fields
    assert "problem_definition.pain_points" in result.missing_fields
    assert result.input_quality == "insufficient"


def test_build_from_raw_text_filters_markdown_field_pollution_and_preserves_base_spec():
    service = CompetitionUnderstandingService()

    result = service.build_from_raw_text(
        """
        # 智慧养老跌倒风险智能评估系统

        ## 一、项目定位
        - 项目名称：智慧养老跌倒风险智能评估系统
        - 赛道/专业方向：人工智能
        - 真实场景：养老院护理站，护理员每天需要对老人进行跌倒风险巡查和记录。

        ### 痛点
        - 项目名称：智慧养老跌倒风险智能评估系统

        ## 四、技能展示模块
        ### 技能模块 1：项目名称：智慧养老跌倒风险智能评估系统
        - 工作任务：项目名称：智慧养老跌倒风险智能评估系统

        ## 五、成果验证
        ### 成果清单
        - 项目名称：智慧养老跌倒风险智能评估系统
        """,
        base_spec={
            "problem_definition": {
                "pain_points": ["护理员依靠经验判断，评估标准不统一"],
            },
            "skill_modules": [
                {"skill_name": "老人跌倒风险信息采集", "work_task": "采集老人基础风险信息"},
            ],
            "result_validation": {
                "deliverables": ["跌倒风险评估表"],
            },
        },
    )

    spec = result.spec

    assert spec["project_positioning"]["track"] == "人工智能"
    assert spec["problem_definition"]["pain_points"] == ["护理员依靠经验判断，评估标准不统一"]
    assert spec["skill_modules"][0]["skill_name"] == "老人跌倒风险信息采集"
    assert spec["result_validation"]["deliverables"] == ["跌倒风险评估表"]


def test_build_from_raw_text_does_not_use_project_request_as_content_lists():
    service = CompetitionUnderstandingService()

    result = service.build_from_raw_text(
        """
        【当前用户手动修订后的 Markdown 稿件】
        【用户本轮修改意见或新增资料】
        我想做一个世界职业院校技能大赛项目，项目名称叫智慧养老跌倒风险智能评估系统，赛道是人工智能。
        真实场景是养老院护理站，护理员每天需要对老人进行跌倒风险巡查。
        """
    )

    spec = result.spec

    assert spec["project_positioning"]["project_name"] == "智慧养老跌倒风险智能评估系统"
    assert spec["project_positioning"]["track"] == "人工智能"
    assert spec["project_positioning"]["real_scene"] == "养老院护理站，护理员每天需要对老人进行跌倒风险巡查"
    assert spec["project_positioning"]["one_sentence_intro"] == ""
    assert spec["problem_definition"]["pain_points"] == []
    assert spec["skill_modules"] == []
    assert spec["result_validation"]["deliverables"] == []


def test_build_from_raw_text_handles_project_naming_dialogue_without_pollution():
    service = CompetitionUnderstandingService()

    first_turn = service.build_from_raw_text("你好，我想做AI农业种番茄的一个方向，你帮我起一个项目名称。")
    first_spec = first_turn.spec

    assert first_spec["project_positioning"]["project_name"] == ""
    assert first_spec["project_positioning"]["track"] == "现代农业"
    assert first_spec["project_positioning"]["one_sentence_intro"] == ""

    second_turn = service.build_from_raw_text(
        "行啊，名称，项目名称就叫AI番茄管家。",
        base_spec=first_spec,
    )
    second_spec = second_turn.spec

    assert second_spec["project_positioning"]["project_name"] == "AI番茄管家"
    assert second_spec["project_positioning"]["track"] == "现代农业"
    assert second_spec["project_positioning"]["one_sentence_intro"] == ""


def test_build_from_raw_text_does_not_use_teacher_dialogue_as_one_sentence_intro():
    service = CompetitionUnderstandingService()

    result = service.build_from_raw_text(
        """
        老师不太懂大赛怎么写，我这边有个大概想法：想做一个中职护理专业的项目，项目名称暂定“校园老年照护风险评估实训系统”。赛道可以放在养老照护或人工智能方向。真实场景是社区养老服务站和学校护理实训室。服务对象是社区老人、护理员和护理专业学生。项目想解决的问题是：老师平时带学生做老人照护训练时，风险评估标准不统一，学生只会背流程不会现场判断，照护记录也容易漏。
        """
    )

    spec = result.spec

    assert spec["project_positioning"]["project_name"] == "校园老年照护风险评估实训系统"
    assert spec["project_positioning"]["real_scene"] == "社区养老服务站和学校护理实训室"
    assert spec["project_positioning"]["service_object"] == "社区老人、护理员和护理专业学生"
    assert spec["project_positioning"]["one_sentence_intro"] == ""


def test_build_from_raw_text_cleans_polluted_saved_base_spec():
    service = CompetitionUnderstandingService()

    result = service.build_from_raw_text(
        """
        请补充价值创新：创新点包括将人工智能用于养老院跌倒风险评估。
        优化前后对比从评估效率、记录完整性、交接准确性三个方面说明。
        """,
        base_spec={
            "project_positioning": {
                "project_name": "智慧养老跌倒风险智能评估系统",
                "track": "人工智能",
                "one_sentence_intro": "【当前用户手动修订后的 Markdown 稿件】 【用户本轮修改意见或新增资料】 我想做一个世界职业院校技能大赛项目，项目名称叫智慧养老跌倒风险智能评估系统，赛道是人工智能",
            },
            "problem_definition": {
                "pain_points": ["我想做一个世界职业院校技能大赛项目，项目名称叫智慧养老跌倒风险智能评估系统，赛道是人工智能。"],
            },
            "skill_modules": [
                {
                    "skill_name": "我想做一个世界职业院校技能大赛项目，项目名称叫智慧养老跌倒风",
                    "work_task": "我想做一个世界职业院校技能大赛项目，项目名称叫智慧养老跌倒风",
                    "responsible_role": "A",
                },
                {
                    "skill_name": "真实场景是养老院护理站，护理员每天需要对老人进行跌倒风险巡查",
                    "work_task": "真实场景是养老院护理站，护理员每天需要对老人进行跌倒风险巡查",
                    "responsible_role": "C",
                },
            ],
            "result_validation": {
                "deliverables": ["我想做一个世界职业院校技能大赛项目，项目名称叫智慧养老跌倒风险智能评估系统，赛道是人工智能。"],
                "evidence_materials": ["真实场景是养老院护理站，护理员每天需要对老人进行跌倒风险巡查"],
            },
            "value_innovation": {
                "innovation_points": ["优化前后对比从评估效率", "记录完整性", "交接准确性三个方面说明。"],
            },
        },
    )

    spec = result.spec

    assert spec["project_positioning"]["one_sentence_intro"] == ""
    assert spec["problem_definition"]["pain_points"] == []
    assert spec["skill_modules"] == []
    assert spec["result_validation"]["deliverables"] == []
    assert spec["result_validation"]["evidence_materials"] == []
    assert spec["value_innovation"]["innovation_points"] == ["将人工智能用于养老院跌倒风险评估"]


def test_build_from_raw_text_parses_deliverables_without_polluting_other_sections():
    service = CompetitionUnderstandingService()

    result = service.build_from_raw_text(
        "最终成果形态包括跌倒风险智能评估系统、护理建议单、交接班记录表、风险等级看板、现场操作评分材料包。"
    )

    spec = result.spec

    assert spec["project_positioning"]["final_deliverable"] == "跌倒风险智能评估系统；护理建议单；交接班记录表；风险等级看板；现场操作评分材料包"
    assert spec["problem_definition"]["pain_points"] == []
    assert spec["skill_modules"] == []
    assert spec["result_validation"]["deliverables"] == [
        "跌倒风险智能评估系统",
        "护理建议单",
        "交接班记录表",
        "风险等级看板",
        "现场操作评分材料包",
    ]


def test_build_from_raw_text_parses_natural_skill_module_blocks():
    service = CompetitionUnderstandingService()

    result = service.build_from_raw_text(
        """
        技能模块 1 是老人跌倒风险信息采集，负责角色是 A，工作任务是采集老人基础信息、身体状况、行动能力、用药情况和环境风险因素。现场演示动作是模拟护理员问询老人并录入系统。验证方式是检查信息采集表是否完整准确。预期证据是老人跌倒风险信息采集表和现场录入截图。工具设备材料是电脑、平板、老人样例数据和风险采集表。

        技能模块 2 是跌倒风险智能评估，负责角色是 B，工作任务是根据采集数据自动计算风险等级。现场演示动作是点击评估按钮，系统输出低风险、中风险或高风险。验证方式是对比系统评估结果和人工评分结果。预期证据是风险评分结果、风险等级说明和评估过程截图。工具设备材料是智能评估系统、测试数据和评分规则表。
        """
    )

    modules = result.spec["skill_modules"]

    assert len(modules) == 2
    assert modules[0]["skill_name"] == "老人跌倒风险信息采集"
    assert modules[0]["responsible_role"] == "A"
    assert modules[0]["work_task"] == "采集老人基础信息、身体状况、行动能力、用药情况和环境风险因素"
    assert modules[0]["onsite_demo_action"] == "模拟护理员问询老人并录入系统"
    assert modules[1]["skill_name"] == "跌倒风险智能评估"
    assert modules[1]["responsible_role"] == "B"


def test_build_from_raw_text_parses_inline_player_actions_without_cross_copy():
    service = CompetitionUnderstandingService()

    result = service.build_from_raw_text(
        """
        项目名称：乡村农产品智能分拣与溯源实训平台
        赛道：现代农业
        真实场景：县域农产品初加工车间
        服务对象：合作社分拣员、质检员和电商运营人员
        最终成果形态：视觉分拣原型、溯源标签生成工具、质量检测记录表
        痛点：人工分拣标准不统一；批次质量记录容易缺失；电商发货前溯源标签制作慢
        项目目标：现场完成样品采集、瑕疵识别、等级判定、标签生成和结果复核
        A选手负责样品采集与工位安全检查，现场动作是在分拣台采集苹果样品并记录批次。B选手负责视觉识别模型调用，现场动作是上传样品图片并解释瑕疵识别结果。C选手负责等级判定与标签生成，现场动作是根据识别结果生成等级标签和二维码。D选手负责质量复核与数据归档，现场动作是导出检测记录表并说明复核依据。
        """
    )

    roles = result.spec["team_roles"]

    assert roles[0]["role"] == "样品采集与工位安全检查"
    assert roles[0]["onsite_action"] == "在分拣台采集苹果样品并记录批次"
    assert roles[1]["role"] == "视觉识别模型调用"
    assert roles[1]["onsite_action"] == "上传样品图片并解释瑕疵识别结果"
    assert roles[2]["role"] == "等级判定与标签生成"
    assert roles[2]["onsite_action"] == "根据识别结果生成等级标签和二维码"
    assert roles[3]["role"] == "质量复核与数据归档"
    assert roles[3]["onsite_action"] == "导出检测记录表并说明复核依据"


def test_build_from_raw_text_parses_inline_skill_modules_without_duplicates_or_truncation():
    service = CompetitionUnderstandingService()

    result = service.build_from_raw_text(
        """
        技能模块：图像采集与预处理，由A负责，现场演示动作是在工位完成光照校准和样品拍摄，验证方式为采集记录；瑕疵识别与等级判定，由B和C负责，现场演示动作是上传图片并生成等级结果，验证方式为识别结果截图；溯源记录归档，由D负责，现场演示动作是导出批次检测记录表，验证方式为记录表。
        成果清单：视觉分拣原型；溯源标签生成工具；质量检测记录表
        证据材料：现场操作录屏；识别结果截图；检测记录表
        """
    )

    modules = result.spec["skill_modules"]

    assert len(modules) == 3
    assert [module["skill_name"] for module in modules] == [
        "图像采集与预处理",
        "瑕疵识别与等级判定",
        "溯源记录归档",
    ]
    assert modules[0]["responsible_role"] == "A"
    assert modules[0]["onsite_demo_action"] == "在工位完成光照校准和样品拍摄"
    assert modules[0]["verification_method"] == "采集记录"
    assert modules[1]["responsible_role"] == "B和C"
    assert modules[1]["onsite_demo_action"] == "上传图片并生成等级结果"
    assert modules[1]["verification_method"] == "识别结果截图"
    assert modules[2]["responsible_role"] == "D"
    assert modules[2]["onsite_demo_action"] == "导出批次检测记录表"
    assert modules[2]["verification_method"] == "记录表"

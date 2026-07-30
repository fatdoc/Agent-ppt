from services.competition_document_edit_service import CompetitionDocumentEditService
from services.competition_spec_state import normalize_spec_state, unwrap_spec_state
from services.competition_understanding_service import CompetitionUnderstandingService


class FakeAIService:
    def __init__(self, payload):
        self.payload = payload
        self.prompt = ""

    def generate_json(self, prompt, thinking_budget=1000):
        self.prompt = prompt
        return self.payload


def test_document_edit_service_applies_semantic_update_and_preserves_context():
    validator = CompetitionUnderstandingService()
    current = validator.build_from_structured_input({
        "project_positioning": {
            "project_name": "智慧养老守护系统",
            "track": "人工智能",
            "real_scene": "养老院护理站",
            "service_object": "老人和护理员",
            "final_deliverable": "评估系统和记录表",
        },
        "problem_definition": {
            "pain_points": ["跌倒风险高", "护理记录不及时"],
            "project_goal": "现场完成评估和复核",
        },
        "team_roles": [
            {"member": "A", "role": "风险评估", "responsibility": "采集状态", "onsite_action": "现场采集"},
            {"member": "B", "role": "护理干预", "responsibility": "处置异常", "onsite_action": "现场干预"},
        ],
        "skill_modules": [
            {"skill_name": "风险评估", "responsible_role": "A", "verification_method": "记录表", "onsite_demo_action": "现场评估"},
        ],
        "result_validation": {
            "deliverables": ["评估表"],
            "evidence_materials": ["测试记录"],
        },
        "value_innovation": {
            "practical_value": "可用于养老照护实训",
        },
    }).spec
    fake_ai = FakeAIService({
        "reply": "已改名，并删除护理记录不及时这个痛点，其他内容保持不变。",
        "ops": [
            {"type": "set", "path": "project_positioning.project_name", "value": "智慧康养风险管家"},
            {"type": "remove_list_item", "path": "problem_definition.pain_points", "value": "护理记录不及时"},
        ],
        "change_summary": ["项目名称：智慧养老守护系统 -> 智慧康养风险管家"],
        "destructive_changes": ["删除痛点：护理记录不及时"],
        "needs_confirmation": True,
        "questions": [],
    })

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(
        "把项目名称改成智慧康养风险管家，删除痛点：护理记录不及时",
        current_spec=current,
    )

    assert "把项目名称改成智慧康养风险管家" in fake_ai.prompt
    assert "当前字段状态稿件 JSON" in fake_ai.prompt
    assert "ops" in fake_ai.prompt
    assert "不要输出整份 updated_spec" in fake_ai.prompt
    spec = unwrap_spec_state(result.spec)
    assert result.spec["project_positioning"]["project_name"]["state"] == "soft"
    assert spec["project_positioning"]["project_name"] == "智慧康养风险管家"
    assert spec["project_positioning"]["real_scene"] == "养老院护理站"
    assert spec["problem_definition"]["pain_points"] == ["跌倒风险高"]
    assert result.destructive_changes == ["删除痛点：护理记录不及时"]
    assert result.needs_confirmation is True


def test_document_edit_service_blocks_instruction_pollution_and_forces_explicit_rename():
    validator = CompetitionUnderstandingService()
    current = validator.build_from_structured_input({
        "project_positioning": {
            "project_name": "智慧养老守护系统",
            "track": "人工智能",
            "real_scene": "养老院护理站",
            "service_object": "老人和护理员",
            "final_deliverable": "跌倒风险评估系统、护理建议单和交接班记录表",
        },
        "problem_definition": {
            "pain_points": ["夜间跌倒风险高", "护理记录不及时", "交接信息容易遗漏"],
            "project_goal": "现场完成风险采集、智能评估、护理干预和成果复核",
        },
        "team_roles": [
            {"member": "A", "role": "风险信息采集", "responsibility": "风险信息采集", "onsite_action": "现场采集"},
            {"member": "B", "role": "智能评估", "responsibility": "智能评估", "onsite_action": "现场评估"},
            {"member": "C", "role": "护理干预", "responsibility": "护理干预", "onsite_action": "现场干预"},
            {"member": "D", "role": "记录归档和成果复核", "responsibility": "记录归档和成果复核", "onsite_action": "现场复核"},
        ],
        "result_validation": {
            "deliverables": ["跌倒风险评估系统", "护理建议单", "交接班记录表"],
            "evidence_materials": ["测试记录"],
        },
    }).spec
    fake_ai = FakeAIService({
        "reply": "已改名。",
        "ops": [
            {"type": "set", "path": "project_positioning.project_name", "value": "智慧康养风险管家"},
            {"type": "set", "path": "project_positioning.one_sentence_intro", "value": "项目名称改成“智慧康养风险管家”，其他内容不要动"},
            {"type": "set", "path": "project_positioning.track", "value": "养老照护"},
        ],
        "change_summary": ["项目名称更新"],
    })

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(
        "项目名称改成“智慧康养风险管家”，其他内容不要动。",
        current_spec=current,
    )

    spec = unwrap_spec_state(result.spec)
    assert spec["project_positioning"]["project_name"] == "智慧康养风险管家"
    assert spec["project_positioning"]["track"] == "人工智能"
    assert spec["project_positioning"]["real_scene"] == "养老院护理站"
    assert spec["project_positioning"]["service_object"] == "老人和护理员"
    assert spec["project_positioning"]["one_sentence_intro"] == ""
    assert spec["problem_definition"]["pain_points"] == ["夜间跌倒风险高", "护理记录不及时", "交接信息容易遗漏"]
    assert spec["team_roles"][1]["role"] == "智能评估"
    assert [item["code"] for item in result.rejected_ops] == ["OUT_OF_SCOPE", "OUT_OF_SCOPE"]


def test_document_edit_service_does_not_update_first_turn_without_ops():
    fake_ai = FakeAIService({
        "reply": "已理解项目资料。",
        "ops": [],
    })
    first_turn = (
        "我做一个世界职业院校技能大赛项目，项目名称叫“智慧养老守护系统”，赛道是人工智能。"
        "真实场景是养老院护理站，服务对象是老人和护理员。最终成果是跌倒风险评估系统、护理建议单和交接班记录表。"
        "痛点是夜间跌倒风险高、护理记录不及时、交接信息容易遗漏。"
        "项目目标是在现场完成风险采集、智能评估、护理干预和成果复核。\n"
        "A选手负责风险信息采集，B选手负责智能评估，C选手负责护理干预，D选手负责记录归档和成果复核。"
    )

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(first_turn)

    spec = unwrap_spec_state(result.spec)
    assert spec["project_positioning"]["project_name"] == ""
    assert spec["project_positioning"]["track"] == ""
    assert spec["project_positioning"]["real_scene"] == ""
    assert spec["project_positioning"]["service_object"] == ""
    assert spec["problem_definition"]["pain_points"] == []
    assert spec["team_roles"][0]["role"] == ""
    assert result.ops == []
    assert result.rejected_ops == []


def test_document_edit_service_first_turn_depends_on_model_ops():
    first_turn = (
        "项目名称：乡村农产品智能分拣与溯源实训平台\n"
        "赛道：现代农业\n"
        "真实场景：县域农产品初加工车间\n"
        "服务对象：合作社分拣员、质检员和电商运营人员\n"
        "最终成果形态：视觉分拣原型、溯源标签生成工具、质量检测记录表\n"
        "痛点：人工分拣标准不统一；批次质量记录容易缺失；电商发货前溯源标签制作慢\n"
        "项目目标：现场完成样品采集、瑕疵识别、等级判定、标签生成和结果复核\n"
        "A选手负责样品采集与工位安全检查，现场动作是在分拣台采集苹果样品并记录批次。"
        "B选手负责视觉识别模型调用，现场动作是上传样品图片并解释瑕疵识别结果。"
        "C选手负责等级判定与标签生成，现场动作是根据识别结果生成等级标签和二维码。"
        "D选手负责质量复核与数据归档，现场动作是导出检测记录表并说明复核依据。\n"
        "技能模块：图像采集与预处理，由A负责，现场演示动作是在工位完成光照校准和样品拍摄，验证方式为采集记录；"
        "瑕疵识别与等级判定，由B和C负责，现场演示动作是上传图片并生成等级结果，验证方式为识别结果截图；"
        "溯源记录归档，由D负责，现场演示动作是导出批次检测记录表，验证方式为记录表。\n"
        "成果清单：视觉分拣原型；溯源标签生成工具；质量检测记录表\n"
        "证据材料：现场操作录屏；识别结果截图；检测记录表"
    )
    fake_ai = FakeAIService({
        "reply": "已整理项目资料。",
        "ops": [
            {"type": "set", "path": "team_roles.B.onsite_action", "value": "在分拣台采集苹果样品并记录批次"},
            {"type": "set", "path": "team_roles.C.onsite_action", "value": "在分拣台采集苹果样品并记录批次"},
            {"type": "set", "path": "team_roles.D.onsite_action", "value": "在分拣台采集苹果样品并记录批次"},
            {
                "type": "add_skill_module",
                "value": {
                    "skill_name": "图像采集与预处理",
                    "responsible_role": "A",
                    "onsite_demo_action": "在工位完成光照校准和样品拍摄",
                    "verification_method": "采集记录",
                },
            },
        ],
    })

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(first_turn)

    spec = unwrap_spec_state(result.spec)
    roles = spec["team_roles"]
    modules = spec["skill_modules"]

    assert roles[1]["onsite_action"] == "在分拣台采集苹果样品并记录批次"
    assert roles[2]["onsite_action"] == "在分拣台采集苹果样品并记录批次"
    assert roles[3]["onsite_action"] == "在分拣台采集苹果样品并记录批次"
    assert len(result.spec["skill_modules"]) == 4
    assert [module["id"] for module in result.spec["skill_modules"]] == ["sm_01", "sm_02", "sm_03", "sm_04"]
    assert [module["skill_name"] for module in modules[:3]] == ["图像采集与预处理", "", ""]
    assert {
        "team_roles.B.onsite_action",
        "team_roles.C.onsite_action",
        "team_roles.D.onsite_action",
        "skill_modules[sm_01].skill_name",
        "skill_modules[sm_01].responsible_role",
        "skill_modules[sm_01].onsite_demo_action",
        "skill_modules[sm_01].verification_method",
    }.issubset({op["path"] for op in result.ops})


def test_document_edit_service_updates_role_and_action_separately():
    validator = CompetitionUnderstandingService()
    current = validator.build_from_structured_input({
        "project_positioning": {
            "project_name": "智慧康养风险管家",
            "track": "人工智能",
            "real_scene": "养老院护理站",
            "service_object": "老人和护理员",
        },
        "team_roles": [
            {"member": "A", "role": "风险信息采集", "responsibility": "风险信息采集", "onsite_action": ""},
            {"member": "B", "role": "智能评估", "responsibility": "智能评估", "onsite_action": ""},
            {"member": "C", "role": "护理干预", "responsibility": "护理干预", "onsite_action": ""},
            {"member": "D", "role": "记录归档和成果复核", "responsibility": "记录归档和成果复核", "onsite_action": ""},
        ],
    }).spec
    fake_ai = FakeAIService({
        "reply": "已更新 B 选手。",
        "ops": [
            {"type": "set", "path": "team_roles.B.role", "value": "风险等级判定"},
            {"type": "set", "path": "team_roles.B.responsibility", "value": "风险等级判定"},
            {"type": "set", "path": "team_roles.B.onsite_action", "value": "点击评估按钮并解释高风险原因"},
        ],
    })

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(
        "B选手角色和负责内容不要再写“智能评估”，都改成“风险等级判定”，现场动作改成“点击评估按钮并解释高风险原因”。A、C、D不要改。",
        current_spec=current,
    )

    roles = unwrap_spec_state(result.spec)["team_roles"]
    assert roles[0]["role"] == "风险信息采集"
    assert roles[1]["role"] == "风险等级判定"
    assert roles[1]["responsibility"] == "风险等级判定"
    assert roles[1]["onsite_action"] == "点击评估按钮并解释高风险原因"
    assert roles[2]["role"] == "护理干预"
    assert roles[3]["role"] == "记录归档和成果复核"


def test_document_edit_service_applies_block_scoped_patch():
    validator = CompetitionUnderstandingService()
    current = validator.build_from_structured_input({
        "project_positioning": {
            "project_name": "智慧康养风险管家",
            "track": "人工智能",
            "real_scene": "养老院护理站",
            "service_object": "老人和护理员",
        },
        "team_roles": [
            {"member": "A", "role": "风险信息采集", "responsibility": "风险信息采集", "onsite_action": "现场采集"},
            {"member": "B", "role": "智能评估", "responsibility": "智能评估", "onsite_action": "现场评估"},
        ],
    }).spec
    fake_ai = FakeAIService({
        "reply": "已更新 A 选手现场动作。",
        "ops": [
            {
                "block_id": "team_roles.A",
                "type": "set",
                "path": "team_roles.A.onsite_action",
                "value": "在护理站现场采集老人跌倒、压疮和用药风险信息",
            },
        ],
    })

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(
        "把 A 选手现场动作改得更具体。",
        current_spec=current,
    )

    assert "可用 block_id" in fake_ai.prompt
    assert "team_roles.A" in fake_ai.prompt
    spec = unwrap_spec_state(result.spec)
    assert spec["team_roles"][0]["onsite_action"] == "在护理站现场采集老人跌倒、压疮和用药风险信息"
    assert spec["team_roles"][1]["onsite_action"] == "现场评估"


def test_document_edit_service_filters_out_of_scope_patch_when_user_says_only():
    validator = CompetitionUnderstandingService()
    current = validator.build_from_structured_input({
        "project_positioning": {
            "project_name": "智慧康养风险管家",
            "track": "人工智能",
            "real_scene": "养老院护理站",
            "service_object": "老人和护理员",
        },
        "team_roles": [
            {"member": "A", "role": "风险信息采集", "responsibility": "风险信息采集", "onsite_action": "现场采集"},
            {"member": "B", "role": "智能评估", "responsibility": "智能评估", "onsite_action": "现场评估"},
        ],
    }).spec
    fake_ai = FakeAIService({
        "reply": "已更新。",
        "ops": [
            {
                "block_id": "team_roles.A",
                "type": "set",
                "path": "team_roles.B.onsite_action",
                "value": "错误跨区修改",
            },
            {
                "block_id": "project_positioning",
                "type": "set",
                "path": "problem_definition.project_goal",
                "value": "错误跨区目标",
            },
        ],
    })

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(
        "只改 A 选手现场动作。",
        current_spec=current,
    )

    spec = unwrap_spec_state(result.spec)
    assert spec["team_roles"][0]["onsite_action"] == "现场采集"
    assert spec["team_roles"][1]["onsite_action"] == "现场评估"
    assert spec["problem_definition"]["project_goal"] == ""


def test_document_edit_service_preserve_other_content_still_applies_target_ops():
    validator = CompetitionUnderstandingService()
    current = validator.build_from_structured_input({
        "project_positioning": {
            "project_name": "智慧养老守护系统",
            "track": "人工智能",
            "real_scene": "养老院护理站",
            "service_object": "老人和护理员",
        },
        "team_roles": [
            {"member": "A", "role": "风险信息采集", "responsibility": "风险信息采集", "onsite_action": "现场采集"},
            {"member": "B", "role": "智能评估", "responsibility": "智能评估", "onsite_action": "现场评估"},
        ],
    }).spec
    fake_ai = FakeAIService({
        "reply": "已更新 A 选手现场动作。",
        "ops": [
            {
                "block_id": "team_roles.A",
                "type": "set",
                "path": "team_roles.A.onsite_action",
                "value": "在护理站现场完成跌倒风险采集并填写记录表",
            },
            {
                "block_id": "project_positioning",
                "type": "set",
                "path": "project_positioning.project_name",
                "value": "不应该被改名",
            },
        ],
    })

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(
        "只改 A 选手现场动作，其他内容不要动：A选手现场动作改成在护理站现场完成跌倒风险采集并填写记录表。",
        current_spec=current,
    )

    spec = unwrap_spec_state(result.spec)
    assert spec["team_roles"][0]["onsite_action"] == "在护理站现场完成跌倒风险采集并填写记录表"
    assert spec["team_roles"][1]["onsite_action"] == "现场评估"
    assert spec["project_positioning"]["project_name"] == "智慧养老守护系统"


def test_document_edit_service_preserve_other_content_allows_skill_module_ops():
    current = normalize_spec_state({
        "project_positioning": {
            "project_name": "智慧养老守护系统",
            "real_scene": "养老院护理站",
        },
    })
    fake_ai = FakeAIService({
        "reply": "已更新技能模块。",
        "ops": [
            {
                "block_id": "skill_modules[sm_01]",
                "type": "set",
                "path": "skill_modules[sm_01].skill_name",
                "value": "风险信息采集",
            },
            {
                "block_id": "skill_modules[sm_01]",
                "type": "set",
                "path": "skill_modules[sm_01].responsible_role",
                "value": "A选手",
            },
            {
                "block_id": "project_positioning",
                "type": "set",
                "path": "project_positioning.project_name",
                "value": "不应该被改名",
            },
        ],
    })

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(
        "只改技能模块，其他内容不要动：技能模块1名称改成风险信息采集，负责角色为A选手。",
        current_spec=current,
    )

    spec = unwrap_spec_state(result.spec)
    assert spec["skill_modules"][0]["skill_name"] == "风险信息采集"
    assert spec["skill_modules"][0]["responsible_role"] == "A选手"
    assert spec["project_positioning"]["project_name"] == "智慧养老守护系统"
    assert {op["path"] for op in result.ops} == {
        "skill_modules[sm_01].skill_name",
        "skill_modules[sm_01].responsible_role",
    }
    assert [op["code"] for op in result.rejected_ops] == ["OUT_OF_SCOPE"]


def test_document_edit_service_rejects_cross_block_path():
    validator = CompetitionUnderstandingService()
    current = validator.build_from_structured_input({
        "project_positioning": {
            "project_name": "智慧养老守护系统",
            "track": "人工智能",
            "real_scene": "养老院护理站",
            "service_object": "老人和护理员",
        },
    }).spec
    fake_ai = FakeAIService({
        "reply": "已改名。",
        "ops": [
            {
                "block_id": "problem_definition",
                "type": "set",
                "path": "project_positioning.project_name",
                "value": "智慧康养风险管家",
            },
        ],
    })

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(
        "项目名称改成智慧康养风险管家，其他内容不要动。",
        current_spec=current,
    )

    assert unwrap_spec_state(result.spec)["project_positioning"]["project_name"] == "智慧养老守护系统"
    assert result.ops == []
    assert result.rejected_ops[0]["code"] == "CROSS_BLOCK_PATH"


def test_document_edit_service_rejects_ai_patch_to_locked_field():
    current = normalize_spec_state({
        "project_positioning": {
            "project_name": {
                "value": "智慧养老守护系统",
                "state": "locked",
                "last_modified_by": "user",
                "updated_at": 1,
            },
            "real_scene": "养老院护理站",
        },
    })
    fake_ai = FakeAIService({
        "reply": "尝试改名。",
        "ops": [
            {
                "block_id": "project_positioning",
                "type": "set",
                "path": "project_positioning.project_name",
                "value": "智慧康养风险管家",
                "source": "ai",
            },
        ],
    })

    result = CompetitionDocumentEditService(fake_ai).build_from_user_message(
        "把项目名称改成智慧康养风险管家。",
        current_spec=current,
    )

    assert unwrap_spec_state(result.spec)["project_positioning"]["project_name"] == "智慧养老守护系统"
    assert result.spec["project_positioning"]["project_name"]["state"] == "locked"
    assert "已被用户锁定" in result.reply


def test_document_edit_service_user_patch_locks_field_and_edits_list_item():
    current = normalize_spec_state({
        "problem_definition": {
            "pain_points": ["跌倒风险高", "护理记录不及时"],
        },
    })
    result = CompetitionDocumentEditService(FakeAIService({"ops": []})).apply_user_patch(
        current,
        [
            {
                "type": "set_at",
                "block_id": "problem_definition",
                "path": "problem_definition.pain_points",
                "index": 1,
                "value": "护理记录滞后",
                "source": "user",
            }
        ],
    )

    assert unwrap_spec_state(result.spec)["problem_definition"]["pain_points"] == ["跌倒风险高", "护理记录滞后"]
    assert result.spec["problem_definition"]["pain_points"]["state"] == "locked"

"""Tests for NoThinkService option normalization."""


def test_no_think_options_from_dict_normalizes_known_fields():
    from services.no_think_service import NoThinkOptions

    options = NoThinkOptions.from_dict({
        "scenario": "路演汇报",
        "density": "信息密度高",
        "page_count": "8页",
        "style_template": "咨询风",
        "extra_instruction": "突出商业价值",
    })

    assert options.scenario == "路演汇报"
    assert options.density == "信息密度高"
    assert options.page_count == "8页"
    assert options.style_template == "咨询风"
    assert options.extra_instruction == "突出商业价值"


def test_normalize_prompt_combines_sparse_input_and_options():
    from services.no_think_service import NoThinkOptions, NoThinkService

    options = NoThinkOptions(
        scenario="内部培训",
        density="简洁",
        page_count="5页",
        style_template="现代商务",
        extra_instruction="适合新员工",
    )

    prompt = NoThinkService().normalize_prompt("AI 工具入门", options)

    assert "用户补充说明：AI 工具入门" in prompt
    assert "用途场景：内部培训" in prompt
    assert "内容密度：简洁" in prompt
    assert "页数倾向：5页" in prompt
    assert "风格模板：现代商务" in prompt
    assert "额外说明：适合新员工" in prompt

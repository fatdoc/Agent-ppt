import importlib.util
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


schemas = _load_module("agent_mode_schemas", "services/agent_mode_schemas.py")
strategies = _load_module("visual_strategies", "services/visual_strategies.py")

SchemaValidationError = schemas.SchemaValidationError
validate_deck_plan = schemas.validate_deck_plan
validate_page_visual_plan = schemas.validate_page_visual_plan
PaperOperatorsStrategy = strategies.PaperOperatorsStrategy


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
        "operator_required": True,
        "operator_family": "Thread Runner / 牵线员",
        "metaphor_world": "纸模工作台",
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


def test_paper_operators_can_skip_operator_for_simple_slide():
    strategy = PaperOperatorsStrategy()
    system = strategy.deck_visual_system("主题", "受众")
    plan = strategy.build_page_plan(
        {
            "title": "封面",
            "main_message": "欢迎",
            "content_points": ["主题"],
        },
        system,
        page_id="p1",
    )

    assert plan["strategy_id"] == "paper_operators"
    assert plan["operator_required"] is False

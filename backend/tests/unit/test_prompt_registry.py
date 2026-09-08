from pathlib import Path

import pytest

from services.prompt_registry import PromptRegistry, prompt_registry
from services.prompts import (
    LANGUAGE_CONFIG,
    get_language_instruction,
    get_narration_generation_prompt,
)


def test_prompt_registry_loads_yaml_templates():
    templates = prompt_registry._load_templates()

    assert "outline.generation" in templates
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


@pytest.mark.parametrize("language", ["zh", "ja", "en", "auto"])
def test_language_config_references_registered_prompts(language):
    config = LANGUAGE_CONFIG[language]
    instruction_id = config["instruction_id"]

    if instruction_id is None:
        assert get_language_instruction(language) == ""
    else:
        assert prompt_registry.get(instruction_id)
        assert get_language_instruction(language)


@pytest.mark.parametrize(
    ("language", "expected_instruction"),
    [
        ("zh", "请使用全中文输出"),
        ("ja", "すべて日本語で出力してください"),
        ("en", "Please output all in English"),
    ],
)
def test_narration_prompt_uses_language_registry_contract(language, expected_instruction):
    prompt = get_narration_generation_prompt(
        pages=[{
            "page_index": 1,
            "title": "Contract smoke test",
            "points": ["Prompt registry"],
            "description_text": "Verify the narration template contract.",
        }],
        language=language,
    )

    assert expected_instruction in prompt
    assert "{{" not in prompt
    assert "=== SLIDE 1 ===" in prompt

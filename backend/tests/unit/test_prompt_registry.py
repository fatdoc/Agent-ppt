from pathlib import Path

import pytest

from services.prompt_registry import PromptRegistry, prompt_registry


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


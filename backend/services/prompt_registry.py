"""
YAML-backed prompt registry.

Prompt text is product configuration. Python code should select templates and
prepare variables, while the wording itself lives under backend/prompts.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


_PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class PromptRegistry:
    """Load prompt templates from YAML files and render by prompt id."""

    def __init__(self, prompts_dir: Path | None = None):
        backend_dir = Path(__file__).resolve().parents[1]
        self.prompts_dir = prompts_dir or (backend_dir / "prompts")
        self._templates: Dict[str, str] | None = None

    def render(self, prompt_id: str, **variables: Any) -> str:
        template = self.get(prompt_id)
        missing = sorted(
            {
                match.group(1)
                for match in _PLACEHOLDER_RE.finditer(template)
                if match.group(1) not in variables
            }
        )
        if missing:
            raise KeyError(f"Prompt '{prompt_id}' missing variables: {', '.join(missing)}")

        def replace(match: re.Match[str]) -> str:
            value = variables.get(match.group(1), "")
            return "" if value is None else str(value)

        return _PLACEHOLDER_RE.sub(replace, template)

    def get(self, prompt_id: str) -> str:
        templates = self._load_templates()
        try:
            return templates[prompt_id]
        except KeyError as exc:
            raise KeyError(f"Prompt template not found: {prompt_id}") from exc

    def reload(self) -> None:
        self._templates = None

    def _load_templates(self) -> Dict[str, str]:
        if self._templates is not None:
            return self._templates

        templates: Dict[str, str] = {}
        if not self.prompts_dir.exists():
            logger.warning("Prompt directory does not exist: %s", self.prompts_dir)
            self._templates = templates
            return templates

        for path in sorted(self.prompts_dir.glob("*.yaml")):
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            prompts = data.get("prompts", {})
            if not isinstance(prompts, dict):
                raise ValueError(f"Invalid prompts section in {path}")

            for prompt_id, value in prompts.items():
                if isinstance(value, dict):
                    template = value.get("template")
                else:
                    template = value
                if not isinstance(template, str):
                    raise ValueError(f"Prompt '{prompt_id}' in {path} must be a string/template")
                if prompt_id in templates:
                    raise ValueError(f"Duplicate prompt id '{prompt_id}' in {path}")
                templates[prompt_id] = template

        self._templates = templates
        logger.info("Loaded %s prompt templates from %s", len(templates), self.prompts_dir)
        return templates


prompt_registry = PromptRegistry()


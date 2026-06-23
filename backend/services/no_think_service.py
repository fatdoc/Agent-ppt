"""No Think PPT option normalization."""
from __future__ import annotations

from dataclasses import dataclass

from services.prompt_registry import prompt_registry


@dataclass
class NoThinkOptions:
    scenario: str | None = None
    color_tone: str | None = None
    density: str | None = None
    page_count: str | None = None
    style_template: str | None = None
    extra_instruction: str | None = None

    @classmethod
    def from_dict(cls, data: dict | None) -> "NoThinkOptions":
        data = data or {}
        return cls(
            scenario=_clean(data.get("scenario")),
            color_tone=_clean(data.get("color_tone")),
            density=_clean(data.get("density")),
            page_count=_clean(data.get("page_count")),
            style_template=_clean(data.get("style_template")),
            extra_instruction=_clean(data.get("extra_instruction")),
        )


class NoThinkService:
    """Translate sparse no-think inputs into a structured generation prompt."""

    def normalize_prompt(self, extra_instruction: str | None, options: NoThinkOptions) -> str:
        parts = ["No Think PPT 生成需求："]

        cleaned_extra = _clean(extra_instruction)
        if cleaned_extra:
            parts.append(f"用户补充说明：{cleaned_extra}")
        if options.scenario:
            parts.append(f"用途场景：{options.scenario}")
        if options.color_tone:
            parts.append(f"色调感觉：{options.color_tone}")
        if options.density:
            parts.append(f"内容密度：{options.density}")
        if options.page_count:
            parts.append(f"页数倾向：{options.page_count}")
        if options.style_template:
            parts.append(f"风格模板：{options.style_template}")
        if options.extra_instruction:
            parts.append(f"额外说明：{options.extra_instruction}")

        parts.append(prompt_registry.render("no_think.final_instruction").strip())
        return "\n".join(parts)


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

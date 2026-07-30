"""Vocational quick-start option normalization."""
from __future__ import annotations

from dataclasses import dataclass

from services.prompt_registry import prompt_registry


@dataclass
class NoThinkOptions:
    project_name: str | None = None
    industry_or_track: str | None = None
    real_scene: str | None = None
    target_user: str | None = None
    team_task_description: str | None = None

    @classmethod
    def from_dict(cls, data: dict | None) -> "NoThinkOptions":
        data = data or {}
        return cls(
            project_name=_clean(data.get("project_name")),
            industry_or_track=_clean(data.get("industry_or_track")),
            real_scene=_clean(data.get("real_scene")),
            target_user=_clean(data.get("target_user")),
            team_task_description=_clean(data.get("team_task_description")),
        )


class NoThinkService:
    """Translate sparse no-think inputs into a structured generation prompt."""

    def normalize_prompt(self, extra_instruction: str | None, options: NoThinkOptions) -> str:
        parts = [
            "职业教育争夺赛 PPT 生成需求：",
            "固定主线：世界职业院校技能大赛/争夺赛现场展示。",
            "生成目标：把“项目/任务 + 岗位现场 + 服务对象”转成可现场展示、可被评委快速理解的竞赛 PPT 输入语义。",
            "表达边界：不是营销型路演、不是公司汇报、不是产品广告；要突出职业岗位任务、真实服务场景、学生技能实施过程和现场成果证明。",
        ]

        cleaned_extra = _clean(extra_instruction)
        if cleaned_extra:
            parts.append(f"项目想法/项目简介：{cleaned_extra}")
        if options.project_name:
            parts.append(f"项目名称：{options.project_name}")
        if options.industry_or_track:
            parts.append(f"赛道/专业方向：{options.industry_or_track}")
        if options.real_scene:
            parts.append(f"真实场景：{options.real_scene}")
        if options.target_user:
            parts.append(f"服务对象/使用对象：{options.target_user}")
        if options.team_task_description:
            parts.append(f"四名选手分工：{options.team_task_description}")

        parts.append(prompt_registry.render("no_think.final_instruction").strip())
        return "\n".join(parts)


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

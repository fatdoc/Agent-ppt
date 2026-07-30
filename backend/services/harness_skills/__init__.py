"""Harness scenario pack registry.

场景包 = 结构 Skill（页面角色/叙事/构图骨架/素材策略/校验）+ 默认视觉 Skill（色板/材质/画风）。
产品层默认绑定，架构层解耦：用户上传模板图、填写风格文字或启用外部风格 Skill 时，
只替换视觉层，结构层与质量约束照常生效。
"""
from __future__ import annotations

from services.harness_skills.base import (
    GENERIC_FORBIDDEN_PATTERNS,
    IMAGE_QUALITY_CONSTRAINTS,
    ScenarioPack,
    StructureSkill,
    VisualStyleSkill,
)
from services.harness_skills import consulting_report, lecture_deck, paper_operators, product_launch


_PACKS: dict[str, ScenarioPack] = {}
for _module in (paper_operators, lecture_deck, product_launch, consulting_report):
    _pack = _module.build_pack()
    _PACKS[_pack.pack_id] = _pack


def normalize_pack_id(pack_id: str | None) -> str | None:
    if not pack_id:
        return None
    normalized = str(pack_id).strip().replace("-", "_")
    return normalized or None


def get_scenario_pack(pack_id: str | None) -> ScenarioPack | None:
    normalized = normalize_pack_id(pack_id)
    if not normalized:
        return None
    return _PACKS.get(normalized)


def list_scenario_packs() -> list[ScenarioPack]:
    return list(_PACKS.values())


def list_scenario_pack_ids() -> list[str]:
    return list(_PACKS.keys())


__all__ = [
    "GENERIC_FORBIDDEN_PATTERNS",
    "IMAGE_QUALITY_CONSTRAINTS",
    "HARNESS_MAX_PAGE_COUNT",
    "ScenarioPack",
    "StructureSkill",
    "VisualStyleSkill",
    "get_scenario_pack",
    "list_scenario_packs",
    "list_scenario_pack_ids",
    "normalize_pack_id",
]

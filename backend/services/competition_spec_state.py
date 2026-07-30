"""Field-state CompetitionProjectSpec helpers."""
from __future__ import annotations

import copy
import time
import re
from typing import Any


FIELD_STATES = {"empty", "soft", "locked"}
MODIFIED_BY = {"ai", "user"}
ROLE_KEYS = ("A", "B", "C", "D")
SKILL_IDS = ("sm_01", "sm_02", "sm_03", "sm_04")
LIST_PATHS = {
    "problem_definition.pain_points",
    "result_validation.deliverables",
    "result_validation.evidence_materials",
    "value_innovation.innovation_points",
}
SCALAR_PATHS = {
    "project_positioning.project_name",
    "project_positioning.subtitle",
    "project_positioning.track",
    "project_positioning.real_scene",
    "project_positioning.service_object",
    "project_positioning.final_deliverable",
    "project_positioning.one_sentence_intro",
    "problem_definition.need_source",
    "problem_definition.current_method",
    "problem_definition.problem_consequences",
    "problem_definition.project_goal",
    "result_validation.test_data",
    "result_validation.before_after_comparison",
    "result_validation.user_feedback",
    "result_validation.quality_evaluation",
    "value_innovation.practical_value",
    "value_innovation.teaching_value",
    "value_innovation.vocational_scene_value",
    "value_innovation.sustainability",
}
TEAM_FIELDS = {"role", "responsibility", "onsite_action", "related_skill_modules"}
SKILL_FIELDS = {
    "skill_name",
    "responsible_role",
    "work_task",
    "onsite_demo_action",
    "verification_method",
    "expected_evidence",
    "tools_or_equipment",
}


def now_ms() -> int:
    return int(time.time() * 1000)


def empty_field(value: str = "", *, source: str = "ai", state: str | None = None) -> dict[str, Any]:
    text = _string(value)
    return {
        "value": text,
        "state": state if state in FIELD_STATES else ("soft" if text else "empty"),
        "last_modified_by": source if source in MODIFIED_BY else "ai",
        "updated_at": now_ms(),
    }


def empty_list_field(value: list[str] | None = None, *, source: str = "ai", state: str | None = None) -> dict[str, Any]:
    items = _string_list(value or [])
    return {
        "value": items,
        "state": state if state in FIELD_STATES else ("soft" if items else "empty"),
        "last_modified_by": source if source in MODIFIED_BY else "ai",
        "updated_at": now_ms(),
    }


def create_empty_spec() -> dict[str, Any]:
    return {
        "competition_context": {
            "competition_name": "世界职业院校技能大赛/争夺赛",
            "generation_goal": "1小时现场技能展示作战稿",
            "presentation_mode": "现场展示",
            "audience": ["评委", "企业导师", "现场观摩人员"],
        },
        "source_material": {"raw_text": "", "file_id": None, "filename": None},
        "project_positioning": {
            "project_name": empty_field(),
            "subtitle": empty_field(),
            "track": empty_field(),
            "real_scene": empty_field(),
            "service_object": empty_field(),
            "final_deliverable": empty_field(),
            "one_sentence_intro": empty_field(),
        },
        "problem_definition": {
            "need_source": empty_field(),
            "current_method": empty_field(),
            "pain_points": empty_list_field(),
            "problem_consequences": empty_field(),
            "project_goal": empty_field(),
        },
        "team_roles": {key: _empty_team_member() for key in ROLE_KEYS},
        "skill_modules": [_empty_skill_module(skill_id) for skill_id in SKILL_IDS],
        "result_validation": {
            "deliverables": empty_list_field(),
            "evidence_materials": empty_list_field(),
            "test_data": empty_field(),
            "before_after_comparison": empty_field(),
            "user_feedback": empty_field(),
            "quality_evaluation": empty_field(),
        },
        "value_innovation": {
            "practical_value": empty_field(),
            "innovation_points": empty_list_field(),
            "teaching_value": empty_field(),
            "vocational_scene_value": empty_field(),
            "sustainability": empty_field(),
        },
        "constraints": {
            "avoid": ["营销路演", "融资汇报", "泛泛产品介绍", "虚构收益数据"],
            "must_show": ["岗位现场", "服务对象", "四名选手动作", "技能模块", "成果证据"],
        },
    }


def normalize_spec_state(raw_spec: Any) -> dict[str, Any]:
    base = create_empty_spec()
    raw = raw_spec if isinstance(raw_spec, dict) else {}

    if isinstance(raw.get("competition_context"), dict):
        base["competition_context"].update({
            key: raw["competition_context"].get(key) or base["competition_context"].get(key)
            for key in ("competition_name", "generation_goal", "presentation_mode", "audience")
        })
    if isinstance(raw.get("source_material"), dict):
        base["source_material"].update({
            "raw_text": _string(raw["source_material"].get("raw_text")),
            "file_id": raw["source_material"].get("file_id"),
            "filename": raw["source_material"].get("filename"),
        })
    if isinstance(raw.get("constraints"), dict):
        base["constraints"] = {
            "avoid": _string_list(raw["constraints"].get("avoid")),
            "must_show": _string_list(raw["constraints"].get("must_show")),
        }

    positioning = raw.get("project_positioning") if isinstance(raw.get("project_positioning"), dict) else {}
    base["project_positioning"] = {
        "project_name": _wrap_field(positioning.get("project_name")),
        "subtitle": _wrap_field(positioning.get("subtitle")),
        "track": _wrap_field(positioning.get("track") or positioning.get("industry")),
        "real_scene": _wrap_field(positioning.get("real_scene")),
        "service_object": _wrap_field(positioning.get("service_object")),
        "final_deliverable": _wrap_field(positioning.get("final_deliverable")),
        "one_sentence_intro": _wrap_field(positioning.get("one_sentence_intro")),
    }

    problem = raw.get("problem_definition") if isinstance(raw.get("problem_definition"), dict) else {}
    base["problem_definition"] = {
        "need_source": _wrap_field(problem.get("need_source")),
        "current_method": _wrap_field(problem.get("current_method")),
        "pain_points": _wrap_list_field(problem.get("pain_points")),
        "problem_consequences": _wrap_field(problem.get("problem_consequences")),
        "project_goal": _wrap_field(problem.get("project_goal")),
    }

    roles = raw.get("team_roles")
    base["team_roles"] = {
        key: _normalize_team_member(_legacy_role(roles, key))
        for key in ROLE_KEYS
    }

    modules = raw.get("skill_modules")
    base["skill_modules"] = [
        _normalize_skill_module(_legacy_module(modules, skill_id, index), skill_id)
        for index, skill_id in enumerate(SKILL_IDS)
    ]

    validation = raw.get("result_validation") if isinstance(raw.get("result_validation"), dict) else {}
    base["result_validation"] = {
        "deliverables": _wrap_list_field(validation.get("deliverables")),
        "evidence_materials": _wrap_list_field(validation.get("evidence_materials")),
        "test_data": _wrap_field(validation.get("test_data")),
        "before_after_comparison": _wrap_field(validation.get("before_after_comparison")),
        "user_feedback": _wrap_field(validation.get("user_feedback")),
        "quality_evaluation": _wrap_field(validation.get("quality_evaluation")),
    }

    value = raw.get("value_innovation") if isinstance(raw.get("value_innovation"), dict) else {}
    base["value_innovation"] = {
        "practical_value": _wrap_field(value.get("practical_value")),
        "innovation_points": _wrap_list_field(value.get("innovation_points")),
        "teaching_value": _wrap_field(value.get("teaching_value")),
        "vocational_scene_value": _wrap_field(value.get("vocational_scene_value")),
        "sustainability": _wrap_field(value.get("sustainability")),
    }
    return base


def unwrap_spec_state(raw_spec: Any) -> dict[str, Any]:
    spec = normalize_spec_state(raw_spec)
    return {
        "competition_context": copy.deepcopy(spec.get("competition_context") or {}),
        "source_material": copy.deepcopy(spec.get("source_material") or {}),
        "project_positioning": {
            "project_name": field_value(spec["project_positioning"]["project_name"]),
            "subtitle": field_value(spec["project_positioning"]["subtitle"]),
            "track": field_value(spec["project_positioning"]["track"]),
            "industry": field_value(spec["project_positioning"]["track"]),
            "real_scene": field_value(spec["project_positioning"]["real_scene"]),
            "service_object": field_value(spec["project_positioning"]["service_object"]),
            "final_deliverable": field_value(spec["project_positioning"]["final_deliverable"]),
            "one_sentence_intro": field_value(spec["project_positioning"]["one_sentence_intro"]),
        },
        "problem_definition": {
            "pain_points": list_value(spec["problem_definition"]["pain_points"]),
            "need_source": field_value(spec["problem_definition"]["need_source"]),
            "current_method": field_value(spec["problem_definition"]["current_method"]),
            "problem_consequences": field_value(spec["problem_definition"]["problem_consequences"]),
            "project_goal": field_value(spec["problem_definition"]["project_goal"]),
        },
        "team_roles": [
            {
                "member": key,
                "name": "",
                "role": field_value(spec["team_roles"][key]["role"]),
                "responsibility": field_value(spec["team_roles"][key]["responsibility"]),
                "onsite_action": field_value(spec["team_roles"][key]["onsite_action"]),
                "related_skill_modules": _split_related_modules(field_value(spec["team_roles"][key]["related_skill_modules"])),
            }
            for key in ROLE_KEYS
        ],
        "skill_modules": [
            {
                "id": module.get("id"),
                "skill_name": field_value(module["skill_name"]),
                "responsible_role": field_value(module["responsible_role"]),
                "work_task": field_value(module["work_task"]),
                "onsite_demo_action": field_value(module["onsite_demo_action"]),
                "verification_method": field_value(module["verification_method"]),
                "expected_evidence": field_value(module["expected_evidence"]),
                "tools_or_equipment": field_value(module["tools_or_equipment"]),
            }
            for module in spec["skill_modules"]
        ],
        "result_validation": {
            "deliverables": list_value(spec["result_validation"]["deliverables"]),
            "evidence_materials": list_value(spec["result_validation"]["evidence_materials"]),
            "test_data": field_value(spec["result_validation"]["test_data"]),
            "before_after_comparison": field_value(spec["result_validation"]["before_after_comparison"]),
            "user_feedback": field_value(spec["result_validation"]["user_feedback"]),
            "quality_evaluation": field_value(spec["result_validation"]["quality_evaluation"]),
        },
        "value_innovation": {
            "practical_value": field_value(spec["value_innovation"]["practical_value"]),
            "innovation_points": list_value(spec["value_innovation"]["innovation_points"]),
            "teaching_value": field_value(spec["value_innovation"]["teaching_value"]),
            "vocational_scene_value": field_value(spec["value_innovation"]["vocational_scene_value"]),
            "sustainability": field_value(spec["value_innovation"]["sustainability"]),
        },
        "constraints": copy.deepcopy(spec.get("constraints") or {}),
    }


def apply_patch_ops_to_spec_state(
    raw_spec: Any,
    ops: list[dict[str, Any]],
    *,
    source: str = "ai",
    allowed_blocks: set[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    spec = normalize_spec_state(raw_spec)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw_op in ops:
        for op in _expand_legacy_op(spec, raw_op):
            op_source = op.get("source") if op.get("source") in MODIFIED_BY else source
            op["source"] = op_source
            valid, reason = _validate_op(spec, op, allowed_blocks)
            if not valid:
                rejected.append({"op": op, "code": reason[0], "message": reason[1]})
                continue
            _apply_valid_op(spec, op)
            accepted.append(op)
    return spec, accepted, rejected


def merge_plain_values_into_state(raw_state: Any, raw_plain: Any, *, source: str = "ai") -> dict[str, Any]:
    state = normalize_spec_state(raw_state)
    plain = normalize_spec_state(raw_plain)
    for path in sorted(SCALAR_PATHS | LIST_PATHS):
        plain_field = _field_at_path(plain, path)
        state_field = _field_at_path(state, path)
        if plain_field is None or state_field is None:
            continue
        if state_field.get("state") == "locked" and source == "ai":
            continue
        if state_field.get("value") != plain_field.get("value"):
            state_field["value"] = copy.deepcopy(plain_field.get("value"))
            _touch_field(state_field, source)
    for key in ROLE_KEYS:
        for field in TEAM_FIELDS:
            path = f"team_roles.{key}.{field}"
            plain_field = _field_at_path(plain, path)
            state_field = _field_at_path(state, path)
            if plain_field is not None and state_field is not None and state_field.get("value") != plain_field.get("value"):
                if state_field.get("state") == "locked" and source == "ai":
                    continue
                state_field["value"] = copy.deepcopy(plain_field.get("value"))
                _touch_field(state_field, source)
    for module_id in SKILL_IDS:
        for field in SKILL_FIELDS:
            path = f"skill_modules[{module_id}].{field}"
            plain_field = _field_at_path(plain, path)
            state_field = _field_at_path(state, path)
            if plain_field is not None and state_field is not None and state_field.get("value") != plain_field.get("value"):
                if state_field.get("state") == "locked" and source == "ai":
                    continue
                state_field["value"] = copy.deepcopy(plain_field.get("value"))
                _touch_field(state_field, source)
    return state


def field_value(field: Any) -> str:
    if isinstance(field, dict) and "value" in field:
        return _string(field.get("value"))
    return _string(field)


def list_value(field: Any) -> list[str]:
    if isinstance(field, dict) and "value" in field:
        return _string_list(field.get("value"))
    return _string_list(field)


def canonical_path(path: Any) -> str:
    if not isinstance(path, str):
        return ""
    path = path.strip()
    legacy_skill = re.match(r"^skill_modules\.(\d+)\.([a-z_]+)$", path)
    if legacy_skill:
        index = int(legacy_skill.group(1))
        if 0 <= index < len(SKILL_IDS):
            return f"skill_modules[{SKILL_IDS[index]}].{legacy_skill.group(2)}"
    return path


def infer_block_id(path: str) -> str:
    if path.startswith("project_positioning."):
        return "project_positioning"
    if path.startswith("problem_definition."):
        return "problem_definition"
    team_match = re.match(r"^(team_roles\.[ABCD])\.", path)
    if team_match:
        return team_match.group(1)
    skill_match = re.match(r"^(skill_modules\[sm_0[1-4]\])\.", path)
    if skill_match:
        return skill_match.group(1)
    if path.startswith("result_validation."):
        return "result_validation"
    if path.startswith("value_innovation."):
        return "value_innovation"
    return ""


def all_patch_blocks() -> set[str]:
    return {
        "project_positioning",
        "problem_definition",
        "result_validation",
        "value_innovation",
        *(f"team_roles.{key}" for key in ROLE_KEYS),
        *(f"skill_modules[{skill_id}]" for skill_id in SKILL_IDS),
    }


def _empty_team_member() -> dict[str, Any]:
    return {
        "role": empty_field(),
        "responsibility": empty_field(),
        "onsite_action": empty_field(),
        "related_skill_modules": empty_field(),
    }


def _empty_skill_module(skill_id: str) -> dict[str, Any]:
    return {
        "id": skill_id,
        "skill_name": empty_field(),
        "responsible_role": empty_field(),
        "work_task": empty_field(),
        "onsite_demo_action": empty_field(),
        "verification_method": empty_field(),
        "expected_evidence": empty_field(),
        "tools_or_equipment": empty_field(),
    }


def _is_field(value: Any) -> bool:
    return isinstance(value, dict) and "value" in value and "state" in value


def _wrap_field(value: Any) -> dict[str, Any]:
    if _is_field(value):
        text = _string(value.get("value"))
        return {
            "value": text,
            "state": value.get("state") if value.get("state") in FIELD_STATES else ("soft" if text else "empty"),
            "last_modified_by": value.get("last_modified_by") if value.get("last_modified_by") in MODIFIED_BY else "ai",
            "updated_at": value.get("updated_at") if isinstance(value.get("updated_at"), (int, float)) else now_ms(),
        }
    text = _string(value)
    return empty_field(text)


def _wrap_list_field(value: Any) -> dict[str, Any]:
    if _is_field(value):
        items = _string_list(value.get("value"))
        return {
            "value": items,
            "state": value.get("state") if value.get("state") in FIELD_STATES else ("soft" if items else "empty"),
            "last_modified_by": value.get("last_modified_by") if value.get("last_modified_by") in MODIFIED_BY else "ai",
            "updated_at": value.get("updated_at") if isinstance(value.get("updated_at"), (int, float)) else now_ms(),
        }
    return empty_list_field(_string_list(value))


def _normalize_team_member(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "role": _wrap_field(raw.get("role")),
        "responsibility": _wrap_field(raw.get("responsibility")),
        "onsite_action": _wrap_field(raw.get("onsite_action")),
        "related_skill_modules": _wrap_field("；".join(_string_list(raw.get("related_skill_modules"))) if isinstance(raw.get("related_skill_modules"), list) else raw.get("related_skill_modules")),
    }


def _normalize_skill_module(raw: Any, skill_id: str) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    module = _empty_skill_module(skill_id)
    for field in SKILL_FIELDS:
        module[field] = _wrap_field(raw.get(field))
    return module


def _legacy_role(roles: Any, key: str) -> dict[str, Any]:
    if isinstance(roles, dict) and isinstance(roles.get(key), dict):
        return roles[key]
    if isinstance(roles, list):
        for role in roles:
            if isinstance(role, dict) and role.get("member") == key:
                return role
    return {}


def _legacy_module(modules: Any, skill_id: str, index: int) -> dict[str, Any]:
    if isinstance(modules, list):
        for module in modules:
            if isinstance(module, dict) and module.get("id") == skill_id:
                return module
        if 0 <= index < len(modules) and isinstance(modules[index], dict):
            return modules[index]
    return {}


def _validate_op(spec: dict[str, Any], op: dict[str, Any], allowed_blocks: set[str] | None) -> tuple[bool, tuple[str, str]]:
    op_type = op.get("type") or op.get("op")
    op["type"] = op_type
    if op_type not in {"set", "append", "remove_at", "set_at"}:
        return False, ("INVALID_OP", "不支持的 patch 操作")
    path = canonical_path(op.get("path"))
    op["path"] = path
    block_id = _canonical_block_id(op.get("block_id") or infer_block_id(path))
    op["block_id"] = block_id
    source = op.get("source") if op.get("source") in MODIFIED_BY else "ai"
    op["source"] = source

    if not block_id or not path.startswith(block_id):
        return False, ("CROSS_BLOCK_PATH", f"path 必须以 block_id 开头：{block_id} -> {path}")
    if path not in LIST_PATHS and path not in SCALAR_PATHS and not _is_team_path(path) and not _is_skill_path(path):
        return False, ("INVALID_PATH", f"非法字段路径：{path}")
    if source == "ai" and allowed_blocks is not None and not _block_allowed(block_id, allowed_blocks):
        return False, ("OUT_OF_SCOPE", f"本轮不允许修改 {block_id}")
    target = _field_at_path(spec, path)
    if target is None:
        return False, ("INVALID_PATH", f"非法字段路径：{path}")
    if target.get("state") == "locked" and source == "ai":
        return False, ("FIELD_LOCKED", f"该字段已锁定：{path}")
    if op_type in {"append", "remove_at", "set_at"} and path not in LIST_PATHS:
        return False, ("INVALID_PATH", f"列表操作只能用于列表字段：{path}")
    if op_type in {"remove_at", "set_at"}:
        index = op.get("index")
        if not isinstance(index, int) or index < 0 or index >= len(target.get("value") or []):
            return False, ("INVALID_INDEX", f"列表下标非法：{path}[{index}]")
    return True, ("", "")


def _apply_valid_op(spec: dict[str, Any], op: dict[str, Any]) -> None:
    target = _field_at_path(spec, op["path"])
    if target is None:
        return
    if op["type"] == "set":
        target["value"] = _string(op.get("value"))
    elif op["type"] == "append":
        target["value"].append(_string(op.get("value")))
    elif op["type"] == "remove_at":
        del target["value"][op["index"]]
    elif op["type"] == "set_at":
        target["value"][op["index"]] = _string(op.get("value"))
    _touch_field(target, op["source"])


def _touch_field(field: dict[str, Any], source: str) -> None:
    if source == "user":
        field["state"] = "locked"
    elif field.get("state") == "empty":
        field["state"] = "soft"
    field["last_modified_by"] = source if source in MODIFIED_BY else "ai"
    field["updated_at"] = now_ms()


def _field_at_path(spec: dict[str, Any], path: str) -> dict[str, Any] | None:
    path = canonical_path(path)
    if path in SCALAR_PATHS or path in LIST_PATHS:
        section, field = path.split(".", 1)
        target = spec.get(section, {}).get(field)
        return target if isinstance(target, dict) else None
    team_match = re.match(r"^team_roles\.([ABCD])\.([a-z_]+)$", path)
    if team_match and team_match.group(2) in TEAM_FIELDS:
        return spec.get("team_roles", {}).get(team_match.group(1), {}).get(team_match.group(2))
    skill_match = re.match(r"^skill_modules\[(sm_0[1-4])\]\.([a-z_]+)$", path)
    if skill_match and skill_match.group(2) in SKILL_FIELDS:
        for module in spec.get("skill_modules", []):
            if isinstance(module, dict) and module.get("id") == skill_match.group(1):
                return module.get(skill_match.group(2))
    return None


def _expand_legacy_op(spec: dict[str, Any], raw_op: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_op, dict):
        return []
    op = dict(raw_op)
    op_type = op.get("type") or op.get("op")
    op["type"] = op_type
    op["path"] = canonical_path(op.get("path"))
    if op_type == "append_list_item":
        return [{**op, "type": "append", "value": item} for item in _string_list(op.get("value"))]
    if op_type == "remove_list_item":
        target = _field_at_path(spec, op["path"])
        if not target:
            return []
        needles = _string_list(op.get("value"))
        expanded = []
        for needle in needles:
            for index, item in enumerate(target.get("value") or []):
                if needle in str(item) or str(item) in needle:
                    expanded.append({**op, "type": "remove_at", "index": index})
                    break
        return expanded
    if op_type == "replace_list_item":
        target = _field_at_path(spec, op["path"])
        if not target:
            return []
        old_items = _string_list(op.get("old_value"))
        new_items = _string_list(op.get("value"))
        if not old_items or not new_items:
            return []
        for index, item in enumerate(target.get("value") or []):
            if old_items[0] in str(item) or str(item) in old_items[0]:
                return [{**op, "type": "set_at", "index": index, "value": new_items[0]}]
        return []
    if op_type == "clear":
        return [{**op, "type": "set", "value": ""}]
    if op_type == "add_skill_module":
        value = op.get("value") if isinstance(op.get("value"), dict) else {}
        target_module = next((module for module in spec["skill_modules"] if not field_value(module["skill_name"]) and not field_value(module["work_task"])), None)
        if not target_module:
            return []
        block_id = f"skill_modules[{target_module['id']}]"
        return [
            {
                "type": "set",
                "block_id": block_id,
                "path": f"{block_id}.{field}",
                "value": value.get(field, ""),
                "source": op.get("source", "ai"),
            }
            for field in SKILL_FIELDS
            if value.get(field)
        ]
    return [op]


def _canonical_block_id(block_id: Any) -> str:
    if not isinstance(block_id, str):
        return ""
    block_id = block_id.strip()
    legacy_skill = re.match(r"^skill_modules\.(\d+)$", block_id)
    if legacy_skill:
        index = int(legacy_skill.group(1))
        if 0 <= index < len(SKILL_IDS):
            return f"skill_modules[{SKILL_IDS[index]}]"
    return block_id


def _block_allowed(block_id: str, allowed: set[str]) -> bool:
    if block_id in allowed:
        return True
    if block_id.startswith("skill_modules[") and (
        "skill_modules" in allowed
        or any(block_id == item for item in allowed)
    ):
        return True
    return any(block_id.startswith(f"{scope}.") for scope in allowed)


def _is_team_path(path: str) -> bool:
    return bool(re.match(r"^team_roles\.[ABCD]\.(role|responsibility|onsite_action|related_skill_modules)$", path))


def _is_skill_path(path: str) -> bool:
    return bool(re.match(r"^skill_modules\[sm_0[1-4]\]\.(skill_name|responsible_role|work_task|onsite_demo_action|verification_method|expected_evidence|tools_or_equipment)$", path))


def _string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[\n；;、,，]", value) if item.strip()]
    return []


def _split_related_modules(value: str) -> list[str]:
    return _string_list(value)

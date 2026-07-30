"""Vocational competition project understanding and normalization."""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


TRACK_OPTIONS = (
    "新一代信息技术",
    "人工智能",
    "智能制造",
    "现代农业",
    "养老照护",
    "文旅服务",
    "数字商贸",
    "交通运输",
)


@dataclass
class UnderstandingResult:
    spec: dict[str, Any]
    missing_fields: list[str]
    risk_flags: list[str]
    confidence: dict[str, float]
    input_quality: str


class CompetitionUnderstandingService:
    """Convert raw or structured inputs into a CompetitionProjectSpec draft."""

    def build_from_structured_input(self, structured_input: dict[str, Any] | None) -> UnderstandingResult:
        spec = _default_spec()
        _deep_merge(spec, structured_input or {})
        self._normalize_spec(spec)
        return self._result(spec)

    def build_from_raw_text(self, raw_text: str | None, base_spec: dict[str, Any] | None = None) -> UnderstandingResult:
        text = _sanitize_raw_text(_clean(raw_text) or "")
        spec = _default_spec()
        if base_spec:
            _deep_merge(spec, base_spec)
        spec["source_material"]["raw_text"] = text

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        keyed = _extract_keyed_lines(lines)

        positioning = spec["project_positioning"]
        positioning["project_name"] = _first_value(keyed, "项目名称", "名称") or positioning.get("project_name", "") or _infer_project_name(text)
        positioning["subtitle"] = _first_value(keyed, "副标题") or positioning.get("subtitle", "")
        positioning["track"] = _first_value(keyed, "赛道", "专业方向", "所属行业") or positioning.get("track", "") or _infer_track(text)
        positioning["real_scene"] = _first_value(keyed, "真实场景", "岗位现场", "现场") or positioning.get("real_scene", "") or _infer_real_scene(text)
        positioning["service_object"] = _first_value(keyed, "服务对象", "使用对象", "对象") or positioning.get("service_object", "") or _infer_service_object(text)
        positioning["final_deliverable"] = _first_value(keyed, "最终成果形态", "成果形态", "成果") or positioning.get("final_deliverable", "") or "；".join(_infer_deliverables(text))
        positioning["one_sentence_intro"] = _first_value(keyed, "一句话介绍", "项目简介", "简介") or positioning.get("one_sentence_intro", "") or _first_sentence(text)

        problem = spec["problem_definition"]
        problem["project_goal"] = _first_value(keyed, "项目目标", "目标") or problem.get("project_goal", "")
        problem["need_source"] = _first_value(keyed, "需求来源") or problem.get("need_source", "")
        problem["current_method"] = _first_value(keyed, "当前做法", "现状") or problem.get("current_method", "")
        problem["problem_consequences"] = _first_value(keyed, "问题后果", "后果") or problem.get("problem_consequences", "")
        extracted_pain_points = _extract_list(keyed, ("痛点", "问题"), text)
        problem["pain_points"] = extracted_pain_points or problem.get("pain_points", [])

        extracted_roles = _extract_team_roles(keyed, text)
        if _has_role_content(extracted_roles):
            spec["team_roles"] = extracted_roles
        extracted_modules = _extract_skill_modules(keyed, text)
        if extracted_modules:
            spec["skill_modules"] = extracted_modules

        validation = spec["result_validation"]
        validation["deliverables"] = _extract_list(keyed, ("成果清单", "成果"), text) or _infer_deliverables(text) or validation.get("deliverables", [])
        validation["evidence_materials"] = _extract_list(keyed, ("证据材料", "证据", "材料"), text) or validation.get("evidence_materials", [])
        validation["test_data"] = _first_value(keyed, "测试数据") or validation.get("test_data", "")
        validation["before_after_comparison"] = _first_value(keyed, "优化前后对比", "前后对比") or validation.get("before_after_comparison", "")
        validation["user_feedback"] = _first_value(keyed, "用户反馈", "反馈") or validation.get("user_feedback", "")
        validation["quality_evaluation"] = _first_value(keyed, "质量评价", "评价") or validation.get("quality_evaluation", "")

        value = spec["value_innovation"]
        value["practical_value"] = _first_value(keyed, "实用性", "应用价值") or value.get("practical_value", "")
        value["innovation_points"] = _extract_innovation_points(keyed, text) or value.get("innovation_points", [])
        value["teaching_value"] = _first_value(keyed, "教学应用价值", "教学价值") or value.get("teaching_value", "")
        value["vocational_scene_value"] = _first_value(keyed, "职业场景落地价值", "落地价值") or value.get("vocational_scene_value", "")
        value["sustainability"] = _first_value(keyed, "可持续性") or value.get("sustainability", "")

        self._normalize_spec(spec)
        return self._result(spec)

    def build_from_reference_file(self, reference_file) -> UnderstandingResult:
        if not reference_file:
            raise ValueError("reference_file is required")
        if reference_file.parse_status != "completed":
            raise ValueError("reference file must be parsed before understanding")
        text = reference_file.markdown_content or ""
        result = self.build_from_raw_text(text)
        result.spec["source_material"]["file_id"] = reference_file.id
        result.spec["source_material"]["filename"] = reference_file.filename
        return result

    def _normalize_spec(self, spec: dict[str, Any]) -> None:
        spec["competition_context"].update({
            "competition_name": "世界职业院校技能大赛/争夺赛",
            "generation_goal": "1小时现场技能展示作战稿",
            "presentation_mode": "现场展示",
            "audience": ["评委", "企业导师", "现场观摩人员"],
        })

        positioning = spec["project_positioning"]
        for field in ("project_name", "subtitle", "track", "industry", "real_scene", "service_object", "final_deliverable", "one_sentence_intro"):
            if _is_bad_extracted_item(positioning.get(field, "")):
                positioning[field] = ""
        if not positioning.get("track") and positioning.get("industry"):
            positioning["track"] = positioning.get("industry")
        if positioning.get("track") and positioning["track"] not in TRACK_OPTIONS:
            positioning["industry"] = positioning["track"]

        problem = spec["problem_definition"]
        for field in ("need_source", "current_method", "problem_consequences", "project_goal"):
            if _is_bad_extracted_item(problem.get(field, "")):
                problem[field] = ""

        validation = spec["result_validation"]
        for field in ("test_data", "before_after_comparison", "user_feedback", "quality_evaluation"):
            if _is_bad_extracted_item(validation.get(field, "")):
                validation[field] = ""

        value = spec["value_innovation"]
        for field in ("practical_value", "teaching_value", "vocational_scene_value", "sustainability"):
            if _is_bad_extracted_item(value.get(field, "")):
                value[field] = ""

        spec["team_roles"] = _normalize_team_roles(spec.get("team_roles") or [])
        spec["skill_modules"] = _normalize_skill_modules(spec.get("skill_modules") or [])
        spec["problem_definition"]["pain_points"] = _dedupe_valid_strings(spec["problem_definition"].get("pain_points") or [])
        spec["result_validation"]["deliverables"] = _dedupe_valid_strings(spec["result_validation"].get("deliverables") or [])
        spec["result_validation"]["evidence_materials"] = _dedupe_valid_strings(spec["result_validation"].get("evidence_materials") or [])
        spec["value_innovation"]["innovation_points"] = _dedupe_valid_strings(
            spec["value_innovation"].get("innovation_points") or [],
            extra_bad=_is_bad_innovation_point,
        )

        evidence = spec["result_validation"].get("evidence_materials") or []
        team_roles = spec.get("team_roles") or []
        for index, module in enumerate(spec.get("skill_modules") or []):
            if not module.get("responsible_role") and index < len(team_roles):
                module["responsible_role"] = team_roles[index].get("member") or team_roles[index].get("role") or ""
            if not module.get("verification_method"):
                module["verification_method"] = "；".join(evidence[:2]) if evidence else "现场操作记录和评分材料"
            if not module.get("onsite_demo_action"):
                module["onsite_demo_action"] = _infer_action(module.get("work_task") or module.get("skill_name") or "")

    def _result(self, spec: dict[str, Any]) -> UnderstandingResult:
        missing = _missing_fields(spec)
        risks = _risk_flags(spec)
        confidence = _confidence(spec)
        if len(missing) <= 2 and not risks:
            quality = "ready"
        elif len(missing) <= 6:
            quality = "needs_review"
        else:
            quality = "insufficient"
        return UnderstandingResult(spec=spec, missing_fields=missing, risk_flags=risks, confidence=confidence, input_quality=quality)


def _default_spec() -> dict[str, Any]:
    return {
        "competition_context": {
            "competition_name": "世界职业院校技能大赛/争夺赛",
            "generation_goal": "1小时现场技能展示作战稿",
            "presentation_mode": "现场展示",
            "audience": ["评委", "企业导师", "现场观摩人员"],
        },
        "source_material": {
            "raw_text": "",
            "file_id": None,
            "filename": None,
        },
        "project_positioning": {
            "project_name": "",
            "subtitle": "",
            "track": "",
            "industry": "",
            "real_scene": "",
            "service_object": "",
            "final_deliverable": "",
            "one_sentence_intro": "",
        },
        "problem_definition": {
            "pain_points": [],
            "need_source": "",
            "current_method": "",
            "problem_consequences": "",
            "project_goal": "",
        },
        "team_roles": _empty_team_roles(),
        "skill_modules": [],
        "result_validation": {
            "deliverables": [],
            "evidence_materials": [],
            "test_data": "",
            "before_after_comparison": "",
            "user_feedback": "",
            "quality_evaluation": "",
        },
        "value_innovation": {
            "practical_value": "",
            "innovation_points": [],
            "teaching_value": "",
            "vocational_scene_value": "",
            "sustainability": "",
        },
        "constraints": {
            "avoid": ["营销路演", "融资汇报", "泛泛产品介绍", "虚构收益数据"],
            "must_show": ["岗位现场", "服务对象", "四名选手动作", "技能模块", "成果证据"],
        },
    }


def _empty_team_roles() -> list[dict[str, Any]]:
    return [
        {"member": "A", "name": "", "role": "", "responsibility": "", "onsite_action": "", "related_skill_modules": []},
        {"member": "B", "name": "", "role": "", "responsibility": "", "onsite_action": "", "related_skill_modules": []},
        {"member": "C", "name": "", "role": "", "responsibility": "", "onsite_action": "", "related_skill_modules": []},
        {"member": "D", "name": "", "role": "", "responsibility": "", "onsite_action": "", "related_skill_modules": []},
    ]


def _missing_fields(spec: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    positioning = spec["project_positioning"]
    if not positioning.get("project_name"):
        missing.append("project_positioning.project_name")
    if not (positioning.get("track") or positioning.get("industry")):
        missing.append("project_positioning.track_or_industry")
    for field in ("real_scene", "service_object", "final_deliverable"):
        if not positioning.get(field):
            missing.append(f"project_positioning.{field}")

    problem = spec["problem_definition"]
    if not problem.get("pain_points"):
        missing.append("problem_definition.pain_points")
    if not problem.get("project_goal"):
        missing.append("problem_definition.project_goal")

    for role in spec.get("team_roles") or []:
        label = role.get("member") or "member"
        for field in ("role", "responsibility", "onsite_action"):
            if not role.get(field):
                missing.append(f"team_roles.{label}.{field}")

    modules = spec.get("skill_modules") or []
    if not modules:
        missing.append("skill_modules")
    for index, module in enumerate(modules, start=1):
        for field in ("skill_name", "responsible_role", "verification_method", "onsite_demo_action"):
            if not module.get(field):
                missing.append(f"skill_modules.{index}.{field}")

    validation = spec["result_validation"]
    if not validation.get("deliverables"):
        missing.append("result_validation.deliverables")
    if not validation.get("evidence_materials"):
        missing.append("result_validation.evidence_materials")

    value = spec["value_innovation"]
    if not (value.get("practical_value") or value.get("innovation_points")):
        missing.append("value_innovation.practical_value_or_innovation_points")
    return missing


def _risk_flags(spec: dict[str, Any]) -> list[str]:
    scan_payload = {
        "source_material": spec.get("source_material"),
        "project_positioning": spec.get("project_positioning"),
        "problem_definition": spec.get("problem_definition"),
        "team_roles": spec.get("team_roles"),
        "skill_modules": spec.get("skill_modules"),
        "result_validation": spec.get("result_validation"),
        "value_innovation": spec.get("value_innovation"),
    }
    text = str(scan_payload)
    flags = []
    if any(word in text for word in ("市场规模", "融资", "商业模式", "投资回报")):
        flags.append("contains_marketing_or_financing_language")
    if re.search(r"\d+(\.\d+)?\s*(万|亿|%|倍)", text) and not any(word in text for word in ("测试", "记录", "评分", "实测")):
        flags.append("quantified_claims_need_evidence")
    return flags


def _confidence(spec: dict[str, Any]) -> dict[str, float]:
    def score(values: list[Any]) -> float:
        if not values:
            return 0.0
        filled = sum(1 for value in values if bool(value))
        return round(filled / len(values), 2)

    positioning = spec["project_positioning"]
    problem = spec["problem_definition"]
    validation = spec["result_validation"]
    value = spec["value_innovation"]
    return {
        "project_positioning": score([
            positioning.get("project_name"),
            positioning.get("track") or positioning.get("industry"),
            positioning.get("real_scene"),
            positioning.get("service_object"),
            positioning.get("final_deliverable"),
        ]),
        "problem_definition": score([problem.get("pain_points"), problem.get("project_goal")]),
        "team_roles": score([
            role.get("role") and role.get("responsibility") and role.get("onsite_action")
            for role in spec.get("team_roles") or []
        ]),
        "skill_modules": min(1.0, round(len(spec.get("skill_modules") or []) / 4, 2)),
        "result_validation": score([validation.get("deliverables"), validation.get("evidence_materials")]),
        "value_innovation": score([value.get("practical_value") or value.get("innovation_points")]),
    }


def _extract_keyed_lines(lines: list[str]) -> dict[str, list[str]]:
    keyed: dict[str, list[str]] = {}
    for line in lines:
        if line.lstrip().startswith("#"):
            continue
        line = line.strip(" -•\t")
        match = re.match(r"^\s*([^：:]{2,16})\s*[：:]\s*(.+?)\s*$", line)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        if _is_bad_extracted_item(value):
            continue
        keyed.setdefault(key, []).append(value)
    return keyed


def _sanitize_raw_text(text: str) -> str:
    text = re.sub(r"【当前用户手动修订后的 Markdown 稿件】", "\n", text)
    text = re.sub(r"【用户本轮修改意见或新增资料】", "\n", text)
    return text.strip()


def _first_value(keyed: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = keyed.get(key)
        if values:
            for value in values:
                if not _is_bad_extracted_item(value):
                    return value
    return ""


def _extract_list(
    keyed: dict[str, list[str]],
    keys: tuple[str, ...],
    text: str,
    fallback_markers: tuple[str, ...] = (),
) -> list[str]:
    items: list[str] = []
    for key in keys:
        for value in keyed.get(key, []):
            items.extend(_split_items(value))
    if not items and fallback_markers:
        for line in text.splitlines():
            stripped = line.strip(" -•\t")
            if 6 <= len(stripped) <= 80 and any(marker in stripped for marker in fallback_markers):
                items.append(stripped)
    return _dedupe_strings([item for item in items[:6] if not _is_bad_extracted_item(item)])


def _is_bad_extracted_item(value: str) -> bool:
    text = _clean(value)
    if not text:
        return True
    if text.lstrip().startswith("#"):
        return True
    if "【当前用户手动修订后的 Markdown 稿件】" in text or "【用户本轮修改意见或新增资料】" in text:
        return True
    field_label_count = len(re.findall(r"(项目名称|副标题|赛道|专业方向|真实场景|服务对象|最终成果形态|一句话介绍|痛点|技能模块|成果清单|证据材料)[：:]", text))
    if field_label_count >= 2:
        return True
    if re.match(r"^(请)?补充(价值创新|成果验证|真实问题|技能展示|四名选手|项目定位)", text):
        return True
    if re.match(r"^(优化前后对比|测试数据|用户反馈|质量评价)", text):
        return True
    if _is_project_meta_sentence(text):
        return True
    if re.match(r"^(一|二|三|四|五|六|七)、", text):
        return True
    if re.match(r"^(项目名称|副标题|赛道|专业方向|真实场景|服务对象|最终成果形态|一句话介绍|需求来源|当前做法|问题后果|项目目标|负责角色|工作任务|现场演示动作|验证方式|预期证据|工具/设备/材料)[：:]", text):
        return True
    if text in {"待补充", "无", "暂无", "痛点", "创新点", "成果清单", "证据材料"}:
        return True
    return False


def _is_bad_innovation_point(value: str) -> bool:
    text = _clean(value)
    if not text:
        return True
    if re.match(r"^(优化前后对比|测试数据|用户反馈|质量评价)", text):
        return True
    if text in {"记录完整性"}:
        return True
    if "交接准确性" in text and "创新" not in text:
        return True
    return False


def _is_project_meta_sentence(text: str) -> bool:
    return bool(
        re.search(r"(我想|我要|计划|准备).{0,20}(做|建设|开发|设计).{0,20}(项目|系统)", text)
        or re.search(r"(我想|我要|计划|准备|打算).{0,40}(方向|起名|取名|项目名称)", text)
        or re.search(r"(帮我|请你|麻烦).{0,30}(起|取|推荐).{0,10}(项目)?名称", text)
        or re.search(r"(老师|小白).{0,20}(不太懂|不会|不懂).{0,20}(大赛|比赛|怎么写)", text)
        or re.search(r"(大概想法|大致想法|初步想法).{0,30}(想做|做一个|项目)", text)
        or re.search(r"(帮我|请你|麻烦).{0,30}(整理|生成|完善).{0,20}(大赛|比赛|项目|稿)", text)
        or re.search(r"(项目名称|项目名|名称)(?:就)?(叫|是|为)", text)
        or re.search(r"赛道(?:是|为|可以|建议|放在)", text)
        or re.search(r"真实场景(是|为)", text)
        or re.search(r"服务对象(是|为)", text)
        or re.search(r"(项目)?想解决的问题(是|为|包括|有|：|:)", text)
        or len(re.findall(r"(项目名称|项目名|赛道|真实场景|服务对象|最终成果|痛点|四个学生分工|四名选手)", text)) >= 2
    )


def _extract_innovation_points(keyed: dict[str, list[str]], text: str) -> list[str]:
    items = _extract_list(keyed, ("创新点", "创新"), text, fallback_markers=("创新", "首次", "优化", "融合"))
    for line in text.splitlines():
        match = re.search(r"创新点包括(.+?)(?:优化前后对比|测试数据|用户反馈|质量评价|$)", line.strip())
        if match:
            items.extend(_split_items(match.group(1)))
    expanded: list[str] = []
    for item in items:
        match = re.search(r"创新点包括(.+)$", item)
        if match:
            expanded.extend(_split_items(match.group(1)))
        else:
            expanded.append(item)
    return _dedupe_valid_strings(expanded, extra_bad=_is_bad_innovation_point)


def _has_role_content(roles: list[dict[str, Any]]) -> bool:
    return any(role.get("role") or role.get("responsibility") or role.get("onsite_action") for role in roles)


def _extract_team_roles(keyed: dict[str, list[str]], text: str) -> list[dict[str, Any]]:
    roles = _empty_team_roles()
    role_lines = []
    for key, values in keyed.items():
        if key in {"A", "B", "C", "D"} or "选手" in key or "成员" in key:
            role_lines.extend(f"{key}：{value}" for value in values)
    if not role_lines:
        role_lines = [line.strip() for line in text.splitlines() if re.match(r"^\s*[ABCD][：:]", line.strip(), re.I)]

    if not role_lines:
        natural_roles = _extract_natural_team_roles(text)
        if _has_role_content(natural_roles):
            return natural_roles

    for line in role_lines:
        match = re.match(r"^\s*([ABCD])\s*[：:]\s*(.+)$", line, re.I)
        if not match:
            continue
        idx = "ABCD".index(match.group(1).upper())
        content = match.group(2).strip()
        parts = _split_items(content)
        roles[idx]["responsibility"] = content
        role_text = re.split(r"[，,；;]", content, maxsplit=1)[0].strip()
        roles[idx]["role"] = role_text or (parts[0] if parts else content[:20])
        roles[idx]["onsite_action"] = _infer_action(content)
    return roles


def _extract_natural_team_roles(text: str) -> list[dict[str, Any]]:
    roles = _empty_team_roles()
    stop_sections = (
        r"\n\s*(?:技能模块|成果清单|证据材料|实用性|创新点|项目名称|赛道|真实场景|服务对象|最终成果形态|痛点|项目目标)[：:]"
    )
    pattern = re.compile(
        rf"([ABCD])\s*选手\s*(?:负责|承担|担任)?(.+?)(?=(?:[ABCD]\s*选手\s*(?:负责|承担|担任))|{stop_sections}|$)",
        re.S,
    )
    for match in pattern.finditer(text or ""):
        idx = "ABCD".index(match.group(1).upper())
        block = re.sub(r"\s+", " ", match.group(2)).strip(" ：:，,。；;")
        if not block or _is_bad_extracted_item(block):
            continue
        action = _extract_sentence_field(block, ("现场动作", "现场演示动作"))
        role_text = re.split(r"(?:现场动作|现场演示动作)\s*(?:是|为|[:：])", block, maxsplit=1)[0]
        role_text = role_text.strip(" ：:，,。；;")
        role_text = re.sub(r"^(?:负责|承担|担任)", "", role_text).strip(" ：:，,。；;")
        if not role_text or _is_bad_extracted_item(role_text):
            continue
        roles[idx]["role"] = role_text
        roles[idx]["responsibility"] = role_text
        roles[idx]["onsite_action"] = action or _infer_action(block)
    return roles


def _extract_skill_modules(keyed: dict[str, list[str]], text: str) -> list[dict[str, Any]]:
    structured_modules = _extract_natural_skill_modules(text)
    if structured_modules:
        return structured_modules[:8]

    values = []
    for line in text.splitlines():
        match = re.match(r"^\s*#+\s*技能模块\s*\d*\s*[：:]\s*(.+?)\s*$", line)
        if match and not _is_bad_extracted_item(match.group(1)):
            values.append(match.group(1))
    for key, items in keyed.items():
        if "技能" in key or "模块" in key:
            values.extend(items)
    modules = []
    for value in values:
        inline_modules = _extract_inline_skill_modules(value)
        if inline_modules:
            modules.extend(inline_modules)
            continue
        for item in _split_items(value):
            if not _is_bad_extracted_item(item):
                modules.append(_skill_module(item))
    return modules[:8]


def _extract_natural_skill_modules(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(r"技能模块\s*(\d+)\s*(?:是|[:：])\s*(.+?)(?=\n\s*技能模块\s*\d+\s*(?:是|[:：])|$)", re.S)
    modules: list[dict[str, Any]] = []
    for match in pattern.finditer(text):
        block = re.sub(r"\s+", " ", match.group(2)).strip()
        name = re.split(r"[，,。.]", block, maxsplit=1)[0].strip()
        if _is_bad_extracted_item(name):
            continue
        module = _skill_module(name)
        module["responsible_role"] = _extract_inline_field(block, ("负责角色",)) or module["responsible_role"]
        module["work_task"] = _extract_inline_field(block, ("工作任务",)) or module["work_task"]
        module["onsite_demo_action"] = _extract_inline_field(block, ("现场演示动作", "现场动作")) or module["onsite_demo_action"]
        module["verification_method"] = _extract_inline_field(block, ("验证方式",)) or module["verification_method"]
        module["expected_evidence"] = _extract_inline_field(block, ("预期证据",)) or module["expected_evidence"]
        module["tools_or_equipment"] = _extract_inline_field(block, ("工具设备材料", "工具/设备/材料")) or module["tools_or_equipment"]
        modules.append(module)
    return modules


def _extract_inline_field(text: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_labels = "负责角色|工作任务|现场演示动作|现场动作|验证方式|预期证据|工具设备材料|工具/设备/材料|技能模块"
    match = re.search(rf"(?:{label_pattern})(?:是|为|[:：])\s*(.+?)(?=(?:{stop_labels})(?:是|为|[:：])|$)", text)
    if not match:
        return ""
    value = match.group(1).strip(" ，,。.")
    return "" if _is_bad_extracted_item(value) else value


def _extract_sentence_field(text: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})(?:是|为|[:：])\s*(.+?)(?:[。；;]|$)", text)
    if not match:
        return ""
    value = match.group(1).strip(" ：:，,。；;")
    return "" if _is_bad_extracted_item(value) else value


def _extract_inline_skill_modules(value: str) -> list[dict[str, Any]]:
    if not any(marker in (value or "") for marker in ("现场演示动作", "现场动作", "验证方式", "负责")):
        return []
    modules: list[dict[str, Any]] = []
    for item in _split_items(value):
        if _is_bad_extracted_item(item):
            continue
        name = re.split(r"[，,。]", item, maxsplit=1)[0].strip(" ：:，,。；;")
        name = re.sub(r"^技能模块\s*\d*\s*(?:是|为|[:：])\s*", "", name).strip(" ：:，,。；;")
        if not name or _is_bad_extracted_item(name):
            continue
        module = _skill_module(name)
        role_match = re.search(r"由\s*([^，,。；;]+?)\s*负责", item)
        if role_match:
            module["responsible_role"] = role_match.group(1).strip(" ：:，,。；;")
        module["work_task"] = _extract_inline_field(item, ("工作任务",)) or name
        module["onsite_demo_action"] = _extract_inline_field(item, ("现场演示动作", "现场动作")) or module["onsite_demo_action"]
        module["verification_method"] = _extract_inline_field(item, ("验证方式",)) or module["verification_method"]
        module["expected_evidence"] = _extract_inline_field(item, ("预期证据",)) or module["expected_evidence"]
        module["tools_or_equipment"] = _extract_inline_field(item, ("工具设备材料", "工具/设备/材料")) or module["tools_or_equipment"]
        modules.append(module)
    return modules


def _skill_module(text: str) -> dict[str, Any]:
    return {
        "skill_name": text[:30],
        "responsible_role": "",
        "work_task": text,
        "verification_method": "",
        "onsite_demo_action": _infer_action(text),
        "expected_evidence": "",
        "tools_or_equipment": "",
    }


def _normalize_team_roles(raw_roles: list[Any]) -> list[dict[str, Any]]:
    roles = _empty_team_roles()
    for index, raw in enumerate(raw_roles[:4]):
        if not isinstance(raw, dict):
            continue
        role = roles[index]
        role.update({key: _clean(raw.get(key)) or role.get(key, "") for key in ("member", "name", "role", "responsibility", "onsite_action")})
        related = raw.get("related_skill_modules") or []
        role["related_skill_modules"] = related if isinstance(related, list) else _split_items(str(related))
    return roles


def _normalize_skill_modules(raw_modules: list[Any]) -> list[dict[str, Any]]:
    modules = []
    for raw in raw_modules:
        if isinstance(raw, str):
            if _is_bad_extracted_item(raw):
                continue
            modules.append(_skill_module(raw))
        elif isinstance(raw, dict):
            module = _skill_module(_clean(raw.get("skill_name")) or _clean(raw.get("work_task")) or "")
            module.update({key: _clean(raw.get(key)) or module.get(key, "") for key in module})
            for key in module:
                if _is_bad_extracted_item(module.get(key, "")):
                    module[key] = ""
            modules.append(module)
    return [module for module in modules if module.get("skill_name") or module.get("work_task")]


def _infer_track(text: str) -> str:
    for option in TRACK_OPTIONS:
        if option in text:
            return option
    if any(word in text for word in ("农业", "温室", "大棚", "种植")):
        return "现代农业"
    if any(word in text for word in ("养老", "护理", "康养")):
        return "养老照护"
    if any(word in text for word in ("AI", "人工智能", "智能评估", "智能识别", "模型", "自动生成")):
        return "人工智能"
    if any(word in text for word in ("数控", "机电", "车间", "设备")):
        return "智能制造"
    return ""


def _infer_project_name(text: str) -> str:
    patterns = (
        r"项目名称\s*(?:就)?(?:叫|是|为|[:：])\s*([^，。；;\n]+)",
        r"项目名称\s*(?:暂定|暂叫|先叫|拟定为)\s*[“\"']?([^”\"'，。；;\n]+)",
        r"项目名\s*(?:就)?(?:叫|是|为|[:：])\s*([^，。；;\n]+)",
        r"项目名\s*(?:暂定|暂叫|先叫|拟定为)\s*[“\"']?([^”\"'，。；;\n]+)",
        r"名称\s*(?:就)?(?:叫|是|为|[:：])\s*([^，。；;\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip(" ：:")
            if name and not _is_bad_project_name(name):
                return name[:60]
    return ""


def _is_bad_project_name(value: str) -> bool:
    text = _clean(value)
    if not text:
        return True
    if text.lstrip().startswith("#"):
        return True
    if "【当前用户手动修订后的 Markdown 稿件】" in text or "【用户本轮修改意见或新增资料】" in text:
        return True
    if len(re.findall(r"(项目名称|副标题|赛道|专业方向|真实场景|服务对象|最终成果形态|一句话介绍|痛点|技能模块|成果清单|证据材料)[：:]", text)) >= 2:
        return True
    if text in {"待补充", "无", "暂无"}:
        return True
    if re.search(r"(帮我|请你|起一个|取一个|推荐).{0,20}(项目)?名称", text):
        return True
    return False


def _infer_real_scene(text: str) -> str:
    patterns = (
        r"真实场景(?:是|为)\s*([^。；;\n]+)",
        r"岗位现场(?:是|为)\s*([^。；;\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            scene = match.group(1).strip(" ：:")
            if scene and not _is_bad_extracted_item(scene):
                return scene[:120]
    return ""


def _infer_service_object(text: str) -> str:
    patterns = (
        r"服务对象(?:是|为)\s*([^。；;\n]+)",
        r"使用对象(?:是|为)\s*([^。；;\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            service_object = match.group(1).strip(" ：:")
            if service_object and not _is_bad_extracted_item(service_object):
                return service_object[:120]
    return ""


def _infer_deliverables(text: str) -> list[str]:
    match = re.search(r"最终成果形态包括\s*([^。\n]+)", text)
    if not match:
        return []
    return _dedupe_valid_strings(_split_items(match.group(1)))


def _infer_action(text: str) -> str:
    verbs = ("评估", "检测", "采集", "调试", "干预", "处置", "记录", "归档", "复核", "演示", "讲解")
    for verb in verbs:
        if verb in text:
            return f"现场{verb}并说明操作依据"
    return ""


def _first_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    parts = re.split(r"[。！？!?]\s*", text)
    for part in parts:
        sentence = part.strip()
        if sentence and not _is_project_meta_sentence(sentence):
            return sentence[:120]
    return ""


def _split_items(value: str) -> list[str]:
    return [
        item.strip(" -•\t")
        for item in re.split(r"[；;\n、]|(?:\s+[0-9]+[.、])", value or "")
        if item.strip(" -•\t")
    ]


def _dedupe_strings(values: list[Any]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = _clean(value).rstrip("。；;，,")
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _dedupe_valid_strings(values: list[Any], extra_bad=None) -> list[str]:
    return _dedupe_strings([
        value
        for value in values
        if not _is_bad_extracted_item(value) and not (extra_bad and extra_bad(value))
    ])


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = deepcopy(value)


def _clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()

"""LLM-backed semantic editing for vocational competition project drafts."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .competition_understanding_service import CompetitionUnderstandingService
from .competition_spec_state import (
    all_patch_blocks,
    apply_patch_ops_to_spec_state,
    canonical_path,
    infer_block_id,
    merge_plain_values_into_state,
    normalize_spec_state,
    unwrap_spec_state,
)


@dataclass
class DocumentEditResult:
    spec: dict[str, Any]
    missing_fields: list[str]
    risk_flags: list[str]
    confidence: dict[str, float]
    input_quality: str
    reply: str = ""
    change_summary: list[str] = field(default_factory=list)
    destructive_changes: list[str] = field(default_factory=list)
    needs_confirmation: bool = False
    questions: list[str] = field(default_factory=list)
    ops: list[dict[str, Any]] = field(default_factory=list)
    rejected_ops: list[dict[str, Any]] = field(default_factory=list)


class CompetitionDocumentEditService:
    """Ask the model for patch operations and apply them server-side."""

    def __init__(self, ai_service):
        self.ai_service = ai_service
        self.validator = CompetitionUnderstandingService()

    def build_from_user_message(
        self,
        user_message: str,
        *,
        current_spec: dict[str, Any] | None = None,
    ) -> DocumentEditResult:
        base_state = normalize_spec_state(current_spec or {})
        base_plain = unwrap_spec_state(base_state)
        base_normalized = self.validator.build_from_structured_input(base_plain)
        # Direct list editing is an optimization for an existing draft. On the
        # first turn, the full message may naturally contain list-like project
        # facts; it still needs model-authored patch ops for the complete spec.
        direct_result = (
            _build_direct_list_edit_result(user_message, base_state, self.validator)
            if current_spec
            else None
        )
        if direct_result:
            return direct_result
        prompt = self._build_prompt(user_message, base_state)
        payload = self.ai_service.generate_json(prompt, thinking_budget=1000)
        print("[DOCUMENT_EDIT_RAW_PAYLOAD]", json.dumps(payload, ensure_ascii=False))
        if not isinstance(payload, dict):
            raise ValueError("document edit model must return a JSON object")

        ops, malformed_rejections = _extract_ops(payload.get("ops"))
        ops, scope_rejections = _reject_ops_outside_user_scope(ops, user_message)
        allowed_blocks = _allowed_blocks_for_user_message(user_message)
        patched_state, accepted_ops, rejected_ops = apply_patch_ops_to_spec_state(
            base_state,
            ops,
            source="ai",
            allowed_blocks=allowed_blocks,
        )
        rejected_ops = [*malformed_rejections, *scope_rejections, *rejected_ops]
        if accepted_ops:
            normalized = self.validator.build_from_structured_input(unwrap_spec_state(patched_state))
            final_state = merge_plain_values_into_state(patched_state, normalized.spec, source="ai")
        else:
            normalized = base_normalized
            final_state = base_state
        reply = _string(payload.get("reply"))
        locked_rejections = [item for item in rejected_ops if item.get("code") == "FIELD_LOCKED"]
        if locked_rejections:
            locked_paths = "、".join(item["op"].get("path", "") for item in locked_rejections if item.get("op"))
            reply = f"{reply} 其中 {locked_paths} 已被用户锁定，AI 未修改。" if reply else f"该字段已锁定，AI 未修改：{locked_paths}"
        return DocumentEditResult(
            spec=final_state,
            missing_fields=normalized.missing_fields,
            risk_flags=normalized.risk_flags,
            confidence=normalized.confidence,
            input_quality=normalized.input_quality,
            reply=reply,
            change_summary=_string_list(payload.get("change_summary")) or _summarize_ops(accepted_ops),
            destructive_changes=_string_list(payload.get("destructive_changes")) or _destructive_ops(accepted_ops),
            needs_confirmation=bool(payload.get("needs_confirmation")),
            questions=_string_list(payload.get("questions")),
            ops=accepted_ops,
            rejected_ops=rejected_ops,
        )

    def apply_user_patch(
        self,
        current_spec: dict[str, Any] | None,
        patch_ops: list[dict[str, Any]],
    ) -> DocumentEditResult:
        patched_state, accepted_ops, rejected_ops = apply_patch_ops_to_spec_state(
            current_spec or {},
            patch_ops,
            source="user",
            allowed_blocks=None,
        )
        normalized = self.validator.build_from_structured_input(unwrap_spec_state(patched_state))
        return DocumentEditResult(
            spec=patched_state,
            missing_fields=normalized.missing_fields,
            risk_flags=normalized.risk_flags,
            confidence=normalized.confidence,
            input_quality=normalized.input_quality,
            reply="字段已更新。" if accepted_ops else "字段未更新。",
            change_summary=_summarize_ops(accepted_ops),
            destructive_changes=_destructive_ops(accepted_ops),
            ops=accepted_ops,
            rejected_ops=rejected_ops,
        )

    def build_from_reference_text(
        self,
        reference_text: str,
        *,
        current_spec: dict[str, Any] | None = None,
        filename: str = "",
    ) -> DocumentEditResult:
        user_message = "\n".join([
            f"请完整理解这份上传资料，并把它整理成大赛项目结构化稿件。文件名：{filename or '未命名文件'}",
            "",
            reference_text or "",
        ])
        return self.build_from_user_message(user_message, current_spec=current_spec)

    def _build_prompt(
        self,
        user_message: str,
        current_spec: dict[str, Any] | None,
    ) -> str:
        base_spec = normalize_spec_state(current_spec or self.validator.build_from_structured_input({}).spec)
        return "\n".join([
            "你是职业院校技能大赛项目文档的语义编辑器。",
            "任务：完整理解当前字段状态稿件和用户本轮指令，只输出需要执行的字段补丁操作 ops。",
            "",
            "关键规则：",
            "1. 不做关键词抽取，不按正则猜字段；必须理解用户真实编辑意图。",
            "2. 当前结构化稿件是基础状态。用户未要求修改的字段不要输出操作。",
            "3. 用户明确说“删除、不要、去掉、清空、替换”时，只改对应目标，不扩大删除范围。",
            "4. 你只能通过 ops 数组修改稿件，禁止在 reply 中直接输出修改后的完整稿件内容。",
            "5. 禁止把提示词标签、Markdown 标题、待补充占位、聊天请求本身写入业务字段。",
            "6. 如果用户要求“帮我生成、补全、完善、你来写、没思路、直接生成”某个章节或字段，必须基于当前稿件上下文主动生成可用内容并输出 ops，不要要求用户逐字段提供。",
            "7. 只有用户纯提问、闲聊或完全无法判断目标章节时，ops 才输出空数组，并在 reply/questions 里说明需要补充什么。",
            "8. 输出必须是纯 JSON，不能包含 Markdown 代码块、注释或额外文本。",
            "9. 不要输出整份 updated_spec / competition_project_spec。",
            "10. 每个 op 必须包含 block_id、path、type、value、source 字段，source 固定为 ai。",
            "11. path 必须以 block_id 开头，否则为非法 op；遇到 locked 字段时只能在 reply 中说明该字段已锁定。",
            "12. skill_modules 固定4条，id 为 sm_01 / sm_02 / sm_03 / sm_04，不能新增或删除；用户要求生成技能模块时，应尽量一次性补齐4个模块的 skill_name、responsible_role、work_task、onsite_demo_action、verification_method、expected_evidence、tools_or_equipment。",
            "13. 主动生成内容必须贴合当前项目名称、真实场景、服务对象、问题目标、四名选手分工和成果验证，不要写成泛泛模板。",
            "",
            "可用 block_id：",
            json.dumps(_block_catalog(), ensure_ascii=False, indent=2),
            "",
            "允许的 ops：",
            "- set: {type:'set', block_id:'project_positioning', path:'project_positioning.project_name', value:'...', source:'ai'}",
            "- append: {type:'append', block_id:'result_validation', path:'result_validation.deliverables', value:'...', source:'ai'}",
            "- remove_at: {type:'remove_at', block_id:'problem_definition', path:'problem_definition.pain_points', index:0, source:'ai'}",
            "- set_at: {type:'set_at', block_id:'problem_definition', path:'problem_definition.pain_points', index:0, value:'...', source:'ai'}",
            "",
            "常用路径：",
            "project_positioning.project_name, project_positioning.track, project_positioning.real_scene, project_positioning.service_object, project_positioning.final_deliverable, project_positioning.one_sentence_intro",
            "problem_definition.pain_points, problem_definition.project_goal",
            "team_roles.A.role, team_roles.A.responsibility, team_roles.A.onsite_action（B/C/D 同理）",
            "skill_modules[sm_01].skill_name, skill_modules[sm_01].responsible_role, skill_modules[sm_01].work_task, skill_modules[sm_01].onsite_demo_action, skill_modules[sm_01].verification_method, skill_modules[sm_01].expected_evidence, skill_modules[sm_01].tools_or_equipment（sm_02/sm_03/sm_04 同理）",
            "result_validation.deliverables, result_validation.evidence_materials",
            "value_innovation.innovation_points, value_innovation.practical_value",
            "",
            "主动生成示例：",
            "用户说：帮我生成技能模块 / 四、技能展示模块我没思路，你来写。",
            "你应输出多个 set ops，例如 block_id:'skill_modules[sm_01]', path:'skill_modules[sm_01].skill_name'，并补齐 sm_01 至 sm_04 的核心字段；不要只在 reply 里解释写法。",
            "",
            "JSON 输出格式：",
            json.dumps({
                "reply": "面向用户的简短回复，说明本轮实际修改了什么",
                "ops": [
                    {"block_id": "project_positioning", "type": "set", "path": "project_positioning.project_name", "value": "示例项目名", "source": "ai"}
                ],
                "change_summary": ["补丁级变更摘要"],
                "destructive_changes": ["删除或清空类变更摘要，没有则空数组"],
                "needs_confirmation": False,
                "questions": ["仍需用户确认的问题，没有则空数组"],
            }, ensure_ascii=False),
            "",
            "【当前字段状态稿件 JSON】",
            json.dumps(base_spec, ensure_ascii=False, indent=2),
            "",
            "【用户本轮指令或资料】",
            (user_message or "")[:16000],
        ])


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _extract_ops(value: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(value, list):
        return [], []
    ops: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            rejected.append({"op": {}, "code": "INVALID_OP", "message": "patch op 必须是对象"})
            continue
        op = dict(item)
        op_type = op.get("type") or op.get("op")
        if not isinstance(op_type, str) or not op_type.strip():
            rejected.append({"op": op, "code": "INVALID_OP", "message": "patch op 缺少 type"})
            continue
        op["type"] = op_type.strip()
        ops.append(op)
    return ops, rejected


def _allowed_blocks_for_user_message(user_message: str) -> set[str]:
    scopes = _explicit_allowed_scopes(user_message)
    if not scopes:
        return all_patch_blocks()
    blocks: set[str] = set()
    for scope in scopes:
        canonical_scope = canonical_path(scope)
        block = infer_block_id(canonical_scope)
        if block:
            blocks.add(block)
        elif canonical_scope == "skill_modules":
            blocks.add("skill_modules")
            blocks.update({f"skill_modules[{skill_id}]" for skill_id in ("sm_01", "sm_02", "sm_03", "sm_04")})
        elif canonical_scope in {"project_positioning", "problem_definition", "result_validation", "value_innovation"}:
            blocks.add(canonical_scope)
    return blocks or all_patch_blocks()


def _filter_ops_for_user_scope(ops: list[dict[str, Any]], user_message: str) -> list[dict[str, Any]]:
    allowed = _explicit_allowed_scopes(user_message)
    if not allowed:
        return ops
    filtered: list[dict[str, Any]] = []
    for op in ops:
        op_type = op.get("type")
        path = canonical_path(_normalize_path(op.get("path")))
        inferred = _infer_block_id_from_path(path, op_type)
        if op_type == "add_skill_module" and "skill_modules" in allowed:
            filtered.append(op)
            continue
        if path and any(path == scope or path.startswith(f"{scope}.") for scope in allowed):
            filtered.append(op)
            continue
        if inferred and inferred in allowed:
            filtered.append(op)
    return filtered


def _reject_ops_outside_user_scope(
    ops: list[dict[str, Any]],
    user_message: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed = _explicit_allowed_scopes(user_message)
    if not allowed:
        return ops, []

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for op in ops:
        op_type = op.get("type")
        path = canonical_path(_normalize_path(op.get("path")))
        inferred = _infer_block_id_from_path(path, op_type)
        in_scope = _scope_allows_patch(path, inferred, op_type, allowed)

        if in_scope:
            accepted.append(op)
        else:
            rejected.append({
                "op": op,
                "code": "OUT_OF_SCOPE",
                "message": f"本轮不允许修改 {path or inferred or '未知字段'}",
            })
    return accepted, rejected


def _scope_allows_patch(path: str, inferred: str, op_type: str, allowed: set[str]) -> bool:
    if op_type == "add_skill_module" and "skill_modules" in allowed:
        return True
    if path and any(path == scope or path.startswith(f"{scope}.") for scope in allowed):
        return True
    if inferred and inferred in allowed:
        return True
    if inferred.startswith("skill_modules[") and "skill_modules" in allowed:
        return True
    return False


def _explicit_allowed_scopes(user_message: str) -> set[str]:
    text = user_message or ""
    if not (_requests_preserve_other_content(text) or "只改" in text or "只修改" in text):
        return set()

    scopes: set[str] = set()
    if re.search(r"项目名称|项目名", text):
        scopes.add("project_positioning.project_name")
    if "真实场景" in text:
        scopes.add("project_positioning.real_scene")
    if "赛道" in text or "专业方向" in text:
        scopes.add("project_positioning.track")
        scopes.add("project_positioning.industry")
    if "服务对象" in text:
        scopes.add("project_positioning.service_object")
    if "最终成果" in text or "成果形态" in text:
        scopes.add("project_positioning.final_deliverable")
    if "一句话" in text or "简介" in text:
        scopes.add("project_positioning.one_sentence_intro")
    if "项目定位" in text:
        scopes.add("project_positioning")

    if "痛点" in text or "问题" in text:
        scopes.add("problem_definition.pain_points")
    if "项目目标" in text:
        scopes.add("problem_definition.project_goal")
    if "真实问题" in text or "问题与目标" in text:
        scopes.add("problem_definition")

    for role_label in ("A", "B", "C", "D"):
        if re.search(rf"{role_label}\s*选手", text):
            if "现场动作" in text:
                scopes.add(f"team_roles.{role_label}.onsite_action")
            if "角色" in text:
                scopes.add(f"team_roles.{role_label}.role")
            if "负责" in text or "负责内容" in text:
                scopes.add(f"team_roles.{role_label}.responsibility")
            if not any(scope.startswith(f"team_roles.{role_label}.") for scope in scopes):
                scopes.add(f"team_roles.{role_label}")

    if "技能" in text or "技能模块" in text:
        scopes.add("skill_modules")
    if "成果验证" in text or "成果清单" in text or "证据材料" in text:
        scopes.add("result_validation")
    if "价值创新" in text or "创新点" in text or "实用性" in text:
        scopes.add("value_innovation")
    return scopes


def _block_catalog() -> list[dict[str, str]]:
    return [
        {"block_id": "project_positioning", "label": "项目定位", "field_path": "project_positioning"},
        {"block_id": "problem_definition", "label": "真实问题与目标", "field_path": "problem_definition"},
        {"block_id": "team_roles.A", "label": "A 选手分工", "field_path": "team_roles.A"},
        {"block_id": "team_roles.B", "label": "B 选手分工", "field_path": "team_roles.B"},
        {"block_id": "team_roles.C", "label": "C 选手分工", "field_path": "team_roles.C"},
        {"block_id": "team_roles.D", "label": "D 选手分工", "field_path": "team_roles.D"},
        {"block_id": "skill_modules", "label": "技能展示模块", "field_path": "skill_modules"},
        {"block_id": "result_validation", "label": "成果验证", "field_path": "result_validation"},
        {"block_id": "value_innovation", "label": "价值创新", "field_path": "value_innovation"},
    ]


DIRECT_LIST_TARGETS = (
    {
        "block_id": "problem_definition",
        "path": "problem_definition.pain_points",
        "label": "痛点",
        "labels": ("痛点", "问题"),
    },
    {
        "block_id": "result_validation",
        "path": "result_validation.deliverables",
        "label": "成果清单",
        "labels": ("成果清单",),
    },
    {
        "block_id": "result_validation",
        "path": "result_validation.evidence_materials",
        "label": "证据材料",
        "labels": ("证据材料", "证据"),
    },
    {
        "block_id": "value_innovation",
        "path": "value_innovation.innovation_points",
        "label": "创新点",
        "labels": ("创新点", "创新"),
    },
)


def _build_direct_list_edit_result(
    user_message: str,
    base_state: dict[str, Any],
    validator: CompetitionUnderstandingService,
) -> DocumentEditResult | None:
    ops = _extract_direct_list_patch_ops(user_message)
    if not ops:
        return None

    patched_state, accepted_ops, rejected_ops = apply_patch_ops_to_spec_state(
        base_state,
        ops,
        source="ai",
        allowed_blocks=None,
    )
    if not accepted_ops and not rejected_ops:
        return None

    normalized = validator.build_from_structured_input(unwrap_spec_state(patched_state))
    final_state = merge_plain_values_into_state(patched_state, normalized.spec, source="ai")
    return DocumentEditResult(
        spec=final_state,
        missing_fields=normalized.missing_fields,
        risk_flags=normalized.risk_flags,
        confidence=normalized.confidence,
        input_quality=normalized.input_quality,
        reply=_direct_list_reply(accepted_ops, rejected_ops),
        change_summary=_summarize_ops(accepted_ops),
        destructive_changes=[],
        needs_confirmation=False,
        questions=[],
        ops=accepted_ops,
        rejected_ops=rejected_ops,
    )


def _extract_direct_list_patch_ops(user_message: str) -> list[dict[str, Any]]:
    text = user_message or ""
    if not text.strip():
        return []

    ops: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for target in DIRECT_LIST_TARGETS:
        for item in _extract_direct_items(text, target["labels"]):
            key = (target["path"], item)
            if key in seen:
                continue
            seen.add(key)
            ops.append({
                "type": "append",
                "block_id": target["block_id"],
                "path": target["path"],
                "value": item,
                "source": "ai",
            })
    return ops


def _extract_direct_items(text: str, labels: tuple[str, ...]) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    items: list[str] = []
    label_pattern = "|".join(re.escape(label) for label in labels)

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        inline = re.search(
            rf"^(?:新增|添加|补充|加入|增加|请补充)?\s*(?:{label_pattern})\s*\d*\s*(?:是|为|包括|包含|有|[:：])\s*(.+)$",
            line,
        )
        if inline:
            items.extend(_split_direct_items(inline.group(1)))

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not re.match(rf"^(?:{label_pattern})\s*\d*\s*[：:]?$", line):
            continue
        for following in lines[index + 1:]:
            stripped = following.strip()
            if not stripped:
                if items:
                    break
                continue
            if _looks_like_direct_section_boundary(stripped):
                break
            items.extend(_split_direct_items(stripped))

    return _dedupe_direct_items(items)


def _split_direct_items(value: str) -> list[str]:
    cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.、])\s*", "", value or "").strip()
    if not cleaned:
        return []
    return [
        _clean_direct_item(item)
        for item in _split_inline_items(cleaned)
        if _clean_direct_item(item)
    ]


def _clean_direct_item(value: str) -> str:
    text = re.sub(r"^\s*(?:[-*•]|\d+[.、])\s*", "", value or "")
    text = text.strip(" ：:，,。；; \t")
    if _is_bad_direct_item(text):
        return ""
    return text


def _dedupe_direct_items(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean_direct_item(value)
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _is_bad_direct_item(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    if text in {"待补充", "无", "暂无", "新增", "添加", "补充", "加入", "增加", "新增内容"}:
        return True
    if re.match(r"^\d+[.、]?$", text):
        return True
    if re.match(r"^(一|二|三|四|五|六|七)、", text):
        return True
    if _looks_like_direct_section_boundary(text):
        return True
    return False


def _looks_like_direct_section_boundary(text: str) -> bool:
    return bool(re.match(
        r"^(项目名称|副标题|赛道|专业方向|真实场景|服务对象|最终成果形态|一句话介绍|需求来源|当前做法|痛点\d*|问题后果|项目目标|[ABCD]\s*选手|技能模块\d*|成果清单|证据材料|测试数据|优化前后对比|用户反馈|质量评价|实用性|创新点|教学应用价值|职业场景落地价值|经济性|可持续性|现场展示|评委需要重点看到什么)\s*[：:]?$",
        text,
    ))


def _direct_list_reply(accepted_ops: list[dict[str, Any]], rejected_ops: list[dict[str, Any]]) -> str:
    if not accepted_ops:
        return "这几个字段没有更新，可能是字段已锁定或内容为空。"
    labels = []
    for op in accepted_ops:
        path = op.get("path")
        label = next((target["label"] for target in DIRECT_LIST_TARGETS if target["path"] == path), path or "字段")
        if label not in labels:
            labels.append(label)
    suffix = "；有字段已锁定的部分我没有覆盖。" if rejected_ops else ""
    return f"已把本轮补充内容写入：{'、'.join(labels)}。{suffix}"


def _path_allowed_by_block(block_id: Any, path: str, op_type: str) -> bool:
    inferred_block = _infer_block_id_from_path(path, op_type)
    if not isinstance(block_id, str) or not block_id.strip():
        # Backward-compatible with existing tests and older prompts.
        return True
    block_id = block_id.strip()
    if inferred_block:
        return True
    if op_type == "add_skill_module":
        return block_id == "skill_modules"
    if block_id == "project_positioning":
        return path.startswith("project_positioning.")
    if block_id == "problem_definition":
        return path.startswith("problem_definition.")
    if block_id.startswith("team_roles."):
        return path.startswith(f"{block_id}.")
    if block_id == "skill_modules":
        return path.startswith("skill_modules.")
    if block_id == "result_validation":
        return path.startswith("result_validation.")
    if block_id == "value_innovation":
        return path.startswith("value_innovation.")
    return False


def _infer_block_id_from_path(path: str, op_type: str) -> str:
    path = canonical_path(path)
    if op_type == "add_skill_module":
        return "skill_modules"
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


def _apply_patch_ops(base_spec: dict[str, Any], ops: list[dict[str, Any]]) -> dict[str, Any]:
    spec = deepcopy(base_spec)
    for op in ops:
        op_type = op.get("type")
        path = _normalize_path(op.get("path"))
        if op_type == "add_skill_module":
            if not _path_allowed_by_block(op.get("block_id"), path, op_type):
                continue
            _append_skill_module(spec, op.get("value"))
            continue
        if not path or not _is_allowed_path(path):
            continue
        if not _path_allowed_by_block(op.get("block_id"), path, op_type):
            continue
        if op_type == "set":
            _set_path_value(spec, path, op.get("value"))
        elif op_type == "clear":
            _clear_path_value(spec, path)
        elif op_type == "append_list_item":
            _append_list_item(spec, path, op.get("value"))
        elif op_type == "remove_list_item":
            _remove_list_item(spec, path, op.get("value"))
        elif op_type == "replace_list_item":
            _replace_list_item(spec, path, op.get("old_value"), op.get("value"))
    return spec


def _protect_initial_seed_ops(seed_spec: dict[str, Any], ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep first-turn extraction as the protected baseline; model ops only fill gaps."""
    filtered: list[dict[str, Any]] = []
    for op in ops:
        op_type = op.get("type")
        if op_type == "add_skill_module":
            if seed_spec.get("skill_modules"):
                continue
            filtered.append(op)
            continue

        path = _normalize_path(op.get("path"))
        existing = _get_path_value(seed_spec, path)
        if _has_existing_value(existing):
            continue
        filtered.append(op)
    return filtered


def _get_path_value(spec: dict[str, Any], path: str) -> Any:
    if not path:
        return None
    path = canonical_path(path)
    parts = path.split(".")
    if parts[0] == "team_roles" and len(parts) == 3:
        for role in spec.get("team_roles") or []:
            if isinstance(role, dict) and role.get("member") == parts[1]:
                return role.get(parts[2])
        return None
    skill_match = re.match(r"^skill_modules\[(sm_0[1-4])\]\.([a-z_]+)$", path)
    if skill_match:
        index = int(skill_match.group(1).split("_")[-1]) - 1
        modules = spec.get("skill_modules") or []
        if 0 <= index < len(modules) and isinstance(modules[index], dict):
            return modules[index].get(skill_match.group(2))
        return None

    current: Any = spec
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _has_existing_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return value is not None


def _normalize_path(path: Any) -> str:
    return path.strip() if isinstance(path, str) else ""


def _is_allowed_path(path: str) -> bool:
    if path in {
        "project_positioning.project_name",
        "project_positioning.subtitle",
        "project_positioning.track",
        "project_positioning.industry",
        "project_positioning.real_scene",
        "project_positioning.service_object",
        "project_positioning.final_deliverable",
        "project_positioning.one_sentence_intro",
        "problem_definition.need_source",
        "problem_definition.current_method",
        "problem_definition.problem_consequences",
        "problem_definition.project_goal",
        "problem_definition.pain_points",
        "result_validation.deliverables",
        "result_validation.evidence_materials",
        "result_validation.test_data",
        "result_validation.before_after_comparison",
        "result_validation.user_feedback",
        "result_validation.quality_evaluation",
        "value_innovation.practical_value",
        "value_innovation.innovation_points",
        "value_innovation.teaching_value",
        "value_innovation.vocational_scene_value",
        "value_innovation.sustainability",
    }:
        return True
    if re.match(r"^team_roles\.[ABCD]\.(name|role|responsibility|onsite_action|related_skill_modules)$", path):
        return True
    if re.match(r"^skill_modules\.\d+\.(skill_name|responsible_role|work_task|onsite_demo_action|verification_method|expected_evidence|tools_or_equipment)$", path):
        return True
    return False


def _set_path_value(spec: dict[str, Any], path: str, value: Any) -> None:
    parent, key = _resolve_parent(spec, path)
    if parent is None or key is None:
        return
    if key in {"pain_points", "deliverables", "evidence_materials", "innovation_points", "related_skill_modules"}:
        parent[key] = _coerce_list(value)
    elif isinstance(value, str):
        parent[key] = value.strip()
    elif value is not None:
        parent[key] = value


def _clear_path_value(spec: dict[str, Any], path: str) -> None:
    parent, key = _resolve_parent(spec, path)
    if parent is None or key is None:
        return
    if key in {"pain_points", "deliverables", "evidence_materials", "innovation_points", "related_skill_modules"}:
        parent[key] = []
    else:
        parent[key] = ""


def _append_list_item(spec: dict[str, Any], path: str, value: Any) -> None:
    parent, key = _resolve_parent(spec, path)
    if parent is None or key is None:
        return
    current = parent.get(key)
    if not isinstance(current, list):
        return
    for item in _coerce_list(value):
        if item and item not in current:
            current.append(item)


def _remove_list_item(spec: dict[str, Any], path: str, value: Any) -> None:
    parent, key = _resolve_parent(spec, path)
    if parent is None or key is None:
        return
    current = parent.get(key)
    if not isinstance(current, list):
        return
    targets = _coerce_list(value)
    if not targets:
        return
    parent[key] = [
        item for item in current
        if not any(target in str(item) or str(item) in target for target in targets)
    ]


def _replace_list_item(spec: dict[str, Any], path: str, old_value: Any, value: Any) -> None:
    parent, key = _resolve_parent(spec, path)
    if parent is None or key is None:
        return
    current = parent.get(key)
    if not isinstance(current, list):
        return
    old_items = _coerce_list(old_value)
    new_items = _coerce_list(value)
    if not old_items or not new_items:
        return
    replaced: list[Any] = []
    did_replace = False
    for item in current:
        if any(old_item in str(item) or str(item) in old_item for old_item in old_items):
            for new_item in new_items:
                if new_item and new_item not in replaced:
                    replaced.append(new_item)
            did_replace = True
        else:
            replaced.append(item)
    if did_replace:
        parent[key] = replaced


def _append_skill_module(spec: dict[str, Any], value: Any) -> None:
    if not isinstance(value, dict):
        return
    modules = spec.setdefault("skill_modules", [])
    if not isinstance(modules, list):
        spec["skill_modules"] = []
        modules = spec["skill_modules"]
    module = {
        "skill_name": _string(value.get("skill_name")),
        "responsible_role": _string(value.get("responsible_role")),
        "work_task": _string(value.get("work_task")),
        "onsite_demo_action": _string(value.get("onsite_demo_action")),
        "verification_method": _string(value.get("verification_method")),
        "expected_evidence": _string(value.get("expected_evidence")),
        "tools_or_equipment": _string(value.get("tools_or_equipment")),
    }
    if not module["skill_name"] and not module["work_task"]:
        return
    if not any(existing.get("skill_name") == module["skill_name"] for existing in modules if isinstance(existing, dict)):
        modules.append(module)


def _resolve_parent(spec: dict[str, Any], path: str) -> tuple[dict[str, Any] | None, str | None]:
    parts = path.split(".")
    if len(parts) < 2:
        return None, None
    if parts[0] == "team_roles" and len(parts) == 3:
        role = _ensure_team_role(spec, parts[1])
        return role, parts[2]
    if parts[0] == "skill_modules" and len(parts) == 3 and parts[1].isdigit():
        module = _ensure_skill_module(spec, int(parts[1]))
        return module, parts[2]

    current: Any = spec
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return None, None
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            return None, None
        current = next_value
    return current if isinstance(current, dict) else None, parts[-1]


def _ensure_team_role(spec: dict[str, Any], label: str) -> dict[str, Any] | None:
    if label not in {"A", "B", "C", "D"}:
        return None
    roles = spec.setdefault("team_roles", [])
    if not isinstance(roles, list):
        spec["team_roles"] = []
        roles = spec["team_roles"]
    for role in roles:
        if isinstance(role, dict) and role.get("member") == label:
            return role
    role = {"member": label, "name": "", "role": "", "responsibility": "", "onsite_action": "", "related_skill_modules": []}
    roles.append(role)
    return role


def _ensure_skill_module(spec: dict[str, Any], index: int) -> dict[str, Any] | None:
    if index < 0:
        return None
    modules = spec.setdefault("skill_modules", [])
    if not isinstance(modules, list):
        spec["skill_modules"] = []
        modules = spec["skill_modules"]
    while len(modules) <= index:
        modules.append({
            "skill_name": "",
            "responsible_role": "",
            "work_task": "",
            "onsite_demo_action": "",
            "verification_method": "",
            "expected_evidence": "",
            "tools_or_equipment": "",
        })
    return modules[index] if isinstance(modules[index], dict) else None


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return _split_inline_items(value)
    return []


def _summarize_ops(ops: list[dict[str, Any]]) -> list[str]:
    summaries = []
    for op in ops:
        op_type = op.get("type")
        path = op.get("path") or "skill_modules"
        if op_type:
            summaries.append(f"{op_type}: {path}")
    return summaries


def _destructive_ops(ops: list[dict[str, Any]]) -> list[str]:
    destructive = []
    for op in ops:
        if op.get("type") in {"clear", "remove_list_item", "replace_list_item"}:
            destructive.append(f"{op.get('type')}: {op.get('path') or ''}".strip())
    return destructive


def _has_meaningful_content(spec: dict[str, Any]) -> bool:
    positioning = spec.get("project_positioning") or {}
    problem = spec.get("problem_definition") or {}
    roles = spec.get("team_roles") or []
    modules = spec.get("skill_modules") or []
    validation = spec.get("result_validation") or {}
    return any([
        positioning.get("project_name"),
        positioning.get("real_scene"),
        positioning.get("service_object"),
        positioning.get("final_deliverable"),
        problem.get("pain_points"),
        problem.get("project_goal"),
        any(role.get("role") or role.get("responsibility") or role.get("onsite_action") for role in roles if isinstance(role, dict)),
        modules,
        validation.get("deliverables"),
        validation.get("evidence_materials"),
    ])


def _looks_like_instruction(value: str, user_message: str) -> bool:
    text = value.strip()
    if not text:
        return True
    compact_text = "".join(text.split())
    compact_user = "".join((user_message or "").split())
    if compact_user and compact_text == compact_user:
        return True
    if all(marker in text for marker in ("A选手", "B选手")) and "负责" in text:
        return True
    markers = (
        "其他内容不要动",
        "不要动",
        "改成",
        "删除痛点",
        "删除",
        "保留其他",
        "真正要改的是",
        "下面这句话只是备注",
        "请在保留已有有效内容",
        "输出更新后的结构化稿件",
    )
    return any(marker in text for marker in markers)


def _requests_preserve_other_content(user_message: str) -> bool:
    return any(marker in (user_message or "") for marker in (
        "其他内容不要动",
        "其他不要动",
        "其他内容保持原样",
        "其他保持原样",
        "其他内容保持不变",
        "其他不变",
        "A、C、D不要改",
        "A、C和D不要改",
    ))


def _apply_explicit_user_overrides(spec: dict[str, Any], user_message: str) -> None:
    text = user_message or ""
    positioning = spec.setdefault("project_positioning", {})
    problem = spec.setdefault("problem_definition", {})

    name = _extract_quoted_or_plain_after(
        text,
        (
            r"项目名称\s*(?:改成|改为|换成|变成)\s*",
            r"项目名\s*(?:改成|改为|换成|变成)\s*",
            r"名称\s*(?:改成|改为|换成|变成)\s*",
            r"项目名称\s*(?:叫|是|为)\s*",
            r"项目名\s*(?:叫|是|为)\s*",
        ),
    )
    if name:
        positioning["project_name"] = name

    scene = _extract_quoted_or_plain_after(text, (r"真实场景\s*(?:改成|改为|补充为|是|为)\s*",))
    if scene:
        positioning["real_scene"] = scene

    track = _extract_quoted_or_plain_after(text, (r"赛道\s*(?:改成|改为|补充为|是|为)\s*", r"专业方向\s*(?:改成|改为|补充为|是|为)\s*"))
    if track:
        positioning["track"] = track

    service_object = _extract_quoted_or_plain_after(text, (r"服务对象\s*(?:改成|改为|补充为|是|为)\s*",))
    if service_object:
        positioning["service_object"] = service_object

    final_deliverable = _extract_quoted_or_plain_after(text, (r"(?:最终成果|最终成果形态)\s*(?:改成|改为|补充为|是|为|包括)\s*",))
    if final_deliverable:
        positioning["final_deliverable"] = final_deliverable

    project_goal = _extract_quoted_or_plain_after(text, (r"项目目标\s*(?:改成|改为|补充为|是|为)\s*",))
    if project_goal:
        problem["project_goal"] = project_goal

    pain_points = _extract_inline_section_items(text, ("痛点", "问题"))
    if pain_points:
        problem["pain_points"] = pain_points

    for item in _extract_remove_items(text, ("痛点", "问题")):
        pain_points = problem.get("pain_points") or []
        problem["pain_points"] = [
            pain
            for pain in pain_points
            if item not in str(pain) and str(pain) not in item
        ]

    for role_label, replacement in _extract_role_replacements(text):
        _apply_role_replacement(spec, role_label, replacement, text)

    for role_label, responsibility, onsite_action in _extract_initial_roles(text):
        _apply_role_replacement(spec, role_label, responsibility, text, onsite_action=onsite_action)


def _extract_quoted_or_plain_after(text: str, prefixes: tuple[str, ...]) -> str:
    for prefix in prefixes:
        quoted = re.search(prefix + r"[“\"']([^”\"'。；;\n]+)[”\"']", text)
        if quoted:
            return quoted.group(1).strip()
        plain = re.search(prefix + r"([^。；;\n]+)", text)
        if plain:
            value = plain.group(1).strip(" ：:，, ")
            value = re.split(
                r"(?:，|,)?\s*(?:服务对象|最终成果|最终成果形态|痛点|项目目标|其他内容不要动|其他不要动|不要动|保留|A、C、D|A、C和D)",
                value,
                maxsplit=1,
            )[0]
            value = re.split(r"(?:，|,)?\s*(?:删除|去掉|删掉|不要)", value, maxsplit=1)[0].strip(" ：:，, ")
            if value and not _looks_like_instruction(value, text):
                return value
    return ""


def _extract_remove_items(text: str, labels: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    label_pattern = "|".join(re.escape(label) for label in labels)
    for match in re.finditer(rf"(?:删除|去掉|删掉|不要)(?:这个|该)?(?:{label_pattern})?[：:]?\s*[“\"']([^”\"']+)[”\"']", text):
        items.append(match.group(1).strip())
    for match in re.finditer(rf"(?:删除|去掉|删掉|不要)(?:这个|该)?(?:{label_pattern})[：:]\s*([^。；;\n]+)", text):
        items.extend(_split_inline_items(match.group(1)))
    return [item for item in items if item]


def _extract_inline_section_items(text: str, labels: tuple[str, ...]) -> list[str]:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})\s*(?:是|为|包括|有|包含)\s*([^。\n]+)", text)
    if not match:
        return []
    return _split_inline_items(match.group(1))


def _extract_role_replacements(text: str) -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []
    for match in re.finditer(r"([ABCD])\s*选手(?:(?!现场动作).)*?(?:改成|改为|换成)\s*[“\"']?([^”\"'，,。；;\n]+)", text):
        replacements.append((match.group(1), match.group(2).strip()))
    return replacements


def _extract_initial_roles(text: str) -> list[tuple[str, str, str]]:
    roles: list[tuple[str, str, str]] = []
    stop_sections = r"\n\s*(?:技能模块|成果清单|证据材料|实用性|创新点|项目名称|赛道|真实场景|服务对象|最终成果形态|痛点|项目目标)[：:]"
    pattern = re.compile(
        rf"([ABCD])\s*选手\s*负责\s*(.+?)(?=(?:[ABCD]\s*选手\s*负责)|{stop_sections}|$)",
        re.S,
    )
    for match in pattern.finditer(text):
        block = re.sub(r"\s+", " ", match.group(2)).strip(" ：:，,。；;")
        responsibility = re.split(r"现场动作\s*(?:是|为|改成|改为|换成|[:：])", block, maxsplit=1)[0]
        responsibility = responsibility.strip(" ：:，,。；;")
        action_match = re.search(r"现场动作\s*(?:是|为|改成|改为|换成|[:：])\s*(.+?)(?:[。；;]|$)", block)
        onsite_action = action_match.group(1).strip(" ：:，,。；;") if action_match else ""
        if responsibility:
            roles.append((match.group(1), responsibility, onsite_action))
    return roles


def _apply_role_replacement(
    spec: dict[str, Any],
    role_label: str,
    replacement: str,
    user_message: str,
    *,
    onsite_action: str | None = None,
) -> None:
    roles = spec.setdefault("team_roles", [])
    if not isinstance(roles, list):
        return
    role = None
    for item in roles:
        if isinstance(item, dict) and item.get("member") == role_label:
            role = item
            break
    if role is None:
        role = {"member": role_label, "name": "", "role": "", "responsibility": "", "onsite_action": "", "related_skill_modules": []}
        roles.append(role)

    role["role"] = replacement
    role["responsibility"] = replacement
    if onsite_action is None:
        onsite_action = _extract_quoted_or_plain_after(user_message, (r"现场动作\s*(?:改成|改为|换成|是|为)\s*",))
    if onsite_action:
        role["onsite_action"] = onsite_action


def _split_inline_items(text: str) -> list[str]:
    return [item.strip(" ：:，,。 ") for item in re.split(r"[；;、,，]", text) if item.strip(" ：:，,。 ")]

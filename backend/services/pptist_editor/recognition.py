"""Small, lossless vision-response adapter; never relax the semantic contract."""
from copy import deepcopy
import json
import re

from pydantic import ValidationError


class RecognitionError(ValueError):
    def __init__(self, code, field, reason):
        self.issues = [dict(code=code, field=field, reason=reason)]
        super().__init__(reason)


def parse_response(response):
    if not isinstance(response, str) or len(response.encode('utf-8')) > 4 * 1024 * 1024:
        raise RecognitionError('response_size', 'response', '识别响应为空、类型错误或超过 4 MiB')
    text = response.strip().lstrip('\ufeff').strip()
    fence = re.fullmatch(r'```(?:json)?\s*\n?(.*?)\s*```', text, re.S | re.I)
    if fence:
        text = fence.group(1)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RecognitionError('duplicate_key', 'response', 'JSON 含重复字段，不能安全选择其中一个值')
            result[key] = value
        return result

    def constant(_):
        raise RecognitionError('nonfinite_number', 'response', 'JSON 含非有限数字')

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except json.JSONDecodeError as exc:
        raise RecognitionError('invalid_json', 'response', f'JSON 格式错误（第 {exc.lineno} 行，第 {exc.colno} 列），可能被截断') from exc


def normalize_plan(value):
    """Only exact representational equivalents; no bbox guessing or content loss."""
    if not isinstance(value, dict):
        raise RecognitionError('object_required', 'response', '识别响应必须是页面对象')
    plan = deepcopy(value)
    changes = []

    def alias(obj, old, new, field):
        if old not in obj:
            return
        if new in obj and obj[new] != obj[old]:
            raise RecognitionError('alias_conflict', field + '.' + new, '同一字段存在相互冲突的别名值')
        obj[new] = obj.pop(old)
        changes.append(field + '.' + new)

    def colors(obj, keys, field):
        for key in keys:
            c = obj.get(key)
            if not isinstance(c, str):
                continue
            raw = c.strip()
            if re.fullmatch(r'#?[a-fA-F0-9]{6}', raw):
                normalized = raw.lstrip('#').upper()
            elif re.fullmatch(r'#[a-fA-F0-9]{3}', raw):
                normalized = ''.join(char * 2 for char in raw[1:]).upper()
            else:
                rgb = re.fullmatch(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', raw)
                if not rgb or any(int(n) > 255 for n in rgb.groups()):
                    continue  # Transparency, gradients, URLs etc. still fail validation.
                normalized = ''.join(f'{int(n):02X}' for n in rgb.groups())
            if normalized != c:
                obj[key] = normalized
                changes.append(field + '.' + key)

    colors(plan, ('background',), 'page')
    if plan.get('groups', []) is None:
        plan['groups'] = []
        changes.append('page.groups')
    if not isinstance(plan.get('nodes'), list):
        raise RecognitionError('nodes_required', 'nodes', '页面对象列表缺失或类型错误')
    for i, node in enumerate(plan['nodes']):
        field = f'nodes[{i}]'
        if not isinstance(node, dict):
            raise RecognitionError('object_required', field, '页面成员必须是对象')
        box = node.get('box')
        if isinstance(box, dict):
            alias(box, 'width', 'w', field + '.box')
            alias(box, 'height', 'h', field + '.box')
        shape = node.get('shape')
        if isinstance(shape, dict):
            colors(shape, ('fill', 'stroke'), field + '.shape')
            if shape.get('geometry') == 'roundedRect':
                shape['geometry'] = 'roundRect'
                changes.append(field + '.shape.geometry')
        text = node.get('text')
        if isinstance(text, dict) and isinstance(text.get('paragraphs'), list):
            for j, paragraph in enumerate(text['paragraphs']):
                if not isinstance(paragraph, dict) or not isinstance(paragraph.get('runs'), list):
                    continue
                for k, run in enumerate(paragraph['runs']):
                    if isinstance(run, dict):
                        run_field = f'{field}.text.paragraphs[{j}].runs[{k}]'
                        alias(run, 'fontSize', 'size', run_field)
                        colors(run, ('color',), run_field)
        table = node.get('table')
        if isinstance(table, dict):
            colors(table, ('header_fill', 'body_fill', 'text_color', 'header_color'), field + '.table')
    return plan, changes


# Do not expose Pydantic's input, ctx repr, unknown keys, or arbitrary exceptions.
REASONS = {
    'duplicate object ID': '页面对象 ID 重复',
    'ambiguous layer order': '对象图层序号重复，无法确定遮挡顺序',
    'missing or cyclic group parent': '组合引用缺失或形成循环',
    'group crosses semantic module': '组合和成员的 module_id 不一致',
    'group must contain contiguous layers; regrouping would change occlusion': '组合成员图层不连续，直接重组会改变遮挡关系',
    'object outside page': '存在超出画布的对象（含旋转边界）',
    'native text overlaps preserved screenshot': '保留的软件截图内重复创建了文字',
    'table must be rectangular with positive column weights': '表格行列不齐或列宽无效',
    'node kind and payload disagree': '对象类型与其内容字段不一致',
    'rotated native tables unsupported in schema v1': '暂不支持旋转的原生表格',
    'nested groups are not editable in PPTist MVP': '暂不支持嵌套组合',
    'mixed paragraph spacing unsupported by PPTist': '同一文本框中的段落间距不一致，暂不支持',
    'unsupported font name': '字体名称格式不受支持',
    'full-page content image forbidden': '不能以整页图片伪装成可编辑页面',
}
TYPE_REASONS = {
    'missing': '缺少必填字段', 'extra_forbidden': '包含不支持的字段',
    'literal_error': '字段值不属于当前支持范围',
    'string_pattern_mismatch': '字段格式不符合约定',
    'greater_than': '数值必须大于约定下限', 'greater_than_equal': '数值低于允许范围',
    'less_than_equal': '数值超过允许范围', 'finite_number': '数值必须有限',
    'string_type': '必须为字符串', 'list_type': '必须为列表',
    'model_type': '必须为对象', 'float_parsing': '数值格式错误',
}
SAFE_FIELDS = set('nodes groups background box x y w h id name kind layer module_id parent_id column_id rotation shape geometry fill stroke stroke_width text paragraphs runs size font color bold italic align line_spacing space_after picture role table rows column_weights header_fill body_fill text_color header_color confidence'.split())


def validation_issues(exc):
    if isinstance(exc, RecognitionError):
        return exc.issues
    if isinstance(exc, ValidationError):
        issues = []
        for error in exc.errors(include_input=False, include_url=False)[:6]:
            path = ''
            for component in error['loc']:
                path += f'[{component}]' if isinstance(component, int) else ('.' if path else '') + (component if component in SAFE_FIELDS else '?')
            known_reason = REASONS.get(str(error.get('ctx', {}).get('error', '')))
            issues.append(dict(code=error['type'], field=path or 'page', reason=known_reason or TYPE_REASONS.get(error['type'], '字段未通过语义约束')))
        return issues
    return [dict(code='semantic_contract', field='page', reason=REASONS.get(str(exc), '对象结构不符合当前编辑器支持范围'))]


def issue_summary(issues):
    return '；'.join(f'{issue["field"]}: {issue["reason"]}' for issue in issues[:3])

#!/usr/bin/env python3
"""Render synchronized competition PPT Markdown from one authored page record.

Standard library only. This does not infer project facts or generate a PPTX.
"""
import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHAPTERS = ('项目设计', '工作流程', '核心技能', '成果展示', '未来展望')
KINDS = {'cover': '首页', 'contents': '目录页', 'transition': '章节过渡页', 'content': '内容页'}
NO_NAV = '不显示导航栏；幻灯片画面不显示页码或页数分式。'
HEAD = re.compile(r'^第\s+(\d+)\s+页：([^\n]+)$', re.M)
GROUPS = {'fact': '已提取事实及依据', 'proposal': '智能体代拟与建议', 'missing': '待确认及素材需求'}
TEMPLATE_NAMES = ('2026世界职业院校技能大赛通用PPT大纲模板.md',
                  '2026世界职业院校技能大赛通用PPT逐页描述模板.md')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def line(value):
    return isinstance(value, str) and bool(value.strip()) and '\n' not in value and '\r' not in value


def chapter_label(chapter):
    return f'{chapter:02d} {CHAPTERS[chapter - 1]}' if chapter else '开场'


def navigation(page):
    if page['kind'] != 'content' or page['chapter'] == 0:
        return NO_NAV
    labels = '｜'.join(chapter_label(i) for i in range(1, len(CHAPTERS) + 1))
    return (f'右上角：{labels}；当前高亮：{chapter_label(page["chapter"])}'
            '（主题色加深背景并加粗）；其余章节常规显示。幻灯片画面不显示页码或页数分式。')


def validate_sequence(pages):
    require(len(pages) >= 2 + 2 * len(CHAPTERS), '需有首页、目录、五张过渡页及每章至少一张内容页')
    require(pages[0]['kind'] == 'cover', '第一页必须为首页')
    opening_team = pages[1]['kind'] == 'content' and pages[1]['chapter'] == 0
    contents_index = 2 if opening_team else 1
    require(pages[contents_index]['kind'] == 'contents', '目录必须紧随首页或第二页开场团队介绍')
    require(sum(p['kind'] == 'cover' for p in pages) == 1, '首页只能有一张')
    require(sum(p['kind'] == 'contents' for p in pages) == 1, '目录只能有一张')
    current = 0
    transitions = []
    counts = {i: 0 for i in range(1, len(CHAPTERS) + 1)}
    for n, p in enumerate(pages, 1):
        kind, ch = p['kind'], p['chapter']
        require(kind in KINDS, f'第{n}页类型无效')
        require(type(ch) is int and ch in range(len(CHAPTERS) + 1), f'第{n}页章节应为0—5的整数')
        if kind in ('cover', 'contents'):
            require(ch == 0, f'第{n}页开场章节必须为0')
            continue
        if kind == 'content' and ch == 0:
            require(n == 2 and opening_team, '开场内容只能位于第二页')
            continue
        require(ch in range(1, len(CHAPTERS) + 1), f'第{n}页缺少有效所属章节')
        if kind == 'transition':
            require(ch == current + 1, f'第{n}页过渡章节顺序错误或重复')
            current = ch
            transitions.append(ch)
        else:
            require(ch == current, f'第{n}页内容未跟随所属章节过渡页')
            counts[ch] += 1
    require(transitions == list(range(1, len(CHAPTERS) + 1)), '必须有按顺序排列的五张章节过渡页')
    require(all(counts.values()), '每章至少保留一张内容页')


def validate_record(record):
    require(isinstance(record, dict), '页面记录必须是JSON对象')
    require(line(record.get('project')), 'project 必须为非空单行项目名称')
    require(record.get('mode') in ('project', 'template'), 'mode 必须为 project 或 template')
    pages = record.get('pages')
    require(isinstance(pages, list) and bool(pages), 'pages 必须是非空列表')
    for n, p in enumerate(pages, 1):
        require(isinstance(p, dict), f'第{n}页必须是对象')
        for field in ('title', 'purpose', 'kind'):
            require(line(p.get(field)), f'第{n}页 {field} 必须是非空单行文字')
        require('chapter' in p, f'第{n}页缺少chapter')
        for field in ('text', 'layout', 'materials'):
            vals = p.get(field)
            require(isinstance(vals, list) and bool(vals) and all(line(v) for v in vals),
                    f'第{n}页 {field} 必须是非空单行文字列表')
        for field in ('speaker_notes', 'action_notes'):
            vals = p.get(field, [])
            require(isinstance(vals, list) and all(line(v) for v in vals),
                    f'第{n}页 {field} 必须是单行文字列表，可为空')
    validate_sequence(pages)
    checklist = record.get('checklist')
    require(isinstance(checklist, list), 'checklist 必须是列表，可为空')
    for n, item in enumerate(checklist, 1):
        require(isinstance(item, dict), f'清单第{n}项必须为对象')
        require(item.get('category') in GROUPS, f'清单第{n}项分类无效')
        for field in ('content', 'status', 'basis', 'action'):
            require(line(item.get(field)), f'清单第{n}项 {field} 必须有说明')
        refs = item.get('pages')
        require(isinstance(refs, list) and bool(refs) and
                all(type(i) is int and 1 <= i <= len(pages) for i in refs),
                f'清单第{n}项引用了不存在的页码')
        require(len(refs) == len(set(refs)), f'清单第{n}项有重复页码')


def section(label, values):
    return label + '：\n' + '\n'.join('- ' + v for v in values) + '\n'


def render_pair(record):
    outline, description = '', ''
    for n, p in enumerate(record['pages'], 1):
        prefix = (f'第 {n} 页：{p["title"]}\n\n'
                  f'页面类型：{KINDS[p["kind"]]}\n'
                  f'所属章节：{chapter_label(p["chapter"])}\n\n')
        outline += (prefix + section('展示用途', [p['purpose']]) + '\n' +
                    section('核心内容', p['text']) + '\n' + section('主画面建议', p['layout']) + '\n' +
                    section('素材要求', p['materials']) + '\n' + section('导航要求', [navigation(p)]) + '\n')
        description += (prefix + section('页面文字', p['text']) + '\n' +
                        section('页面画面与版式', p['layout']) + '\n' + section('展示用途', [p['purpose']]) + '\n' +
                        section('素材要求', p['materials']) + '\n' + section('导航状态', [navigation(p)]) + '\n')
    return outline, description


def render_checklist(record):
    result = (f'# {record["project"]}｜待确认与素材清单\n\n'
              '本清单供内容确认和素材准备，不是幻灯片正文。建议方案不等于已实现；材料陈述不等于本次验证。\n\n')
    for category, label in GROUPS.items():
        result += f'## {label}\n\n'
        items = [x for x in record['checklist'] if x['category'] == category]
        if not items:
            result += '当前未列出此类事项。\n\n'
        for item in items:
            refs = '、'.join(f'P{i}' for i in item['pages'])
            result += (f'### {item["content"]}\n\n对应页码：{refs}\n\n'
                       f'- 状态：{item["status"]}\n- 来源或理由：{item["basis"]}\n'
                       f'- 补充或替代处理：{item["action"]}\n\n')
    result += '## 讲稿与现场提示（不上屏）\n\n'
    result += '优先核对已有逐字稿；已覆盖的不重复补写。以下是讲稿对照与演练提示，不是完整逐字稿，也不是新增幻灯片文字。\n\n'
    for n, page in enumerate(record['pages'], 1):
        speech, action = page.get('speaker_notes', []), page.get('action_notes', [])
        if not speech and not action:
            continue
        result += f'### 第{n}页｜{page["title"]}\n\n对应页码：P{n}\n\n'
        if speech:
            result += section('讲稿对照与补充', speech) + '\n'
        if action:
            result += section('现场动作与同步', action) + '\n'
    return result


def parse_markdown(text, labels):
    matches = list(HEAD.finditer(text))
    require(bool(matches), '没有可解析的“第 X 页：标题”页头')
    pages = []
    for index, match in enumerate(matches):
        number, title = int(match[1]), match[2].strip()
        require(number == index + 1, f'页码不连续：预期{index+1}，实际{number}')
        block = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        kind_match = re.findall(r'^页面类型：([^\n]+)$', block, re.M)
        ch_match = re.findall(r'^所属章节：([^\n]+)$', block, re.M)
        require(len(kind_match) == len(ch_match) == 1, f'第{number}页类型/章节字段缺失或重复')
        reverse_kind = {v: k for k, v in KINDS.items()}
        reverse_ch = {chapter_label(i): i for i in range(len(CHAPTERS) + 1)}
        require(kind_match[0] in reverse_kind and ch_match[0] in reverse_ch, f'第{number}页类型/章节非法')
        p = dict(title=title, kind=reverse_kind[kind_match[0]], chapter=reverse_ch[ch_match[0]])
        sections = {}
        section_matches = list(re.finditer(r'^([^\n：]+)：\s*$', block, re.M))
        for j, m in enumerate(section_matches):
            label = m[1]
            require(label not in sections, f'第{number}页重复栏目：{label}')
            sections[label] = block[m.end():section_matches[j + 1].start() if j + 1 < len(section_matches) else len(block)].strip()
        for label in labels:
            require(bool(sections.get(label, '').strip('- \n')), f'第{number}页缺少或空白栏目：{label}')
        nav = sections[labels[-1]]
        require(nav.removeprefix('- ').strip() == navigation(p), f'第{number}页导航状态错误或格式不一致')
        if p['kind'] != 'content':
            require('当前高亮：' not in block and '右上角：01' not in block, f'第{number}页免导航页出现导航')
        require(not re.search(r'P\s*\d+\s*/\s*\d+', block), f'第{number}页含画面页数分式')
        p['sections'] = sections
        pages.append(p)
    validate_sequence(pages)
    return pages


def validate_markdown(outline, description, checklist=None):
    a = parse_markdown(outline, ('展示用途', '核心内容', '主画面建议', '素材要求', '导航要求'))
    b = parse_markdown(description, ('页面文字', '页面画面与版式', '展示用途', '素材要求', '导航状态'))
    require(len(a) == len(b), '大纲与逐页描述页数不一致')
    for i, (x, y) in enumerate(zip(a, b), 1):
        for field in ('title', 'kind', 'chapter'):
            require(x[field] == y[field], f'第{i}页 {field} 不一致')
        for left, right in [('核心内容', '页面文字'), ('主画面建议', '页面画面与版式'),
                            ('素材要求', '素材要求'), ('展示用途', '展示用途')]:
            require(x['sections'][left] == y['sections'][right], f'第{i}页{left}与{right}未同步')
    if checklist is not None:
        for label in GROUPS.values():
            require(f'## {label}' in checklist, f'配套清单缺少：{label}')
        for refs in re.findall(r'^对应页码：([^\n]+)$', checklist, re.M):
            require(bool(re.fullmatch(r'P\d+(?:、P\d+)*', refs)), '清单页码格式错误')
            require(all(1 <= int(n) <= len(a) for n in re.findall(r'P(\d+)', refs)), '清单页码超出实际页数')
    return {'pages': len(a), 'titles_aligned': True, 'navigation_valid': True,
            'transitions': [i for i, p in enumerate(a, 1) if p['kind'] == 'transition']}


def safe_name(project):
    name = re.sub(r'[\x00-\x1f/\\:*?"<>|]', '_', project).strip(' .')
    require(bool(name) and name not in ('.', '..'), '项目名不能转换为有效文件名')
    return name


def save_files(output_dir, files):
    """Validate first, stage all files, back up originals, then replace each atomically."""
    output_dir.mkdir(parents=True, exist_ok=True)
    internal_dir = output_dir if output_dir.name == '.ppt-input' else output_dir / '.ppt-input'
    backup = internal_dir / 'backups' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    existing = [name for name in files if (output_dir / name).exists()]
    if existing:
        backup.mkdir(parents=True)
        for name in existing:
            shutil.copy2(output_dir / name, backup / name)
    with tempfile.TemporaryDirectory(prefix='.ppt-stage-', dir=output_dir) as temp:
        stage = Path(temp)
        for name, content in files.items():
            (stage / name).write_text(content, encoding='utf-8')
        replaced = []
        try:
            for name in files:
                (stage / name).replace(output_dir / name)
                replaced.append(name)
        except OSError:
            for name in reversed(replaced):
                if name in existing:
                    shutil.copy2(backup / name, output_dir / name)
                else:
                    (output_dir / name).unlink(missing_ok=True)
            raise
    return [str((output_dir / name).resolve()) for name in files]


def load_record(path):
    record = json.loads(path.read_text(encoding='utf-8'))
    validate_record(record)
    return record


def render_to_directory(record, output_dir, templates=False):
    validate_record(record)
    a, b = render_pair(record)
    c = render_checklist(record)
    result = validate_markdown(a, b, c)
    name = safe_name(record['project'])
    names = TEMPLATE_NAMES if templates else (f'{name}_PPT大纲.md', f'{name}_PPT逐页描述.md')
    files = {names[0]: a, names[1]: b}
    checklist_name = ('2026世界职业院校技能大赛通用PPT待确认与素材清单.md' if templates
                      else f'{name}_待确认与素材清单.md')
    files[checklist_name] = c
    result['files'] = save_files(output_dir, files)
    # Retain the same record for subsequent edits, including callers outside .ppt-input.
    internal = output_dir / '.ppt-input'
    record_name = 'template-record.json' if templates else name + '.json'
    save_files(internal, {record_name: json.dumps(record, ensure_ascii=False, indent=2) + '\n'})
    result['record'] = str((internal / record_name).resolve())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    render = subs.add_parser('render', help='从智能体整理的统一JSON生成三份Markdown')
    render.add_argument('record', type=Path)
    render.add_argument('--output-dir', required=True, type=Path)
    export = subs.add_parser('export-templates', help='同步导出两份通用模板及含讲稿提示的配套清单')
    export.add_argument('--output-dir', required=True, type=Path)
    validate = subs.add_parser('validate', help='只读校验两份Markdown与可选清单')
    validate.add_argument('outline', type=Path)
    validate.add_argument('description', type=Path)
    validate.add_argument('--checklist', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'validate':
            result = validate_markdown(args.outline.read_text(encoding='utf-8'),
                                       args.description.read_text(encoding='utf-8'),
                                       args.checklist.read_text(encoding='utf-8') if args.checklist else None)
        elif args.command == 'render':
            result = render_to_directory(load_record(args.record), args.output_dir)
        else:
            record = load_record(ROOT / 'resources' / 'page-blueprint.json')
            require(record['mode'] == 'template' and len(record['pages']) == 47,
                    '默认通用骨架应为47页template记录')
            result = render_to_directory(record, args.output_dir, templates=True)
        print(json.dumps({'ok': True, **result}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

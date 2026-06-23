"""
AI Service Prompts - 集中管理所有 AI 服务的 prompt 模板

分区:
  1. 共享工具 & 常量    — 语言配置、格式化辅助、DRY 常量
  2. 大纲 Prompts       — 生成、解析、细化大纲
  3. 描述 Prompts       — 单页、流式、拆分、细化描述
  4. 图片生成 Prompts   — 文生图、图片编辑
  5. 图片处理 Prompts   — 背景提取、画质修复
  6. 内容提取 Prompts   — 文字属性、页面内容、排版分析、风格提取
  7. 旁白 Prompts        — TTS 播报视频旁白生成
"""
import json
import logging
import re
from typing import List, Dict, Optional, TYPE_CHECKING, Any

from services.prompt_registry import prompt_registry

if TYPE_CHECKING:
    from services.ai_service import ProjectContext

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 共享工具 & 常量
# ═══════════════════════════════════════════════════════════════════════════════


# --- 常量 ---

LANGUAGE_CONFIG = {
    'zh': {
        'name': '中文',
        'instruction_id': 'language.instruction.zh',
        'ppt_text_id': 'language.ppt_text.zh'
    },
    'ja': {
        'name': '日本語',
        'instruction_id': 'language.instruction.ja',
        'ppt_text_id': 'language.ppt_text.ja'
    },
    'en': {
        'name': 'English',
        'instruction_id': 'language.instruction.en',
        'ppt_text_id': 'language.ppt_text.en'
    },
    'auto': {
        'name': '自动',
        'instruction_id': None,
        'ppt_text_id': None
    }
}

DETAIL_LEVEL_SPECS = {
    'concise': 'detail.concise',
    'default': 'detail.default',
    'detailed': 'detail.detailed',
}

DEFAULT_NARRATION_CONFIG = {
    'speaker_persona': 'knowledgeable and patient university professor',
    'target_audience': 'the general public with no technical background',
    'speech_tone': 'analytical, data-driven, and highly professional',
    'presentation_topic': 'the main ideas and key takeaways of this presentation',
    'min_words': 100,
    'max_words': 200,
}

_NARRATION_MIN_WORDS_LOWER_BOUND = 30
_NARRATION_MAX_WORDS_UPPER_BOUND = 300

_OUTLINE_JSON_FORMAT = "outline.json_format"
_DESCRIPTION_STYLE_BOUNDARY = "description.style_boundary"


# --- 辅助函数 ---

def _build_prompt(prompt_text: str, reference_files_content=None, *, tag: str = '') -> str:
    """Prepend reference files XML and log the final prompt."""
    files_xml = _format_reference_files_xml(reference_files_content)
    final = files_xml + prompt_text
    if tag:
        logger.debug(f"[{tag}] Final prompt:\n{final}")
    return final


def _get_original_input(project_context: 'ProjectContext') -> str:
    """Extract original user input from project context (shared across prompt builders)."""
    if project_context.creation_type == 'idea' and project_context.idea_prompt:
        return project_context.idea_prompt
    if project_context.creation_type == 'outline' and project_context.outline_text:
        return f"用户提供的大纲：\n{project_context.outline_text}"
    if project_context.creation_type == 'descriptions' and project_context.description_text:
        return f"用户提供的描述：\n{project_context.description_text}"
    return project_context.idea_prompt or ""


def _get_original_input_labeled(project_context: 'ProjectContext') -> str:
    """Build labeled original input section for refinement prompts."""
    text = "\n原始输入信息：\n"
    if project_context.creation_type == 'idea' and project_context.idea_prompt:
        text += f"- PPT构想：{project_context.idea_prompt}\n"
    elif project_context.creation_type == 'outline' and project_context.outline_text:
        text += f"- 用户提供的大纲文本：\n{project_context.outline_text}\n"
    elif project_context.creation_type == 'descriptions' and project_context.description_text:
        text += f"- 用户提供的页面描述文本：\n{project_context.description_text}\n"
    elif project_context.idea_prompt:
        text += f"- 用户输入：{project_context.idea_prompt}\n"
    return text


def _get_previous_requirements_text(previous_requirements: Optional[List[str]]) -> str:
    """Format previous modification history."""
    if not previous_requirements:
        return ""
    prev_list = "\n".join([f"- {req}" for req in previous_requirements])
    return f"\n\n之前用户提出的修改要求：\n{prev_list}\n"


def _normalize_word_count(value: Any, default: int) -> int:
    """Normalize narration word-count inputs to a safe integer range."""
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = default
    return max(_NARRATION_MIN_WORDS_LOWER_BOUND, min(_NARRATION_MAX_WORDS_UPPER_BOUND, normalized))


def get_default_narration_generation_config(fallback_topic: str = '') -> Dict[str, Any]:
    """Return the default narration config, filling topic from project context when possible."""
    config = dict(DEFAULT_NARRATION_CONFIG)
    topic = (fallback_topic or '').strip()
    if topic:
        config['presentation_topic'] = topic
    return config


def normalize_narration_generation_config(
    config: Optional[Dict[str, Any]] = None,
    fallback_topic: str = '',
) -> Dict[str, Any]:
    """Normalize narration generation options from UI/API payloads."""
    normalized = get_default_narration_generation_config(fallback_topic=fallback_topic)
    if not isinstance(config, dict):
        return normalized

    for field in ('speaker_persona', 'target_audience', 'speech_tone', 'presentation_topic'):
        value = config.get(field)
        if isinstance(value, str) and value.strip():
            normalized[field] = value.strip()

    min_words = _normalize_word_count(config.get('min_words'), normalized['min_words'])
    max_words = _normalize_word_count(config.get('max_words'), normalized['max_words'])
    if max_words < min_words:
        max_words = min_words

    normalized['min_words'] = min_words
    normalized['max_words'] = max_words
    return normalized


def parse_narration_generation_result(result: str) -> Dict[int, str]:
    """Parse batched narration output split by the `=== SLIDE n ===` delimiter."""
    if not result or not result.strip():
        return {}

    sections = re.split(r'===\s*SLIDE\s+(\d+)\s*===', result)
    if len(sections) <= 1:
        return {}

    parsed: Dict[int, str] = {}
    iterator = iter(sections[1:])
    for idx_str, text in zip(iterator, iterator):
        try:
            parsed[int(idx_str)] = text.strip()
        except ValueError:
            continue
    return parsed


def _format_extra_field_instructions(extra_fields: list | None) -> str:
    """将额外字段列表格式化为 prompt 中的输出要求。"""
    if not extra_fields:
        return ''
    parts = [f'{f}：[关于{f}的建议]' for f in extra_fields]
    return '\n'.join([''] + parts)  # 前导换行


def _format_reference_files_xml(reference_files_content: Optional[List[Dict[str, str]]]) -> str:
    """Format reference files content as XML structure."""
    if not reference_files_content:
        return ""
    xml_parts = ["<uploaded_files>"]
    for file_info in reference_files_content:
        filename = file_info.get('filename', 'unknown')
        content = file_info.get('content', '')
        xml_parts.append(f'  <file name="{filename}">')
        xml_parts.append('    <content>')
        xml_parts.append(content)
        xml_parts.append('    </content>')
        xml_parts.append('  </file>')
    xml_parts.append('</uploaded_files>')
    xml_parts.append('')  # Empty line after XML
    return '\n'.join(xml_parts)


def _format_requirements(requirements: str, context: str = "outline") -> str:
    """格式化用户提供的生成要求，返回可直接拼接到 prompt 中的文本段。

    context: "outline" 或 "description"，用于生成对应的结构标记示例。
    """
    if requirements and requirements.strip():
        if context == "description":
            marker_example = (
                "For example, if the user asks to avoid certain symbols, "
                "do NOT use them in the page content, but still use structural markers "
                "like '页面文字：', '图片素材：', and '<!-- PAGE_END -->' as-is."
            )
        else:
            marker_example = (
                "For example, if the user asks to avoid '#' symbols, "
                "do NOT use '#' in the page content, but still use '## Title' as "
                "the structural heading delimiter between pages."
            )
        return (
            "<user_requirements>\n"
            f"{requirements.strip()}\n"
            "</user_requirements>\n"
            "Note: The requirements above apply to the generated content of each page and "
            "take precedence over other content-related instructions. The required output format "
            f"and structural markers must still be used as-is. {marker_example}\n\n"
        )
    return ""


def _get_detail_level_spec(detail_level: str) -> str:
    prompt_id = DETAIL_LEVEL_SPECS.get(detail_level, DETAIL_LEVEL_SPECS['default'])
    return prompt_registry.render(prompt_id).strip()


def _get_outline_json_format() -> str:
    return prompt_registry.render(_OUTLINE_JSON_FORMAT).strip()


def _get_description_style_boundary() -> str:
    return prompt_registry.render(_DESCRIPTION_STYLE_BOUNDARY).strip()


def get_default_output_language() -> str:
    """获取环境变量中配置的默认输出语言"""
    from config import Config
    return getattr(Config, 'OUTPUT_LANGUAGE', 'zh')


def get_language_instruction(language: str = None) -> str:
    """获取语言限制指令文本"""
    lang = language if language else get_default_output_language()
    config = LANGUAGE_CONFIG.get(lang, LANGUAGE_CONFIG['zh'])
    prompt_id = config.get('instruction_id')
    return prompt_registry.render(prompt_id).strip() if prompt_id else ''


def get_ppt_language_instruction(language: str = None) -> str:
    """获取PPT文字语言限制指令"""
    lang = language if language else get_default_output_language()
    config = LANGUAGE_CONFIG.get(lang, LANGUAGE_CONFIG['zh'])
    prompt_id = config.get('ppt_text_id')
    return prompt_registry.render(prompt_id).strip() if prompt_id else ''


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 大纲 Prompts — 生成、解析、细化大纲
# ═══════════════════════════════════════════════════════════════════════════════


def get_outline_generation_prompt(project_context: 'ProjectContext', language: str = None) -> str:
    """生成 PPT 大纲的 prompt（JSON 输出）"""
    idea_prompt = project_context.idea_prompt or ""

    prompt = prompt_registry.render(
        "outline.generation",
        outline_json_format=_get_outline_json_format(),
        idea_prompt=idea_prompt,
        requirements=_format_requirements(project_context.outline_requirements),
        language_instruction=get_language_instruction(language),
    )

    return _build_prompt(prompt, project_context.reference_files_content, tag='get_outline_generation_prompt')


def get_outline_generation_prompt_markdown(project_context: 'ProjectContext', language: str = None) -> str:
    """生成 PPT 大纲的 prompt（Markdown 输出，用于流式生成）"""
    idea_prompt = project_context.idea_prompt or ""

    prompt = prompt_registry.render(
        "outline.generation_markdown",
        idea_prompt=idea_prompt,
        requirements=_format_requirements(project_context.outline_requirements),
        language_instruction=get_language_instruction(language),
    )

    return _build_prompt(prompt, project_context.reference_files_content, tag='get_outline_generation_prompt_markdown')


def get_outline_parsing_prompt(project_context: 'ProjectContext', language: str = None) -> str:
    """解析用户提供的大纲文本的 prompt（JSON 输出）"""
    outline_text = project_context.outline_text or ""

    prompt = prompt_registry.render(
        "outline.parsing",
        outline_text=outline_text,
        outline_json_format=_get_outline_json_format(),
        language_instruction=get_language_instruction(language),
    )

    return _build_prompt(prompt, project_context.reference_files_content, tag='get_outline_parsing_prompt')


def get_outline_parsing_prompt_markdown(project_context: 'ProjectContext', language: str = None) -> str:
    """解析用户提供的大纲文本的 prompt（Markdown 输出，用于流式生成）"""
    outline_text = project_context.outline_text or ""

    prompt = prompt_registry.render(
        "outline.parsing_markdown",
        outline_text=outline_text,
        language_instruction=get_language_instruction(language),
    )

    return _build_prompt(prompt, project_context.reference_files_content, tag='get_outline_parsing_prompt_markdown')


def get_description_to_outline_prompt(project_context: 'ProjectContext', language: str = None) -> str:
    """从描述文本解析出大纲的 prompt（JSON 输出）"""
    description_text = project_context.description_text or ""

    prompt = prompt_registry.render(
        "outline.from_description",
        description_text=description_text,
        outline_json_format=_get_outline_json_format(),
        language_instruction=get_language_instruction(language),
    )

    return _build_prompt(prompt, project_context.reference_files_content, tag='get_description_to_outline_prompt')


def get_description_to_outline_prompt_markdown(project_context: 'ProjectContext', language: str = None) -> str:
    """从描述文本解析出大纲的 prompt（Markdown 输出，用于流式生成）"""
    description_text = project_context.description_text or ""

    prompt = prompt_registry.render(
        "outline.from_description_markdown",
        description_text=description_text,
        language_instruction=get_language_instruction(language),
    )

    return _build_prompt(prompt, project_context.reference_files_content, tag='get_description_to_outline_prompt_markdown')


def get_outline_refinement_prompt(current_outline: List[Dict], user_requirement: str,
                                   project_context: 'ProjectContext',
                                   previous_requirements: Optional[List[str]] = None,
                                   language: str = None) -> str:
    """根据用户要求修改已有大纲的 prompt"""
    if not current_outline or len(current_outline) == 0:
        outline_text = "(当前没有内容)"
    else:
        outline_text = json.dumps(current_outline, ensure_ascii=False, indent=2)

    prompt = prompt_registry.render(
        "outline.refinement",
        original_input_labeled=_get_original_input_labeled(project_context),
        outline_text=outline_text,
        previous_requirements=_get_previous_requirements_text(previous_requirements),
        user_requirement=user_requirement,
        language_instruction=get_language_instruction(language),
    )

    return _build_prompt(prompt, project_context.reference_files_content, tag='get_outline_refinement_prompt')


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 描述 Prompts — 单页、流式、拆分、细化描述
# ═══════════════════════════════════════════════════════════════════════════════


def get_page_description_prompt(project_context: 'ProjectContext', outline: list,
                                page_outline: dict, page_index: int,
                                part_info: str = "",
                                language: str = None,
                                detail_level: str = "default",
                                extra_fields: list = None) -> str:
    """生成单个页面描述的 prompt"""
    original_input = _get_original_input(project_context)

    prompt = prompt_registry.render(
        "description.page",
        original_input=original_input,
        outline=outline,
        part_info=part_info,
        requirements=_format_requirements(project_context.description_requirements, "description"),
        page_index=page_index,
        page_outline=page_outline,
        first_page_note=(
            "**除非特殊要求，第一页的内容需要保持极简，只放标题副标题以及演讲人等（输出到标题后）, 不添加任何素材。**"
            if page_index == 1 else ""
        ),
        description_style_boundary=_get_description_style_boundary(),
        detail_level_spec=_get_detail_level_spec(detail_level),
        extra_field_instructions=_format_extra_field_instructions(extra_fields),
        language_instruction=get_language_instruction(language),
    )

    return _build_prompt(prompt, project_context.reference_files_content, tag='get_page_description_prompt')


def get_all_descriptions_stream_prompt(project_context: 'ProjectContext',
                                       outline: list,
                                       flat_pages: list,
                                       language: str = None,
                                       detail_level: str = "default",
                                       extra_fields: list = None) -> str:
    """一次性生成所有页面描述的 prompt（用于流式生成）"""
    original_input = _get_original_input(project_context)

    # 构建页面大纲列表
    outline_lines = []
    for i, page in enumerate(flat_pages):
        part_str = f"  [章节: {page['part']}]" if page.get('part') else ""
        points_str = ", ".join(page.get('points', []))
        outline_lines.append(f"第 {i + 1} 页：{page.get('title', '')}{part_str}\n  要点：{points_str}")
    pages_outline_text = "\n".join(outline_lines)

    prompt = prompt_registry.render(
        "description.all_stream",
        original_input=original_input,
        pages_outline_text=pages_outline_text,
        requirements=_format_requirements(project_context.description_requirements, "description"),
        detail_level_spec=_get_detail_level_spec(detail_level),
        description_style_boundary=_get_description_style_boundary(),
        extra_field_instructions=_format_extra_field_instructions(extra_fields),
        language_instruction=get_language_instruction(language),
    )

    return _build_prompt(prompt, project_context.reference_files_content, tag='get_all_descriptions_stream_prompt')


def get_description_split_prompt(project_context: 'ProjectContext',
                                 outline: List[Dict],
                                 language: str = None) -> str:
    """从描述文本切分出每页描述的 prompt"""
    outline_json = json.dumps(outline, ensure_ascii=False, indent=2)
    description_text = project_context.description_text or ""

    prompt = prompt_registry.render(
        "description.split",
        description_text=description_text,
        outline_json=outline_json,
        language_instruction=get_language_instruction(language),
    )

    logger.debug(f"[get_description_split_prompt] Final prompt:\n{prompt}")
    return prompt


def get_descriptions_refinement_prompt(current_descriptions: List[Dict], user_requirement: str,
                                       project_context: 'ProjectContext',
                                       outline: List[Dict] = None,
                                       previous_requirements: Optional[List[str]] = None,
                                       language: str = None) -> str:
    """根据用户要求修改已有页面描述的 prompt"""
    # 构建大纲文本
    outline_text = ""
    if outline:
        outline_json = json.dumps(outline, ensure_ascii=False, indent=2)
        outline_text = f"\n\n完整的 PPT 大纲：\n{outline_json}\n"

    # 构建所有页面描述的汇总
    all_descriptions_text = "当前所有页面的描述：\n\n"
    has_any_description = False
    for desc in current_descriptions:
        page_num = desc.get('index', 0) + 1
        title = desc.get('title', '未命名')
        content = desc.get('description_content', '')
        if isinstance(content, dict):
            content = content.get('text', '')

        if content:
            has_any_description = True
            all_descriptions_text += f"--- 第 {page_num} 页：{title} ---\n{content}\n\n"
        else:
            all_descriptions_text += f"--- 第 {page_num} 页：{title} ---\n(当前没有内容)\n\n"

    if not has_any_description:
        all_descriptions_text = "当前所有页面的描述：\n\n(当前没有内容，需要基于大纲生成新的描述)\n\n"

    prompt = prompt_registry.render(
        "description.refinement",
        original_input_labeled=_get_original_input_labeled(project_context),
        outline_text=outline_text,
        all_descriptions_text=all_descriptions_text,
        previous_requirements=_get_previous_requirements_text(previous_requirements),
        user_requirement=user_requirement,
        language_instruction=get_language_instruction(language),
    )

    return _build_prompt(prompt, project_context.reference_files_content, tag='get_descriptions_refinement_prompt')


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 图片生成 Prompts — 文生图、图片编辑
# ═══════════════════════════════════════════════════════════════════════════════


def get_image_generation_prompt(page_desc: str, outline_text: str,
                                current_section: str,
                                has_material_images: bool = False,
                                extra_requirements: str = None,
                                language: str = None,
                                has_template: bool = True,
                                page_index: int = 1,
                                aspect_ratio: str = "16:9",
                                visual_guidance: dict = None) -> str:
    """生成图片生成 prompt"""
    material_images_note = ""
    if has_material_images:
        material_images_note = (
            "\n\n提示：" + ("除了模板参考图片（用于风格参考）外，还提供了额外的素材图片。" if has_template else "用户提供了额外的素材图片。") +
            "这些素材图片是可供挑选和使用的元素，你可以从这些素材图片中选择合适的图片、图标、图表或其他视觉元素"
            "直接整合到生成的PPT页面中。请根据页面内容的需要，智能地选择和组合这些素材图片中的元素。"
        )

    extra_req_text = ""
    if extra_requirements and extra_requirements.strip():
        extra_req_text = f"\n\n额外要求（请务必遵循）：\n{extra_requirements}\n"

    template_style_guideline = "- 配色和设计语言和模板图片严格相似。" if has_template else "- 严格按照风格描述进行设计。"
    forbidden_template_text_guidline = "- 只参考风格设计，禁止出现模板中的文字。\n" if has_template else ""
    cover_note = (
        "**注意：当前页面为ppt的封面页，请你采用专业的封面设计美学技巧，务必凸显出页面标题，分清主次，确保一下就能抓住观众的注意力。**"
        if page_index == 1 else ""
    )

    if visual_guidance:
        prompt = prompt_registry.render(
            "image.generation_with_visual_guidance",
            global_visual_system=visual_guidance.get('global_visual_system', ''),
            page_desc=page_desc,
            page_visual_notes=visual_guidance.get('page_visual_notes', ''),
            aspect_ratio=aspect_ratio,
            forbidden_template_text_guidline=forbidden_template_text_guidline,
            ppt_language_instruction=get_ppt_language_instruction(language),
            material_images_note=material_images_note,
            extra_req_text=extra_req_text,
            cover_note=cover_note,
        )

        logger.debug(f"[get_image_generation_prompt] Final prompt:\n{prompt}")
        return prompt

    prompt = prompt_registry.render(
        "image.generation",
        page_desc=page_desc,
        aspect_ratio=aspect_ratio,
        template_style_guideline=template_style_guideline,
        forbidden_template_text_guidline=forbidden_template_text_guidline,
        ppt_language_instruction=get_ppt_language_instruction(language),
        material_images_note=material_images_note,
        extra_req_text=extra_req_text,
        cover_note=cover_note,
    )

    logger.debug(f"[get_image_generation_prompt] Final prompt:\n{prompt}")
    return prompt


def get_image_edit_prompt(edit_instruction: str, original_description: str = None) -> str:
    """生成图片编辑 prompt"""
    if original_description:
        if "其他页面素材" in original_description:
            original_description = original_description.split("其他页面素材")[0].strip()

        prompt = prompt_registry.render(
            "image.edit_with_description",
            original_description=original_description,
            edit_instruction=edit_instruction,
        )
    else:
        prompt = prompt_registry.render(
            "image.edit",
            edit_instruction=edit_instruction,
        )

    logger.debug(f"[get_image_edit_prompt] Final prompt:\n{prompt}")
    return prompt


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 图片处理 Prompts — 背景提取、画质修复
# ═══════════════════════════════════════════════════════════════════════════════


def get_clean_background_prompt() -> str:
    """生成纯背景图的 prompt（去除文字和插画）"""
    prompt = prompt_registry.render("image.clean_background")
    logger.debug(f"[get_clean_background_prompt] Final prompt:\n{prompt}")
    return prompt


def get_quality_enhancement_prompt(inpainted_regions: list = None) -> str:
    """生成画质提升的 prompt（用于百度图像修复后的画质修复）"""
    regions_info = ""
    if inpainted_regions and len(inpainted_regions) > 0:
        regions_json = json.dumps(inpainted_regions, ensure_ascii=False, indent=2)
        regions_info = f"""
以下是被抹除工具处理过的具体区域（共 {len(inpainted_regions)} 个矩形区域），请重点修复这些位置：

```json
{regions_json}
```

坐标说明（所有数值都是相对于图片宽高的百分比，范围0-100%）：
- left: 区域左边缘距离图片左边缘的百分比
- top: 区域上边缘距离图片上边缘的百分比
- right: 区域右边缘距离图片左边缘的百分比
- bottom: 区域下边缘距离图片上边缘的百分比
- width_percent: 区域宽度占图片宽度的百分比
- height_percent: 区域高度占图片高度的百分比

例如：left=10 表示区域从图片左侧10%的位置开始。
"""

    prompt = prompt_registry.render(
        "image.quality_enhancement",
        regions_info=regions_info,
    )
    return prompt


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 内容提取 Prompts — 文字属性、页面内容、排版分析、风格提取
# ═══════════════════════════════════════════════════════════════════════════════


def get_text_attribute_extraction_prompt(content_hint: str = "") -> str:
    """生成文字属性提取的 prompt（提取文字内容、颜色、公式等信息）"""
    return prompt_registry.render(
        "extraction.text_attribute",
        content_hint=content_hint,
    )


def get_batch_text_attribute_extraction_prompt(text_elements_json: str) -> str:
    """生成批量文字属性提取的 prompt（给模型全图 + 所有文本元素的 bbox）"""
    return prompt_registry.render(
        "extraction.batch_text_attribute",
        text_elements_json=text_elements_json,
    )


def get_ppt_page_content_extraction_prompt(markdown_text: str, language: str = None) -> str:
    """从 fileparser 解析出的 markdown 文本中提取页面内容（title, points, description）"""
    prompt = prompt_registry.render(
        "extraction.ppt_page_content",
        markdown_text=markdown_text,
        language_instruction=get_language_instruction(language),
    )
    logger.debug(f"[get_ppt_page_content_extraction_prompt] Final prompt:\n{prompt}")
    return prompt


def get_layout_caption_prompt() -> str:
    """描述 PPT 页面的排版布局（给 caption model 用）"""
    prompt = prompt_registry.render("extraction.layout_caption")
    logger.debug(f"[get_layout_caption_prompt] Final prompt:\n{prompt}")
    return prompt


def get_style_extraction_prompt() -> str:
    """从图片中提取风格描述（通用，可复用于所有创建模式）"""
    prompt = prompt_registry.render("extraction.style")
    logger.debug(f"[get_style_extraction_prompt] Final prompt:\n{prompt}")
    return prompt


# ═══════════════════════════════════════════════════════════════════════════════
# 7. 旁白 Prompts — TTS 播报视频旁白生成
# ═══════════════════════════════════════════════════════════════════════════════


def get_narration_generation_prompt(
    pages: list,
    language: str = 'zh',
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    一次性生成所有页面旁白的 prompt。

    Args:
        pages: 页面列表，每项包含 {title, points, description_text, page_index}
        language: 输出语言
        config: 可配置的演讲稿生成参数
    """
    lang_cfg = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG['zh'])
    lang_instruction = lang_cfg['instruction']
    total_pages = len(pages)
    fallback_topic = ''
    if pages:
        first_title = str(pages[0].get('title', '') or '').strip()
        fallback_topic = first_title or fallback_topic
    normalized_config = normalize_narration_generation_config(config, fallback_topic=fallback_topic)

    slides_block = ''
    for p in pages:
        idx = p['page_index']
        title = p.get('title', '')
        points = p.get('points', [])
        points_text = '\n'.join(f'- {p2}' for p2 in points) if points else '(无)'
        desc = p.get('description_text', '')
        slides_block += f"""\
=== SLIDE {idx} ===
<slide_title>{title}</slide_title>
<slide_key_points>
{points_text}
</slide_key_points>
<slide_description>
{desc}
</slide_description>

"""

    prompt = prompt_registry.render(
        "narration.generation",
        speaker_persona=normalized_config['speaker_persona'],
        target_audience=normalized_config['target_audience'],
        total_pages=total_pages,
        presentation_topic=normalized_config['presentation_topic'],
        language_instruction=lang_instruction,
        speech_tone=normalized_config['speech_tone'],
        min_words=normalized_config['min_words'],
        max_words=normalized_config['max_words'],
        slides_block=slides_block,
    )

    logger.debug(
        "[get_narration_generation_prompt] total_pages=%s, lang=%s, config=%s",
        total_pages,
        language,
        normalized_config,
    )
    return prompt

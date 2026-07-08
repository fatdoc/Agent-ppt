from controllers.reference_file_controller import _safe_reference_filename


def test_safe_reference_filename_preserves_extension_for_chinese_pdf():
    assert _safe_reference_filename("报告材料.pdf") == "file.pdf"


def test_safe_reference_filename_preserves_extension_for_chinese_docx():
    assert _safe_reference_filename("全国社会工作者职业资格考试指导教材.docx") == "file.docx"


def test_safe_reference_filename_keeps_ascii_stem_and_extension():
    assert _safe_reference_filename("AI 全自动智慧蘑菇种植系统方案(1).docx") == "AI_1.docx"

from pathlib import Path
from types import SimpleNamespace

import pytest

from services.ppt_to_ppt.reference_renderer import ReferenceRenderer


class FakeUploadFile:
    def __init__(self, filename: str, payload: bytes = b"%PDF-1.4\n"):
        self.filename = filename
        self.payload = payload

    def save(self, path: str):
        Path(path).write_bytes(self.payload)


def test_renderer_rejects_unsupported_file(tmp_path):
    renderer = ReferenceRenderer(upload_folder=str(tmp_path))

    with pytest.raises(ValueError) as exc:
        renderer.validate_reference_file(FakeUploadFile("deck.key"))

    assert "Only PDF and PPT files are supported" in str(exc.value)


def test_renderer_saves_reference_with_stable_filename(tmp_path):
    renderer = ReferenceRenderer(upload_folder=str(tmp_path))
    file = FakeUploadFile("优秀案例.pdf")

    saved = renderer.save_reference_file(file, "project-1")

    assert saved.name == "reference.pdf"
    assert saved.exists()
    assert saved.parent == tmp_path / "project-1" / "ppt_to_ppt_reference"


def test_render_pdf_pages_returns_at_least_one_page(tmp_path, monkeypatch):
    pdf = tmp_path / "reference.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    out_dir = tmp_path / "pages"

    class FakePixmap:
        def save(self, path):
            Path(path).write_bytes(b"png")

    class FakePage:
        rect = SimpleNamespace(width=1600, height=900)

        def get_pixmap(self, matrix):
            return FakePixmap()

    class FakeDoc:
        def __len__(self):
            return 1

        def __iter__(self):
            return iter([FakePage()])

        def close(self):
            pass

    fake_fitz = SimpleNamespace(open=lambda path: FakeDoc(), Matrix=lambda x, y: (x, y))
    monkeypatch.setitem(__import__("sys").modules, "fitz", fake_fitz)

    result = ReferenceRenderer(upload_folder=str(tmp_path)).render_pdf_pages(pdf, out_dir)

    assert result.page_count == 1
    assert result.page_images[0].name == "reference_page_1.png"
    assert result.aspect_ratio == "16:9"

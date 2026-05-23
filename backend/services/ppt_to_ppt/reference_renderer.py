import subprocess
from dataclasses import dataclass
from pathlib import Path

from utils.validators import normalize_aspect_ratio


@dataclass
class RenderedReferenceDeck:
    original_path: Path
    pdf_path: Path
    page_images: list[Path]
    page_count: int
    aspect_ratio: str


class ReferenceRenderer:
    def __init__(self, upload_folder: str):
        self.upload_folder = Path(upload_folder)

    def validate_reference_file(self, file) -> None:
        filename = (file.filename or "").lower()
        if not filename.endswith((".pdf", ".pptx", ".ppt")):
            raise ValueError("Only PDF and PPT files are supported")

    def save_reference_file(self, file, project_id: str) -> Path:
        self.validate_reference_file(file)
        ext = file.filename.rsplit(".", 1)[-1].lower()
        reference_dir = self.upload_folder / project_id / "ppt_to_ppt_reference"
        reference_dir.mkdir(parents=True, exist_ok=True)
        saved_path = reference_dir / f"reference.{ext}"
        file.save(str(saved_path))
        return saved_path

    def save_reference_path(self, source_path: str | Path, project_id: str) -> Path:
        source = Path(source_path)
        if source.suffix.lower() not in {".pdf", ".pptx", ".ppt"}:
            raise ValueError("Only PDF and PPT files are supported")

        reference_dir = self.upload_folder / project_id / "ppt_to_ppt_reference"
        reference_dir.mkdir(parents=True, exist_ok=True)
        saved_path = reference_dir / f"reference{source.suffix.lower()}"
        saved_path.write_bytes(source.read_bytes())
        return saved_path

    def convert_to_pdf_if_needed(self, original_path: Path) -> Path:
        if original_path.suffix.lower() == ".pdf":
            return original_path

        output_dir = original_path.parent
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(original_path),
            ],
            check=True,
            timeout=120,
            capture_output=True,
        )
        pdf_path = output_dir / "reference.pdf"
        if not pdf_path.exists():
            raise ValueError("PPT to PDF conversion failed")
        return pdf_path

    def render_pdf_pages(self, pdf_path: Path, output_dir: Path) -> RenderedReferenceDeck:
        output_dir.mkdir(parents=True, exist_ok=True)

        import fitz

        doc = fitz.open(str(pdf_path))
        page_images: list[Path] = []
        aspect_ratio = "16:9"
        try:
            for index, page in enumerate(doc):
                if index == 0:
                    rect = page.rect
                    aspect_ratio = normalize_aspect_ratio(
                        f"{int(round(rect.width))}:{int(round(rect.height))}"
                    )

                image_path = output_dir / f"reference_page_{index + 1}.png"
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                pix.save(str(image_path))
                page_images.append(image_path)
        finally:
            doc.close()

        if not page_images:
            raise ValueError("No reference pages rendered")

        return RenderedReferenceDeck(
            original_path=pdf_path,
            pdf_path=pdf_path,
            page_images=page_images,
            page_count=len(page_images),
            aspect_ratio=aspect_ratio,
        )

    def prepare_reference_deck(self, file, project_id: str) -> RenderedReferenceDeck:
        original_path = self.save_reference_file(file, project_id)
        pdf_path = self.convert_to_pdf_if_needed(original_path)
        rendered = self.render_pdf_pages(
            pdf_path,
            self.upload_folder / project_id / "ppt_to_ppt_reference" / "pages",
        )
        rendered.original_path = original_path
        return rendered

    def prepare_reference_deck_from_path(
        self, source_path: str | Path, project_id: str
    ) -> RenderedReferenceDeck:
        original_path = self.save_reference_path(source_path, project_id)
        pdf_path = self.convert_to_pdf_if_needed(original_path)
        rendered = self.render_pdf_pages(
            pdf_path,
            self.upload_folder / project_id / "ppt_to_ppt_reference" / "pages",
        )
        rendered.original_path = original_path
        return rendered

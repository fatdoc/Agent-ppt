"""
Unit tests for FileParserService provider-specific behavior.
"""

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image
from requests.exceptions import SSLError

from services.file_parser_service import FileParserService


def _create_temp_image() -> str:
    with tempfile.NamedTemporaryFile(prefix='caption_test_', suffix='.png', delete=False) as tmp:
        Image.new('RGB', (20, 20), color='green').save(tmp.name)
        return tmp.name


def test_generate_single_caption_uses_provider_factory():
    """Caption generation should delegate to the provider factory's generate_with_image."""
    image_path = _create_temp_image()
    try:
        service = FileParserService(
            mineru_token='test-token',
            image_caption_model='gpt-4.1-mini',
            provider_format='openai',
        )

        mock_provider = MagicMock()
        mock_provider.generate_with_image.return_value = '示例描述'

        with patch('utils.path_utils.find_mineru_file_with_prefix', return_value=Path(image_path)):
            with patch.object(service, '_get_caption_provider', return_value=mock_provider):
                caption = service._generate_single_caption('/files/mineru/demo.png')

        assert caption == '示例描述'
        mock_provider.generate_with_image.assert_called_once()
        call_args = mock_provider.generate_with_image.call_args
        assert '描述' in call_args[0][0]
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


def test_can_generate_captions_returns_false_when_factory_fails():
    """_can_generate_captions should return False when the provider factory raises."""
    service = FileParserService(
        mineru_token='test-token',
        provider_format='lazyllm',
    )
    with patch(
        'services.file_parser_service.FileParserService._get_caption_provider',
        side_effect=ValueError("no key"),
    ):
        assert service._can_generate_captions() is False


def test_can_generate_captions_returns_true_when_factory_succeeds():
    """_can_generate_captions should return True when the provider factory returns a provider."""
    service = FileParserService(
        mineru_token='test-token',
        provider_format='openai',
    )
    mock_provider = MagicMock()
    with patch.object(service, '_get_caption_provider', return_value=mock_provider):
        assert service._can_generate_captions() is True


def test_generate_single_caption_vertex_uses_provider_factory():
    """Vertex provider should also go through the factory (the original bug)."""
    image_path = _create_temp_image()
    try:
        service = FileParserService(
            mineru_token='test-token',
            image_caption_model='gemini-2.0-flash',
            provider_format='vertex',
        )

        mock_provider = MagicMock()
        mock_provider.generate_with_image.return_value = '顶点描述'

        with patch('utils.path_utils.find_mineru_file_with_prefix', return_value=Path(image_path)):
            with patch.object(service, '_get_caption_provider', return_value=mock_provider):
                caption = service._generate_single_caption('/files/mineru/demo.png')

        assert caption == '顶点描述'
        mock_provider.generate_with_image.assert_called_once()
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


def test_parse_file_uses_local_mineru_gradio_zip_response(tmp_path):
    """Local MinerU should call Gradio, unzip the output file, and rewrite image paths."""
    input_pdf = tmp_path / "demo1.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    zip_path = tmp_path / "mineru-result.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("demo1/auto/demo1.md", "# Demo\n\n![](images/chart.jpg)\n")
        archive.writestr("demo1/auto/images/chart.jpg", b"fake-image")

    service = FileParserService(
        mineru_provider="local",
        local_api_base="http://127.0.0.1:7860",
        local_backend="pipeline",
        local_parse_method="auto",
        local_return_images=True,
        local_response_format_zip=True,
        local_return_original_file=False,
    )

    with patch.object(
        service,
        "_call_local_mineru_gradio",
        return_value=("<p>done</p>", str(zip_path), "# Demo", "# Demo\n\n![](images/chart.jpg)\n", "[]", None),
    ) as gradio_mock:
        with patch.object(service, "_can_generate_captions", return_value=False):
            batch_id, markdown, extract_id, error, failed = service.parse_file(str(input_pdf), "demo1.pdf")

    assert batch_id is None
    assert error is None
    assert failed == 0
    assert extract_id
    assert markdown == f"# Demo\n\n![](/files/mineru/{extract_id}/images/chart.jpg)\n"

    extracted_image = (
        Path(__file__).resolve().parents[3]
        / "uploads"
        / "mineru_files"
        / extract_id
        / "images"
        / "chart.jpg"
    )
    assert extracted_image.read_bytes() == b"fake-image"

    gradio_mock.assert_called_once_with(str(input_pdf))
    shutil.rmtree(extracted_image.parents[1])


def test_mineru_provider_is_not_inferred_from_api_base():
    """Provider selection must follow explicit configuration, not hidden inference."""
    service = FileParserService(
        mineru_provider="cloud",
        mineru_api_base="http://127.0.0.1:8000",
        local_api_base="http://127.0.0.1:8000",
    )

    assert service.mineru_provider == "cloud"


def test_remote_mineru_base_does_not_override_local_provider():
    """A saved remote base must not silently rewrite the explicitly selected provider."""
    service = FileParserService(
        mineru_provider="local",
        mineru_api_base="https://mineru.net/api/v4/extract/task",
        local_api_base="http://127.0.0.1:8000",
    )

    assert service.mineru_provider == "local"
    assert service.mineru_api_base == "https://mineru.net"
    assert service.get_upload_url_api == "https://mineru.net/api/v4/file-urls/batch"


def test_local_provider_uses_configured_api_base_for_gradio():
    """Local MinerU should call the API base chosen in Settings, not hidden env defaults."""
    service = FileParserService(
        mineru_provider="local",
        mineru_api_base="http://127.0.0.1:7860",
        local_api_base="http://127.0.0.1:8000",
    )

    assert service.mineru_provider == "local"
    assert service.local_api_base == "http://127.0.0.1:7860"


def test_extract_local_mineru_gradio_result_uses_md_text_when_zip_missing():
    """Gradio md_text fallback should still produce usable markdown for diagnostics."""
    service = FileParserService(mineru_provider="local")

    markdown, extract_id, error = service._extract_local_mineru_gradio_result(
        ("<p>done</p>", None, "# Demo", "# Demo", "[]", None)
    )

    assert markdown == "# Demo"
    assert extract_id
    assert error is None

    output_dir = Path(__file__).resolve().parents[3] / "uploads" / "mineru_files" / extract_id
    shutil.rmtree(output_dir)


def test_download_markdown_retries_transient_ssl_error():
    """MinerU CDN downloads can fail once with SSL EOF; retry should recover."""
    service = FileParserService(mineru_token="test-token")

    response = MagicMock()
    response.content = b"zip-bytes"
    response.raise_for_status.return_value = None

    with patch(
        "services.file_parser_service.requests.get",
        side_effect=[SSLError("unexpected eof"), response],
    ) as get_mock:
        with patch.object(
            service,
            "_extract_markdown_zip",
            return_value=("# Demo", "extract-id", None),
        ) as extract_mock:
            result = service._download_markdown(
                "https://cdn-mineru.openxlab.org.cn/result.zip",
                max_attempts=2,
                retry_delay=0,
            )

    assert result == ("# Demo", "extract-id", None)
    assert get_mock.call_count == 2
    extract_mock.assert_called_once_with(b"zip-bytes")


def test_download_markdown_retries_invalid_partial_zip():
    """A truncated CDN response should be retried before surfacing ZIP errors."""
    service = FileParserService(mineru_token="test-token")

    bad_response = MagicMock()
    bad_response.content = b"partial"
    bad_response.raise_for_status.return_value = None

    good_response = MagicMock()
    good_response.content = b"zip-bytes"
    good_response.raise_for_status.return_value = None

    with patch(
        "services.file_parser_service.requests.get",
        side_effect=[bad_response, good_response],
    ) as get_mock:
        with patch.object(
            service,
            "_extract_markdown_zip",
            side_effect=[(None, None, "Downloaded file is not a valid ZIP archive"), ("# Demo", "extract-id", None)],
        ):
            result = service._download_markdown(
                "https://cdn-mineru.openxlab.org.cn/result.zip",
                max_attempts=2,
                retry_delay=0,
            )

    assert result == ("# Demo", "extract-id", None)
    assert get_mock.call_count == 2

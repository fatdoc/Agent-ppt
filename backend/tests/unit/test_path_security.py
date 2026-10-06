import pytest

from services.file_service import FileService
from utils.path_utils import convert_mineru_path_to_local, is_path_within


def test_common_path_rejects_sibling_prefix(tmp_path):
    upload_root = tmp_path / "uploads"
    sibling = tmp_path / "uploads_secret" / "image.png"
    upload_root.mkdir()
    sibling.parent.mkdir()
    sibling.write_bytes(b"not exposed")

    assert not is_path_within(sibling, upload_root)


def test_file_service_rejects_parent_and_sibling_prefix(tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    service = FileService(str(upload_root))

    with pytest.raises(ValueError, match="escapes allowed root"):
        service.get_absolute_path("../uploads_secret/image.png")


def test_mineru_conversion_rejects_traversal(tmp_path):
    upload_root = tmp_path / "uploads"
    (upload_root / "mineru_files").mkdir(parents=True)

    assert convert_mineru_path_to_local(
        "/files/mineru/../../uploads_secret/image.png",
        upload_folder=upload_root,
    ) is None


def test_mineru_conversion_uses_configured_upload_root(tmp_path):
    upload_root = tmp_path / "custom-uploads"
    expected = upload_root / "mineru_files" / "extract-1" / "image.png"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"image")

    resolved = convert_mineru_path_to_local(
        "/files/mineru/extract-1/image.png",
        upload_folder=upload_root,
    )
    assert resolved == expected.resolve()

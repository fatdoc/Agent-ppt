from unittest.mock import MagicMock

from services.ai_service import AIService, _is_retryable_caption_error


def test_edit_image_labels_current_page_and_uploaded_references():
    service = AIService.__new__(AIService)
    service.generate_image = MagicMock(return_value='edited')

    result = service.edit_image(
        '把左上角的车替换成参考图中的车',
        '/tmp/current-page.png',
        additional_ref_images=['/tmp/replacement-car.png'],
    )

    assert result == 'edited'
    prompt = service.generate_image.call_args.args[0]
    assert '图1是当前PPT页面' in prompt
    assert '图2及后续图片是用户上传的替换素材' in prompt
    assert '不得继续沿用图1原对象' in prompt
    assert service.generate_image.call_args.args[1] == '/tmp/current-page.png'
    assert service.generate_image.call_args.args[4] == ['/tmp/replacement-car.png']


def test_caption_retry_classifier_accepts_timeouts_and_5xx_only():
    class ServerFailure(Exception):
        status_code = 502

    class AuthFailure(Exception):
        status_code = 401

    assert _is_retryable_caption_error(TimeoutError('timed out')) is True
    assert _is_retryable_caption_error(ServerFailure('bad gateway')) is True
    assert _is_retryable_caption_error(AuthFailure('invalid api key')) is False

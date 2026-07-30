"""Business platform configuration and outline-template API tests."""
from conftest import assert_error_response, assert_success_response


def template_payload(**overrides):
    payload = {
        'name': '测试大纲模板',
        'description': '用于测试',
        'competitionId': 'wvcc',
        'competitionTypeId': 'championship',
        'supportScope': 'PRIVATE',
        'status': 'PUBLISHED',
        'targetPageCount': 2,
        'styleTags': ['测试'],
        'sections': [
            {
                'id': 'section-1',
                'title': '技能展示',
                'recommendedPageCount': 2,
                'scoreDimensions': ['skill-level'],
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_competition_support_matrix_does_not_fake_scores(client):
    response = client.get('/api/platform/competitions')
    data = assert_success_response(response)['data']['competitions']
    wvcc = next(item for item in data if item['id'] == 'wvcc')
    assert wvcc['supportLevel'] == 'FULL'
    assert len(wvcc['scoreDimensions']) == 5
    for competition in data:
        if competition['id'] != 'wvcc':
            assert 'scoreDimensions' not in competition


def test_outline_template_crud_and_version_snapshot(client):
    created = assert_success_response(
        client.post('/api/outline-templates', json=template_payload()),
        201,
    )['data']
    assert created['version'] == 1

    updated_payload = template_payload(name='测试大纲模板 v2', changeNote='调整章节')
    updated = assert_success_response(
        client.put(f"/api/outline-templates/{created['id']}", json=updated_payload)
    )['data']
    assert updated['version'] == 2
    assert updated['versions'][0]['version'] == 1

    listed = assert_success_response(client.get('/api/outline-templates'))['data']['templates']
    assert any(item['id'] == created['id'] for item in listed)

    assert_success_response(client.delete(f"/api/outline-templates/{created['id']}"))


def test_generic_competition_cannot_store_wvcc_score_dimensions(client):
    response = client.post(
        '/api/outline-templates',
        json=template_payload(competitionId='challenge-cup'),
    )
    assert_error_response(response, 400)


def test_template_matching_uses_specificity_priority(client):
    generic = template_payload(
        name='平台通用',
        competitionId=None,
        competitionTypeId=None,
        sections=[{'id': 'generic', 'title': '通用', 'recommendedPageCount': 1}],
    )
    specific = template_payload(name='世职赛争夺赛专用')
    assert_success_response(client.post('/api/outline-templates', json=generic), 201)
    specific_created = assert_success_response(
        client.post('/api/outline-templates', json=specific), 201
    )['data']

    matched = assert_success_response(client.get(
        '/api/outline-templates/match?competitionId=wvcc&competitionTypeId=championship'
    ))['data']['template']
    assert matched['id'] == specific_created['id']


def test_project_persists_platform_context(client, sample_project):
    project_id = sample_project['project_id']
    context = {
        'competitionId': 'wvcc',
        'competitionTypeId': 'championship',
        'trackId': 'ai-application',
        'themeId': 'ai-industry',
        'targetPageCount': 39,
    }
    updated = assert_success_response(client.put(
        f'/api/projects/{project_id}',
        json={
            'platform_context': context,
            'outline_template_id': 'wvcc-championship-39',
            'ppt_template_id': '1',
        },
    ))['data']
    assert updated['platform_context'] == context
    assert updated['outline_template_id'] == 'wvcc-championship-39'
    assert updated['ppt_template_id'] == '1'

def test_create_agent_plan_with_non_paper_pack(client):
    response = client.post('/api/agent-mode/plans', json={
        'topic': '新能源车队管理方案',
        'audience': '企业高管',
        'page_count': 3,
        'style': '',
        'generation_mode': 'harness',
        'harness_template': 'consulting_report',
    })

    assert response.status_code == 201, response.get_json()
    data = response.get_json()['data']
    assert data['slides'] and len(data['slides']) == 3
    system = data['visual_system']['system'] if isinstance(data.get('visual_system'), dict) and 'system' in (data.get('visual_system') or {}) else data.get('visual_system')
    assert system['strategy_id'] == 'consulting_report'
    assert system['quality_constraints']
    first_plan = data['slides'][0]['visual_plan']
    assert first_plan['strategy_id'] == 'consulting_report'
    assert first_plan['structure_prompt']
    assert first_plan['style_prompt']


def test_create_agent_plan_rejects_unknown_pack(client):
    response = client.post('/api/agent-mode/plans', json={
        'topic': '主题',
        'audience': '受众',
        'page_count': 2,
        'generation_mode': 'harness',
        'harness_template': 'not_a_pack',
    })

    assert response.status_code == 400
    assert 'harness_template' in response.get_json()['error']['message']


def test_create_agent_plan_accepts_hyphenated_pack_id(client):
    response = client.post('/api/agent-mode/plans', json={
        'topic': '课程设计',
        'audience': '大学生',
        'page_count': 2,
        'generation_mode': 'harness',
        'harness_template': 'paper-operators',
    })

    assert response.status_code == 201, response.get_json()
    data = response.get_json()['data']
    assert data['slides'][0]['visual_plan']['strategy_id'] == 'paper_operators'

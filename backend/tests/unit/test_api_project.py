"""
项目管理API单元测试
"""

import pytest
from conftest import assert_success_response, assert_error_response


class TestProjectCreate:
    """项目创建测试"""
    
    def test_create_project_idea_mode(self, client):
        """测试从想法创建项目"""
        response = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '生成一份关于AI的PPT'
        })
        
        data = assert_success_response(response, 201)
        assert 'project_id' in data['data']
        assert data['data']['status'] == 'DRAFT'
    
    def test_create_project_outline_mode(self, client):
        """测试从大纲创建项目"""
        response = client.post('/api/projects', json={
            'creation_type': 'outline',
            'outline': [
                {'title': '第一页', 'points': ['要点1']},
                {'title': '第二页', 'points': ['要点2']}
            ]
        })
        
        data = assert_success_response(response, 201)
        assert 'project_id' in data['data']
    
    def test_create_project_missing_type(self, client):
        """测试缺少creation_type参数"""
        response = client.post('/api/projects', json={
            'idea_prompt': '测试'
        })
        
        # 应该返回错误
        assert response.status_code in [400, 422]
    
    def test_create_project_invalid_type(self, client):
        """测试无效的creation_type"""
        response = client.post('/api/projects', json={
            'creation_type': 'invalid_type',
            'idea_prompt': '测试'
        })
        
        assert response.status_code in [400, 422]

    def test_create_project_accepts_external_visual_strategy(self, client):
        """测试创建项目时可保存外部视觉策略"""
        response = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '生成一份关于AI的PPT',
            'template_style': '原生商务风',
            'visual_strategy': 'external_skill',
            'external_style_skill_id': 'ppt-style-pro',
            'external_style_payload': {'style_prompt': '外部 Skill 黑金风格'},
        })

        data = assert_success_response(response, 201)
        project_id = data['data']['project_id']

        get_response = client.get(f'/api/projects/{project_id}')
        project = assert_success_response(get_response)['data']

        assert project['visual_strategy'] == 'external_skill'
        assert project['external_style_skill_id'] == 'ppt-style-pro'
        assert project['external_style_payload'] == {'style_prompt': '外部 Skill 黑金风格'}

    def test_create_project_rejects_empty_external_visual_strategy(self, client):
        """测试外部视觉策略必须提供 Skill ID 或 payload"""
        response = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '测试',
            'visual_strategy': 'external_skill',
        })

        assert response.status_code in [400, 422]

    def test_create_project_accepts_harness_generation_mode(self, client):
        """测试 Harness 生成模式独立于视觉策略保存"""
        response = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '生成一份关于AI的PPT',
            'template_style': '稳重科技风',
            'generation_mode': 'harness',
            'harness_template': 'paper_operators',
            'visual_strategy': 'native',
        })

        data = assert_success_response(response, 201)
        project_id = data['data']['project_id']

        get_response = client.get(f'/api/projects/{project_id}')
        project = assert_success_response(get_response)['data']

        assert project['generation_mode'] == 'harness'
        assert project['harness_template'] == 'paper_operators'
        assert project['template_style'] == '稳重科技风'
        assert project['visual_strategy'] == 'native'

    def test_create_project_rejects_paper_operators_visual_strategy(self, client):
        """测试 paper_operators 不再是视觉策略"""
        response = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '测试',
            'visual_strategy': 'paper_operators',
        })

        assert response.status_code in [400, 422]


class TestProjectGet:
    """项目获取测试"""
    
    def test_get_project_success(self, client, sample_project):
        """测试获取项目成功"""
        if not sample_project:
            pytest.skip("项目创建失败")
        
        project_id = sample_project['project_id']
        response = client.get(f'/api/projects/{project_id}')
        
        data = assert_success_response(response)
        assert data['data']['project_id'] == project_id
    
    def test_get_project_not_found(self, client):
        """测试获取不存在的项目"""
        response = client.get('/api/projects/non-existent-id')
        
        assert response.status_code == 404
    
    def test_get_project_invalid_id_format(self, client):
        """测试无效的项目ID格式"""
        response = client.get('/api/projects/invalid!@#$%id')
        
        # 可能返回404或400
        assert response.status_code in [400, 404]


class TestProjectUpdate:
    """项目更新测试"""
    
    def test_update_project_status(self, client, sample_project):
        """测试更新项目状态"""
        if not sample_project:
            pytest.skip("项目创建失败")
        
        project_id = sample_project['project_id']
        response = client.put(f'/api/projects/{project_id}', json={
            'status': 'GENERATING'
        })
        
        # 状态更新应该成功
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_update_project_title(self, client, sample_project):
        """测试更新项目标题不影响 idea_prompt"""
        if not sample_project:
            pytest.skip("项目创建失败")

        project_id = sample_project['project_id']
        get_before = client.get(f'/api/projects/{project_id}')
        before_data = assert_success_response(get_before)

        response = client.put(f'/api/projects/{project_id}', json={
            'project_title': '新的项目标题'
        })

        data = assert_success_response(response)
        assert data['data']['project_title'] == '新的项目标题'
        assert data['data']['idea_prompt'] == before_data['data']['idea_prompt']


class TestProjectDelete:
    """项目删除测试"""
    
    def test_delete_project_success(self, client, sample_project):
        """测试删除项目成功"""
        if not sample_project:
            pytest.skip("项目创建失败")
        
        project_id = sample_project['project_id']
        response = client.delete(f'/api/projects/{project_id}')
        
        data = assert_success_response(response)
        
        # 确认项目已删除
        get_response = client.get(f'/api/projects/{project_id}')
        assert get_response.status_code == 404
    
    def test_delete_project_not_found(self, client):
        """测试删除不存在的项目"""
        response = client.delete('/api/projects/non-existent-id')
        
        assert response.status_code == 404


class TestProjectGenerationEndpoints:
    """Legacy project generation endpoint tests."""

    def test_generate_outline_idea_uses_existing_api_shape(self, client, monkeypatch):
        from services.input_generation_service import InputGenerationResult

        created = client.post('/api/projects', json={
            'creation_type': 'idea',
            'idea_prompt': '生成 AI 主题 PPT',
        }).get_json()['data']
        project_id = created['project_id']

        class FakeInputGenerationService:
            def __init__(self, ai_service):
                self.ai_service = ai_service

            def generate(self, project, project_context, options, save_mode='merge_by_index'):
                from models import Page, db
                page = Page(project_id=project.id, order_index=0, status='DRAFT')
                page.set_outline_content({'title': '封面', 'points': ['主题']})
                db.session.add(page)
                project.status = 'OUTLINE_GENERATED'
                return InputGenerationResult(
                    input_kind=options.input_kind,
                    outline=[{'title': '封面', 'points': ['主题']}],
                    page_descriptions=None,
                    status='OUTLINE_GENERATED',
                    page_count=1,
                )

        monkeypatch.setattr('controllers.project_controller.InputGenerationService', FakeInputGenerationService)

        response = client.post(f'/api/projects/{project_id}/generate/outline', json={'language': 'zh'})

        data = assert_success_response(response)
        assert data['data']['pages'][0]['outline_content']['title'] == '封面'

    def test_generate_from_description_uses_existing_api_shape(self, client, monkeypatch):
        from services.input_generation_service import InputGenerationResult

        created = client.post('/api/projects', json={
            'creation_type': 'descriptions',
            'description_text': '第1页 封面：介绍主题',
        }).get_json()['data']
        project_id = created['project_id']

        class FakeInputGenerationService:
            def __init__(self, ai_service):
                self.ai_service = ai_service

            def generate(self, project, project_context, options, save_mode='merge_by_index'):
                from models import Page, db
                page = Page(project_id=project.id, order_index=0, status='DESCRIPTION_GENERATED')
                page.set_outline_content({'title': '封面', 'points': ['介绍主题']})
                page.set_description_content({'text': '封面页描述'})
                db.session.add(page)
                project.status = 'DESCRIPTIONS_GENERATED'
                return InputGenerationResult(
                    input_kind=options.input_kind,
                    outline=[{'title': '封面', 'points': ['介绍主题']}],
                    page_descriptions=[{'text': '封面页描述'}],
                    status='DESCRIPTIONS_GENERATED',
                    page_count=1,
                )

        monkeypatch.setattr('controllers.project_controller.InputGenerationService', FakeInputGenerationService)

        response = client.post(f'/api/projects/{project_id}/generate/from-description', json={'language': 'zh'})

        data = assert_success_response(response)
        assert data['data']['status'] == 'DESCRIPTIONS_GENERATED'
        assert data['data']['pages'][0]['description_content']['text'] == '封面页描述'


class TestNoThinkProject:
    """No Think PPT project API tests."""

    def test_create_no_think_project_normalizes_options(self, client):
        response = client.post('/api/projects', json={
            'creation_type': 'no_think',
            'idea_prompt': 'AI 工具入门',
            'no_think_options': {
                'scenario': '内部培训',
                'density': '简洁',
                'page_count': '5页',
                'style_template': '现代商务',
                'extra_instruction': '适合新员工',
            },
        })

        data = assert_success_response(response, 201)
        project_id = data['data']['project_id']

        get_response = client.get(f'/api/projects/{project_id}')
        project = assert_success_response(get_response)['data']

        assert project['creation_type'] == 'no_think'
        assert 'No Think PPT 生成需求' in project['idea_prompt']
        assert '用途场景：内部培训' in project['idea_prompt']
        assert '色调感觉' not in project['idea_prompt']
        assert '页数倾向：5页' in project['idea_prompt']

    def test_generate_outline_for_no_think_generates_descriptions(self, client, monkeypatch):
        from services.input_generation_service import InputGenerationResult

        created = client.post('/api/projects', json={
            'creation_type': 'no_think',
            'idea_prompt': 'AI 工具入门',
            'no_think_options': {'page_count': '3页'},
        }).get_json()['data']
        project_id = created['project_id']
        observed = {}

        class FakeInputGenerationService:
            def __init__(self, ai_service):
                self.ai_service = ai_service

            def generate(self, project, project_context, options, save_mode='merge_by_index'):
                from models import Page, db
                observed['input_kind'] = options.input_kind
                observed['target_depth'] = options.target_depth
                page = Page(project_id=project.id, order_index=0, status='DESCRIPTION_GENERATED')
                page.set_outline_content({'title': '封面', 'points': ['主题']})
                page.set_description_content({'text': '封面描述'})
                db.session.add(page)
                project.status = 'DESCRIPTIONS_GENERATED'
                return InputGenerationResult(
                    input_kind=options.input_kind,
                    outline=[{'title': '封面', 'points': ['主题']}],
                    page_descriptions=[{'text': '封面描述'}],
                    status='DESCRIPTIONS_GENERATED',
                    page_count=1,
                )

        monkeypatch.setattr('controllers.project_controller.InputGenerationService', FakeInputGenerationService)

        response = client.post(f'/api/projects/{project_id}/generate/outline', json={'language': 'zh'})

        data = assert_success_response(response)
        assert observed == {'input_kind': 'no_think', 'target_depth': 'outline_and_descriptions'}
        assert data['data']['pages'][0]['description_content']['text'] == '封面描述'

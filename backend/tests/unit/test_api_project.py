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
    """Vocational quick-start project API tests."""

    def test_create_no_think_project_normalizes_options(self, client):
        response = client.post('/api/projects', json={
            'creation_type': 'no_think',
            'idea_prompt': '解决老人跌倒风险',
            'no_think_options': {
                'project_name': '智慧养老守护系统',
                'industry_or_track': '人工智能',
                'real_scene': '养老院',
                'target_user': '老人和护理员',
                'team_task_description': '四名学生分别负责评估、护理、记录和成果展示',
            },
        })

        data = assert_success_response(response, 201)
        project_id = data['data']['project_id']

        get_response = client.get(f'/api/projects/{project_id}')
        project = assert_success_response(get_response)['data']

        assert project['creation_type'] == 'no_think'
        assert '职业教育争夺赛 PPT 生成需求' in project['idea_prompt']
        assert '世界职业院校技能大赛/争夺赛' in project['idea_prompt']
        assert '项目名称：智慧养老守护系统' in project['idea_prompt']
        assert '真实场景：养老院' in project['idea_prompt']
        assert '服务对象/使用对象：老人和护理员' in project['idea_prompt']

    def test_generate_outline_for_no_think_defaults_to_outline_only(self, client, monkeypatch):
        from services.input_generation_service import InputGenerationResult

        created = client.post('/api/projects', json={
            'creation_type': 'no_think',
            'idea_prompt': '解决老人跌倒风险',
            'no_think_options': {'industry_or_track': '人工智能'},
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
        assert observed == {'input_kind': 'no_think', 'target_depth': 'outline_only'}
        assert data['data']['pages'][0].get('description_content') is None

    def test_generate_outline_for_no_think_can_request_outline_only(self, client, monkeypatch):
        from services.input_generation_service import InputGenerationResult

        created = client.post('/api/projects', json={
            'creation_type': 'no_think',
            'idea_prompt': '解决老人跌倒风险',
            'no_think_options': {'industry_or_track': '人工智能'},
        }).get_json()['data']
        project_id = created['project_id']
        observed = {}

        class FakeInputGenerationService:
            VALID_TARGET_DEPTHS = {'outline_only', 'outline_and_descriptions'}

            def __init__(self, ai_service):
                self.ai_service = ai_service

            def generate(self, project, project_context, options, save_mode='merge_by_index'):
                from models import Page, db
                observed['input_kind'] = options.input_kind
                observed['target_depth'] = options.target_depth
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

        response = client.post(
            f'/api/projects/{project_id}/generate/outline',
            json={'language': 'zh', 'target_depth': 'outline_only'},
        )

        data = assert_success_response(response)
        assert observed == {'input_kind': 'no_think', 'target_depth': 'outline_only'}
        assert data['data']['pages'][0].get('description_content') is None

    def test_generate_outline_for_no_think_can_request_outline_and_descriptions(self, client, monkeypatch):
        from services.input_generation_service import InputGenerationResult

        created = client.post('/api/projects', json={
            'creation_type': 'no_think',
            'idea_prompt': '解决老人跌倒风险',
            'no_think_options': {'industry_or_track': '人工智能'},
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

        response = client.post(
            f'/api/projects/{project_id}/generate/outline',
            json={'language': 'zh', 'target_depth': 'outline_and_descriptions'},
        )

        data = assert_success_response(response)
        assert observed == {'input_kind': 'no_think', 'target_depth': 'outline_and_descriptions'}
        assert data['data']['pages'][0]['description_content']['text'] == '封面描述'


class TestPreciseCompetitionUnderstanding:
    """Vocational precise-generation understanding API tests."""

    def test_understand_project_from_raw_text_persists_spec(self, client, monkeypatch):
        class FakeAIService:
            def generate_json(self, prompt, thinking_budget=1000):
                assert '用户本轮指令或资料' in prompt
                return {
                    'reply': '已完整理解资料并生成结构化稿件。',
                    'ops': [
                        {'type': 'set', 'path': 'project_positioning.project_name', 'value': '智慧养老守护系统'},
                        {'type': 'set', 'path': 'project_positioning.track', 'value': '人工智能'},
                        {'type': 'set', 'path': 'project_positioning.real_scene', 'value': '养老院护理站'},
                        {'type': 'set', 'path': 'project_positioning.service_object', 'value': '老人和护理员'},
                        {'type': 'set', 'path': 'value_innovation.practical_value', 'value': '可用于养老照护课程训练和岗位现场展示'},
                        {'type': 'append_list_item', 'path': 'result_validation.deliverables', 'value': ['评估表', '护理记录表', '演示清单']},
                        {'type': 'append_list_item', 'path': 'result_validation.evidence_materials', 'value': ['测试记录', '评分材料', '用户反馈']},
                    ],
                    'change_summary': ['生成结构化项目稿件'],
                    'destructive_changes': [],
                    'needs_confirmation': False,
                    'questions': [],
                }

        monkeypatch.setattr('controllers.project_controller.get_ai_service', lambda: FakeAIService())

        response = client.post('/api/projects/understand', json={
            'generation_mode': 'precise',
            'input_mode': 'raw_text',
            'raw_text': '''
项目名称：智慧养老守护系统
赛道：人工智能
真实场景：养老院护理站
服务对象：老人和护理员
最终成果形态：跌倒风险评估系统和护理记录表
痛点：夜间跌倒风险高；护理记录不及时
项目目标：完成风险评估、护理干预和记录复核的现场展示
A：风险评估，现场采集老人状态并评估
B：护理干预，现场干预并处置异常
C：记录归档，现场记录并归档
D：成果复核，现场复核评分材料
技能模块：风险评估；护理干预；记录归档；成果复核
成果清单：评估表；护理记录表；演示清单
证据材料：测试记录；评分材料；用户反馈
实用性：可用于养老照护课程训练和岗位现场展示
''',
        })

        data = assert_success_response(response, 201)
        project_id = data['data']['project_id']
        spec = data['data']['competition_project_spec']

        assert data['data']['generation_mode'] == 'precise'
        assert data['data']['next_action'] == 'edit_structured_spec'
        assert spec['competition_context']['competition_name'] == '世界职业院校技能大赛/争夺赛'
        assert spec['project_positioning']['project_name']['value'] == '智慧养老守护系统'

        get_response = client.get(f'/api/projects/{project_id}')
        project = assert_success_response(get_response)['data']

        assert project['status'] == 'UNDERSTOOD'
        assert project['creation_type'] == 'no_think'
        assert project['competition_project_spec']['project_positioning']['real_scene']['value'] == '养老院护理站'
        assert '职业教育争夺赛 PPT 生成需求' in project['idea_prompt']

    def test_understand_project_updates_existing_draft(self, client):
        created = client.post('/api/projects/understand', json={
            'generation_mode': 'precise',
            'input_mode': 'structured_input',
            'structured_input': {
                'project_positioning': {
                    'project_name': '旧项目',
                    'track': '现代农业',
                },
            },
        }).get_json()['data']

        response = client.post('/api/projects/understand', json={
            'generation_mode': 'precise',
            'project_id': created['project_id'],
            'input_mode': 'structured_input',
            'structured_input': {
                'project_positioning': {
                    'project_name': '温室大棚巡检项目',
                    'track': '现代农业',
                    'real_scene': '温室大棚',
                    'service_object': '种植户',
                    'final_deliverable': '巡检记录表和调控方案',
                },
                'problem_definition': {
                    'pain_points': ['巡检不及时'],
                    'project_goal': '现场完成采集、判断、调控和复核',
                },
                'team_roles': [
                    {'member': 'A', 'role': '采集', 'responsibility': '采集环境数据', 'onsite_action': '现场采集并记录'},
                    {'member': 'B', 'role': '判断', 'responsibility': '判断异常', 'onsite_action': '现场检测并判断'},
                    {'member': 'C', 'role': '调控', 'responsibility': '执行调控', 'onsite_action': '现场调试设备'},
                    {'member': 'D', 'role': '复核', 'responsibility': '复核归档', 'onsite_action': '现场复核并归档'},
                ],
                'skill_modules': [
                    {'skill_name': '环境采集', 'responsible_role': 'A', 'verification_method': '记录表', 'onsite_demo_action': '现场采集并说明'},
                ],
                'result_validation': {
                    'deliverables': ['巡检记录表'],
                    'evidence_materials': ['测试记录'],
                },
                'value_innovation': {
                    'practical_value': '可用于现代农业实训',
                    'innovation_points': [],
                },
            },
        })

        data = assert_success_response(response, 201)

        assert data['data']['project_id'] == created['project_id']
        assert data['data']['competition_project_spec']['project_positioning']['project_name']['value'] == '温室大棚巡检项目'

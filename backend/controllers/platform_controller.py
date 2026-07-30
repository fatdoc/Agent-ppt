"""Competition configuration and outline-template business APIs."""
from datetime import datetime
from flask import Blueprint, request
from sqlalchemy import or_

from models import db, OutlineTemplate
from utils import bad_request, error_response, not_found, success_response
from utils.auth import current_user_id


platform_bp = Blueprint('platform', __name__, url_prefix='/api/platform')
outline_template_bp = Blueprint('outline_templates', __name__, url_prefix='/api/outline-templates')


COMPETITIONS = [
    {
        'id': 'wvcc', 'name': '世界职业院校技能大赛', 'shortName': '世职赛',
        'supportLevel': 'FULL', 'enabled': True,
        'competitionTypes': [
            {'id': 'championship', 'name': '争夺赛'},
            {'id': 'ranking', 'name': '排位赛'},
            {'id': 'custom', 'name': '自定义'},
        ],
        'tracks': [
            {'id': 'electronic-information', 'name': '电子信息'},
            {'id': 'equipment-manufacturing', 'name': '装备制造'},
            {'id': 'agriculture', 'name': '农林牧渔'},
            {'id': 'healthcare', 'name': '医药卫生'},
            {'id': 'eldercare', 'name': '康养服务'},
            {'id': 'modern-agriculture', 'name': '现代农业'},
            {'id': 'ai-application', 'name': '人工智能应用'},
            {'id': 'other', 'name': '其他'},
        ],
        'themes': [
            {'id': 'smart-manufacturing', 'name': '智能制造与产业升级'},
            {'id': 'smart-agriculture', 'name': '智慧农业与乡村振兴'},
            {'id': 'smart-eldercare', 'name': '智慧养老与健康服务'},
            {'id': 'ai-industry', 'name': '人工智能赋能产业应用'},
            {'id': 'custom', 'name': '自定义主题'},
        ],
        'scoreDimensions': [
            {'id': 'skill-level', 'name': '技能水平', 'weight': 60},
            {'id': 'professionalism', 'name': '职业素养', 'weight': 10},
            {'id': 'application-value', 'name': '应用价值', 'weight': 10},
            {'id': 'teamwork', 'name': '团队合作', 'weight': 10},
            {'id': 'innovation', 'name': '创新创意', 'weight': 10},
        ],
        'recommendedPageCount': 39, 'promptProfileId': 'wvcc-v1',
        'narrationProfileId': 'wvcc-39-page-v1',
        'outlineTemplateIds': ['wvcc-championship-39'], 'caseLibraryId': 'wvcc',
    },
    {
        'id': 'challenge-cup', 'name': '挑战杯', 'shortName': '挑战杯',
        'supportLevel': 'GENERIC', 'enabled': True,
        'competitionTypes': [{'id': 'custom', 'name': '自定义'}],
        'tracks': [{'id': 'custom', 'name': '自定义赛道'}],
        'themes': [{'id': 'custom', 'name': '自定义主题'}],
        'unsupportedMessage': '当前赛事暂未配置专属规则与案例，将使用通用PPT生成模式。',
    },
    {
        'id': 'innovation-competition', 'name': '中国国际大学生创新大赛', 'shortName': '创新大赛',
        'supportLevel': 'GENERIC', 'enabled': True,
        'competitionTypes': [{'id': 'custom', 'name': '自定义'}],
        'tracks': [{'id': 'custom', 'name': '自定义赛道'}],
        'themes': [{'id': 'custom', 'name': '自定义主题'}],
        'unsupportedMessage': '当前赛事暂未配置专属规则与案例，将使用通用PPT生成模式。',
    },
    {
        'id': 'career-planning', 'name': '全国大学生职业规划大赛', 'shortName': '职业规划大赛',
        'supportLevel': 'COMING_SOON', 'enabled': True,
        'competitionTypes': [], 'tracks': [], 'themes': [],
        'unsupportedMessage': '正在建设专属能力，暂不能进入正式生成流程。',
    },
    {
        'id': 'teaching-ability', 'name': '职业院校技能大赛教学能力比赛', 'shortName': '教学能力比赛',
        'supportLevel': 'COMING_SOON', 'enabled': True,
        'competitionTypes': [], 'tracks': [], 'themes': [],
        'unsupportedMessage': '正在建设专属能力，暂不能进入正式生成流程。',
    },
    {
        'id': 'custom', 'name': '自定义赛事', 'shortName': '自定义赛事',
        'supportLevel': 'GENERIC', 'enabled': True,
        'competitionTypes': [{'id': 'custom', 'name': '自定义'}],
        'tracks': [{'id': 'custom', 'name': '自定义赛道'}],
        'themes': [{'id': 'custom', 'name': '自定义主题'}],
        'unsupportedMessage': '自定义赛事使用通用PPT能力，不启用专属规则、评分或案例。',
    },
]


@platform_bp.route('/competitions', methods=['GET'])
def list_competitions():
    return success_response({'competitions': [item for item in COMPETITIONS if item['enabled']]})


def _owned_template(template_id):
    query = OutlineTemplate.query.filter(OutlineTemplate.id == template_id)
    user_id = current_user_id()
    if user_id:
        query = query.filter(or_(OutlineTemplate.user_id == user_id, OutlineTemplate.user_id.is_(None)))
    return query.first()


def _contains_scores(sections):
    return any(
        section.get('scoreDimensions') or _contains_scores(section.get('children') or [])
        for section in (sections or [])
    )


def _validate(data):
    if not isinstance(data, dict) or not str(data.get('name', '')).strip():
        return 'name is required'
    if data.get('supportScope', 'PRIVATE') not in ('SYSTEM', 'TEAM', 'PRIVATE'):
        return 'Invalid supportScope'
    if data.get('status', 'DRAFT') not in ('DRAFT', 'PUBLISHED', 'ARCHIVED'):
        return 'Invalid status'
    if not isinstance(data.get('sections'), list) or not data['sections']:
        return 'sections must be a non-empty array'
    if data.get('competitionId') not in (None, '', 'wvcc') and _contains_scores(data['sections']):
        return 'Only wvcc templates may contain configured score dimensions'
    return None


def _apply(template, data):
    template.name = str(data.get('name', template.name)).strip()
    template.description = data.get('description')
    template.competition_id = data.get('competitionId') or None
    template.competition_type_id = data.get('competitionTypeId') or None
    template.track_id = data.get('trackId') or None
    template.theme_id = data.get('themeId') or None
    template.support_scope = data.get('supportScope', template.support_scope or 'PRIVATE')
    template.status = data.get('status', template.status or 'DRAFT')
    template.target_page_count = data.get('targetPageCount')
    template.set_style_tags(data.get('styleTags', []))
    template.set_sections(data.get('sections', []))


@outline_template_bp.route('', methods=['GET'])
def list_outline_templates():
    query = OutlineTemplate.query
    user_id = current_user_id()
    if user_id:
        query = query.filter(or_(OutlineTemplate.user_id == user_id, OutlineTemplate.user_id.is_(None)))
    for field, column in (
        ('competitionId', OutlineTemplate.competition_id),
        ('supportScope', OutlineTemplate.support_scope),
        ('status', OutlineTemplate.status),
    ):
        value = request.args.get(field)
        if value:
            query = query.filter(column == value)
    templates = query.order_by(OutlineTemplate.updated_at.desc()).all()
    return success_response({'templates': [template.to_dict() for template in templates]})


@outline_template_bp.route('', methods=['POST'])
def create_outline_template():
    try:
        data = request.get_json(silent=True)
        validation_error = _validate(data)
        if validation_error:
            return bad_request(validation_error)
        template = OutlineTemplate(
            user_id=current_user_id(), name=data['name'].strip(),
            support_scope=data.get('supportScope', 'PRIVATE'),
            status=data.get('status', 'DRAFT'), version=1, created_by='CURRENT_USER',
        )
        _apply(template, data)
        template.set_versions([])
        db.session.add(template)
        db.session.commit()
        return success_response(template.to_dict(), status_code=201)
    except Exception as error:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(error), 500)


@outline_template_bp.route('/<template_id>', methods=['PUT'])
def update_outline_template(template_id):
    try:
        template = _owned_template(template_id)
        if not template:
            return not_found('OutlineTemplate')
        if template.created_by == 'SYSTEM':
            return bad_request('System templates cannot be edited')
        data = request.get_json(silent=True)
        validation_error = _validate(data)
        if validation_error:
            return bad_request(validation_error)
        versions = template.get_versions()
        versions.append({
            'version': template.version,
            'createdAt': template.updated_at.isoformat() + 'Z',
            'changeNote': data.get('changeNote', '编辑模板'),
            'sections': template.get_sections(),
        })
        template.set_versions(versions)
        template.version += 1
        _apply(template, data)
        template.updated_at = datetime.utcnow()
        db.session.commit()
        return success_response(template.to_dict())
    except Exception as error:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(error), 500)


@outline_template_bp.route('/<template_id>', methods=['DELETE'])
def delete_outline_template(template_id):
    try:
        template = _owned_template(template_id)
        if not template:
            return not_found('OutlineTemplate')
        if template.created_by == 'SYSTEM':
            return bad_request('System templates cannot be deleted')
        db.session.delete(template)
        db.session.commit()
        return success_response(message='Outline template deleted')
    except Exception as error:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(error), 500)


@outline_template_bp.route('/<template_id>/duplicate', methods=['POST'])
def duplicate_outline_template(template_id):
    source = _owned_template(template_id)
    if not source:
        return not_found('OutlineTemplate')
    copy = OutlineTemplate(
        user_id=current_user_id(), name=f'{source.name}（副本）',
        description=source.description, competition_id=source.competition_id,
        competition_type_id=source.competition_type_id, track_id=source.track_id,
        theme_id=source.theme_id, support_scope='PRIVATE', status='DRAFT',
        version=1, target_page_count=source.target_page_count, created_by='CURRENT_USER',
    )
    copy.set_style_tags(source.get_style_tags())
    copy.set_sections(source.get_sections())
    copy.set_versions([])
    db.session.add(copy)
    db.session.commit()
    return success_response(copy.to_dict(), status_code=201)


@outline_template_bp.route('/match', methods=['GET'])
def match_outline_template():
    context = {
        'competition_id': request.args.get('competitionId'),
        'competition_type_id': request.args.get('competitionTypeId'),
        'track_id': request.args.get('trackId'),
        'theme_id': request.args.get('themeId'),
    }
    query = OutlineTemplate.query.filter(OutlineTemplate.status == 'PUBLISHED')
    user_id = current_user_id()
    if user_id:
        query = query.filter(or_(OutlineTemplate.user_id == user_id, OutlineTemplate.user_id.is_(None)))

    def rank(template):
        score = 0
        for field, weight in (
            ('competition_id', 2), ('competition_type_id', 1),
            ('track_id', 1), ('theme_id', 1),
        ):
            value = getattr(template, field)
            if value and value != context[field]:
                return -1
            if value:
                score += weight
        return score

    ranked = sorted(((rank(item), item) for item in query.all()), key=lambda item: item[0], reverse=True)
    match = next((item for score, item in ranked if score >= 0), None)
    return success_response({'template': match.to_dict() if match else None})

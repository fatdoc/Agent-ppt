"""Credit balance and estimation endpoints."""
from flask import Blueprint, request

from models import Project
from services.credit_service import (
    account_payload,
    estimate_operation,
    estimate_page_count_from_text,
    estimate_project_pages,
)
from utils import bad_request, success_response
from utils.auth import current_user, current_user_id, owned_project_or_404

credit_bp = Blueprint('credits', __name__, url_prefix='/api/credits')


@credit_bp.route('/me', methods=['GET'])
def my_credits():
    user = current_user()
    if not user:
        return bad_request('Login required')
    return success_response(account_payload(user.id))


@credit_bp.route('/estimate', methods=['POST'])
def estimate_credits():
    data = request.get_json() or {}
    operation = data.get('operation')
    if not operation:
        return bad_request('operation is required')

    page_count = data.get('page_count')
    project_id = data.get('project_id')
    if page_count is None and project_id:
        project = owned_project_or_404(project_id)
        page_count = estimate_project_pages(project) if project else 1
    if page_count is None:
        page_count = estimate_page_count_from_text(data.get('text'), default=10)

    estimate = estimate_operation(
        operation,
        page_count=page_count,
        reference_page_count=data.get('reference_page_count'),
        target_page_count=data.get('target_page_count'),
    )
    return success_response({'estimate': estimate.to_dict()})

"""
File Controller - handles static file serving
"""
from flask import Blueprint, send_from_directory, current_app
from utils import error_response, not_found
from utils.auth import current_user_id
from models import FileArtifact, Material, Page, Project, ReferenceFile, UserTemplate
from utils.path_utils import find_file_with_prefix, is_path_within, resolve_path_within
import os
import re
from pathlib import Path
from werkzeug.utils import secure_filename

file_bp = Blueprint('files', __name__, url_prefix='/files')


@file_bp.route('/<project_id>/<file_type>/<filename>', methods=['GET'])
def serve_file(project_id, file_type, filename):
    """
    GET /files/{project_id}/{type}/{filename} - Serve static files
    
    Args:
        project_id: Project UUID
        file_type: 'template' or 'pages'
        filename: File name
    """
    try:
        if file_type not in ['template', 'pages', 'materials', 'exports']:
            return not_found('File')

        user_id = current_user_id()
        if not user_id:
            return not_found('File')
        query = Project.query.filter(Project.id == project_id)
        query = query.filter(Project.user_id == user_id)
        if not query.first():
            return not_found('File')
        
        # Construct file path
        file_dir = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            project_id,
            file_type
        )
        
        # Check if directory exists
        if not os.path.exists(file_dir):
            return not_found('File')
        
        # Check if file exists
        file_path = os.path.join(file_dir, filename)
        if not os.path.exists(file_path):
            return not_found('File')
        
        # Serve file
        return send_from_directory(file_dir, filename)
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@file_bp.route('/user-templates/<template_id>/<filename>', methods=['GET'])
def serve_user_template(template_id, filename):
    """
    GET /files/user-templates/{template_id}/{filename} - Serve user template files
    
    Args:
        template_id: Template UUID
        filename: File name
    """
    try:
        user_id = current_user_id()
        if not user_id:
            return not_found('File')
        query = UserTemplate.query.filter(UserTemplate.id == template_id)
        query = query.filter(UserTemplate.user_id == user_id)
        if not query.first():
            return not_found('File')

        # Construct file path
        file_dir = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'user-templates',
            template_id
        )
        
        # Check if directory exists
        if not os.path.exists(file_dir):
            return not_found('File')
        
        # Check if file exists
        file_path = os.path.join(file_dir, filename)
        if not os.path.exists(file_path):
            return not_found('File')
        
        # Serve file
        return send_from_directory(file_dir, filename)
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@file_bp.route('/materials/<filename>', methods=['GET'])
def serve_global_material(filename):
    """
    GET /files/materials/{filename} - Serve global material files (not bound to a project)
    
    Args:
        filename: File name
    """
    try:
        safe_filename = secure_filename(filename)
        user_id = current_user_id()
        if not user_id:
            return not_found('File')
        query = Material.query.filter(
            Material.project_id.is_(None),
            Material.filename == safe_filename,
        )
        query = query.filter(Material.user_id == user_id)
        if not query.first():
            return not_found('File')

        # Construct file path
        file_dir = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'materials'
        )
        
        # Check if directory exists
        if not os.path.exists(file_dir):
            return not_found('File')
        
        # Check if file exists
        file_path = os.path.join(file_dir, safe_filename)
        if not os.path.exists(file_path):
            return not_found('File')
        
        # Serve file
        return send_from_directory(file_dir, safe_filename)
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@file_bp.route('/mineru/<extract_id>/<path:filepath>', methods=['GET'])
def serve_mineru_file(extract_id, filepath):
    """
    GET /files/mineru/{extract_id}/{filepath} - Serve MinerU extracted files.

    Args:
        extract_id: Extract UUID
        filepath: Relative file path within the extract
    """
    try:
        user_id = current_user_id()
        if not user_id or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', extract_id):
            return not_found('File')

        artifact = FileArtifact.query.filter_by(
            extract_id=extract_id,
            user_id=user_id,
            deleted_at=None,
        ).first()
        if artifact:
            root_relative_path = artifact.root_relative_path
        else:
            marker = f'/files/mineru/{extract_id}/'
            legacy_reference = ReferenceFile.query.filter(
                ReferenceFile.user_id == user_id,
                ReferenceFile.markdown_content.contains(marker),
            ).first()
            legacy_page = (
                Page.query
                .join(Project, Page.project_id == Project.id)
                .filter(
                    Project.user_id == user_id,
                    Page.description_content.contains(marker),
                )
                .first()
            )
            if not legacy_reference and not legacy_page:
                return not_found('File')
            root_relative_path = f'mineru_files/{extract_id}'

        try:
            root_dir = resolve_path_within(root_relative_path, current_app.config['UPLOAD_FOLDER'])
        except ValueError:
            return error_response('INVALID_PATH', 'Invalid file path', 403)
        full_path = Path(root_dir) / filepath

        # This prevents path traversal attacks
        resolved_root_dir = Path(root_dir).resolve()
        
        try:
            # Check if the path is trying to escape the root directory
            resolved_full_path = full_path.resolve()
            if not is_path_within(resolved_full_path, resolved_root_dir):
                return error_response('INVALID_PATH', 'Invalid file path', 403)
        except Exception:
            # If we can't resolve the path at all, it's invalid
            return error_response('INVALID_PATH', 'Invalid file path', 403)

        # Try to find file with prefix matching
        matched_path = find_file_with_prefix(full_path)
        
        if matched_path is not None:
            # Additional security check for matched path
            try:
                resolved_matched_path = matched_path.resolve(strict=True)
                
                # Verify the matched file is still within the root directory
                if not is_path_within(resolved_matched_path, resolved_root_dir):
                    return error_response('INVALID_PATH', 'Invalid file path', 403)
            except FileNotFoundError:
                return not_found('File')
            except Exception:
                return error_response('INVALID_PATH', 'Invalid file path', 403)
            
            return send_from_directory(str(matched_path.parent), matched_path.name)

        return not_found('File')
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)

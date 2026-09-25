"""
Simplified Flask Application Entry Point
"""
import os
import sys
import hmac
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
from sqlalchemy.exc import SQLAlchemyError
from flask_migrate import Migrate

# Load environment variables from project root .env file
_project_root = Path(__file__).parent.parent
_env_file = _project_root / '.env'


def _load_project_dotenv(env_file=_env_file):
    """Load development defaults unless the operator explicitly opts out."""
    enabled = os.getenv('LOAD_DOTENV', 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
    if enabled:
        # Explicit deployment/test environment values always win.
        load_dotenv(dotenv_path=env_file, override=False)


_load_project_dotenv()

from flask import Flask
from services.provider_config import ProviderScopedConfig, capture_provider_snapshot, provider_snapshot_scope
from flask_cors import CORS
from models import db
from config import Config
from controllers.editor_controller import editor_bp
from controllers.material_controller import material_bp, material_global_bp
from controllers.reference_file_controller import reference_file_bp
from controllers.settings_controller import settings_bp
from controllers.credit_controller import credit_bp
from controllers.auth_controller import auth_bp
from controllers.openai_oauth_controller import openai_oauth_bp
from controllers.ppt_to_ppt_controller import ppt_to_ppt_bp
from controllers.agent_mode_controller import agent_mode_bp
from controllers.api_key_controller import api_key_bp
from controllers.public_ppt_controller import public_ppt_bp
from controllers import project_bp, page_bp, template_bp, user_template_bp, user_style_template_bp, export_bp, file_bp, style_bp


# Enable SQLite WAL mode for all connections
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Enable WAL mode and related PRAGMAs for each SQLite connection.
    Registered once at import time to avoid duplicate handlers when
    create_app() is called multiple times.
    """
    # Only apply to SQLite connections
    if not isinstance(dbapi_conn, sqlite3.Connection):
        return

    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")  # 60 seconds timeout
    finally:
        cursor.close()


def create_app(config_overrides=None):
    """Application factory"""
    app = Flask(__name__)
    app.config = ProviderScopedConfig(app.root_path, app.config)
    
    # Load configuration from Config class
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    _validate_security_configuration(app)

    # Allow DATABASE_URL env var to override config at runtime (supports test isolation)
    if os.getenv('DATABASE_URL'):
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')

    # Ensure instance directory exists for the default SQLite path in Config
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    instance_dir = os.path.join(backend_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)

    # Ensure upload folder exists
    project_root = os.path.dirname(backend_dir)
    upload_folder = (config_overrides or {}).get('UPLOAD_FOLDER') or os.getenv('UPLOAD_FOLDER') or app.config.get('UPLOAD_FOLDER') or os.path.join(project_root, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder
    
    # CORS configuration (parse from environment)
    raw_cors = os.getenv('CORS_ORIGINS', 'http://localhost:3000')
    if raw_cors.strip() == '*':
        cors_origins = '*'
    else:
        cors_origins = [o.strip() for o in raw_cors.split(',') if o.strip()]
    app.config['CORS_ORIGINS'] = cors_origins
    
    # Initialize logging (log to stdout so Docker can capture it)
    log_level = getattr(logging, app.config['LOG_LEVEL'], logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    from services.provider_config import install_provider_log_redaction
    install_provider_log_redaction()

    # 设置第三方库的日志级别，避免过多的DEBUG日志
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.INFO)  # Flask开发服务器日志保持INFO
    logging.getLogger('volcenginesdkarkruntime').setLevel(logging.WARNING)

    # Initialize extensions
    db.init_app(app)
    CORS(app, origins=cors_origins, supports_credentials=cors_origins != '*')
    # Database migrations (Alembic via Flask-Migrate)
    Migrate(app, db)
    
    from services.task_execution import register_recovery_command
    register_recovery_command(app)

    # Register blueprints
    app.register_blueprint(project_bp)
    app.register_blueprint(editor_bp)
    app.register_blueprint(ppt_to_ppt_bp)
    app.register_blueprint(agent_mode_bp)
    app.register_blueprint(page_bp)
    app.register_blueprint(template_bp)
    app.register_blueprint(user_template_bp)
    app.register_blueprint(user_style_template_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(material_bp)
    app.register_blueprint(material_global_bp)
    app.register_blueprint(reference_file_bp, url_prefix='/api/reference-files')
    app.register_blueprint(settings_bp)
    app.register_blueprint(credit_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(openai_oauth_bp)
    app.register_blueprint(style_bp)
    app.register_blueprint(api_key_bp)
    app.register_blueprint(public_ppt_bp)


    @app.before_request
    def _authenticate_user():
        from flask import g, request
        from utils.auth import authenticate_request, validate_csrf_request
        if request.path in ('/', '/health'):
            return
        if request.path in ('/api/auth/config', '/api/auth/login', '/api/auth/register'):
            return
        if request.path.startswith('/api/access-code/'):
            return
        if not (request.path.startswith('/api/') or request.path.startswith('/files/')):
            return
        auth_error = authenticate_request()
        if auth_error:
            return auth_error
        csrf_error = validate_csrf_request()
        if csrf_error:
            return csrf_error
        user = getattr(g, 'current_user', None)
        if user:
            # Deterministic editor requests must not refresh OAuth or load keys.
            from services.provider_config import ProviderConfigSnapshot
            snapshot = (ProviderConfigSnapshot(user.id, 'local-editor-v1', {}, id(app.config))
                        if request.blueprint == 'editor' else capture_provider_snapshot(user_id=user.id))
            scope = provider_snapshot_scope(snapshot)
            scope.__enter__()
            g.provider_snapshot_scope = scope

    @app.teardown_request
    def _release_provider_snapshot(error=None):
        from flask import g
        scope = g.pop('provider_snapshot_scope', None)
        if scope is not None:
            scope.__exit__(None, None, None)

    # Access code enforcement on all /api/ routes
    @app.before_request
    def _enforce_access_code():
        from flask import request, jsonify
        expected = os.getenv('ACCESS_CODE', '').strip()
        if not expected:
            return  # not enabled
        if not request.path.startswith('/api/'):
            return  # non-API routes (health, static, etc.)
        if request.path.startswith('/api/access-code/'):
            return  # allow check/verify endpoints
        if request.path in ('/api/auth/config', '/api/auth/login', '/api/auth/register'):
            return  # allow login/register endpoints
        code = request.headers.get('X-Access-Code', '')
        if hmac.compare_digest(code, expected):
            return
        return jsonify({'error': 'Access code required'}), 403

    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'ok', 'message': 'Banana Slides API is running'}

    # Access code verification
    @app.route('/api/access-code/check', methods=['GET'])
    def check_access_code():
        """Check if access code protection is enabled"""
        enabled = bool(os.getenv('ACCESS_CODE', '').strip())
        return {'data': {'enabled': enabled}}

    @app.route('/api/access-code/verify', methods=['POST'])
    def verify_access_code():
        """Verify the provided access code"""
        from flask import request, jsonify
        expected = os.getenv('ACCESS_CODE', '').strip()
        if not expected:
            return {'data': {'valid': True}}
        code = (request.json or {}).get('code', '')
        if hmac.compare_digest(code, expected):
            return {'data': {'valid': True}}
        return jsonify({'error': 'Invalid access code'}), 403
    
    # Output language endpoint
    @app.route('/api/output-language', methods=['GET'])
    def get_output_language():
        """
        获取用户的输出语言偏好（从数据库 Settings 读取）
        返回: zh, ja, en, auto
        """
        from models import Settings
        try:
            settings = Settings.get_settings()
            return {'data': {'language': settings.output_language or Config.OUTPUT_LANGUAGE}}
        except SQLAlchemyError as db_error:
            logging.warning(f"Failed to load output language from settings: {db_error}")
            return {'data': {'language': Config.OUTPUT_LANGUAGE}}  # 默认中文

    # Root endpoint
    @app.route('/')
    def index():
        return {
            'name': 'Banana Slides API',
            'version': '1.0.0',
            'description': 'AI-powered PPT generation service',
            'endpoints': {
                'health': '/health',
                'api_docs': '/api',
                'projects': '/api/projects'
            }
        }
    
    return app


def _validate_security_configuration(app):
    """Fail closed for production settings that make signed sessions forgeable."""
    if os.getenv('FLASK_ENV', '').strip().lower() != 'production':
        return
    secret_key = str(app.config.get('SECRET_KEY') or '')
    if secret_key == 'your-secret-key-change-this' or len(secret_key) < 32:
        raise RuntimeError('Production SECRET_KEY must be explicitly set to at least 32 characters')


# Create app instance
app = create_app()


def _compute_worktree_port(base_port: int) -> int:
    """Compute a deterministic port from the worktree directory name.

    Uses MD5 of the project root basename so each worktree gets a unique,
    stable port pair (backend 5xxx, frontend 3xxx) without manual config.
    """
    import hashlib
    basename = _project_root.name
    offset = int(hashlib.md5(basename.encode()).hexdigest()[:8], 16) % 500
    return base_port + offset


if __name__ == '__main__':
    # Run development server
    if os.getenv("IN_DOCKER", "0") == "1":
        port = 5000  # Docker 容器内部固定使用 5000 端口
    elif os.getenv('BACKEND_PORT'):
        port = int(os.getenv('BACKEND_PORT'))
    else:
        port = _compute_worktree_port(5000)
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    
    logging.info(
        "\n"
        "╔══════════════════════════════════════╗\n"
        "║   🍌 Banana Slides API Server 🍌   ║\n"
        "╚══════════════════════════════════════╝\n"
        f"Server starting on: http://localhost:{port}\n"
        f"Output Language: {Config.OUTPUT_LANGUAGE}\n"
        f"Environment: {os.getenv('FLASK_ENV', 'development')}\n"
        f"Debug mode: {debug}\n"
        f"API Base URL: http://localhost:{port}/api\n"
        f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}\n"
        f"Uploads: {app.config['UPLOAD_FOLDER']}"
    )
    
    # Using absolute paths for database, so WSL path issues should not occur
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=debug)

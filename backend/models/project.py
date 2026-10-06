"""
Project model
"""
import json
import uuid
from datetime import datetime
from . import db


class Project(db.Model):
    """
    Project model - represents a PPT project
    """
    __tablename__ = 'projects'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    project_title = db.Column(db.String(255), nullable=True)
    idea_prompt = db.Column(db.Text, nullable=True)
    outline_text = db.Column(db.Text, nullable=True)  # 用户输入的大纲文本（用于outline类型）
    description_text = db.Column(db.Text, nullable=True)  # 用户输入的描述文本（用于description类型）
    extra_requirements = db.Column(db.Text, nullable=True)  # 额外要求，应用到每个页面的AI提示词
    outline_requirements = db.Column(db.Text, nullable=True)  # 大纲生成要求
    description_requirements = db.Column(db.Text, nullable=True)  # 页面描述生成要求
    creation_type = db.Column(db.String(20), nullable=False, default='idea')  # idea|outline|descriptions
    template_image_path = db.Column(db.String(500), nullable=True)
    template_style = db.Column(db.Text, nullable=True)  # 风格描述文本（无模板图模式）
    template_mode = db.Column(db.String(10), nullable=False, server_default='single', default='single')
    generation_mode = db.Column(db.String(30), nullable=False, server_default='fast', default='fast')
    harness_template = db.Column(db.String(80), nullable=True)
    harness_payload = db.Column(db.Text, nullable=True)
    visual_strategy = db.Column(db.String(30), nullable=False, server_default='native', default='native')
    external_style_skill_id = db.Column(db.String(128), nullable=True)
    external_style_payload = db.Column(db.Text, nullable=True)
    ppt_to_ppt_blueprint = db.Column(db.Text, nullable=True)
    # 导出设置
    export_extractor_method = db.Column(db.String(50), nullable=True, default='hybrid')  # 组件提取方法: mineru, hybrid
    export_inpaint_method = db.Column(db.String(50), nullable=True, default='hybrid')  # 背景图获取方法: generative, baidu, hybrid
    export_allow_partial = db.Column(db.Boolean, nullable=True, default=False)  # 是否允许返回半成品（导出出错时继续而非停止）
    enable_icon_subject_extraction = db.Column(db.Boolean, nullable=True, default=True)  # 是否对小尺寸图标走百度智能抠图
    image_aspect_ratio = db.Column(db.String(10), nullable=False, server_default='16:9', default='16:9')
    status = db.Column(db.String(50), nullable=False, default='DRAFT')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    # 使用 'select' 策略支持 eager loading，同时保持灵活性
    pages = db.relationship('Page', back_populates='project', lazy='select', 
                           cascade='all, delete-orphan', order_by='Page.order_index')
    tasks = db.relationship('Task', back_populates='project', lazy='select',
                           cascade='all, delete-orphan')
    materials = db.relationship('Material', back_populates='project', lazy='select',
                           cascade='all, delete-orphan')
    template_assets = db.relationship(
        'ProjectTemplateAsset',
        back_populates='project',
        lazy='select',
        cascade='all, delete-orphan',
        order_by='ProjectTemplateAsset.sort_order',
    )
    user = db.relationship('User', back_populates='projects')
    
    def to_dict(self, include_pages=False):
        """Convert to dictionary"""
        # Format created_at and updated_at with UTC timezone indicator for proper frontend parsing
        created_at_str = None
        if self.created_at:
            created_at_str = self.created_at.isoformat() + 'Z' if not self.created_at.tzinfo else self.created_at.isoformat()
        
        updated_at_str = None
        if self.updated_at:
            updated_at_str = self.updated_at.isoformat() + 'Z' if not self.updated_at.tzinfo else self.updated_at.isoformat()
        
        data = {
            'project_id': self.id,
            'user_id': self.user_id,
            'project_title': self.project_title,
            'idea_prompt': self.idea_prompt,
            'outline_text': self.outline_text,
            'description_text': self.description_text,
            'extra_requirements': self.extra_requirements,
            'outline_requirements': self.outline_requirements,
            'description_requirements': self.description_requirements,
            'creation_type': self.creation_type,
            'template_image_url': f'/files/{self.id}/template/{self.template_image_path.split("/")[-1]}' if self.template_image_path else None,
            'template_style': self.template_style,
            'template_mode': self.template_mode or 'single',
            'generation_mode': self.generation_mode or 'fast',
            'harness_template': self.harness_template,
            'harness_payload': self.get_harness_payload(),
            'visual_strategy': self.visual_strategy or 'native',
            'external_style_skill_id': self.external_style_skill_id,
            'external_style_payload': self.get_external_style_payload(),
            'ppt_to_ppt_blueprint': self.get_ppt_to_ppt_blueprint(),
            'export_extractor_method': self.export_extractor_method or 'hybrid',
            'export_inpaint_method': self.export_inpaint_method or 'hybrid',
            'export_allow_partial': self.export_allow_partial or False,
            'enable_icon_subject_extraction': True if self.enable_icon_subject_extraction is None else bool(self.enable_icon_subject_extraction),
            'image_aspect_ratio': self.image_aspect_ratio,
            'status': self.status,
            'created_at': created_at_str,
            'updated_at': updated_at_str,
        }
        
        if include_pages:
            # pages 现在是列表，不需要 order_by（已在 relationship 中定义）
            data['pages'] = [page.to_dict() for page in self.pages]
        
        return data

    def get_ppt_to_ppt_blueprint(self):
        """Parse PPT-to-PPT blueprint JSON."""
        if self.ppt_to_ppt_blueprint:
            try:
                return json.loads(self.ppt_to_ppt_blueprint)
            except json.JSONDecodeError:
                return None
        return None

    def set_ppt_to_ppt_blueprint(self, data):
        """Store PPT-to-PPT blueprint as JSON text."""
        if data:
            self.ppt_to_ppt_blueprint = json.dumps(data, ensure_ascii=False)
        else:
            self.ppt_to_ppt_blueprint = None

    def get_harness_payload(self):
        """Parse harness payload JSON."""
        if self.harness_payload:
            try:
                return json.loads(self.harness_payload)
            except json.JSONDecodeError:
                return self.harness_payload
        return None

    def set_harness_payload(self, data):
        """Store harness payload as JSON text."""
        if data is None or data == "":
            self.harness_payload = None
        elif isinstance(data, str):
            self.harness_payload = data
        else:
            self.harness_payload = json.dumps(data, ensure_ascii=False)

    def get_external_style_payload(self):
        """Parse external style skill payload JSON."""
        if self.external_style_payload:
            try:
                return json.loads(self.external_style_payload)
            except json.JSONDecodeError:
                return self.external_style_payload
        return None

    def set_external_style_payload(self, data):
        """Store external style skill payload as JSON text."""
        if data is None or data == "":
            self.external_style_payload = None
        elif isinstance(data, str):
            self.external_style_payload = data
        else:
            self.external_style_payload = json.dumps(data, ensure_ascii=False)
    
    def __repr__(self):
        return f'<Project {self.id}: {self.status}>'

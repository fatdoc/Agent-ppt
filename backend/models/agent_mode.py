"""Agent Mode v1 planning and generation tracking models."""
import json
import uuid
from datetime import datetime

from . import db


def _json_loads(value, fallback=None):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _json_dumps(value):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


class DeckVersion(db.Model):
    """A versioned deck plan generated or edited before image generation."""

    __tablename__ = "deck_versions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey("projects.id"), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(32), nullable=False, default="draft")
    deck_plan = db.Column(db.Text, nullable=True)
    qa_result = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    slide_versions = db.relationship(
        "SlideVersion",
        back_populates="deck_version",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="SlideVersion.order_index",
    )
    visual_system = db.relationship(
        "DeckVisualSystem",
        back_populates="deck_version",
        lazy="select",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def get_deck_plan(self):
        return _json_loads(self.deck_plan, {})

    def set_deck_plan(self, data):
        self.deck_plan = _json_dumps(data)

    def get_qa_result(self):
        return _json_loads(self.qa_result, None)

    def set_qa_result(self, data):
        self.qa_result = _json_dumps(data)

    def to_dict(self, include_children=True):
        data = {
            "deck_version_id": self.id,
            "project_id": self.project_id,
            "version_number": self.version_number,
            "status": self.status,
            "deck_plan": self.get_deck_plan(),
            "qa_result": self.get_qa_result(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_children:
            data["visual_system"] = self.visual_system.to_dict() if self.visual_system else None
            data["slides"] = [slide.to_dict() for slide in self.slide_versions]
        return data


class SlideVersion(db.Model):
    """A versioned editable plan for a single slide."""

    __tablename__ = "slide_versions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deck_version_id = db.Column(db.String(36), db.ForeignKey("deck_versions.id"), nullable=False, index=True)
    page_id = db.Column(db.String(36), db.ForeignKey("pages.id"), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False, default=1)
    order_index = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending_confirmation")
    locked = db.Column(db.Boolean, nullable=False, default=False)
    slide_plan = db.Column(db.Text, nullable=False)
    qa_result = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    deck_version = db.relationship("DeckVersion", back_populates="slide_versions")
    page = db.relationship("Page")
    visual_plans = db.relationship(
        "PageVisualPlan",
        back_populates="slide_version",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="PageVisualPlan.version_number.desc()",
    )

    def get_slide_plan(self):
        return _json_loads(self.slide_plan, {})

    def set_slide_plan(self, data):
        self.slide_plan = _json_dumps(data)

    def get_qa_result(self):
        return _json_loads(self.qa_result, None)

    def set_qa_result(self, data):
        self.qa_result = _json_dumps(data)

    @property
    def current_visual_plan(self):
        return self.visual_plans[0] if self.visual_plans else None

    def to_dict(self):
        return {
            "slide_version_id": self.id,
            "deck_version_id": self.deck_version_id,
            "page_id": self.page_id,
            "version_number": self.version_number,
            "order_index": self.order_index,
            "status": self.status,
            "locked": self.locked,
            "slide_plan": self.get_slide_plan(),
            "qa_result": self.get_qa_result(),
            "visual_plan": self.current_visual_plan.to_dict() if self.current_visual_plan else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DeckVisualSystem(db.Model):
    """The global visual system used by a deck version."""

    __tablename__ = "deck_visual_systems"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey("projects.id"), nullable=False, index=True)
    deck_version_id = db.Column(db.String(36), db.ForeignKey("deck_versions.id"), nullable=False, index=True)
    strategy_id = db.Column(db.String(64), nullable=False, default="native")
    version_number = db.Column(db.Integer, nullable=False, default=1)
    system_json = db.Column(db.Text, nullable=False)
    qa_result = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    deck_version = db.relationship("DeckVersion", back_populates="visual_system")

    def get_system(self):
        return _json_loads(self.system_json, {})

    def set_system(self, data):
        self.system_json = _json_dumps(data)

    def get_qa_result(self):
        return _json_loads(self.qa_result, None)

    def set_qa_result(self, data):
        self.qa_result = _json_dumps(data)

    def to_dict(self):
        return {
            "visual_system_id": self.id,
            "project_id": self.project_id,
            "deck_version_id": self.deck_version_id,
            "strategy_id": self.strategy_id,
            "version_number": self.version_number,
            "system": self.get_system(),
            "qa_result": self.get_qa_result(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PageVisualPlan(db.Model):
    """A versioned visual plan for a slide/page."""

    __tablename__ = "page_visual_plans"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey("projects.id"), nullable=False, index=True)
    page_id = db.Column(db.String(36), db.ForeignKey("pages.id"), nullable=False, index=True)
    slide_version_id = db.Column(db.String(36), db.ForeignKey("slide_versions.id"), nullable=False, index=True)
    deck_visual_system_id = db.Column(db.String(36), db.ForeignKey("deck_visual_systems.id"), nullable=False, index=True)
    strategy_id = db.Column(db.String(64), nullable=False, default="native")
    version_number = db.Column(db.Integer, nullable=False, default=1)
    plan_json = db.Column(db.Text, nullable=False)
    qa_result = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="pending_confirmation")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    slide_version = db.relationship("SlideVersion", back_populates="visual_plans")
    page = db.relationship("Page")
    deck_visual_system = db.relationship("DeckVisualSystem")

    def get_plan(self):
        return _json_loads(self.plan_json, {})

    def set_plan(self, data):
        self.plan_json = _json_dumps(data)

    def get_qa_result(self):
        return _json_loads(self.qa_result, None)

    def set_qa_result(self, data):
        self.qa_result = _json_dumps(data)

    def to_dict(self):
        plan = self.get_plan()
        return {
            "visual_plan_id": self.id,
            "project_id": self.project_id,
            "page_id": self.page_id,
            "slide_version_id": self.slide_version_id,
            "deck_visual_system_id": self.deck_visual_system_id,
            "strategy_id": self.strategy_id,
            "version_number": self.version_number,
            "status": self.status,
            "source_anchor": plan.get("source_anchor"),
            "reader_takeaway": plan.get("reader_takeaway"),
            "operator_required": plan.get("operator_required"),
            "operator_family": plan.get("operator_family"),
            "metaphor_world": plan.get("metaphor_world"),
            "composition": plan.get("composition"),
            "labels": plan.get("labels", []),
            "negative_prompts": plan.get("negative_prompts", []),
            "visual_prompt": plan.get("visual_prompt"),
            "plan": plan,
            "qa_result": self.get_qa_result(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentRun(db.Model):
    """Audit record for one Agent Mode run."""

    __tablename__ = "agent_runs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    project_id = db.Column(db.String(36), db.ForeignKey("projects.id"), nullable=True, index=True)
    run_type = db.Column(db.String(64), nullable=False, default="agent_mode_v1")
    status = db.Column(db.String(32), nullable=False, default="running")
    input_json = db.Column(db.Text, nullable=True)
    output_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    steps = db.relationship("AgentStep", back_populates="agent_run", lazy="select", cascade="all, delete-orphan")
    tool_calls = db.relationship("AgentToolCall", back_populates="agent_run", lazy="select", cascade="all, delete-orphan")

    def set_input(self, data):
        self.input_json = _json_dumps(data)

    def set_output(self, data):
        self.output_json = _json_dumps(data)

    def to_dict(self):
        return {
            "agent_run_id": self.id,
            "project_id": self.project_id,
            "run_type": self.run_type,
            "status": self.status,
            "input": _json_loads(self.input_json, None),
            "output": _json_loads(self.output_json, None),
            "error_message": self.error_message,
            "steps": [step.to_dict() for step in self.steps],
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AgentStep(db.Model):
    """One structured Agent pipeline step."""

    __tablename__ = "agent_steps"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_run_id = db.Column(db.String(36), db.ForeignKey("agent_runs.id"), nullable=False, index=True)
    step_name = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="running")
    input_json = db.Column(db.Text, nullable=True)
    output_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    agent_run = db.relationship("AgentRun", back_populates="steps")

    def to_dict(self):
        return {
            "agent_step_id": self.id,
            "step_name": self.step_name,
            "status": self.status,
            "input": _json_loads(self.input_json, None),
            "output": _json_loads(self.output_json, None),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AgentToolCall(db.Model):
    """Audit record for one controlled business tool call."""

    __tablename__ = "agent_tool_calls"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_run_id = db.Column(db.String(36), db.ForeignKey("agent_runs.id"), nullable=False, index=True)
    tool_name = db.Column(db.String(96), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="running")
    input_json = db.Column(db.Text, nullable=True)
    output_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    agent_run = db.relationship("AgentRun", back_populates="tool_calls")

    def to_dict(self):
        return {
            "agent_tool_call_id": self.id,
            "tool_name": self.tool_name,
            "status": self.status,
            "input": _json_loads(self.input_json, None),
            "output": _json_loads(self.output_json, None),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class GenerationJob(db.Model):
    """Per-slide generation job for preview, retry, and stale-result protection."""

    __tablename__ = "generation_jobs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey("projects.id"), nullable=False, index=True)
    page_id = db.Column(db.String(36), db.ForeignKey("pages.id"), nullable=False, index=True)
    slide_version_id = db.Column(db.String(36), db.ForeignKey("slide_versions.id"), nullable=False, index=True)
    visual_plan_version_id = db.Column(db.String(36), db.ForeignKey("page_visual_plans.id"), nullable=False, index=True)
    task_id = db.Column(db.String(36), db.ForeignKey("tasks.id"), nullable=True, index=True)
    job_type = db.Column(db.String(32), nullable=False, default="style_preview")
    idempotency_key = db.Column(db.String(128), nullable=False, index=True)
    input_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    page = db.relationship("Page")
    slide_version = db.relationship("SlideVersion")
    visual_plan = db.relationship("PageVisualPlan")
    task = db.relationship("Task")

    def to_dict(self):
        return {
            "generation_job_id": self.id,
            "project_id": self.project_id,
            "page_id": self.page_id,
            "slide_version_id": self.slide_version_id,
            "visual_plan_version_id": self.visual_plan_version_id,
            "task_id": self.task_id,
            "job_type": self.job_type,
            "idempotency_key": self.idempotency_key,
            "input_hash": self.input_hash,
            "status": self.status,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

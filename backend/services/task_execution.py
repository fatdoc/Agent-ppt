"""Cooperative task controls and explicit offline recovery (no startup DB writes)."""
from dataclasses import dataclass, field
from threading import Event
from time import monotonic
from contextvars import ContextVar
from contextlib import contextmanager

_EXECUTION = ContextVar('banana_task_execution', default=None)


def current_task_execution():
    return _EXECUTION.get()


@contextmanager
def task_execution_scope(control):
    token = _EXECUTION.set(control)
    try:
        yield control
    finally:
        _EXECUTION.reset(token)



class TaskCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class TaskExecutionContext:
    task_id: str
    user_id: str | None
    project_id: str | None = None
    deadline: float | None = None
    cancel_event: Event = field(default_factory=Event, repr=False, compare=False)
    progress_callback: object = field(default=None, repr=False, compare=False)

    @property
    def tenant_id(self):
        return self.user_id

    def checkpoint(self, stage=None, completed=None, total=None):
        if self.cancel_event.is_set():
            raise TaskCancelled('Task cancelled')
        if self.deadline is not None and monotonic() >= self.deadline:
            raise TimeoutError('Task deadline exceeded')
        if stage is not None and self.progress_callback is not None:
            self.progress_callback(stage=stage, completed=completed, total=total)


def fail_interrupted_tasks(task_ids, *, workers_stopped=False):
    """Offline recovery. Caller must guarantee all workers are stopped and backup verified.

    Status + reservation release commit atomically. No replay under fresh credentials.
    Repeated recovery is a no-op; callers resubmit through the authenticated API.
    """
    if not workers_stopped:
        raise RuntimeError('Recovery requires exclusive offline ownership')
    from datetime import datetime
    from models import db, Task, PublicPptGeneration
    from services.credit_service import settle_task_credits
    recovered = []
    try:
        from sqlalchemy import or_
        ids = set(task_ids)
        generations = PublicPptGeneration.query.filter(or_(
            PublicPptGeneration.id.in_(ids),
            PublicPptGeneration.description_task_id.in_(ids),
            PublicPptGeneration.image_task_id.in_(ids),
        )).all()
        for generation in generations:
            if generation.status in {'QUEUED', 'PROCESSING'}:
                ids.update((generation.description_task_id, generation.image_task_id))
                generation.status = 'FAILED'
                generation.current_stage = 'failed'
                generation.error_message = 'WORKER_RESTARTED: resubmit explicitly'
                generation.completed_at = datetime.utcnow()
                if generation.project:
                    generation.project.status = 'FAILED'
        for task_id in sorted(ids):
            task = db.session.get(Task, task_id)
            if task is None or task.status not in {'PENDING', 'PROCESSING', 'RUNNING'}:
                continue
            task.status = 'FAILED'
            task.error_message = 'WORKER_RESTARTED: configuration snapshot lost; resubmit explicitly'
            task.completed_at = datetime.utcnow()
            settle_task_credits(task.id, force_release=True)
            recovered.append(task.id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return recovered


def register_recovery_command(app):
    import click
    @app.cli.command('recover-interrupted-tasks')
    @click.argument('task_ids', nargs=-1, required=True)
    @click.option('--workers-stopped-and-backup-verified', is_flag=True)
    def recover(task_ids, workers_stopped_and_backup_verified):
        """Fail named interrupted tasks and release reservations after offline backup."""
        if not workers_stopped_and_backup_verified:
            raise click.ClickException('Stop all workers and verify backup/restore before recovery')
        recovered = fail_interrupted_tasks(task_ids, workers_stopped=True)
        click.echo(f'Recovered {len(recovered)} interrupted tasks')

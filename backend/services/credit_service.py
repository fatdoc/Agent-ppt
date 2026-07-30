"""Credit estimation, reservation, and settlement."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from models import CreditAccount, CreditLedger, Page, Project, Task, db


class InsufficientCredits(Exception):
    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(f"积分不足：需要 {required}，当前可用 {available}")


@dataclass(frozen=True)
class CreditEstimate:
    operation: str
    amount: int
    details: dict[str, Any]

    def to_dict(self):
        return {
            'operation': self.operation,
            'amount': self.amount,
            'details': self.details,
        }


def credit_enabled() -> bool:
    return os.getenv('CREDIT_ENABLED', 'true').strip().lower() not in {'0', 'false', 'no', 'off'}


def initial_balance() -> int:
    return max(0, int(os.getenv('CREDIT_INITIAL_BALANCE', '3000')))


def get_or_create_account(user_id: str) -> CreditAccount:
    account = CreditAccount.query.get(user_id)
    if account:
        return account

    amount = initial_balance()
    account = CreditAccount(
        user_id=user_id,
        balance=amount,
        reserved_balance=0,
        lifetime_credited=amount,
        lifetime_spent=0,
    )
    db.session.add(account)
    db.session.flush()
    if amount:
        _add_ledger(
            account,
            entry_type='grant',
            operation='initial_grant',
            amount=amount,
            metadata={'reason': 'initial_balance'},
        )
    return account


def account_payload(user_id: str, recent_limit: int = 20) -> dict[str, Any]:
    account = get_or_create_account(user_id)
    entries = (
        CreditLedger.query
        .filter_by(user_id=user_id)
        .order_by(CreditLedger.created_at.desc())
        .limit(recent_limit)
        .all()
    )
    return {
        'account': account.to_dict(),
        'recent_entries': [entry.to_dict() for entry in entries],
        'pricing': pricing_rules(),
    }


def pricing_rules() -> dict[str, Any]:
    return {
        'unit': 'credits',
        'currency_hint': '100 credits ~= 1 CNY',
        'rules': {
            'outline': '20 + 3/page',
            'outline_and_descriptions': '20 + 8/page',
            'descriptions': '10 + 8/page',
            'page_description': '8/page',
            'images': '100/page',
            'image_edit': '120/page',
            'material_image': '100/image',
            'editable_export': '30 + 80/page',
            'ppt_to_ppt': '80 + 5/reference_page + 15/target_page',
        },
    }


def estimate_operation(
    operation: str,
    *,
    page_count: int | None = None,
    reference_page_count: int | None = None,
    target_page_count: int | None = None,
) -> CreditEstimate:
    pages = max(0, int(page_count or 0))
    refs = max(0, int(reference_page_count or 0))
    targets = max(0, int(target_page_count or pages or refs or 0))

    if operation == 'outline':
        amount = 20 + 3 * max(1, pages)
    elif operation in {'outline_and_descriptions', 'from_description', 'no_think'}:
        amount = 20 + 8 * max(1, pages)
    elif operation == 'descriptions':
        amount = 10 + 8 * max(1, pages)
    elif operation == 'page_description':
        amount = 8 * max(1, pages)
    elif operation == 'images':
        amount = 100 * max(1, pages)
    elif operation == 'image_edit':
        amount = 120 * max(1, pages)
    elif operation == 'material_image':
        amount = 100 * max(1, pages or 1)
    elif operation == 'editable_export':
        amount = 30 + 80 * max(1, pages)
    elif operation == 'ppt_to_ppt':
        amount = 80 + 5 * max(1, refs) + 15 * max(1, targets)
    else:
        amount = 0

    return CreditEstimate(
        operation=operation,
        amount=max(0, int(amount)),
        details={
            'page_count': pages,
            'reference_page_count': refs,
            'target_page_count': targets,
        },
    )


def estimate_project_pages(project: Project | None, default: int = 10) -> int:
    if not project:
        return default
    page_count = Page.query.filter_by(project_id=project.id).count()
    if page_count:
        return page_count
    for text in (project.outline_text, project.description_text, project.idea_prompt):
        guessed = estimate_page_count_from_text(text)
        if guessed:
            return guessed
    return default


def estimate_page_count_from_text(text: str | None, default: int | None = None) -> int | None:
    if not text:
        return default

    page_markers = re.findall(r'(?:第\s*)?(\d{1,3})\s*(?:页|頁)|(?:slide|page)\s*(\d{1,3})', text, re.IGNORECASE)
    marker_numbers = [int(a or b) for a, b in page_markers if (a or b)]
    if marker_numbers:
        return max(marker_numbers)

    count_hints = re.findall(r'(\d{1,3})\s*(?:页|頁|p|P|slides?|pages?)', text, re.IGNORECASE)
    if count_hints:
        return max(1, min(80, int(count_hints[-1])))

    return default


def estimate_selected_pages(project_id: str, page_ids: list[str] | None = None, default: int = 1) -> int:
    query = Page.query.filter_by(project_id=project_id)
    if page_ids:
        query = query.filter(Page.id.in_(page_ids))
    count = query.count()
    return count or default


def reserve_credits(
    *,
    user_id: str | None,
    amount: int,
    operation: str,
    project_id: str | None = None,
    task_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CreditLedger | None:
    if not credit_enabled() or not user_id or amount <= 0:
        return None

    account = get_or_create_account(user_id)
    if account.available_balance < amount:
        raise InsufficientCredits(amount, account.available_balance)

    account.reserved_balance += amount
    account.updated_at = datetime.utcnow()
    entry = _add_ledger(
        account,
        entry_type='reserve',
        operation=operation,
        amount=amount,
        project_id=project_id,
        task_id=task_id,
        metadata=metadata,
    )
    return entry


def ensure_credits_available(user_id: str | None, amount: int) -> None:
    if not credit_enabled() or not user_id or amount <= 0:
        return
    account = get_or_create_account(user_id)
    if account.available_balance < amount:
        raise InsufficientCredits(amount, account.available_balance)


def debit_credits_now(
    *,
    user_id: str | None,
    amount: int,
    operation: str,
    project_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CreditLedger | None:
    if not credit_enabled() or not user_id or amount <= 0:
        return None

    account = get_or_create_account(user_id)
    if account.available_balance < amount:
        raise InsufficientCredits(amount, account.available_balance)

    account.balance -= amount
    account.lifetime_spent += amount
    account.updated_at = datetime.utcnow()
    return _add_ledger(
        account,
        entry_type='debit',
        operation=operation,
        amount=-amount,
        project_id=project_id,
        metadata=metadata,
    )


def settle_task_credits(
    task_id: str,
    *,
    completed_units: int | None = None,
    total_units: int | None = None,
    force_release: bool = False,
) -> None:
    if not credit_enabled():
        return

    reserve = (
        CreditLedger.query
        .filter_by(task_id=task_id, entry_type='reserve')
        .order_by(CreditLedger.created_at.desc())
        .first()
    )
    if not reserve:
        return

    already_settled = (
        CreditLedger.query
        .filter(
            CreditLedger.task_id == task_id,
            CreditLedger.entry_type.in_(['debit', 'release']),
        )
        .first()
    )
    if already_settled:
        return

    account = get_or_create_account(reserve.user_id)
    reserved_amount = max(0, reserve.amount)
    account.reserved_balance = max(0, account.reserved_balance - reserved_amount)

    if force_release:
        debit_amount = 0
    elif completed_units is not None and total_units and total_units > 0:
        ratio = max(0.0, min(1.0, completed_units / total_units))
        debit_amount = int(round(reserved_amount * ratio))
    else:
        debit_amount = reserved_amount

    release_amount = reserved_amount - debit_amount
    if debit_amount > 0:
        account.balance -= debit_amount
        account.lifetime_spent += debit_amount
        _add_ledger(
            account,
            entry_type='debit',
            operation=reserve.operation,
            amount=-debit_amount,
            project_id=reserve.project_id,
            task_id=task_id,
            metadata={
                **reserve.get_metadata(),
                'reserved_amount': reserved_amount,
                'completed_units': completed_units,
                'total_units': total_units,
            },
        )
    if release_amount > 0:
        _add_ledger(
            account,
            entry_type='release',
            operation=reserve.operation,
            amount=release_amount,
            project_id=reserve.project_id,
            task_id=task_id,
            metadata={
                **reserve.get_metadata(),
                'reserved_amount': reserved_amount,
                'completed_units': completed_units,
                'total_units': total_units,
            },
        )
    account.updated_at = datetime.utcnow()


def attach_task_credit_progress(task: Task, estimate: CreditEstimate) -> None:
    progress = task.get_progress()
    progress['credit_estimate'] = estimate.to_dict()
    task.set_progress(progress)


def _add_ledger(
    account: CreditAccount,
    *,
    entry_type: str,
    operation: str,
    amount: int,
    project_id: str | None = None,
    task_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CreditLedger:
    entry = CreditLedger(
        user_id=account.user_id,
        task_id=task_id,
        project_id=project_id,
        entry_type=entry_type,
        operation=operation,
        amount=amount,
        balance_after=account.balance,
        reserved_after=account.reserved_balance,
    )
    entry.set_metadata(metadata or {})
    db.session.add(entry)
    return entry

# No Think Backend Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend support for `No Think PPT` as a low-description input mode that normalizes user options and generates outline plus descriptions by default.

**Architecture:** Add `NoThinkService` to translate sparse user input and option fields into a normalized `idea_prompt`. Let `create_project` accept `creation_type=no_think` and persist the normalized prompt. Reuse `InputGenerationService` from Phase 1 so `/generate/outline` generates `outline_and_descriptions` for no-think projects without a new frontend endpoint.

**Tech Stack:** Python, Flask, SQLAlchemy, pytest, existing `InputGenerationService`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/services/no_think_service.py` | Normalize low-description options into prompt context |
| Modify | `backend/services/__init__.py` | Export `NoThinkService` and `NoThinkOptions` |
| Modify | `backend/controllers/project_controller.py` | Accept `creation_type=no_think` and default no-think generation to outline plus descriptions |
| Create | `backend/tests/unit/test_no_think_service.py` | Unit tests for option normalization |
| Modify | `backend/tests/unit/test_api_project.py` | API regression tests for no-think project creation and generation dispatch |
| Modify | `docs/superpowers/progress/backend-generation-progress.md` | Record Phase 3 progress and verification |

---

## Task 1: NoThinkService

- [ ] Write failing tests for normalizing scenario, tone, density, page count, style template, and extra instruction.
- [ ] Implement `NoThinkOptions.from_dict()` and `NoThinkService.normalize_prompt()`.
- [ ] Run `uv run pytest backend/tests/unit/test_no_think_service.py -q`.

## Task 2: API Integration

- [ ] Add failing tests that `POST /api/projects` accepts `creation_type=no_think`.
- [ ] Add failing test that `/generate/outline` dispatches no-think as `input_kind=no_think` and `target_depth=outline_and_descriptions`.
- [ ] Update `project_controller.py`.
- [ ] Run `uv run pytest backend/tests/unit/test_api_project.py::TestNoThinkProject -q`.

## Task 3: Verification And Progress

- [ ] Run `uv run pytest backend/tests/unit/test_no_think_service.py backend/tests/unit/test_api_project.py backend/tests/unit/test_input_generation_service.py -q`.
- [ ] Run `uv run python -m py_compile backend/services/no_think_service.py backend/controllers/project_controller.py backend/services/__init__.py`.
- [ ] Update `docs/superpowers/progress/backend-generation-progress.md`.

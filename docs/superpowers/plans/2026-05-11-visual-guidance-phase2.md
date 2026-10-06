# Visual Guidance Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a visual guidance layer so image generation applies style sources in a deterministic priority order instead of mixing template style, page style, and extra requirements as equal instructions.

**Architecture:** Create `VisualGuidanceService` to classify global style, page notes, override permission, and reference-image roles. Thread the guidance into `AIService.generate_image_prompt()` and `get_image_generation_prompt()` as structured prompt blocks. Update batch and single-page image generation to stop appending `template_style` into `extra_requirements`, and let the new service build the layered guidance.

**Tech Stack:** Python, Flask, pytest, existing `AIService`, `Project`, and `TaskManager` image generation paths

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/services/visual_guidance_service.py` | Style policy, override keyword detection, guidance dict construction |
| Modify | `backend/services/__init__.py` | Export `VisualGuidanceService` |
| Modify | `backend/services/prompts.py` | Render visual guidance as structured prompt blocks |
| Modify | `backend/services/ai_service.py` | Accept optional `visual_guidance` and pass it to prompt builder |
| Modify | `backend/services/task_manager.py` | Build guidance for batch and single-page image generation |
| Modify | `backend/controllers/project_controller.py` | Stop merging `template_style` into `extra_requirements` before image tasks |
| Modify | `backend/controllers/page_controller.py` | Stop merging `template_style` into `extra_requirements` before single-page image tasks |
| Create | `backend/tests/unit/test_visual_guidance_service.py` | Unit tests for priority and override rules |
| Modify | `backend/tests/unit/test_image_prompt_ratio.py` | Prompt regression tests for guidance blocks and aspect ratio |

---

## Task 1: VisualGuidanceService

**Files:**
- Create: `backend/services/visual_guidance_service.py`
- Test: `backend/tests/unit/test_visual_guidance_service.py`

- [ ] Write tests for template-first priority, explicit page override keywords, and blueprint priority.
- [ ] Implement `VisualGuidanceService.build_visual_guidance(...)`.
- [ ] Run `uv run pytest backend/tests/unit/test_visual_guidance_service.py -q`.

## Task 2: Prompt Layering

**Files:**
- Modify: `backend/services/prompts.py`
- Modify: `backend/services/ai_service.py`
- Test: `backend/tests/unit/test_image_prompt_ratio.py`

- [ ] Add failing tests that assert `<global_visual_system>`, `<page_content>`, `<page_layout_notes>`, and `<style_conflict_rule>` appear when guidance is passed.
- [ ] Add `visual_guidance` parameter through `AIService.generate_image_prompt()` to `get_image_generation_prompt()`.
- [ ] Preserve existing aspect-ratio prompt behavior.
- [ ] Run `uv run pytest backend/tests/unit/test_image_prompt_ratio.py -q`.

## Task 3: Image Generation Integration

**Files:**
- Modify: `backend/services/task_manager.py`
- Modify: `backend/controllers/project_controller.py`
- Modify: `backend/controllers/page_controller.py`
- Test: focused unit tests from Tasks 1-2 plus py_compile

- [ ] In batch image tasks, build guidance per page using the current `Project`, template image presence, page description, and `extra_requirements`.
- [ ] In single-page image tasks, build the same guidance.
- [ ] Keep reference image ordering unchanged for Phase 2 MVP: template image remains the main `ref_image_path`; page material images remain `additional_ref_images`.
- [ ] Stop appending `template_style` into `extra_requirements` in controllers.
- [ ] Run `uv run python -m py_compile backend/services/visual_guidance_service.py backend/services/task_manager.py backend/controllers/project_controller.py backend/controllers/page_controller.py backend/services/prompts.py backend/services/ai_service.py`.

## Task 4: Phase 2 Verification And Progress Update

**Files:**
- Modify: `docs/superpowers/progress/backend-generation-progress.md`

- [ ] Run `uv run pytest backend/tests/unit/test_visual_guidance_service.py backend/tests/unit/test_image_prompt_ratio.py backend/tests/unit/test_input_generation_service.py backend/tests/unit/test_api_project.py -q`.
- [ ] Update progress notes with completed tasks, verification evidence, and known integration-test caveat.

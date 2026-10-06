# Backend Generation Progress

## 2026-05-11

### Phase 1: Unified Input Generation

Status: implemented in branch `codex/backend-generation-phase1`.

Completed:
- Added `InputGenerationService` for outline/description validation, orchestration, and page persistence.
- Routed legacy non-streaming `generate_outline` and `generate_from_description` endpoints through the new service.
- Added unit coverage for validation, save modes, endpoint response compatibility, and status preservation.

Verification:
- `uv run pytest backend/tests/unit/test_input_generation_service.py backend/tests/unit/test_smart_merge.py backend/tests/unit/test_api_project.py -q` -> 31 passed.
- `uv run python -m py_compile backend/services/input_generation_service.py backend/controllers/project_controller.py backend/services/__init__.py` -> passed.
- Live service integration smoke reached image generation after outline/descriptions, then timed out in image generation. This failure is outside the Phase 1 text-generation path.

### Phase 2: Visual Guidance

Status: implemented and focused-regression verified.

Completed:
- Added `VisualGuidanceService`.
- Covered template-first, explicit page override, and blueprint-first priority rules.
- Added layered prompt blocks for `global_visual_system`, `page_content`, `page_layout_notes`, and `style_conflict_rule`.
- Passed visual guidance through `AIService.generate_image_prompt()` into `get_image_generation_prompt()`.
- Integrated guidance into batch and single-page image generation tasks.
- Stopped appending `template_style` into generic `extra_requirements` before image tasks.

Verification:
- `uv run pytest backend/tests/unit/test_visual_guidance_service.py -q` -> 3 passed.
- `uv run pytest backend/tests/unit/test_image_prompt_ratio.py -q` -> 4 passed.
- `uv run python -m py_compile backend/services/visual_guidance_service.py backend/services/task_manager.py backend/controllers/project_controller.py backend/controllers/page_controller.py backend/services/prompts.py backend/services/ai_service.py` -> passed.
- `uv run pytest backend/tests/unit/test_visual_guidance_service.py backend/tests/unit/test_image_prompt_ratio.py backend/tests/unit/test_input_generation_service.py backend/tests/unit/test_api_project.py -q` -> 32 passed.

### Phase 3: No Think PPT Backend

Status: implemented and focused-regression verified.

Completed:
- Add `NoThinkService` for low-description option normalization.
- Accept `creation_type=no_think` in project creation.
- Make no-think generation produce outline plus descriptions by default through `InputGenerationService`.

Verification:
- `uv run pytest backend/tests/unit/test_no_think_service.py -q` -> 2 passed.
- `uv run pytest backend/tests/unit/test_api_project.py::TestNoThinkProject -q` -> 2 passed.
- `uv run pytest backend/tests/unit/test_no_think_service.py backend/tests/unit/test_api_project.py backend/tests/unit/test_input_generation_service.py -q` -> 29 passed.
- `uv run python -m py_compile backend/services/no_think_service.py backend/controllers/project_controller.py backend/services/__init__.py` -> passed.

### Combined Focused Regression

Verification:
- `uv run pytest backend/tests/unit/test_input_generation_service.py backend/tests/unit/test_visual_guidance_service.py backend/tests/unit/test_no_think_service.py backend/tests/unit/test_image_prompt_ratio.py backend/tests/unit/test_api_project.py backend/tests/unit/test_smart_merge.py -q` -> 42 passed.
- `uv run python -m py_compile backend/services/input_generation_service.py backend/services/visual_guidance_service.py backend/services/no_think_service.py backend/services/task_manager.py backend/controllers/project_controller.py backend/controllers/page_controller.py backend/services/prompts.py backend/services/ai_service.py backend/services/__init__.py` -> passed.

## 2026-05-12

### Frontend Verification Entry: No Think PPT

Status: implemented and focused-regression verified.

Completed:
- Added frontend `NoThinkOptions` request typing and allowed `creation_type=no_think`.
- Updated `createProject()` to respect explicit `creation_type` and pass `no_think_options` to `/api/projects`.
- Updated `useProjectStore.initializeProject()` to create no-think projects and immediately call `/generate/outline`, which triggers backend outline plus descriptions generation for no-think projects.
- Added a `No Think PPT` mode on the home page with topic input plus scenario, color tone, density, page count, style direction, and extra instruction controls.
- No-think submissions now navigate directly to the detail editor after generation because backend produces page descriptions in the same flow.

Verification:
- `npm run test:run -- src/tests/pages/Home.noThink.test.tsx src/tests/api/createProject.test.ts src/tests/store/useProjectStore.initializeProject.test.ts` -> 9 passed.
- `npm run build` -> passed.
- `npm run build:check` -> failed on existing broad TypeScript strictness issues unrelated to no-think wiring, including missing `Material` exports and nullable API response typing in older frontend files.

Browser validation:
- Frontend dev server started at `http://127.0.0.1:3000/`.
- Browser plugin connection timed out twice before page inspection, so rendered screenshot validation is still pending.

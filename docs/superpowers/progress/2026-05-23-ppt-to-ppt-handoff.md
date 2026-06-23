# PPT to PPT 项目进度与交接文档

**日期:** 2026-05-23  
**计划文件:** `docs/superpowers/plans/2026-05-23-ppt-to-ppt.md`  
**规格文件:** `docs/superpowers/specs/2026-05-23-ppt-to-ppt-design.md`  
**当前状态:** Task 1-5 已完成并通过 review；Task 6 开始时遇到 subagent 使用额度限制，尚未实现。

---

## 1. 已完成 Task

### Task 1: Data Model And Project Storage

**状态:** 已完成，spec review 通过，code quality review 通过。  
**最终提交:** `958cb7ff2c7c48c7f7af41cf6340cdd47a971346`

**完成内容:**
- 新增 PPT-to-PPT 数据模型。
- 新增 `Project.ppt_to_ppt_blueprint` 存储字段和 JSON helper。
- 新增 Alembic migration。
- 修复 migration head，避免 Alembic 多头。
- 增强 `PptToPptOptions.from_form()` 对 `page_count` 的解析和校验。

**代码文件:**
- `backend/services/ppt_to_ppt/__init__.py`
- `backend/services/ppt_to_ppt/data_models.py`
- `backend/models/project.py`
- `backend/migrations/versions/019_add_ppt_to_ppt_blueprint.py`
- `backend/tests/unit/test_ppt_to_ppt_models.py`

**验证:**
- `uv run pytest backend/tests/unit/test_ppt_to_ppt_models.py -v`
- 结果: `10 passed`

---

### Task 2: Reference Deck Rendering Service

**状态:** 已完成，spec review 通过，code quality review 通过。  
**最终提交:** `0873fd4e484f3cb313b3077771304547406db784`

**完成内容:**
- 新增 `ReferenceRenderer`。
- 支持参考文件校验、稳定路径保存、从路径复制参考文件。
- 支持 PDF 原样使用，PPT/PPTX 通过 LibreOffice 转 PDF。
- 支持 PyMuPDF 渲染 PDF 页面为 `reference_page_N.png`。
- 增加路径逃逸防护，避免不可信 `project_id` 写出 upload 根目录。
- 包装 LibreOffice/PyMuPDF 错误为可读 `ValueError`。

**代码文件:**
- `backend/services/ppt_to_ppt/reference_renderer.py`
- `backend/services/ppt_to_ppt/__init__.py`
- `backend/tests/unit/test_ppt_to_ppt_reference_renderer.py`

**验证:**
- `uv run pytest backend/tests/unit/test_ppt_to_ppt_reference_renderer.py -v`
- 结果: `8 passed`

---

### Task 3: Blueprint Extraction Service

**状态:** 已完成，spec review 通过，code quality review 通过。  
**最终提交:** `cd33beb`

**完成内容:**
- 新增 `BlueprintService`。
- 构建参考 PPT blueprint extraction prompt。
- 支持 AI strict JSON 解析为 `PptToPptBlueprint`。
- 支持 raw JSON、fenced JSON、带前后说明文本的 JSON 解析。
- 支持 fallback blueprint。
- 接入 `generate_layout_caption(str(image_path))`，将页面图片布局 caption 纳入 prompt。
- 增加 prompt 总预算、页面文本/布局 caption 截断。
- 增加 warning 日志，避免静默 fallback。

**代码文件:**
- `backend/services/ppt_to_ppt/blueprint_service.py`
- `backend/services/ppt_to_ppt/__init__.py`
- `backend/tests/unit/test_ppt_to_ppt_blueprint_service.py`

**验证:**
- `uv run pytest backend/tests/unit/test_ppt_to_ppt_blueprint_service.py -v`
- 结果: `8 passed`

---

### Task 4: Content Mapping And Page Generation Service

**状态:** 已完成，spec review 通过，code quality review 通过。  
**最终提交:** `f78d366`

**完成内容:**
- 新增 `PptToPptGenerationService` 和 `PptToPptGenerationResult`。
- 根据用户内容、blueprint、match strength、页数等生成 outline 与逐页描述。
- 在 prompt 中明确用户内容是 source of truth。
- 增加 prompt boundary：用户内容、额外要求、blueprint 都作为 data section，不得覆盖 JSON schema、安全边界和 source-of-truth 规则。
- 支持 tolerant JSON parsing。
- 支持 page pattern 按页映射，描述中追加：
  - `Reference Page Pattern`
  - `Reference Page Index`
  - `Layout`
  - `Content Pattern`
  - `Visual Elements`
  - `Style Guidance`
- 修复 AI 将 `points` 返回为字符串时被拆成字符列表的问题。
- 补充 package root export 测试。

**代码文件:**
- `backend/services/ppt_to_ppt/generation_service.py`
- `backend/services/ppt_to_ppt/__init__.py`
- `backend/tests/unit/test_ppt_to_ppt_generation_service.py`

**验证:**
- `uv run pytest backend/tests/unit/test_ppt_to_ppt_generation_service.py -v`
- 结果: `9 passed`

---

### Task 5: Async Task Orchestration

**状态:** 已完成，spec review 通过，code quality review 通过。  
**最终提交:** `1d511ab`

**完成内容:**
- 在 `task_manager.py` 中新增 `process_ppt_to_ppt_task(...)`。
- 串联完整后台流程：
  1. 校验 options。
  2. 渲染参考文件。
  3. 提取 blueprint。
  4. 存储 blueprint、全局风格、画面比例。
  5. 根据用户内容生成 outline 和 page descriptions。
  6. 替换旧 pages。
  7. 创建新 pages。
  8. 更新 project/task 状态。
- 失败时 rollback，task 标记为 `FAILED`，project 回到 `DRAFT`。
- 修复空 `result.pages` 被误标记成功的问题。
- 失败 progress 标记为 `current_step: "failed"`。

**代码文件:**
- `backend/services/task_manager.py`
- `backend/tests/unit/test_ppt_to_ppt_task.py`

**验证:**
- `uv run pytest backend/tests/unit/test_ppt_to_ppt_task.py -v`
- 结果: `3 passed`

**注意:**
- `backend/services/task_manager.py` 在本轮任务开始前已有其他未提交改动。Task 5 的实现者只提交了本任务相关 diff，没有回滚其他改动。

---

## 2. 当前遇到的问题

### 2.1 Subagent 使用额度限制

执行 Task 6 时，subagent 启动失败：

```text
You've hit your usage limit. Upgrade to Pro, visit usage settings, or try again at 5:30 PM.
```

因此 Task 6 未开始实现。

### 2.2 工作区存在大量既有未提交改动

当前工作区在本轮 PPT-to-PPT 任务之前就存在较多 dirty files。后续继续时需要注意：

- 不要 `git reset --hard`。
- 不要回滚非本任务文件。
- 每个 Task 仍应只提交自己的 owned files。
- 如果某个文件已有非本任务改动，先查看 diff，再在现有内容上叠加改动。

### 2.3 Task 5 的一个非阻塞质量备注

Code review 提到：如果 blueprint extraction 已提交 metadata，随后 generation 失败，`ppt_to_ppt_blueprint`、`template_style`、`image_aspect_ratio` 可能保留在失败项目上。当前不阻塞，因为 task 会失败、pages 会保留/回滚、project 回到 `DRAFT`。如果以后想让失败完全无副作用，可以将 metadata commit 延后到 generation 成功之后。

---

## 3. 下一步计划

### 下一步 1: Task 6 Backend API Endpoint

**目标:** 新增 `/api/projects/ppt-to-ppt` multipart endpoint。

**需要创建/修改:**
- `backend/controllers/ppt_to_ppt_controller.py`
- `backend/app.py`
- `backend/controllers/project_controller.py`
- `backend/tests/unit/test_ppt_to_ppt_controller.py`

**实现重点:**
- 校验 `reference_file` 和 `content`。
- 解析 `PptToPptOptions`。
- 用 `ReferenceRenderer.validate_reference_file()` 校验文件类型。
- 创建 `Project(creation_type="ppt_to_ppt")`。
- 保存上传文件到临时路径。
- 创建 `Task(task_type="PPT_TO_PPT_ANALYSIS")`。
- 调用 `task_manager.submit_task(process_ppt_to_ppt_task, ...)`。
- 注册 `ppt_to_ppt_bp`。
- 让 central project creation validation 接受 `ppt_to_ppt`。

**建议验证:**
- `uv run pytest backend/tests/unit/test_ppt_to_ppt_controller.py -v`

---

### 下一步 2: Task 7 Visual Guidance Integration

**目标:** 图片生成时优先使用 PPT-to-PPT blueprint 作为视觉指导。

**需要修改:**
- `backend/services/visual_guidance_service.py`
- `backend/tests/unit/test_visual_guidance_service.py`

**实现重点:**
- 如果 project 有 `get_ppt_to_ppt_blueprint()` 且返回内容，则优先使用 blueprint guidance。
- 匹配 page description 中的 `Reference Page Index`。
- 输出 `style_priority = "ppt_to_ppt_blueprint_first"`。
- 输出 `reference_images.blueprint_layout_reference = "primary"`。

**建议验证:**
- `uv run pytest backend/tests/unit/test_visual_guidance_service.py -v`

---

### 下一步 3: Task 8 Frontend API And Home Page Entry

**目标:** 首页新增「借鉴优秀 PPT 生成」入口和表单。

**需要修改:**
- `frontend/src/api/endpoints.ts`
- `frontend/src/pages/Home.tsx`
- `frontend/src/tests/pages/Home.pptToPpt.test.tsx`

**实现重点:**
- 新增 `createPptToPptProject()`。
- 新增 `ppt_to_ppt` tab。
- 上传参考 PPT/PDF。
- 输入用户内容。
- 选择 match strength。
- 可选页数和额外要求。
- submit 后跳转到 detail editor，并保存 `pptToPptTaskId`。

**建议验证:**
- `cd frontend && npm run test:run -- src/tests/pages/Home.pptToPpt.test.tsx`

---

### 下一步 4: Task 9 Integration Verification And Manual QA

**目标:** 集成验证和手工 QA。

**需要创建/修改:**
- `backend/tests/integration/test_ppt_to_ppt_flow.py`
- `docs/superpowers/progress/backend-generation-progress.md`

**建议验证:**
- 后端 PPT-to-PPT unit/integration tests。
- 前端 Home PPT-to-PPT tests。
- `python3 -m py_compile` 覆盖新增后端文件。
- 如环境允许，再跑 `npm run quick-check`。

---

## 4. 推荐恢复执行方式

如果 subagent 额度恢复，继续按 Subagent-Driven Development：

1. Task 6 implementer agent。
2. Task 6 spec reviewer agent。
3. Task 6 code quality reviewer agent。
4. Task 7 implementer/review。
5. Task 8 implementer/review。
6. Task 9 implementer/review。
7. 最终整体 code review。

如果额度未恢复，可以 inline 执行 Task 6，但仍保留两个 review checkpoint：

1. 实现 Task 6。
2. 自查 spec compliance。
3. 自查 code quality。
4. 跑 Task 6 测试。
5. 再进入 Task 7。

---

## 5. 快速命令清单

```bash
uv run pytest backend/tests/unit/test_ppt_to_ppt_models.py -v
uv run pytest backend/tests/unit/test_ppt_to_ppt_reference_renderer.py -v
uv run pytest backend/tests/unit/test_ppt_to_ppt_blueprint_service.py -v
uv run pytest backend/tests/unit/test_ppt_to_ppt_generation_service.py -v
uv run pytest backend/tests/unit/test_ppt_to_ppt_task.py -v
```

后续 Task 6 完成后应新增：

```bash
uv run pytest backend/tests/unit/test_ppt_to_ppt_controller.py -v
```

---

## 6. 当前完成度

按计划 9 个任务计算：

- 已完成: Task 1-5
- 未完成: Task 6-9
- 完成比例: 5/9

后端核心服务链路已经基本成型：

```text
data models
 -> reference renderer
 -> blueprint extraction
 -> generation service
 -> async task persistence
```

仍缺：

```text
API endpoint
 -> visual guidance integration
 -> frontend entry
 -> integration/manual QA
```

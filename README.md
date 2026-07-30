# 兰台 Harness PPT Agent

兰台是一个面向 PPT 生产交付的 Harness 工程。它不是单纯的“一句话生成 PPT”工具，而是把材料接入、结构规划、视觉计划、风格验证、批量生成和最终导出串成一条可检查、可编辑、可复用的生产链路。

本仓库早期基于 Banana Slides 工程演进，现在的主要目标是服务当前的 Harness / Agent 工作流：先把 PPT 变成可审查的计划，再进入图像生成和交付。

![Lantai Deck Agent](frontend/public/lantai-deck-agent-logo.png)

## 项目定位

传统 AI PPT 生成器通常直接从主题跳到成图，问题是中间过程不可控：结构是否合理、每页主张是否清楚、风格是否一致、失败页面如何重试，都很难管理。

兰台的核心思路是把 PPT 生产拆成几个明确阶段：

1. 材料接入：主题、大纲、逐页描述、PDF、PPTX、文档和参考图都可以作为输入。
2. 结构规划：生成 DeckPlan，明确目标受众、交付目的和每页 main message。
3. 视觉计划：生成 DeckVisualSystem 和 PageVisualPlan，把每页的 reader takeaway、构图、标签和负面约束结构化。
4. 风格验证：先生成少量验证页，确认视觉方向后再批量生成剩余页面。
5. 稳定交付：支持项目历史、用户登录、积分估算、PPTX/PDF 导出和后续编辑。

## 当前核心能力

### Harness Agent

Agent 模式是当前项目最重要的工作流。它通过 `/api/agent-mode` 创建一个可编辑的计划版本，而不是直接批量出图。

主要能力：

- 输入主题、受众、页数和风格描述。
- 生成结构化 DeckPlan。
- 生成 DeckVisualSystem。
- 为每一页生成 PageVisualPlan。
- 支持编辑页面标题、主张、reader takeaway 和构图描述。
- 支持锁定页面，避免后续覆盖。
- 支持先生成风格验证页，再确认批量生成剩余页面。
- 内置 Harness 场景包：`paper_operators`（纸片人）、`lecture_deck`（课程讲义）、`product_launch`（产品发布会）、`consulting_report`（咨询汇报）。

### Harness 场景包（结构与视觉解耦）

每个场景包由两层组成，产品层默认绑定、架构层解耦：

- **结构 Skill**：页面角色系统、叙事组织、构图骨架、素材策略和校验规则，对任何视觉来源都生效。
- **默认视觉 Skill**：色板、材质、画风、字体气质，仅在用户未指定视觉来源时生效。

视觉覆写规则（resolver 优先级）：用户模板图 > 用户风格文字 > 场景包默认视觉；外部风格 Skill 启用时锁定其他视觉来源。上传模板图会整体替换默认视觉，风格文字在默认视觉之上优先生效，页面结构与成图质量硬约束（4K、真实可读文字、无伪影乱码）始终保留。

场景包会为页面生成：

- `source_anchor` / `reader_takeaway`：本页叙事依据与读者收获。
- `page_role`：页面角色（如概念页、例题页、hero 产品页、结论页）。
- `composition`：与画风无关的构图骨架。
- `structure_prompt` / `style_prompt`：结构指令与默认视觉指令分离存储。
- `material_status`：产品发布会包在无真实产品图时标记 `concept_placeholder`（概念图占位，禁止虚构品牌标识）。
- `labels` / `negative_prompts`：中文短标签与负面约束。

`paper_operators` 的纸片人角色（牵线员、检视员、闸门员、权衡员等）在结构层是功能角色，默认视觉把它渲染成无脸折纸小人；替换视觉后角色叙事仍然保留。

### 混乱材料模式

首页的“混乱材料模式”面向用户只有材料、没有清晰 PPT 结构的场景。用户可以输入主题、场景、内容密度、页数和额外约束，系统会自动搭建结构、页面描述和视觉初稿。

### 借鉴生成和旧稿翻新

项目支持把已有 PDF/PPTX 接入生成链路：

- 借鉴生成：上传参考 PPT 或 PDF，再输入新内容，让系统学习结构、表达方式和视觉约束。
- 旧稿翻新：上传已有讲稿或旧版 PPT/PDF，解析后按 Harness 流程重新组织页面。

### 素材和文件解析

支持上传和解析多种参考文件：

- PDF
- PPT / PPTX
- DOC / DOCX
- XLS / XLSX / CSV
- TXT / Markdown
- 图片素材

文件解析可接入 MinerU，本地或云端均可配置。

### 用户、权限和积分

当前工程已经接入：

- 用户注册和登录。
- 项目归属隔离。
- 可选访问口令 `ACCESS_CODE`。
- 积分账户和余额接口。
- 操作前积分估算。
- 服务器托管模型配置 `SERVER_MANAGED_AI_CONFIG`。

### 导出能力

当前保留并扩展了原有导出链路：

- 导出 PDF。
- 导出 PPTX。
- 可编辑 PPTX 导出相关能力。
- 讲解视频导出相关能力。

## 技术栈

后端：

- Python 3.10+
- Flask
- Flask-SQLAlchemy
- Flask-Migrate / Alembic
- SQLite 默认数据库，可通过 `DATABASE_URL` 替换
- Google GenAI / OpenAI / Anthropic / LazyLLM provider 适配

前端：

- React 18
- TypeScript
- Vite
- Tailwind CSS
- Zustand
- Vitest

主要目录：

```text
backend/
  app.py                         Flask 入口
  controllers/                   API 控制器
  models/                        数据模型
  services/                      PPT 生成、Agent、Harness、积分、导出等服务
  migrations/                    Alembic 数据库迁移
  tests/                         后端单元测试

frontend/
  src/pages/Home.tsx             兰台首页和主要创建入口
  src/components/agent/          Harness Agent 面板
  src/api/endpoints.ts           前端 API 封装
  src/store/                     项目状态管理

login/                           独立登录页原型/设计稿工程
uploads/                         本地上传和生成文件目录，默认不提交
```

## 本地启动

### 1. 准备环境变量

在项目根目录创建 `.env`：

```bash
cp .env.example .env
```

至少配置一个模型 provider。

Gemini 示例：

```env
AI_PROVIDER_FORMAT=gemini
GOOGLE_API_KEY=your-api-key-here
GOOGLE_API_BASE=https://generativelanguage.googleapis.com
TEXT_MODEL=gemini-3-flash-preview
IMAGE_MODEL=gemini-3-pro-image-preview
```

OpenAI 兼容接口示例：

```env
AI_PROVIDER_FORMAT=openai
OPENAI_API_KEY=your-api-key-here
OPENAI_API_BASE=https://api.openai.com/v1
TEXT_MODEL=gpt-4o
IMAGE_MODEL=gpt-image-1
```

常用项目配置：

```env
BACKEND_PORT=5000
FRONTEND_PORT=3000
CORS_ORIGINS=*
SECRET_KEY=change-this-in-production

CREDIT_ENABLED=true
CREDIT_INITIAL_BALANCE=3000
SERVER_MANAGED_AI_CONFIG=true

OUTPUT_LANGUAGE=zh
```

如果需要上传 PDF/PPTX 并解析材料，可继续配置 MinerU：

```env
MINERU_PROVIDER=local
MINERU_LOCAL_API_BASE=http://127.0.0.1:7860
```

### 2. 启动后端

推荐在项目根目录创建虚拟环境并安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

执行数据库迁移并启动服务：

```bash
cd backend
flask --app app db upgrade
python app.py
```

默认后端地址：

```text
http://localhost:5000
```

健康检查：

```text
http://localhost:5000/health
```

### 3. 启动前端

新开一个终端：

```bash
cd frontend
pnpm install
pnpm dev
```

默认前端地址：

```text
http://localhost:3000
```

如果没有显式设置 `BACKEND_PORT` / `FRONTEND_PORT`，项目会根据 worktree 目录名自动计算稳定端口，避免多个 worktree 同时启动时冲突。

## 使用流程

### Harness Agent 流程

1. 打开首页，选择 `Harness Agent`。
2. 输入主题、受众、页数和风格。
3. 点击“生成 Agent 计划”。
4. 检查 DeckVisualSystem 和每页计划。
5. 必要时编辑页面主张、reader takeaway 或构图。
6. 点击“生成风格验证页”。
7. 确认风格后点击“确认风格，生成剩余页面”。
8. 打开项目继续预览、编辑和导出。

### 快速 Harness 流程

1. 打开首页，选择“混乱材料模式”。
2. 输入主题、使用场景、内容密度、页数和额外要求。
3. 选择风格模板或输入文字风格。
4. 创建项目并进入大纲、描述和图片生成流程。

### 参考文件流程

1. 上传 PDF、PPTX、DOCX、TXT、Markdown 等材料。
2. 等待解析完成。
3. 将解析后的材料关联到项目。
4. 使用借鉴生成、旧稿翻新或普通 Harness 模式生成页面。

## 主要 API

Agent Mode：

- `POST /api/agent-mode/plans` 创建 Agent 计划。
- `GET /api/agent-mode/projects/:project_id/deck-versions/:deck_version_id` 获取计划版本。
- `PUT /api/agent-mode/projects/:project_id/deck-versions/:deck_version_id/slides/:slide_version_id/content` 修改页面内容计划。
- `PUT /api/agent-mode/projects/:project_id/deck-versions/:deck_version_id/slides/:slide_version_id/visual-plan` 修改页面视觉计划。
- `POST /api/agent-mode/projects/:project_id/deck-versions/:deck_version_id/slides/:slide_version_id/lock` 锁定或解锁页面。
- `POST /api/agent-mode/projects/:project_id/deck-versions/:deck_version_id/style-preview` 生成风格验证页。
- `POST /api/agent-mode/projects/:project_id/deck-versions/:deck_version_id/generate-remaining` 批量生成剩余页面。

Credits：

- `GET /api/credits/me` 查询当前用户积分。
- `POST /api/credits/estimate` 估算操作消耗。

Projects：

- `POST /api/projects` 创建普通项目。
- `GET /api/projects` 查询项目列表。
- `GET /api/projects/:project_id` 查询项目详情。

## 测试和检查

后端测试：

```bash
pytest backend/tests
```

前端测试：

```bash
cd frontend
pnpm test:run
```

前端构建检查：

```bash
cd frontend
pnpm build:check
```

## 当前重点模块

与 Harness 工程关系最密切的代码：

- `backend/services/agent_mode_service.py`：Agent Mode v1 主流程。
- `backend/services/agent_mode_tools.py`：Agent 工具层，负责创建项目、页面和生成任务。
- `backend/services/agent_mode_schemas.py`：结构化计划校验。
- `backend/services/harness_skills/`：Harness 场景包（结构 Skill + 默认视觉 Skill + 注册表），内置 `paper_operators`、`lecture_deck`、`product_launch`、`consulting_report`。
- `backend/services/harness_generation_service.py`：普通生成流程中的 Harness 增强。
- `backend/controllers/agent_mode_controller.py`：Agent Mode API。
- `backend/controllers/credit_controller.py`：积分接口。
- `frontend/src/components/agent/AgentModePanel.tsx`：前端 Agent 工作台。
- `frontend/src/pages/Home.tsx`：兰台首页和创建入口。

## 生产部署提示

生产环境至少需要关注：

- 设置强随机 `SECRET_KEY`。
- 不要提交 `.env`。
- 如果启用访问口令，配置 `ACCESS_CODE`。
- 如果统一由服务器管理模型配置，保持 `SERVER_MANAGED_AI_CONFIG=true`。
- 根据并发和模型耗时调整 `MAX_DESCRIPTION_WORKERS` 和 `MAX_IMAGE_WORKERS`。
- 为 `uploads/`、数据库和导出文件配置持久化存储。
- 如果使用 SQLite，注意备份和并发写入限制；生产多用户场景建议切换到外部数据库。

## 许可证和来源说明

本仓库从 Banana Slides 代码基础演进而来，当前 README 以本项目的兰台 Harness PPT Agent 工程为准。原项目相关的演示链接、宣传案例和 Roadmap 已不再作为当前项目说明。

具体许可证以仓库中的 `LICENSE` 文件为准。

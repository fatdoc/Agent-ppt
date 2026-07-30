# 世职赛 PPT 平台重构审计

> 审计日期：2026-07-30
> 审计范围：`frontend/`、`backend/`、`UI/`、用户提供的两份世职赛模板

## 1. 当前技术结构

- 前端：React 18、TypeScript、Vite、React Router、Zustand。
- 后端：Flask、SQLAlchemy、异步任务管理器、多模型 Provider。
- 现有主流程：创建项目 → 生成/编辑大纲 → 生成页面描述 → 生成/编辑图片 → 预览 → 导出。
- 当前分支包含未提交的既有改动；本次重构必须增量集成，不能覆盖用户工作。

## 2. 可直接复用的底层能力

| 能力 | 现有证据 | 重构用途 |
|---|---|---|
| 项目创建、读取、更新、删除 | `project_controller.py` `/api/projects` | 统一 ProjectContext 的持久化主体 |
| 项目材料理解 | `/api/projects/understand`、`understand/stream` | 内容分析师、竞赛总策划 |
| 大纲生成与流式生成 | `/generate/outline`、`/generate/outline/stream` | 大纲架构师与模板驱动生成 |
| 页面描述与 AI 修改 | page/project generate/refine 接口 | 页面内容生成、评分整改 |
| 生图与图片编辑 | page generate/edit image 接口 | 素材生成师、在线编辑 |
| 素材生成、处理、上传、关联 | `material_controller.py` | 素材中心与项目资产 |
| 页面讲解稿 | page narration 与批量 narrations 接口 | 演讲稿助手 |
| PPTX、可编辑 PPTX、PDF、图片、视频 | `export_controller.py` | 交付工程师与导出中心 |
| 用户视觉模板 | `template_controller.py` | PPT 模板库 |
| 参考文件上传、解析、关联 | `reference_file_controller.py` | 上传资料步骤 |

结论：无需重写模型、生图、编辑和导出服务；新增业务层应编排现有接口。

## 3. 现有前端页面与差距

| 现有页面 | 当前职责 | 主要差距 |
|---|---|---|
| `Landing.tsx` | 产品入口 | 品牌仍为通用 Banana Slides 语义 |
| `Home.tsx` | 创建项目、多输入模式 | 未形成赛事驱动的 PPT 工作台 |
| `PptEditor.tsx` | 世职赛精准材料理解和结构化编辑 | 逻辑已偏世职赛，但缺少统一 CompetitionConfig 和 supportLevel |
| `OutlineEditor.tsx` | 大纲编辑、排序、导入导出、AI 修改 | 缺少模板中心、模板版本、评分映射和页面目的 |
| `DetailEditor.tsx` | 页面描述与图片生成/编辑 | 缺少全局业务布局和对象感知的数字员工入口 |
| `SlidePreview.tsx` | 预览与导出 | 导出能力未形成独立交付中心 |
| `History.tsx` | 历史项目 | 项目缺少赛事/主题筛选 |
| `Settings.tsx` | 模型与系统设置 | 尚无赛事、模板和数字员工配置入口 |

## 4. 数据模型差距

当前 `Project` 已具备生成模式、模板、页面和 `competition_project_spec` 的基础，但尚未形成以下统一领域对象：

- `CompetitionSupportLevel` 与 `CompetitionConfig`
- 跨页面稳定的 `CompetitionContext` / `ProjectContext`
- 可复用、可版本化的 `OutlineTemplate`
- 项目级 `ProjectAsset`
- 配置化 `DigitalEmployee`
- 可观察、可取消、可重试的 `AgentTask`

现有赛事理解数据只能作为项目内容规范，不能替代赛事目录与支持等级配置。

## 5. 用户提供模板审计

### 《世界职业院校技能大赛通用 PPT 模板与逐字稿模板》

- 明确用于总决赛/争夺赛类项目汇报。
- 含 39 页真实 PPT 大纲。
- 技能展示为主体，第 16–33 页覆盖核心技能链。
- 每个技能点强调“任务、难点、操作、标准、结果”。
- 五项评分维度均有明确页码映射。

### 《世界职业院校技能大赛通用逐字稿模板》

- 与 39 页 PPT 一一对应。
- 包含四名工程师的角色、交接、现场实操、异常处置和验收话术。
- 可生成页面绑定讲解稿，但【】占位内容必须由项目材料填充，不得臆造。
- 适合作为 `wvcc` 专属 narration profile，不适用于其他赛事。

## 6. 关键业务风险

1. **赛事逻辑散落**：现有 `PptEditor.tsx` 中直接使用世职赛语义，需迁移到配置与上下文。
2. **模板概念混用**：当前“模板”主要是视觉模板；必须新增独立大纲模板模型和路由。
3. **假交互风险**：数字员工必须映射现有真实接口，任务状态须来自实际 Promise/后端任务，不使用定时动画冒充执行。
4. **其他赛事数据越界**：仅 `wvcc` 可配置评分、案例、专属提示词与 39 页模板。
5. **39/38 页冲突**：UI 示例显示 38 页，真实用户模板为 39 页；以用户模板为权威。
6. **脏工作区冲突**：多处现有修改尚未提交；新增架构优先采用新文件和小范围接线。

## 7. 实施决策

- 新建 `frontend/src/platform/`，集中放置赛事、项目、模板、素材和数字员工业务配置。
- 使用 Context 承载当前项目业务上下文，Zustand 继续承载现有项目实体和生成状态。
- 新建统一 AppShell，旧页面逐步挂入，不中断现有生成链路。
- 大纲模板先建立可持久化前端仓库与系统模板，再增加后端模型/API，避免与视觉模板表混用。
- 数字员工使用固定工作流定义；每个步骤显式映射现有 endpoint，设置最大步骤数并允许取消/重试。
- 每阶段执行 `npm run build:check`，关键 API 变更补充后端测试。

## 8. 第一阶段结论

项目底层能力完整，重构重点是领域建模、项目上下文连续性、业务导航和现有服务编排。UI 参考可以映射到真实能力，无需以图片充当页面；新增的 39 页真实模板为世职赛 FULL 模式提供了可靠专属数据来源。

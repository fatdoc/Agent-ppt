# 窗口三：PPTist 在线编辑 MVP 验收记录

日期：2026-09-25；独立分支 `codex/pptist-editor-mvp-20260925`，基线 `2ce5463f8499707a5f02a63e410f042fa3e4c45c`。

交付结论：已实现可运行的结构化文档编辑、版本保存、冲突保护和确定性语义导出闭环；属于受限 MVP，不能表述为全部 PPTist 能力已上线。没有推送、合并、部署或迁移真实数据库，没有调用付费 Provider。

## 已实现

- 固定官方 PPTist 源码提交 `82ecf10040ca8da67832f173b58d3baf5da59887`，Vue 子应用独立构建，React 以 `/editor-app/` iframe 加载。协议验证来源、窗口、会话、版本、消息尺寸和序号；READY 重试直到开始加载，卸载清理监听。
- 已有语义文本、卡片形状、图片、SVG、表格和单层组合映射；文本编辑、移动缩放、组合/图层、已有授权图片替换。Unsupported 修改明确拒绝保存，原始来源及稳定 ID 保留。纯图片项目明确提示尚未结构化，不伪装成可编辑对象。
- 服务端编辑文档与不可变历史快照、CAS 版本冲突、单次保存串行、新编辑排队、失败草稿保留与下载、刷新恢复、历史版本恢复为新版本。
- 所有 editor API 复用认证/CSRF/项目所有权；迁移 031 接续 030。仅精确 editor 蓝图绑定空 Provider 快照，其他蓝图原样。此保证不涵盖现有 React AuthGuard 的非 editor API。
- 授权素材按内容哈希冻结，历史版本引用不覆盖；尺寸/路径/hash/SVG 检查。导出绑定不可变版本，复用 TaskManager、TaskExecutionContext 与 semantic export_jobs，取消检查及私有 staging 后原子发布。积分余额、预留及账本不变。
- 原图导出和非 editor Provider 流程保持现有入口；现有导出任务列表识别 semantic-editor。

## 验证证据

- 后端全量：599 passed、8 skipped（607 项；最终补丁后重跑 136.67 秒，1921 warnings）；最终日志 `outputs/pptist-qa/pptist-backend-final.log`。
- 编辑器专项：23 passed，包含适配器拒绝危险输入/不支持字段、元数据保留、CAS、恢复、鉴权/CSRF、素材历史、不可变导出、OAuth/工厂不调用及积分账户完全不变。
- React：16 文件、91 项测试通过，包含 iframe 协议和保存竞态；React TypeScript + 生产构建通过。
- Vue：干净 `npm ci --ignore-scripts`、vue-tsc、生产构建通过；Node v20.19.6，子应用 Vite 6.4.3。主 React 工具链未升级。
- 子应用 npm audit 全依赖及 `--omit=dev` 均 0 findings；原始 27 项详见依赖审计文档。这不是安全证明。
- 隔离 SQLite 迁移：空库→030→031、031→030→031；模型漂移为空，integrity/FK 检查通过。
- 浏览器 Chromium 使用隔离临时账户/数据库，子应用使用生产静态构建：中文正文编辑并服务端回读、表格单元格编辑、组合移动、已有图片替换再换回、刷新恢复、当前版本导出下载通过。
- 浏览器双窗口：窗口一保存“第一窗口保存版本”，窗口二保存收到 409，仍保留“第二窗口未保存草稿”，服务器内容未覆盖；截图 `conflict-retains-draft.png`。
- 浏览器断网编辑：失败后草稿保留，恢复网络手动保存并回读一致；历史恢复版本 1 后服务器新版本 7、iframe 内容一致。
- 中文 composition 生命周期测试：组合期间版本/服务端内容不变，compositionend 后保存完成。采用合成事件，不能等同真实 macOS 输入法验收。
- 实际下载 `editor-r8.pptx`：OOXML 结构检查通过；代表页 3 文本/1形状/1图片/1SVG/1组合，第二页原生表格。使用 Codex 捆绑 LibreOffice 无界面渲染，两页 PNG 目视检查中文和布局；临时字体配置修正本机渲染字体目录。没有操作用户 WPS。

## 复现

```sh
# 各依赖目录先按现有项目指引安装；不加载真实 .env
cd editor-pptist
npm ci --ignore-scripts
cd ..
node scripts/build_pptist_editor.mjs
cd frontend
npm run test:run
npm run build:check
cd ..
# 使用项目依赖齐备的 Python 环境
python -m pytest backend/tests -k pptist
python scripts/verify_pptist_migration.py
python scripts/verify_pptist_runtime.py --port 5191 --output /tmp/pptist-qa
```

隔离验收账户仅用于该临时服务：`editor-test` / `editor-test-only`，项目 `pptist-acceptance`。后端脚本清空继承配置、禁用 dotenv、临时 HOME/SQLite/uploads，并阻断向外 socket 连接。另开子应用本地 preview 5188、React dev 5190（BACKEND_PORT=5191），访问 `/project/pptist-acceptance/editor`。本地 preview 不是部署服务。

证据目录 `outputs/pptist-qa/` 被 gitignore 排除，包含截图、下载 PPTX、渲染结果和测试日志；无临时数据库和密钥。提交内保留复现脚本与文档。

## 明确未完成 / 风险

- 新建、复制、删除、重排页面暂禁用，等待与 Local Page 的事务同步；新元素创建也未开放。已有对象可删除。
- 没有新增文件上传 UI；图片替换限当前页已授权 raster 素材。自动图片转结构化/OCR、AI 候选版本 UI 未实现。
- 嵌套组合、原生 line、图片背景和其他超出语义 v1 的效果不支持；部分样式控件仍可见，但提交会明确拒绝。不宣称任意 PPTX 往返无损。
- 草稿仅内存保存；接受离开警告后会丢失未保存内容。冲突后可下载草稿，尚无自动合并 UI。
- 普通文本粘贴安全路径有实现，但没有完整浏览器剪贴板实测；撤销/重做触发过快捷键，未逐步断言版本/内容，不列为已完成验收。
- 真实 OS 中文输入法、WPS/PowerPoint 手工编辑回验、Docker 镜像构建/部署和线上数据迁移未验收。取消/超时采用协作检查，尚无完整浏览器故障矩阵。
- 上游 AGPL LICENSE 保留，商业授权由用户另行处理；没有以来源固定或 npm audit 替代许可/安全审查。
- 生产包有较大 chunk 警告；不阻塞当前验收，后续可独立拆包优化。

合入前先阅读 `PPTIST_INTEGRATION_CONTRACT.md`，备份编辑版本数据；031 downgrade 会删除本功能历史，不可直接在真实库尝试回滚。

## 本次临时服务与交接

工作区：`/Users/docfat/.codex/worktrees/e058/banana-slides`。审计复核时间 2026-09-25 23:50 +0800：在 `editor-pptist` 执行 `npm audit --json` 和 `npm audit --omit=dev --json`，均 total=0。

当前临时进程：React PID 27928 / 127.0.0.1:5190；Vue preview PID 32019（npm 父进程 31997）/ 127.0.0.1:5188；隔离 Python 子进程 32023（父进程 32022）/ 127.0.0.1:5191。PID 会失效，停止前用 `ps`、`lsof` 再确认本工作区和端口；本次可先 `kill -INT 32023` 让父进程回收临时目录，再 `kill 32019 31997 27928`。不得按通用 node/python 进程名批量终止。

启动命令（分别在三个终端，仓库根目录为起点）：

```sh
/Users/docfat/Desktop/work/Project/github/banana-slides/.venv/bin/python scripts/verify_pptist_runtime.py --port 5191 --output /tmp/pptist-qa
(cd editor-pptist && npm run preview -- --host 127.0.0.1 --port 5188 --strictPort)
(cd frontend && BACKEND_PORT=5191 FRONTEND_PORT=5190 npm run dev -- --host 127.0.0.1)
```

使用其他项目现有 Python 虚拟环境仅借用已安装依赖，没有修改其源码或数据。

固定证据绝对目录：`/Users/docfat/.codex/worktrees/e058/banana-slides/outputs/pptist-qa/`。
主要文件：`editor-representative.png`、`editor-table-export.png`、`editor-moved-group.png`、`conflict-retains-draft.png`、`editor-r8.pptx`、`structure-report.json`、`render-fixed/editor-r8.pdf`、`render-fixed/page-1.png`、`render-fixed/page-2.png`。根目录旧 render-1/2 和旧 PDF 是字体发现问题的诊断中间产物，最终查看 render-fixed。

相对基线变更摘要：独立引入 PPTist 源码和补丁；新增 editor API/模型/031 迁移/adapter/导出 worker/测试；React 新增编辑路由与预览按钮并复用导出任务列表；限定 app 蓝图 Provider 快照例外；新增共享消息协议、构建/隔离验证脚本和三份交接文档。语义核心未修改。

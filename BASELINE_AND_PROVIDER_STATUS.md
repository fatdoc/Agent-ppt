# Batch 02：稳定底座与 Provider 隔离

日期：2026-09-25。范围止于运行/测试基线、Provider 隔离和通用任务生命周期；未迁移 Template/Preview，未引入在线编辑器，未修改窗口二新增语义模型/构建器。

## 1. 现场基线与数据边界

- 共同集成基线：`bb3b2b300ef87aefbc3a0cbe8a871b54f5dd02c3`。由原统筹窗口及真正的“窗口二：语义对象模型与可编辑导出样板”通过任务通信确认。
- 原目录：`/Users/docfat/Desktop/work/Project/github/banana-slides`，分支 `codex/safety-export-recovery-20260908`；原 Codex worktree：`/Users/docfat/.codex/worktrees/9674/banana-slides`，detached HEAD。两处无 tracked 修改，`.playwright-cli/`、`outputs/` 原样保留。
- 本分支：`codex/batch02-provider-isolation`；独立目录 `/Users/docfat/.codex/worktrees/batch02-provider-isolation/banana-slides`。
- `origin`/`master` 指向二开 `fatdoc/Agent-ppt`；还存在以原上游 URL 为名称的 remote。本阶段未 fetch、未推送、未合并窗口二分支。
- 已检查适用父级/仓库 AGENTS.md；仅 `/Users/docfat/.codex/AGENTS.md` 存在且为空。
- 没有读取 `.env`，没有复制真实库、uploads、凭据。Python 复用原 checkout 的 venv；前端仅使用未提交的 node_modules 链接。所有新增测试/HTTP 验收使用独立数据库、HOME、上传目录及 fake/mock。

## 2. 实际服务与真实库：只读证据

- 监听端口及进程 cwd 检查未找到本项目运行中的 Flask/Vite 服务。3000/8000 属于 TinyRagProject，5000 属于 macOS ControlCenter，不能当作 Banana Slides 已启动。原仓库的其余 cwd 进程为编辑器/终端/Codex 工具，未见真实数据库打开句柄；这不是远端付费调用已结束的证明。
- 因未读取 `.env`，不宣称知道未启动服务的部署端口。隔离验收在系统分配的 `127.0.0.1` 临时端口启动真实线程 WSGI 服务，验收后关闭，仅关闭本脚本创建的服务。
- 真实库：`/Users/docfat/Desktop/work/Project/github/banana-slides/backend/instance/database.db`。只用 `mode=ro` + `PRAGMA query_only=ON` 连接。
- `integrity_check=ok`；外键违规 0；revision `030_batch01_safety_expand`；`projects.user_id IS NULL` 为 0。
- ORM 与真实库通过 Alembic `compare_metadata(compare_type=True)` 比较结果 `[]`，包括列/类型/索引/约束差异检查；从空库迁移至 head 的临时库同样为 `[]`，完整性正常、外键违规 0。
- 任务状态：COMPLETED 267、FAILED 49、PENDING 1、PROCESSING 1。未终结任务创建时间分别为 2026-06-29（AGENT_STYLE_PREVIEW）和 2026-08-31（GENERATE_IMAGES）。未修改任务、积分、文件或真实 schema，未擅自判定远端调用可取消。
- 真实 uploads 的默认代码路径为原仓库 `uploads/`；未重新挂载或复制。真实服务配置未验收。

## 3. 实现内容

### 配置与 Provider

- 删除启动时/请求中把用户 Settings 写入共享 app.config 的逻辑，删除 settings 更新/临时测试对共享配置和 `os.environ` 的写入。
- `ProviderConfigSnapshot` 为 frozen dataclass，值为复制后的只读 scalar mapping；repr 隐藏配置，禁止 pickle。捕获用户行是只读操作，缺失设置不会借用首个用户的设置。
- Local 现有租户边界是 `user_id`。`tenant_id` 仅为同一归属的接口别名，无新租户表或字段。
- `ProviderScopedConfig` 兼容现有 Provider 配置的 `[]`/`get`/`in` 消费点；ContextVar 快照只覆盖 Provider/runtime 键，底层 app.config 保留服务器默认值。请求退出后恢复；用户更新只影响下次捕获。
- Web Cookie/Bearer 认证及 Public API Key 认证之后分别绑定用户快照。后台不继承 Flask request/session 对象。
- AIService 每次新建，移除全局 AIService 单例。Provider 缓存按 app、tenant/user、配置版本、全部有效配置的进程私有 HMAC-SHA256 摘要隔离；不含明文密钥或 base URL。每类缓存最多 128 项，失败构造不入缓存；清缓存不改变正在运行服务持有的实例。
- 轮换配置改变版本/摘要，新请求不能命中旧配置。旧任务继续持有旧快照；若旧密钥被撤销则明确失败，不能静默换新密钥。旧实例仅保留在运行任务或有界内存缓存中，不落盘。
- LazyLLM 通过实例参数 `api_key=` 传递凭据，VLM 延迟初始化复用已捕获的 key；不再写共享 BANANA_* 环境变量。核查锁定版本 0.7.5 的 PyPI wheel 源码确认 OnlineChat/MultiModal 接受显式 api_key，未安装或调用真实厂商 SDK。[官方 API 文档](https://docs.lazyllm.ai/en/stable/API%20Reference/module/)
- OAuth 在捕获时解析/刷新并固定 access token，运行中不重新查询另一用户的 Settings；真实 OAuth 刷新与厂商调用未验收。
- 活跃凭据从日志/错误响应/Task 和 PublicGeneration 错误及 Task progress 中脱敏，未保存的临时测试配置在异常退出前脱敏。缓存诊断只报告数量。

### 任务生命周期

- `TaskManager.submit_task` 在提交时捕获快照，校验任务/公共生成任务的用户归属，拒绝同进程重复提交活动 task ID。
- `ContextThreadPoolExecutor` 将 Provider 快照及任务控制上下文传播给子线程；已替换通用任务、文件解析、旧导出及其 image_editability 子池的 executor 导入。普通文件异步解析线程也显式绑定快照。
- `TaskExecutionContext` 提供 task/user/project IDs、取消 Event、monotonic deadline 和阶段 callback；`checkpoint()` 为协作检查。老函数签名保持兼容，新导出 runner 主动调用 checkpoint。不会强行终止正在进行的 Provider HTTP 调用；未插入 checkpoint 的旧任务仅有提交前检查。
- 未捕获的任务异常标记失败并释放预留积分；沿用已有幂等结算机制。业务函数已捕获的失败继续由其既有状态/结算路径处理。
- Task/公共生成记录持久化业务状态与 owner IDs；凭据/快照/内存 callback 不放普通 JSON、页面数据或任务记录。没有新数据库迁移。
- **重启不自动重放**：快照随进程消失。维护命令 `flask recover-interrupted-tasks` 仅在明确独占离线且备份恢复验证完成后，处理指定任务或 PublicGeneration ID：标 FAILED、释放未结算预留，公共生成的未完成两阶段一起收敛；重复执行不重复退款。之后通过认证请求显式重新提交，捕获当前配置。既有公共 API 的同一幂等键继续返回原失败任务，需要新的幂等键提交新任务。
- 真实库两条历史未终结任务尚未执行恢复；没有凭时间戳自动清理，也没有启动新进程去抢占旧任务。

## 4. 验证与证据层级

历史记录的 523 passed / 8 skipped、Vitest 87 仅作为线索。本次重新导出 `bb3b2b30` 到临时目录并使用净化环境测试：518 passed / 13 skipped；其中 5 项因净化 PATH 没有 ffmpeg 跳过，已补跑原基线 TTS 测试。最终分支验证结果见本节结尾。

可复现命令（从本 worktree 根目录；`PY` 为带项目依赖的 Python）：

```sh
PY=/Users/docfat/Desktop/work/Project/github/banana-slides/.venv/bin/python
"$PY" scripts/verify_isolated.py backend
"$PY" scripts/verify_isolated.py runtime
cd frontend
npm run test:run -- --maxWorkers=1 --minWorkers=1
npm run build:check
```

`verify_isolated.py` 使用环境白名单，不传入账户凭据，强制 `LOAD_DOTENV=false`，自动创建/销毁 DB、HOME、uploads。pytest 默认拦截真实网络连接，防止 mock 漏接触发付费调用。前端 worktree 无 `.env`。

覆盖：A/B 顺序与并发、后台与前台设置轮换、嵌套池、配置/用户/版本独立缓存隔离、初始化失败重试、固定配置重试、LazyLLM 显式注入、配置/错误脱敏、Public API 两阶段恢复、取消/超时/阶段回调、重复提交，以及既有 Auth/Credit/Public API/Tenant/文件访问/数据库备份恢复/旧导出回归。

- Provider 专项：19 passed（18 项新增 + 1 项改造原单例测试）。
- HTTP：health；A/B 顺序 4 次、并发 2 次；Cookie/CSRF；跨用户项目 404；Public API Key 200/401 均通过。真实 HTTP + fake Provider，**不是生产库/真实付费模型验收**。
- Vitest：14 files / 87 passed。
- TypeScript + Vite 生产构建：通过；仍有原有 >500 KB bundle 提示，本阶段未扩展到打包重构。
- Alembic：单 head `030_batch01_safety_expand`；空库 upgrade head 成功；真实/临时库 schema diff 均 `[]`。
- 后端最终全量：**541 passed / 8 skipped**，549 项收集；8 项为要求真实服务/真实 Provider 的测试及提示项，默认不调用付费模型。最后完整运行使用收集前网络隔离（而非只在 fixture 阶段阻断）。
- 原基线补跑 TTS：50 passed；包含此前因 PATH 中缺少 ffmpeg 跳过的 5 项。

## 5. 恢复运行与回滚

1. 先在本 worktree 执行上述隔离验收；核对生产服务所属 checkout/启动入口/端口，由运维以已有安全方式注入配置，禁止把 `.env`/凭据放入提交或命令日志。
2. 恢复真实服务前确认历史付费调用/所有 worker 状态。若需要写真实库：使用 `scripts/db_safety.py backup` 创建 SQLite 一致性备份及 manifest，在临时目的地用 `restore` 演练并比对完整性；再核对 uploads 备份。现有备份/恢复自动测试只证明临时库机制，不替代真实备份演练。
3. 确保独占离线，显式指定真实 `DATABASE_URL`，使用 `python -m flask --app app recover-interrupted-tasks <已核实任务ID...> --workers-stopped-and-backup-verified` 回收确认中断的任务。该确认标志是运维前提，**不是程序自动证明其他主机 worker 已停止**。先检查输出/预留积分，再启动服务；本阶段未执行此真实写操作。
4. 用指定账户检查 health、登录 Cookie/CSRF、自己的项目与文件、积分账户、Public API Key。真 Provider 的可用性另行验收，不能用 fake 结果代替。
5. 代码回滚可切回 `bb3b2b30` 或 revert 本批次提交；本批次无 schema 迁移，因此无需降级 schema。先等活动任务结束再切换 worker。若后续执行了真实恢复命令，只有停服并采用已验证的 db_safety restore 及隔离旧文件流程才能回滚数据；不要直接覆盖 WAL 数据库。

## 6. 多用户门禁与窗口二

**SINGLE_USER_MODE 门禁未解除、相关配置未修改。** 源码/fake 并发、业务回归、隔离 HTTP 的门禁通过后，仍须完成生产真实部署验收、历史未终结任务与积分预留核对、真实备份恢复演练、受控真实 Provider/OAuth 验证。不能仅凭测试绿灯开放多用户。

已与真正窗口二交换接口和文件归属；窗口二回传提交 `9d96ff075a1ff2fb386445511d548062efd8a2b3`（`codex/semantic-editable-export`），其 45 项测试/样本渲染是对方报告，未在本分支合并复测。本阶段不宣称双方已合并或完成集成。可复制接口、示例、最终提交查询方式见 `PROVIDER_INTERFACE_HANDOFF.md`。

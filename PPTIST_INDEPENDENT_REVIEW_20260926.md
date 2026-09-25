# PPTist MVP 独立审查与合入验收

日期：2026-09-26（Asia/Shanghai）。结论：下述两个阻塞问题已修复，受限 MVP 可合入现有集成分支。不是生产部署、真实数据库迁移或完整 PPTX 无损编辑验收。

## 基线与范围

- 目标：`codex/integration-provider-semantic-20260925`，合入前 `2ce5463f8499707a5f02a63e410f042fa3e4c45c`。
- 来源：`codex/pptist-editor-mvp-20260925`，最终审查 SHA `12be3646027c1188d9cad59fa958980e3e755243`。
- 原 MVP：`c092836f4c6af01187bdf851545a61e3815d4685`；事务修复：`6599479291230f82cedc9ac1357e001461bfb30c`；状态修复：`12be3646027c1188d9cad59fa958980e3e755243`。
- 非快进合并保留来源历史。仅推送集成分支，不修改远端默认分支，不发布服务。
- 独立回归在 integration-provider-semantic 工作树执行；浏览器访问已冻结、与合并结果相同的 e058 源码及其 Vue 生产静态构建。
- 临时账户、SQLite 和 uploads；后端禁止外网连接，不读取用户 `.env`，不触碰真实数据，不调用付费模型。

## 代码审查发现及修复

| 级别 | 问题与证据 | 处理与验证 |
| --- | --- | --- |
| P1 | `EditorDocument/EditorRevision` 的限制性 FK 未进入原项目删除事务；原 `delete_project` 在数据库提交前删除文件，可能出现删除失败却丢失文件 | `65994792`：同事务删除获授权项目的编辑历史；提交成功后才清理文件。新增跨用户/相邻项目/FK/提交失败回滚测试，修复前失败、修复后通过 |
| P1 | `PptistEditor.tsx` 保存 ACK 未更新重载快照；重试可加载旧正文并带最新 revision；复用路由可能串用上一项目 refs | `12be3646`：ACK 更新已确认快照，独立保留较新草稿；按 project/fixture 建立会话 key，卸载失效旧异步回包。新增两个回归测试，修复前失败、修复后通过 |

另外检查：editor 路由认证、CSRF、项目归属、历史素材授权、CAS 与不可变导出版本、Provider 例外的蓝图边界、迁移谱系、协议来源/窗口/session、Docker/Nginx 构建配置。当前审查范围内无剩余阻塞发现；不等同完整安全审计。

## 合并树独立自动验证

| 检查 | 结果 |
| --- | --- |
| `python scripts/verify_isolated.py backend` | 601 passed，8 skipped，140.18 秒；跳过需真实服务、Codex 或付费 Provider 的测试；1943 warnings，不能表述为零警告 |
| `npm run test:run -- --maxWorkers=1 --minWorkers=1` | 16 文件、93 测试全部通过 |
| `node scripts/build_pptist_editor.mjs` | vue-tsc + Vite 构建成功，编辑器产物复制到 React public |
| `npm run build:check`（复制后再次执行） | TypeScript + React 生产构建成功，`frontend/dist/editor-app/index.html` 存在 |
| `python scripts/verify_pptist_migration.py` | 临时库 empty→030→031、031→030→031；schema drift=[]；integrity/FK 检查通过 |
| 自有补丁 whitespace 检查 | `git diff --cached --check -- . ':!editor-pptist'` 通过；vendor 固定快照存在既有尾空格，未进行无关格式化 |

前端日志：`/tmp/pptist-independent-frontend.log`；迁移日志：`/tmp/pptist-independent-migration.log`。后端结果保留于本次任务终端输出。构建仍有大 chunk 提示。

## 独立真实浏览器验收

使用 Playwright CLI 操作独立 Edge 会话，访问 `http://127.0.0.1:5190/project/pptist-acceptance/editor`；临时后端 5191、编辑器静态预览 5188。不是 API-only 验收。

| 操作 | 实际观察 |
| --- | --- |
| 登录与加载 | 临时用户 UI 登录成功；结构化样例两页正常展示 |
| 中文改字与保存 | 原生编辑区输入中文，保存成功；本次为直接 Unicode 输入，不是 OS 输入法验收 |
| 撤销/重做 | 逐次断言内容：Meta+Z 撤销，Meta+Y 恢复；Meta+Shift+Z 并非当前上游实现的重做快捷键 |
| 剪贴板粘贴 | 真实 clipboard + Meta+V 粘贴“粘贴验收”；保存并刷新后文字仍在；测试后恢复原剪贴板，未输出其内容 |
| 双窗口冲突 | 主窗口保存成功；第二窗口提示“文档已由其他窗口保存”，提供下载未保存草稿；主窗口刷新后仍有“主窗”，没有“冲突草稿” |
| 历史恢复 | 恢复版本 1 生成新版本 15，iframe 恢复原始标题，不覆盖历史 |
| 断网恢复 | 浏览器 offline 后编辑，保存失败但草稿在；恢复网络并点击保存成功至版本 16 |
| 表格改字 | 双击表格进入编辑，首格改为“独立验收项”；保存、刷新、导出文件均保留 |
| 实际导出下载 | 点击导出并等待完成，实际浏览器下载 `editor-r20-e7588fc8-e853-4415-9e50-ce52a8c0daf4.pptx`；download.failure=null |
| 文件检查 | `unzip -t` 无错误；OOXML 包含原生 `a:tbl`、“独立验收项”、正文“断网恢复验证”、`p:grpSp`、独立 shape/picture，而非只核验任务状态 |
| 视觉检查 | 独立截图目视检查：工具栏、两页缩略图、卡片、中文正文和图片正常显示；未声称任意输入均无溢出 |

导出请求会先 flush 当前 iframe 内容并保存，因此测试中 revision 会继续增加；应按实际完成版本验收，不能假设 export 不产生版本。

第一次下载受离页提示/待完成导航干扰，不能计成功；重新加载已保存文档、再次导出后完成实际下载。两次中间截图超时，最终截图成功。断网试验产生预期网络错误；恢复并重新加载后为 0 console errors、2 warnings。

本次独立产物（不入 Git）：`output/playwright/editor-final.png`、`output/playwright/independent-editor.pptx`。下载文件 SHA-256：`78df8e1934ed7dd50d72ff6e3df0460e6a9d35e5476d71adf5bf861a39d00d49`。

## 尚未验收与后续项

- 这次未独立操作 WPS/PowerPoint、真实 macOS 中文 IME、Docker 镜像/线上部署；窗口三的 LibreOffice 渲染、组合移动及图片替换证据见 `PPTIST_MVP_STATUS.md`，不冒充本次独立复验。
- MVP 只接受已结构化语义文档；纯图片自动重建、任意 PPTX 无损导入、新增对象/页面、页面重排、新文件上传没有交付。图片替换仍限既有授权素材。
- 部分不支持的样式控件仍可见，提交时明确拒绝。建议下一批将控件能力与 adapter 同源，减少用户试错。
- 草稿目前在内存；冲突不自动合并。下载后新修改仍需重新导出；建议后续在下载链接明确显示所绑定版本，减少旧文件误解。
- 文件清理失败会留下隔离于已删除项目的孤儿文件，需要运维回收；不回滚已经提交的项目删除。
- 历史素材查询遍历版本、编辑器大包、macOS 快捷键提示、无变化导出仍增加 revision，列为后续性能/UX 优化，不在本批扩大重构。
- 导出 checkpoint 以任务为边界；新建导出任务不会自动复用上一任务 checkpoint。取消/超时没有完整浏览器故障矩阵。
- editor API 不构造 Provider 的专项断言通过，但该保证不扩大到原有 AuthGuard 等非 editor API。
- 生产启用前：一致性备份真实库及素材，复核 030→031，构建部署并做真实入口 smoke test。不得在真实库用 031 downgrade 作为无损回滚；它会删除编辑历史。当前保留单用户安全边界。

本报告补充原交付文档，不改写其历史测试数字。本次用户授权仅合入与推送，未执行生产发布。

# 可编辑转换：校验、诊断与失败页验证

2026-09-26，基于 `4e7c922c` 的修复。原始 31 页任务在第 2 页失败；旧实现没有保存该页响应或异常细节，因此不能证明它具体触发了哪一条规则，也不能用本次离线测试宣称原页已转换成功。

## 改动范围

- 只规范化可确定等价的表示：JSON Markdown fence/BOM，六位/三位十六进制与不透明 RGB 颜色，`box.width/height` → `w/h`，文本 run 的 `fontSize` → `size`，`roundedRect` → `roundRect`，空 groups → 空列表。
- 别名冲突、未知字段、JSON 重复键、非有限数字、坐标越界、重复图层、跨模块/不连续/嵌套组合、截图内重复文字、整页图片仍拒绝。不会猜坐标、重排图层、删除未知对象或修改正文来强行通过。
- 错误包含页码、字段路径及受控原因；任务 progress 新增 `failed_page_id/number`、`validation_errors` 和 `diagnostic_id`。JSON/字段错误不向浏览器返回模型正文、原始 input 或异常堆栈。
- 失败响应存放在项目私有 `.editor-generation-diagnostics/<随机编号>.json`：目录 0700、文件 0600，现有文件路由不提供该目录。当前快照凭据被脱敏，不记录请求头、密钥配置或 Provider 原始异常。响应最大 4 MiB，超限只保留诊断元数据；诊断写盘失败不能覆盖原始校验错误。文件包含用户文档内容，按私有项目数据备份和管理，不提交 Git。
- 新增诊断仅适用于修复之后的失败；不伪造旧任务缺失的响应。

## 单页验证

`POST /api/projects/<project_id>/editable-generation` 原 `{}` 仍执行整套转换；新增 `{ "mode": "validate_failed_page" }`。

失败页由服务端根据当前用户/项目的最近失败任务选择，不能传任意页 ID、路径或用户 ID。兼容旧任务 `正在转换第 N/M 页`；包装阶段失败不推测为某一页。

GET 返回 `validation_page_number` 和 `validation_credit_estimate`，不加载 Provider。前端单独确认后才提交。验证包括该页识别、语义对象、原生 PPTX 构建和结构检查；完成后 `validation_passed=true`，不会创建半套 editor document/revision，不自动继续其他页，不自动进入编辑器。当前活跃任务重复提交沿用同一个任务。

普通账号单页验证沿用一页转换规则（110 积分），失败释放预留，管理员免系统积分但模型调用可能收费。后续整套转换仍按整套积分计费，界面明确说明；成功页在同一配置快照范围内复用缓存，缓存命中不会重新识别。进程重启/配置更换可能改变 Provider scope，**不保证跨重启复用**，既有成功缓存文件不删除或覆盖。

## 离线复现（零模型调用）

```sh
python scripts/validate_editor_page.py \
  --image /absolute/path/page.png \
  --diagnostic /absolute/path/private-diagnostic.json \
  --output /tmp/new-single-page-check
```

也可用 `--response /path/response.json` 提供人工修正后的识别 JSON。输出目录必须不存在；诊断模式核对原图 SHA-256。只产生本地单页 PPTX、页面 JSON、素材和结构报告；不连接业务数据库、加载 `.env` 或调用 Provider。结构通过不等于渲染/Office 人工验收通过。

## 隔离浏览器验收

`scripts/verify_pptist_runtime.py --validation-failure --port 5196 --output /tmp/banana-validation-repair-qa` 创建两页人工样例，第二次模拟响应故意给错误颜色，后续返回合法格式。临时数据库/上传目录和账号，后端阻断外网。可验证完整失败、单页验证、继续整套转换的流程；这不是实际模型质量验收。

## 2026-09-26 验证与部署记录

- 后端全量：630 passed，8 skipped（含真实外部服务测试未运行）。
- 前端全量串行：101 passed / 17 files；首次并行运行有 3 个既有保存竞态测试失败，未修改这些测试，不将首次运行计为通过。
- TypeScript / Vite 生产构建通过；保留已有大 chunk 告警。
- 浏览器仅完成模拟第 2 页失败提示、诊断编号与单页确认弹窗检查。自动化会话重置后，按用户要求停止等待。单页成功后停留预览、整套完成后进入编辑器的真实浏览器端闭环未完成；对应离线测试已通过。未做 WPS/PowerPoint 操作验收，未调用真实付费 Provider。
- 已部署至日常服务 `http://localhost:3000`，后端 PID `83908`、端口 `5005`。健康检查正常，认证启用，未登录的转换接口返回 401；前端已提供新单页验证代码。
- 一致性数据库备份及成功页缓存副本：`/Users/docfat/Desktop/work/Project/github/banana-slides-backups/semantic-validation-repair-K2CZuzgK/`。完整 uploads 未重新复制；原文件保持原位。没有读取或备份 `.env`。
- 重启前后积分审计与成功页缓存哈希一致；原失败任务仍为 `FAILED / 正在转换第 2/31 页`，未代用户重试。维护脚本第一次因自身只读审计句柄中止，关闭句柄后完成备份与部署，没有强制杀进程。
- 部署时基于 `4e7c922c`，当时修复尚未提交或推送。用户刷新页面后手动确认“仅验证第 2 页”；该操作可能产生模型服务商费用，成功不代表整套 31 页均已通过。

## 2026-10-07 远端同步

本次将上述修复、离线工具、测试和本文档纳入提交，目标为 `origin/codex/safety-export-recovery-20260908`。不包含 `.env`、数据库、备份、uploads 或生成产物；不合并官方 Upstream，不重新部署服务，不调用付费模型。上述部署状态为 9 月 26 日记录，不代表本次重新验收运行状态；浏览器完整闭环与真实失败页结果仍未验证。

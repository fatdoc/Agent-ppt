# Provider 与语义导出集成记录

## 基线与范围

- 集成分支：`codex/integration-provider-semantic-20260925`。
- 共同基线：`bb3b2b300ef87aefbc3a0cbe8a871b54f5dd02c3`。
- Provider：`bf894d1e7a95e26f0f1ed1f495998c92e85db043`。
- 语义导出：`9d96ff075a1ff2fb386445511d548062efd8a2b3`。
- 独立 worktree 合并，保留双方提交历史，无文本冲突。不覆盖原工作目录或其未跟踪产物。
- 本批不更改数据库迁移、不读取用户 .env、不修改真实数据库/uploads、不启动正式服务、不解除单用户门禁。

## 合并后验证

- 后端全量：`python scripts/verify_isolated.py backend`，576 passed / 8 skipped，142.26 秒。8 项为真实服务/Provider 条件测试；1847 条 warning 未在本批清理，测试通过不代表无警告。
- 隔离 HTTP：`python scripts/verify_isolated.py runtime` 通过。临时数据库和 fake Provider；覆盖 A/B 顺序与并发、Cookie/CSRF、项目隔离及 Public API Key。
- 前端：`npm run test:run -- --maxWorkers=1 --minWorkers=1`，14 个文件、87 项通过。
- 构建：`npm run build:check` 通过。已有动态/静态混合导入和大于 500 KB chunk 警告仍存在。
- 使用原 checkout 已安装依赖，未执行依赖升级；集成目录无 .env。依赖链接和构建产物不提交。

## 能力边界

本批是两项底层交付的代码集成与回归，不是新导出 HTTP 端到端上线。语义导出仍需显式结构化/人工区域输入，经离线或服务层入口调用；未实现自动区域识别、网页入口、计费接线或在线保存。真实 Provider/OAuth、真实中断任务恢复及 WPS 交互验收未在本轮执行。

PPTist 已由用户确定为下一阶段在线编辑器，授权由用户联系作者处理。下一步是固定 PPTist 版本、编辑子应用与 React 宿主消息桥，以及统一语义模型双向适配；本批没有引入编辑器代码。

## 后续与回滚

真实库两条历史未终结任务按底座交付记录仍待单独核验；本批不执行恢复命令。Provider 的配置快照与语义 runner 的授权素材、取消和进度回调仍需在正式路由挂载时联合验收。

集成分支不替换原分支，原代码及数据保持不变。如后续部署，先等待活动任务结束再切换到已验证提交；本批没有 schema 变化，不需要数据库 downgrade。推送新分支不等于部署服务或合并默认分支。

# 给语义导出窗口的接口交接

共同基线：`bb3b2b300ef87aefbc3a0cbe8a871b54f5dd02c3`。
本分支：`codex/batch02-provider-isolation`。最终提交由 `git rev-parse codex/batch02-provider-isolation` 获取，并通过任务通信回传。

## 配置与身份

```python
from services.provider_config import capture_provider_snapshot, provider_snapshot_scope
from services.ai_service_manager import get_ai_service

# 在已认证且已校验项目所有权的请求内，提交前捕获。
snapshot = capture_provider_snapshot()
service = get_ai_service(snapshot=snapshot)
# 离线测试替身，不会创建真实 Provider：
fake_service = get_ai_service(snapshot=snapshot, factory=lambda snapshot: FakeProvider())
```

快照含 `user_id`、`tenant_id`（现有 user_id 的别名）、版本与隐藏凭据 mapping。不要 `dict(snapshot.values)` 落日志/任务 JSON/页面模型；不要持久化快照或 provider 实例。应用外使用必须显式传 snapshot，不能靠 worker 重新查询用户设置。`provider_snapshot_scope(snapshot)` 供直接调用既有工厂/配置读者的适配层使用。

## 后台任务与阶段回调

```python
from time import monotonic
from services.task_execution import TaskExecutionContext, current_task_execution
from services.task_manager import task_manager

control = TaskExecutionContext(
    task_id=task.id, user_id=task.user_id, project_id=task.project_id,
    deadline=monotonic() + 900,
    progress_callback=write_safe_stage_progress,
)

def worker(task_id, jobs, store, app):
    with app.app_context():
        execution = current_task_execution()
        def on_event(event):
            execution.checkpoint(
                stage=event['stage'], completed=None, total=None,
            )
            # 按需持久化安全的 page_id/stage/status/cache_hit；
            # failure.message 必须经过既有脱敏边界，禁止保存配置。
        execution.checkpoint()
        return export_jobs(jobs, store=store, mode='semantic', on_event=on_event)

task_manager.submit_task(task.id, worker, jobs, authorized_asset_store, app,
    provider_snapshot=snapshot, execution_context=control)
```

- `TaskExecutionContext` 的 user/project/task 与提交记录必须一致；tenant 仍为 user 归属。`AssetStore` 必须从已授权项目根构造，快照不是文件授权凭证。
- `checkpoint()` 检查 `cancel_event` 与 deadline，可传 `stage/completed/total`。取消设 `control.cancel_event.set()`。这是协作取消，不中断已发出的付费 HTTP 请求；runner 须在页/阶段边界主动检查。
- 新建线程池请使用 `ContextThreadPoolExecutor`，只传播快照/任务控制，不传播 request 或 DB session；数据库操作仍进入 app context。
- 保留同一个内存 snapshot 做失败重试；新提交可用新配置。Provider 缓存键包含 owner、版本及 secret digest，禁止借用原缓存对象手动替换密钥。
- 进程重启丢失快照：先独占离线、备份恢复验证，再显式恢复中断状态/释放预留，之后由认证请求新建任务。无明文凭据持久化，不自动拿当前 Settings 续跑旧任务。

## 共享文件与集成边界

- 窗口一拥有 provider_config、AIService/factories、app、认证积分边界、TaskManager/TaskExecution、必要迁移（本批无迁移）。
- `export_service.py` 仅 5 处 ThreadPoolExecutor 导入替换；`image_editability/service.py`、`hybrid_extractor.py` 同样仅替换池导入。未改导出签名/业务逻辑/公共 API 类型。
- 窗口二继续拥有新增 semantic_export 模型/runner/builder/测试；双方没有合并半成品。接入业务路由、计费估算和新模式 API 必须另行协商。
- 证明：隔离专项、实际本地 HTTP + fake、既有 Auth/Credit/Public API/文件/Tenant/旧导出回归；详见状态文档。真实 Provider、生产运行以及窗口二最终接口联合验收尚未完成。

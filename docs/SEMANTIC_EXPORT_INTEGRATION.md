# 窗口一集成说明

共同基线 `bb3b2b300ef87aefbc3a0cbe8a871b54f5dd02c3`；本分支 `codex/semantic-editable-export`。不要合并另一个工作区的未提交文件。本提交仅新增语义包、专属测试、样本脚本和文档，与窗口一的 executor/Provider 改动没有重叠。

## 调用方式

```python
from services.semantic_export import AssetStore, PageJob, export_jobs

# authenticated_user/project、root、cache_dir 来自服务器授权上下文。
store = AssetStore(project_root, user_id=user_id, project_id=project_id)
raw, report = export_jobs(
    jobs,
    store=store,
    checkpoint_dir=project_cache / 'semantic-v1',
    mode='semantic',
    on_event=on_event,
    check_cancelled=check_cancelled,
)
# 仅返回成功后，宿主以临时文件 + os.replace 发布到 exports。
# report[].structure='passed'；render/client 仍是 'not_run'。
```

PageJob：`id, source: Source, extraction_signature, organization_signature, correction_revision, extract(), organize(extraction)`。organize 返回可校验 Page dict。source 为 ID/revision/SHA256，必须与最终 Page 相同。已有准确内容直接复用；若传 EditableImage，用 from_editable_image 显式提供区域 ownership/styles/asset 映射。不要沿用旧导出失败后整页原图回退。

on_event 接收 `{page_id, stage, status, cache_hit?, error?}`；stage 为 extract/semantic/objects/acceptance；status 为 completed/failed。失败抛 SemanticExportFailure，`.errors` 包含页/阶段/原因，`.completed` 记录可恢复成功页，绝不返回半套文件。回调异常或 check_cancelled 异常转为 ExportInterrupted 并中止整次导出，不继续其他页面。取消是阶段间合作式检查，不承诺中断正在执行的第三方同步调用。

## 对窗口一已提供接口的适配（未合入对方分支）

窗口一通知接口为 ProviderConfigSnapshot / capture_provider_snapshot / provider_snapshot_scope / ContextThreadPoolExecutor；get_ai_service(snapshot=..., factory=...)；TaskManager.submit_task(..., provider_snapshot=..., execution_context=...)；worker 中 current_task_execution().checkpoint(stage=..., completed=..., total=...)。

建议由该窗口的 worker wrapper 在提交时捕获 snapshot，构造 PageJob 的 fake/真实提取闭包，语义包不接触凭据。

```python
control = current_task_execution()
progress = {'completed': 0}

def check_cancelled():
    if control:
        control.checkpoint()  # 依最终接口签名调整；本分支不依赖该模块。

def on_event(event):
    if event['status'] == 'completed':
        progress['completed'] += 1
    if control:
        control.checkpoint(stage=event['stage'],
                           completed=progress['completed'], total=4*len(jobs))
    # 另外将完整 event 持久化到已有进度结构，以保留失败页原因。
```

上面的集成片段为接口示意，未声称已验证另一分支最终签名。宿主须把结构通过与人工渲染/客户端验收状态分开，且不能复用当前旧 controller 的固定 Provider 创建和模型计费来收费纯手工 JSON 样本。公共 API/费用策略由窗口一拥有，本分支没有改这些文件。

## 集成验收与回滚

先 cherry-pick 本分支提交到窗口一已稳定且提交完的分支，运行文档中的 45 项隔离测试；再验证 fake task 的用户/项目 scope、取消、失败恢复和最终输出发布。不读取 .env，不连接真实数据库，不调用付费 Provider。HTTP 路由若要接入需显式 mode / feature flag，不能默认替换 legacy。

未部署，无迁移。不开启 adapter 即旧行为；若已集成可 revert 单个实现提交。完整历史项目迁移和在线编辑器均不在阶段一范围。

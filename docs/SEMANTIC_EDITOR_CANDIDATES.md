# 在线编辑器前置评估（2026-09-25）

本阶段只核对官方仓库、文档和当前提交，不安装、不接入编辑器。下面的能力是文档支持范围，不是 Banana Slides 样本的生产验收。

| 维度 | PPTist：浏览器演示对象编辑器 | ONLYOFFICE Docs：完整办公文档服务 |
|---|---|---|
| 许可证与商用 | 当前 AGPL-3.0；闭源方案需另行商业授权。旧 Apache 版本已停止维护，不能用旧许可推断当前版本 | Community 为 AGPL v3，Enterprise/Developer 为专有授权；版本、附加条款和集成范围需在采购/引入时核对 |
| 部署 | Vue 3/TypeScript 前端，业务后端、文件与租户权限需自己对接 | 独立 Document Server；文件存储、下载地址、保存回调、服务间鉴权由宿主提供 |
| React | 非原生 React 组件，建议独立微前端或 iframe，使用版本化消息协议 | 官方 React `DocumentEditor` 包；对象级 Automation API 仅 Developer 版，不应假定 Community 免费提供 |
| 中文排版 | 有富文本、行高、字间距等；中文断行、字体回退、输入法组合仍需实测 | 需要服务器与客户端字体策略；不能把 Office 兼容宣传当作本项目中文保真证明 |
| 分组 | 文档声明支持组合、图层、命名 | 文档明确支持组合、解组、整体移动和旋转 |
| 图片 | 裁切、替换、重置；需验证 crop 与核心模型的比例换算 | 图片插入、裁切；完整截图及 SVG 回退需用本阶段样本验收 |
| 表格 | 可编辑行列/合并/单元格样式；PPTX 往返的原生性待实测 | 原生表格编辑与格式化；复杂合并单元格不属于当前核心 v1 |
| 撤销重做 | 官方功能列表支持 | 办公编辑器支持；宿主语义历史不能与编辑器会话历史混为一谈 |
| 导入导出 | PPTX、JSON、自有格式等；官方明确不保证复杂内容完全保真 | PPTX/ODP/PDF 等文件边界；不能直接假定有完整的语义 JSON 双向映射 |
| 当前维护证据 | 官方最新提交 `82ecf10040ca8da67832f173b58d3baf5da59887`，2026-09-19 | 官方最新提交 `f580eb58439432310943ece02c9730c6a21365e7`，2026-07-22；发布列表可见 9.4.0 |

依据：[PPTist 官方仓库与商业说明](https://github.com/pipipi-pikachu/PPTist)、[ONLYOFFICE 仓库与版本区别](https://github.com/ONLYOFFICE/DocumentServer)、[React 集成与 Automation API 限制](https://api.onlyoffice.com/docs/docs-api/get-started/frontend-frameworks/react/)、[组合操作](https://helpcenter.onlyoffice.com/docs/userguides/presentation_editor/AlignArrangeObjects.aspx)、[图片](https://helpcenter.onlyoffice.com/docs/userguides/presentation_editor/InsertImages.aspx)、[表格](https://helpcenter.onlyoffice.com/docs/userguides/presentation_editor/InsertTables.aspx)、[导出格式](https://helpcenter.onlyoffice.com/docs/userguides/presentation_editor/SavePrintDownload.aspx)、[发布记录](https://github.com/ONLYOFFICE/DocumentServer/releases)。提交日期通过官方 GitHub commits API 核验。许可证判断以引入时锁定的版本与协议为准，本阶段没有购买或接受授权协议。

## 适配建议（工程判断）

若产品重点是“编辑 AI 重构的模块”，下一阶段优先验证 PPTist，前提是许可证路线可接受。它的对象能力更接近核心模型，但 Vue/React 隔离、文字布局差异、SVG 裁切、组合的子坐标和表格映射需要适配。官方 Demo 明确不是可直接运营的在线服务，不采用其展示作为验收。

若重点变成“在线编辑已有办公文件”，评估 ONLYOFFICE 独立服务更合适。它以文件为边界，保存回调返回的 PPTX 应当作为新的文档版本；在没有经过验证的对象导入器之前，不能把它静默转回核心模型，也不能宣称编辑后的语义来源、ID 和局部修正记录完整保留。

## 核心接口约束

`services.semantic_export.adapters.EditorAdapter` 预留 `to_editor(page)` / `from_editor(data, base=page)`。实现前要求：

- 核心 Page JSON 是持久化业务对象；候选编辑器 JSON 只在适配边界暂存，不作为项目主数据。
- 往返保持 source revision、page revision、稳定 ID、模块/组合、段落原文、绝对坐标、层次、裁切和表格单元格。
- 从核心到编辑器的资源 URL 由已授权素材服务临时签发；返回时解析为同一 user/project 下的 asset ID/hash，不能保存本机路径或跨租户 URL。
- 对不支持的能力返回显式损失报告和 `needs_correction`，不得栅格化整个页面后标记成功。
- 保存携带 base revision，旧版本写入返回冲突；本阶段不实现协同编辑或完整动画模型。
- 先跑当前两页样本的导入、改字、整体移动组合、换图、单元格编辑、撤销重做、再次导出与结构/渲染对比，验收后才讨论全站编辑 UI。

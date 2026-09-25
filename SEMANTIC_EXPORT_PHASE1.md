# Semantic Editable Export Phase 1

## 范围与结果

本阶段提供可运行的离线语义导出适配器：现有结构化内容/人工区域标注 → 版本化 Page → 原生 PPTX → OOXML 验收，以及独立的 PDF 渲染对比工具。保留旧导出入口，没有修改 UI、Provider、任务公共实现、认证积分、数据库或 migrations，也没有启动真实后端或调用模型。

共同基线：`bb3b2b300ef87aefbc3a0cbe8a871b54f5dd02c3`。与窗口一通过任务通信确认；本分支 `codex/semantic-editable-export` 使用独立 worktree。原仓库及 9674 的未跟踪文件未变更。对仓库和适用父目录的 AGENTS.md 检索无命中。

交付是“人工标注/已有结构化输入通过”的阶段性实现，不是任意 PPT 自动转换器。HTTP controller 和全站导出按钮仍走旧链路；新入口是显式 `mode='semantic'` 的 service adapter/离线脚本，未来公共 API 挂载由窗口一协调。

## 设计与接入点

新增 `backend/services/semantic_export/`：

- `model.py`：Pydantic 版本化 schema `1.0`（附 docs/semantic-page-v1.schema.json），JSON 可序列化，拒绝未知版本/字段。px@96 dpi、页面/源版本、稳定 ID、文字 runs/段落、形状、位图、SVG、裁切、原生矩形表格、模块/列/真实组合、置信度、警告和修改前后 hash。
- `adapters.py`：EditableImage/EditableElement 显式桥接。采用 bbox_global；未归属元素失败；截图子元素保留在来源记录而不重复创建；原生文字不得被标注无记录地改写。`merge_paragraphs` 检查模块/列/父组、对齐、间距和样式，原文不删改。预留 EditorAdapter，未实现候选编辑器私有 JSON。
- `assets.py`：可信服务器选择的项目 root + user_id/project_id 作用域；模型只存相对 URI/hash。拒绝绝对路径、穿越、逃逸 symlink、跨项目、hash 变更及活动/外链 SVG；完整截图检查比例，防止拉伸。
- `builder.py`：复用现有 PPTXBuilder 的 Presentation/元数据和同一 python-pptx 库。使用严格对象构建而非旧 builder 会吞异常的图片占位逻辑。原生 textbox、完整 shape、可替换 pic、SVG source + PNG fallback、原生 table；中英文字体明确设置。先绘制全局叶子顺序，再自底向上组合，off=chOff、ext=chExt；组名含稳定 ID 与可读名称。
- `audit.py`：检查实际 ZIP/关系、OOXML ID、全部嵌套叶子、父组、前后层序、坐标/旋转、文本/表格数据、完整形状、PNG/SVG hash、裁切、源整页图和图片背景。结构通过不意味着渲染或客户端操作通过。
- `pipeline.py`：extract → semantic → objects → acceptance。复用 EditableExportCheckpoint._publish 的原子发布，不改旧 manifest；语义缓存存于独立 scope hash 子目录。每页失败不发布失败阶段、不污染成功页；任一页失败抛明确错误，不返回伪成功文件。

核心对全页内容图同时做来源 hash 和面积检查，当前只允许原生纯色背景。缺素材、未知对象、跨卡片组合、会改变遮挡关系的非连续组、截图覆盖上的原生重复字都明确失败。低置信度内容保留并警告，不自动删除。纯色替代参考稿装饰背景作为可见的样本差异记录，不伪装视觉等同。

### 复用现有来源的边界

旧 `export_service.py` 的 recursive analysis 可以交付 EditableImage，已有 checkpoint 恢复它；先显式补充区域所有权、角色和素材映射，再交给本适配器。旧链路中的整页背景回退不会进入新 builder。

`harness_generation_service.ensure_page_visual_plans` 生成 DeckVersion / SlideVersion / PageVisualPlan，可复用已确认的正文、素材引用、来源版本和模块语义。但当前基线的 plan 是生成前意图，不等于最终图片坐标或文字。没有发现独立名为 VisualResolver 的可直接输出本模型的实现，不能凭其名称声称已接入。出现文案差异时保存 proposed_text + mismatch/unverified，保留实际来源文字；需要逐字核验或显式 correction。自动 OCR、区域识别、图文对齐尚未验收。

### 缓存与恢复

key 依赖 scope、page/source ID/revision/hash、schema、策略、提取签名、组织签名、修正版本、Page 内容、builder/audit 版本。PageJob 的签名由调用方提供稳定的模型/策略指纹（不得放凭据）。只修改组织/局部修正版本时提取复用，修改源/提取器使下游失效。资产每次重新核对，即使缓存命中也不信任旧路径。对象页缓存为独立 PPTX；最终多页打包仍会做一次廉价重建并重新 audit，不跨页挪用关系。

`export_pages` 是已经完成语义组织的便捷入口，输入整页 JSON 的任何变化会使该页全部阶段重新运行。需要精细失效的提取任务使用 PageJob/export_jobs；测试证明局部修正复用 extraction，其他页四阶段全命中。失败重试、损坏缓存重建均有测试。

## 运行与验证

使用仓库已有 Python 环境及 pyproject 依赖，未新增生产依赖；不依赖 artifact-tool。脚本不加载 .env，不创建 app/DB。已输出的 JSON/素材也可通过 scripts/semantic_export/export_json.py 独立复建，本次已实际执行并再次结构验收。测试以 fake callback/禁网络运行。

```bash
python -m pytest backend/tests/semantic_export \
  backend/tests/unit/test_editable_export_checkpoint.py \
  backend/tests/unit/test_editable_pptx_style_extraction.py -q
python scripts/semantic_export/sample.py --output /tmp/semantic-sample
python scripts/semantic_export/sample.py --output /tmp/semantic-reference \
  --reference-dir '/path/to/完整卡片式可编辑重构'
```

独立业务表格为明确标注的虚构数据。可复现样本复用仓库已有图像，并附小型 SVG/PNG fixture。参考导入只转换明确标注的第 21 页，不是通用 deck.json 导入器；引用素材和大交付文件不提交 Git。

渲染使用 Codex bundled LibreOffice（外部验收工具，不作为生产依赖）。设置 FONTCONFIG_FILE 指向仓库 backend/fonts，确保字体内部名 `Noto Sans CJK SC` 被解析。导出 PDF 后执行：

```bash
python scripts/semantic_export/render_check.py /tmp/semantic-reference
```

脚本输出 PNG、side-by-side comparison、review.html、render-report.json；检查可见文字覆盖、页面边界和原生文本框范围。复杂遮挡、图片内容和美观仍需人工视觉检查，不能只靠字符覆盖率。

### 本次证据

- 45 项通过：34 项语义专属 + 11 项旧导出回归。包含模型/序列化/版本，模块与列边界，截图子字，原生对象，嵌套组合，ID/关系/坐标/图层/crop，完整卡片，整页回退拒绝，作用域/路径/hash，局部失效、失败恢复、取消中断。
- 代表页：20 个叶子（7 文本、6 形状、3 位图、4 SVG），7 个真实命名组合。表格页：3 文本、1 原生表格。另有不依赖外部参考路径的两页小样本。
- 渲染首轮发现字体内部名错误和标题越框；已改正字体名称，标题宽度/字号调整通过 `correct_node` 记录（正文不改写），并移除默认主题阴影。最终复核见交付目录 validation.json。
- WPS/PowerPoint 实际改字、移动组合、替换照片：未执行。WPS 在其他文档操作中发生窗口切换，未继续干扰现有工作；没有把 OOXML/PDF 验证当作客户端操作证明。
- 旧 builder 元数据写入 `last_printed=None` 会记录既有 warning；python-pptx 仍能生成/打开文件。该共享代码本阶段未修改。MuPDF 读取 LO PDF 有 structure-tree 提示，渲染和文本提取成功；不据此宣称 PDF 无障碍标签合规。

## 参考实现审查

已阅读 ocr.swift、regions.py、prepare.py、reconstruct.py、deck.json、build.mjs、package_groups.py、render_compare.py、audit_delivery.py、rebuild.sh，核对验证说明、comparisons/21.png 和交付 PPTX 结构。

参考 OCR 固定 38 页/1280×720、regions 人工坐标、重构有过滤与文字修正；builder 依赖本机 artifact-tool。只借鉴阶段划分和语义卡片思想，不搬入业务颜色、坐标或本机路径到核心。其全局按 group 收集再移动节点会改变非连续元素图层，本模型直接拒绝这种输入。其记录没有客户端交互验收、没有原生业务表格，本次分别标记未做与独立补测。

## 剩余问题与回滚

未实现：自动区域识别、多模型对齐、任意旧 PPT 导入、渐变/透明装饰背景、复杂合并表格、动画、字体嵌入、整站在线画布、通用 PPTX 回读、跨页部件增量合并。当前 core 支持矩形 crop、简单原生形状、身份变换的嵌套组；不支持的能力应当扩版本或报错。

素材授权仍由宿主基于真实登录用户与项目归属决定，AssetStore 的 root 不能直接接受客户端输入。缓存目录也是服务器指定的项目目录。当前缓存没有自动 GC，生命周期由后续文件管理策略负责。

回滚只需不挂载新 adapter，或 revert 本分支提交；旧服务/任务/API 未变、无迁移、无历史项目转换，无需数据库回滚。线上尚未部署。编辑器建议见 `docs/SEMANTIC_EDITOR_CANDIDATES.md`，窗口一接入说明见 `docs/SEMANTIC_EXPORT_INTEGRATION.md`。

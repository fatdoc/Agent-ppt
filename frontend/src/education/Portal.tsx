import { useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  FileText,
  UploadCloud,
  AlignLeft,
  Plus,
  X,
  Check,
  ChevronRight,
  Presentation,
} from "lucide-react";
import { base, create, data, failure, load, patch, type Snapshot } from "./api";
import { uploadReferenceFile, triggerFileParse } from "../api/endpoints";
import "./portal.css";
import { EducationSpace, type SpaceItem } from "./Space";
import { LongTermPicker, LONG_TERM_SELECTION_ENABLED } from "./LongTermPicker";
export type ProjectSummary = {
  project_id: string;
  project_title: string;
  updated_at?: string;
};
const styles = [
  {
    id: "technology",
    name: "科技蓝",
    label: "技能展示 · 技术方案",
    title: "让技能成果清晰呈现",
    chapters: "项目设计 / 工作流程 / 核心技能",
  },
  {
    id: "minimal",
    name: "简洁白",
    label: "答辩汇报 · 综合赛道",
    title: "以专业，呈现每一步",
    chapters: "任务拆解 / 岗位协作 / 成果验证",
  },
  {
    id: "ecology",
    name: "生态绿",
    label: "农业生态 · 绿色发展",
    title: "从真实场景，到实践成果",
    chapters: "场景需求 / 实践过程 / 应用价值",
  },
];
export function EducationPortal({
  section,
  projects,
  onCreated,
}: {
  section: string;
  projects: ProjectSummary[];
  onCreated: () => Promise<unknown>;
}) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [mode, setMode] = useState(params.get("mode") || "file");
  const [style, setStyle] = useState(params.get("style") || "technology");
  const [title, setTitle] = useState("");
  const [material, setMaterial] = useState("");
  const [outline, setOutline] = useState("");
  const [descriptions, setDescriptions] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [libraryFiles, setLibraryFiles] = useState<SpaceItem[]>([]);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [track, setTrack] = useState("");
  const [level, setLevel] = useState("高职专科");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");
  const [recoveryId, setRecoveryId] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const creating = useRef(false);
  const addFiles = (incoming: File[]) => {
    if (files.length + libraryFiles.length + incoming.length > 30) {
      setError("最多支持 30 份材料，请减少选择后重试");
      return;
    }
    setFiles((old) => [...old, ...incoming]);
  };
  const start = async () => {
    if (creating.current) return;
    if (recoveryId) {
      navigate(`/education/project/${recoveryId}`);
      return;
    }
    if (mode === "file" && !files.length && !libraryFiles.length) {
      setError("请先选择材料文件");
      return;
    }
    if (mode === "text" && !material.trim()) {
      setError("请粘贴项目材料");
      return;
    }
    if (mode === "import" && !outline.trim()) {
      setError("请粘贴已有大纲");
      return;
    }
    creating.current = true;
    setPending(true);
    setError("");
    let createdId = "";
    try {
      setProgress("正在创建项目…");
      let s = await create();
      createdId = s.project_id;
      s.content.profile = {
        ...s.content.profile,
        name:
          title.trim() ||
          files[0]?.name.replace(/\.[^.]+$/, "") ||
          libraryFiles[0]?.name.replace(/\.[^.]+$/, "") ||
          "未命名竞赛项目",
        track,
        education_level: level,
      };
      s.content.preferences.style = style;
      s.content.raw_material = material;
      s = await patch(s.project_id, s.revision, s.content);
      if (mode === "import")
        s = await data<Snapshot>("post", base(s.project_id) + "/import", {
          revision: s.revision,
          outline,
          descriptions,
        });
      for (const [i, file] of (mode === "file" ? files : []).entries()) {
        setProgress(`正在上传材料 ${i + 1}/${files.length}…`);
        const res = await uploadReferenceFile(file, s.project_id);
        if (!res.data?.file) throw new Error("材料上传失败");
        s.content.reference_file_ids.push(res.data.file.id);
        s = await patch(s.project_id, s.revision, s.content);
        await triggerFileParse(res.data.file.id);
      }
      for (const file of mode === "file" ? libraryFiles : []) {
        setProgress(`正在添加长期文件：${file.name}`);
        const attached = await data<{ id: string; parse_status: string }>(
          "post",
          `/api/competition/space/${file.kind}/${file.id}/use`,
          { project_id: s.project_id, revision: s.revision },
        );
        s = await load(s.project_id);
        if (attached.parse_status !== "completed")
          await triggerFileParse(attached.id);
      }
      await onCreated();
      navigate(`/education/project/${s.project_id}`);
    } catch (e) {
      setError(failure(e));
      if (createdId) {
        setRecoveryId(createdId);
        await onCreated().catch(() => {});
        setProgress(`项目已保留，可从“我的空间”继续上传。`);
      }
    } finally {
      creating.current = false;
      setPending(false);
    }
  };
  const templateGrid = (
    <div className="education-template-grid">
      {styles.map((s) => (
        <button
          key={s.id}
          className="education-template"
          onClick={() => navigate(`/education/create?style=${s.id}`)}
        >
          <div className={`education-slide-sample ${s.id}`}>
            <span>世界职业院校技能大赛</span>
            <strong>{s.title}</strong>
            <div className="sample-rule" />
            <small>{s.chapters}</small>
            <div className="sample-art" aria-hidden="true">
              <i />
              <i />
              <i />
            </div>
          </div>
          <div className="education-template-caption">
            <div>
              <strong>{s.name}</strong>
              <span>{s.label}</span>
            </div>
            <span>
              使用此风格 <ArrowRight size={14} />
            </span>
          </div>
        </button>
      ))}
    </div>
  );
  const projectList = () => (
    <div className="education-project-list">
      {projects.slice(0, 4).map((p) => (
        <Link to={`/education/project/${p.project_id}`} key={p.project_id}>
          <span className="project-file-icon">
            <Presentation size={23} />
          </span>
          <div>
            <strong>{p.project_title}</strong>
            <span>
              竞赛演示项目
              {p.updated_at
                ? ` · ${new Date(p.updated_at).toLocaleDateString("zh-CN")}`
                : ""}
            </span>
          </div>
          <span className="project-continue">
            继续编辑 <ChevronRight size={16} />
          </span>
        </Link>
      ))}
      {!projects.length && (
        <div className="education-empty-list">
          还没有项目，从一份材料开始创建。
        </div>
      )}
    </div>
  );
  return (
    <main className="education-portal">
      <header className="education-portal-header">
        <div>
          <strong>
            {(
              {
                home: "首页",
                create: "智能演示",
                projects: "我的空间",
                templates: "模板中心",
                help: "帮助中心",
              } as Record<string, string>
            )[section] || "首页"}
          </strong>
          <span>兰台 · 竞赛教育版</span>
        </div>
        <Link to="/education/create">
          <Plus size={16} /> 新建作品
        </Link>
      </header>
      <div className="education-portal-scroll">
        {section === "home" && (
          <>
            <section className="education-home-hero">
              <div>
                <span className="education-badge">世界职业院校技能大赛</span>
                <h1>你的竞赛作品，从这里开始</h1>
                <p>上传项目材料，完成大纲、逐页内容和演示文稿。</p>
              </div>
              <div className="education-hero-art" aria-hidden="true">
                <div className="hero-paper back" />
                <div className="hero-paper">
                  <Presentation size={34} />
                  <b>技能 · 实践 · 成果</b>
                  <i />
                  <i />
                </div>
              </div>
            </section>
            <section className="education-entry-grid" aria-label="创作方式">
              {[
                {
                  mode: "file",
                  name: "上传文件生成",
                  desc: "项目方案、逐字稿、旧演示文稿",
                  icon: UploadCloud,
                },
                {
                  mode: "text",
                  name: "粘贴材料生成",
                  desc: "从零散想法与项目说明开始",
                  icon: AlignLeft,
                },
                {
                  mode: "import",
                  name: "导入已有稿件",
                  desc: "保留已写好的大纲与逐页描述",
                  icon: FileText,
                },
              ].map(({ mode, name, desc, icon: Icon }) => (
                <Link key={mode} to={`/education/create?mode=${mode}`}>
                  <Icon size={28} />
                  <div>
                    <strong>{name}</strong>
                    <span>{desc}</span>
                  </div>
                  <ArrowRight size={17} />
                </Link>
              ))}
            </section>
            <section>
              <div className="education-section-heading">
                <h2>精选模板</h2>
                <Link to="/education/templates">
                  查看全部 <ChevronRight size={15} />
                </Link>
              </div>
              {templateGrid}
            </section>
            <section>
              <div className="education-section-heading">
                <h2>最近作品</h2>
                <Link to="/education/projects">
                  我的空间 <ChevronRight size={15} />
                </Link>
              </div>
              {projectList()}
            </section>
          </>
        )}
        {section === "templates" && (
          <>
            <div className="education-page-heading">
              <h1>选择作品风格</h1>
              <p>自有基础风格。也可以进入工作台后上传你的参考模板。</p>
            </div>
            {templateGrid}
          </>
        )}
        {section === "projects" && <EducationSpace onChanged={onCreated} />}
        {section === "create" && (
          <div className="education-create">
            <div className="education-page-heading">
              <h1>开始制作竞赛演示文稿</h1>
              <p>先确认材料与场景，再进入内容工作台。</p>
            </div>
            <div
              role="tablist"
              aria-label="材料输入方式"
              className="education-input-tabs"
            >
              {[
                ["file", "上传文件"],
                ["text", "粘贴材料"],
                ["import", "已有稿件"],
              ].map(([id, label]) => (
                <button
                  role="tab"
                  aria-selected={mode === id}
                  key={id}
                  disabled={pending}
                  onClick={() => {
                    setMode(id);
                    setError("");
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <fieldset disabled={pending} className="education-create-fields">
              <label>
                作品名称
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="例如：草莓精准生长智控系统"
                  maxLength={200}
                />
              </label>
              {mode === "file" && (
                <>
                  <div className="education-source-actions">
                    <button
                      type="button"
                      onClick={() => input.current?.click()}
                    >
                      上传本地文件
                    </button>
                    {LONG_TERM_SELECTION_ENABLED && (<button type="button" onClick={() => setLibraryOpen(true)}>
                      从长期文件选择
                    </button>)}
                  </div>
                  <button
                    className="education-dropzone"
                    type="button"
                    onClick={() => input.current?.click()}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (!pending) addFiles(Array.from(e.dataTransfer.files));
                    }}
                  >
                    <UploadCloud size={35} />
                    <strong>点击上传，或将文件拖到这里</strong>
                    <span>支持项目方案、逐字稿及旧稿；最多 30 份材料</span>
                  </button>
                  <input
                    ref={input}
                    hidden
                    multiple
                    type="file"
                    accept=".pdf,.pptx,.docx,.txt,.md,.xlsx"
                    onChange={(e) => {
                      addFiles(Array.from(e.target.files || []));
                      e.target.value = "";
                    }}
                  />
                  {libraryFiles.map((file) => (
                    <div className="education-file-row" key={file.key}>
                      <FileText size={16} />
                      <span>{file.name}</span>
                      <small>长期文件</small>
                      <button
                        aria-label={`移除 ${file.name}`}
                        onClick={() =>
                          setLibraryFiles((old) =>
                            old.filter((i) => i.id !== file.id),
                          )
                        }
                      >
                        <X size={15} />
                      </button>
                    </div>
                  ))}
                  {files.map((f, i) => (
                    <div className="education-file-row" key={i}>
                      <FileText size={16} />
                      <span>{f.name}</span>
                      <small>{(f.size / 1024).toFixed(0)} 千字节</small>
                      <button
                        aria-label={`移除 ${f.name}`}
                        onClick={() =>
                          setFiles(files.filter((_, n) => n !== i))
                        }
                      >
                        <X size={15} />
                      </button>
                    </div>
                  ))}
                </>
              )}
              {mode !== "import" ? (
                <label>
                  {mode === "text" ? "项目材料" : "补充要求（选填）"}
                  <textarea
                    value={material}
                    onChange={(e) => setMaterial(e.target.value)}
                    placeholder="介绍项目、团队分工、技术重点和已有成果…"
                    rows={mode === "text" ? 8 : 3}
                  />
                </label>
              ) : (
                <div className="education-import-grid">
                  <label>
                    已有大纲
                    <textarea
                      value={outline}
                      onChange={(e) => setOutline(e.target.value)}
                      rows={10}
                      placeholder="粘贴大纲，保留原有章节和页面…"
                    />
                  </label>
                  <label>
                    逐页描述（选填）
                    <textarea
                      value={descriptions}
                      onChange={(e) => setDescriptions(e.target.value)}
                      rows={10}
                      placeholder="粘贴配套的逐页描述…"
                    />
                  </label>
                </div>
              )}
              <div className="education-context-grid">
                <label>
                  赛事
                  <input value="世界职业院校技能大赛" readOnly />
                </label>
                <label>
                  赛道
                  <input
                    value={track}
                    onChange={(e) => setTrack(e.target.value)}
                    placeholder="输入赛道，暂未确定可留空"
                  />
                </label>
                <label>
                  教育层次
                  <select
                    value={level}
                    onChange={(e) => setLevel(e.target.value)}
                  >
                    <option>中职</option>
                    <option>高职专科</option>
                    <option>职业本科</option>
                    <option>暂未确定</option>
                  </select>
                </label>
              </div>
              <div className="education-style-picker">
                <span>基础风格</span>
                {styles.map((s) => (
                  <button
                    key={s.id}
                    aria-pressed={style === s.id}
                    className={style === s.id ? "selected" : ""}
                    onClick={() => setStyle(s.id)}
                  >
                    {style === s.id && <Check size={15} />} {s.name}
                  </button>
                ))}
              </div>
            </fieldset>
            {error && (
              <p role="alert" className="education-form-error">
                {error}
              </p>
            )}
            {progress && <p role="status">{progress}</p>}
            <div className="education-create-footer">
              <span>材料先保存，生成前再确认内容与积分。</span>
              <button
                className="edu-primary"
                disabled={pending}
                onClick={() => void start()}
              >
                {pending
                  ? "正在处理…"
                  : recoveryId
                    ? "继续已创建项目"
                    : "进入内容工作台"}
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}
        {section === "help" && (
          <div className="education-help">
            <div className="education-page-heading">
              <h1>制作指南</h1>
              <p>从材料准备到作品交付。</p>
            </div>
            {[
              [
                "准备材料",
                "上传方案、逐字稿或旧演示文稿；也可以导入已有大纲与逐页描述。",
              ],
              [
                "确认项目内容",
                "在工作台补充赛道、团队和展示重点。五章四岗 47 页是可调整的预设。",
              ],
              [
                "绑定人物与素材",
                "在团队介绍页上传单人照；产品图、系统截图和证明材料绑定到对应页面。",
              ],
              [
                "先试稿，再生成整套",
                "选择三页查看风格，确认后生成剩余页面。修改过的页面可以单独更新。",
              ],
              [
                "保存与交付",
                "从我的空间继续项目，在工作台导出大纲、描述、待补清单和 PDF。可编辑转换需通过校验后进入编辑器。",
              ],
            ].map(([name, text], i) => (
              <article key={name}>
                <span>{i + 1}</span>
                <div>
                  <h2>{name}</h2>
                  <p>{text}</p>
                </div>
              </article>
            ))}
            <Link to="/education/create" className="education-help-start">
              开始创建作品 <ArrowRight size={16} />
            </Link>
          </div>
        )}
      </div>
      {libraryOpen && (
        <LongTermPicker
          kind="reference"
          context="选择本次作品的项目材料"
          excludeIds={libraryFiles.map((i) => i.id)}
          onClose={() => setLibraryOpen(false)}
          onSelect={async (item) => {
            if (files.length + libraryFiles.length >= 30)
              throw new Error("最多支持 30 份材料");
            setLibraryFiles((old) => [...old, item]);
          }}
        />
      )}
    </main>
  );
}

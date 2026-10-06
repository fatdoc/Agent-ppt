import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ArrowDown,
  ArrowUp,
  Check,
  FileText,
  ImagePlus,
  Lock,
  MessageSquare,
  Plus,
  Send,
  Sparkles,
  Trash2,
  Unlock,
  Upload,
  Download,
  RefreshCw,
} from "lucide-react";
import {
  uploadReferenceFile,
  listProjectReferenceFiles,
  uploadMaterial,
  triggerFileParse,
} from "../api/endpoints";
import {
  active,
  isTeamPage,
  base,
  data,
  download,
  failure,
  load,
  patch,
  submitOperation,
  type Content,
  type EduPage,
  type EduTask,
  type Snapshot,
  type Binding,
} from "./api";
import "./education.css";
import { EducationNavigation } from "./Navigation";
import { EducationPortal } from "./Portal";
import { TeamPhotos } from "./TeamPhotos";
import { LongTermPicker, LONG_TERM_SELECTION_ENABLED } from "./LongTermPicker";
import type { SpaceItem } from "./Space";

const chapters = [
  "开场",
  "项目设计",
  "工作流程",
  "核心技能",
  "成果展示",
  "未来展望",
];
type RefFile = {
  id: string;
  filename: string;
  parse_status: string;
  error_message?: string | null;
};
type Material = { id: string; url: string; filename: string };
const copy = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

export default function EducationWorkspace() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const section = location.pathname.split("/")[2] || "home";
  const [snap, setSnap] = useState<Snapshot | null>(null),
    [draft, setDraft] = useState<Content | null>(null);
  const [draftRevision, setDraftRevision] = useState(0);
  const [dirty, setDirty] = useState(false),
    [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [history, setHistory] = useState<
    { project_id: string; project_title: string }[]
  >([]);
  const [files, setFiles] = useState<RefFile[]>([]),
    [materials, setMaterials] = useState<Material[]>([]);
  const [tab, setTab] = useState<"outline" | "detail" | "materials">("outline"),
    [selected, setSelected] = useState("");
  const [trial, setTrial] = useState<string[]>([]),
    [message, setMessage] = useState(""),
    [localRewrite, setLocalRewrite] = useState(false);
  const [settings, setSettings] = useState(false),
    [showImport, setShowImport] = useState(false),
    [outline, setOutline] = useState(""),
    [descriptions, setDescriptions] = useState("");
  const [editor, setEditor] = useState<{
    ready: boolean;
    stale?: boolean;
    revision?: number;
    task: EduTask | null;
    editor_url?: string;
  } | null>(null);
  const [revisions, setRevisions] = useState<
    { revision: number; created_at: string }[] | null
  >(null);
  const [assetPurpose, setAssetPurpose] =
      useState<Binding["purpose"]>("reference"),
    [roleId, setRoleId] = useState("");
  const [libraryTarget, setLibraryTarget] = useState<{
    kind: "reference" | "material";
    pageId?: string;
    purpose?: Binding["purpose"];
    roleId?: string;
    label: string;
  } | null>(null);
  const currentProjectId = useRef(projectId);
  currentProjectId.current = projectId;
  const refreshing = useRef(false);
  const state = useRef({ dirty, snap, draft });
  state.current = { dirty, snap, draft };
  const refreshHistory = useCallback(
    () =>
      data<typeof history>("get", "/api/competition/projects").then(setHistory),
    [],
  );
  const accept = useCallback((s: Snapshot) => {
    setSnap(s);
    setDraftRevision(s.revision);
    setDraft(copy(s.content));
    setDirty(false);
    setSelected((id) =>
      s.content.pages.some((p) => p.id === id)
        ? id
        : s.content.pages[0]?.id || "",
    );
    setTrial((ids) =>
      ids.length
        ? ids.filter((id) => s.content.pages.some((p) => p.id === id))
        : s.default_trial_page_ids,
    );
  }, []);
  const refresh = useCallback(async () => {
    if (!projectId) return;
    if (refreshing.current) return;
    refreshing.current = true;
    try {
      const [s, refs, mats, ed] = await Promise.all([
        load(projectId),
        listProjectReferenceFiles(projectId),
        data<{ materials: Material[] }>(
          "get",
          `/api/projects/${projectId}/materials`,
        ),
        data<NonNullable<typeof editor>>(
          "get",
          `/api/projects/${projectId}/editable-generation`,
        ),
      ]);
      if (currentProjectId.current !== projectId) return;
      setSnap(s);
      if (!state.current.dirty) {
        setDraftRevision(s.revision);
        setDraft(copy(s.content));
        setSelected((id) =>
          s.content.pages.some((p) => p.id === id)
            ? id
            : s.content.pages[0]?.id || "",
        );
      }
      setTrial((ids) =>
        ids.length
          ? ids.filter((id) => s.content.pages.some((p) => p.id === id))
          : s.default_trial_page_ids,
      );
      setFiles(refs.data?.files || []);
      setMaterials(mats.materials || []);
      setEditor(ed);
    } finally {
      refreshing.current = false;
    }
  }, [projectId]);
  useEffect(() => {
    document.title = "兰台 · 竞赛教育版";
    refreshHistory().catch((e) => setError(failure(e)));
  }, [refreshHistory]);
  useEffect(() => {
    setSnap(null);
    setDraft(null);
    setDirty(false);
    setTrial([]);
    setFiles([]);
    setLibraryTarget(null);
    setEditor(null);
    setError("");
    if (projectId)
      load(projectId)
        .then((s) => {
          if (currentProjectId.current === projectId) accept(s);
        })
        .then(refresh)
        .catch((e) => {
          if (currentProjectId.current === projectId) setError(failure(e));
        });
  }, [projectId, accept, refresh]);
  useEffect(() => {
    if (!projectId) return;
    const id = window.setInterval(
      () => refresh().catch((e) => setError(failure(e))),
      4000,
    );
    return () => clearInterval(id);
  }, [projectId, refresh]);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (state.current.dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);
  const run = async (fn: () => Promise<void>) => {
    if (pending) return;
    setPending(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(failure(e));
    } finally {
      setPending(false);
    }
  };
  const update = (fn: (d: Content) => void) => {
    setDraft((d) => {
      if (!d) return d;
      const n = copy(d);
      fn(n);
      return n;
    });
    setDirty(true);
  };
  const save = async () => {
    if (!projectId || !snap || !draft) throw new Error("请先新建项目");
    if (!dirty) return snap;
    const s = await patch(projectId, draftRevision, draft);
    accept(s);
    return s;
  };
  const page = draft?.pages.find((p) => p.id === selected);
  const rendered = snap?.pages.find((p) => p.page_id === selected);
  useEffect(() => {
    if (page && !(page.chapter === 0 && page.kind === "content")) {
      setAssetPurpose((purpose) =>
        purpose === "person" ? "reference" : purpose,
      );
    }
  }, [page?.id, page?.chapter, page?.kind]);
  const busy = active(snap?.task) || active(editor?.task),
    imageBusy =
      active(editor?.task) ||
      (active(snap?.task) && snap?.task?.task_type === "GENERATE_IMAGES");
  const launch = (action: string, extra: Record<string, unknown> = {}) =>
    run(async () => {
      const s = await save();
      await submitOperation(s.project_id, action, s.revision, extra);
      setMessage("");
      await refresh();
    });
  const editPage = (patchValue: Partial<EduPage>) =>
    update((d) => {
      d.pages = d.pages.map((p) =>
        p.id === selected ? { ...p, ...patchValue } : p,
      );
    });
  const move = (offset: number) =>
    update((d) => {
      const i = d.pages.findIndex((p) => p.id === selected),
        j = i + offset;
      if (j >= 0 && j < d.pages.length)
        [d.pages[i], d.pages[j]] = [d.pages[j], d.pages[i]];
    });
  const addPage = () => {
    const id = crypto.randomUUID();
    update((d) => {
      const i = d.pages.findIndex((p) => p.id === selected);
      d.pages.splice(i + 1, 0, {
        id,
        title: "新增页面",
        kind: "content",
        chapter: page?.chapter || 1,
        purpose: "说明本页核心结论",
        text: ["待补充页面内容"],
        layout: ["主画面与简洁短标注"],
        materials: ["待补真实素材"],
        speaker_notes: [],
        action_notes: [],
      });
    });
    setSelected(id);
  };
  const fileInput = useRef<HTMLInputElement>(null),
    assetInput = useRef<HTMLInputElement>(null),
    templateInput = useRef<HTMLInputElement>(null);
  const uploadFiles = (uploads: FileList | null) => {
    if (!uploads?.length) return;
    // FileList is live: the input is cleared as soon as its change handler returns.
    const selectedFiles = Array.from(uploads);
    void run(async () => {
      let s = await save();
      for (const f of selectedFiles) {
        const r = await uploadReferenceFile(f, s.project_id);
        if (!r.data?.file) throw new Error("上传失败");
        const next = copy(s.content);
        next.reference_file_ids.push(r.data.file.id);
        s = await patch(s.project_id, s.revision, next);
        accept(s);
        await triggerFileParse(r.data.file.id);
      }
      await refresh();
    });
  };
  const uploadAsset = (f?: File, personRoleId?: string) => {
    if (!f || !page) return;
    void run(async () => {
      const s = await save();
      const res = await uploadMaterial(f, s.project_id, false);
      if (!res.data) throw new Error("素材上传失败");
      const next = copy(s.content);
      const purpose = personRoleId ? "person" : assetPurpose;
      const memberId = personRoleId || roleId || next.profile.roles[0].id;
      if (purpose === "person")
        next.bindings = next.bindings.filter(
          (b) =>
            !(
              b.page_id === page.id &&
              b.purpose === "person" &&
              b.role_id === memberId
            ),
        );
      next.bindings.push({
        page_id: page.id,
        material_id: res.data.id,
        purpose,
        ...(purpose === "person" ? { role_id: memberId } : {}),
      });
      accept(await patch(s.project_id, s.revision, next));
      await refresh();
    });
  };
  const selectLibraryFile = async (file: SpaceItem) => {
    if (!libraryTarget || pending) throw new Error("正在处理，请稍后重试");
    setPending(true);
    setError("");
    setNotice("");
    try {
      const s = await save();
      const binding =
        libraryTarget.kind === "material"
          ? {
              page_id: libraryTarget.pageId,
              purpose: libraryTarget.purpose,
              ...(libraryTarget.purpose === "person"
                ? { role_id: libraryTarget.roleId }
                : {}),
            }
          : undefined;
      const result = await data<{ id: string; parse_status: string }>(
        "post",
        `/api/competition/space/${file.kind}/${file.id}/use`,
        {
          project_id: s.project_id,
          revision: s.revision,
          ...(binding ? { binding } : {}),
        },
      );
      accept(await load(s.project_id));
      if (file.kind === "reference" && result.parse_status !== "completed") {
        try {
          await triggerFileParse(result.id);
        } catch {
          setNotice("材料已添加，解析尚未启动，可在材料列表重试解析。");
        }
      } else
        setNotice(
          libraryTarget.kind === "reference"
            ? "长期材料已添加"
            : "长期图片已绑定到当前页面",
        );
      await refresh();
    } finally {
      setPending(false);
    }
  };
  const doImport = () =>
    run(async () => {
      const s = await save();
      accept(
        await data<Snapshot>("post", base(s.project_id) + "/import", {
          revision: s.revision,
          outline,
          descriptions,
        }),
      );
      setShowImport(false);
    });
  const exportText = (kind: string) =>
    run(async () => {
      const s = await save();
      await download(
        base(s.project_id) + `/exports/${kind}`,
        `${s.content.profile.name}_${kind}.md`,
      );
    });
  const field = (
    key: keyof Content["profile"],
    label: string,
    placeholder = "",
  ) =>
    draft && (
      <label className="edu-field" key={key}>
        <span>
          {label}
          <button
            type="button"
            className="edu-icon"
            aria-label={`${draft.locks.includes(key) ? "解锁" : "锁定"}${label}`}
            onClick={() =>
              update((d) => {
                d.locks = d.locks.includes(key)
                  ? d.locks.filter((k) => k !== key)
                  : [...d.locks, key];
              })
            }
          >
            {draft.locks.includes(key) ? (
              <Lock size={12} />
            ) : (
              <Unlock size={12} />
            )}
          </button>
        </span>
        <input
          value={String(draft.profile[key])}
          placeholder={placeholder}
          onChange={(e) =>
            update((d) => {
              (d.profile as unknown as Record<string, unknown>)[key] =
                e.target.value;
            })
          }
        />
      </label>
    );
  return (
    <div className="edu-app edu-v2">
      <EducationNavigation
        onNavigate={(path) => {
          void run(async () => {
            if (dirty) await save();
            navigate(path);
          });
        }}
      />
      <div className="edu-body">
        {!projectId ? (
          <EducationPortal
            key={section + location.search}
            section={section}
            projects={history}
            onCreated={refreshHistory}
          />
        ) : !draft || !snap ? (
          <main className="edu-loading">
            {error || "正在载入项目…"}
            <button onClick={() => run(refresh)}>重试</button>
          </main>
        ) : (
          <main className="edu-workspace">
            <div className="edu-projectbar">
              <div>
                <span className="edu-eyebrow">竞赛项目 / 内容工作台</span>
                <h1>{draft.profile.name}</h1>
              </div>
              <div className="edu-project-actions">
                <span>
                  {dirty ? "有未保存修改" : `已保存 · v${snap.revision}`}
                </span>
                <button onClick={() => setSettings(!settings)}>项目设置</button>
                <button
                  onClick={() =>
                    run(async () => {
                      await save();
                      setNotice("内容已保存");
                      await refreshHistory();
                    })
                  }
                  disabled={pending || imageBusy || !dirty}
                >
                  <Check size={15} />
                  保存
                </button>
                <button
                  title="重新载入会替换未保存草稿"
                  onClick={() =>
                    run(async () => {
                      accept(await load(projectId));
                      setNotice("已载入最新版本");
                    })
                  }
                >
                  <RefreshCw size={15} />
                </button>
              </div>
            </div>
            {error && (
              <div className="edu-alert error" role="alert">
                {error}
                <button onClick={() => setError("")}>关闭</button>
              </div>
            )}
            {notice && (
              <div className="edu-alert" role="status">
                {notice}
              </div>
            )}
            {settings && (
              <section className="edu-settings">
                <div className="edu-settings-grid">
                  {field("name", "项目名称")}
                  {field("track", "赛道", "按实际赛道填写")}
                  {field("education_level", "教育层次")}
                  {field("duration", "展示时长", "未知可留空")}
                  {field("focus", "内容重点")}
                  {field("rule_year", "规则年份", "待核验")}
                  {field(
                    "rule_source",
                    "规则文件与来源",
                    "填写文件名或官方来源",
                  )}
                </div>
                <div className="edu-team-head">
                  <strong>团队岗位</strong>
                  <button
                    onClick={() =>
                      update((d) => {
                        d.locks = d.locks.includes("roles")
                          ? d.locks.filter((k) => k !== "roles")
                          : [...d.locks, "roles"];
                      })
                    }
                  >
                    {draft.locks.includes("roles") ? "解锁岗位" : "锁定岗位"}
                  </button>
                  <button
                    disabled={draft.profile.roles.length >= 12}
                    onClick={() =>
                      update((d) => {
                        d.profile.roles.push({
                          id: crypto.randomUUID(),
                          name: "",
                          responsibility: "",
                        });
                      })
                    }
                  >
                    <Plus size={13} />
                    添加岗位
                  </button>
                </div>
                <div className="edu-role-grid">
                  {draft.profile.roles.map((r, i) => (
                    <div key={r.id}>
                      <input
                        aria-label={`岗位${i + 1}`}
                        placeholder={`岗位 ${i + 1} 名称`}
                        value={r.name}
                        onChange={(e) =>
                          update((d) => {
                            d.profile.roles[i].name = e.target.value;
                          })
                        }
                      />
                      <input
                        aria-label={`职责${i + 1}`}
                        placeholder="实际职责与操作"
                        value={r.responsibility}
                        onChange={(e) =>
                          update((d) => {
                            d.profile.roles[i].responsibility = e.target.value;
                          })
                        }
                      />
                      <button
                        disabled={draft.profile.roles.length === 1}
                        onClick={() =>
                          update((d) => {
                            d.profile.roles.splice(i, 1);
                            d.bindings = d.bindings.filter(
                              (b) => b.role_id !== r.id,
                            );
                            d.pages.forEach((p) => {
                              p.role_ids = p.role_ids?.filter(
                                (id) => id !== r.id,
                              );
                            });
                          })
                        }
                      >
                        移除
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            )}
            <div className="edu-split">
              <section className="edu-conversation">
                <div className="edu-panel-heading">
                  <h2>
                    <MessageSquare size={17} />
                    资料与对话
                  </h2>
                  <button onClick={() => setShowImport(true)}>
                    导入已有稿
                  </button>
                </div>
                <div className="edu-conversation-scroll">
                  <div className="edu-material-intake">
                    <label htmlFor="source-text">项目材料</label>
                    <textarea
                      id="source-text"
                      placeholder="粘贴逐字稿、项目方案或零散想法，也可以上传文件。"
                      value={draft.raw_material}
                      disabled={imageBusy}
                      onChange={(e) =>
                        update((d) => {
                          d.raw_material = e.target.value;
                        })
                      }
                    />
                    <button
                      onClick={() => fileInput.current?.click()}
                      disabled={pending || imageBusy}
                    >
                      <Upload size={14} />
                      上传参考文件
                    </button>
                    {LONG_TERM_SELECTION_ENABLED && (<button
                      className="edu-library-button"
                      disabled={pending || busy}
                      onClick={() =>
                        setLibraryTarget({
                          kind: "reference",
                          label: "为当前作品补充项目材料",
                        })
                      }
                    >
                      从长期文件选择
                    </button>)}
                    <input
                      ref={fileInput}
                      type="file"
                      hidden
                      multiple
                      accept=".pdf,.docx,.pptx,.txt,.md"
                      onChange={(e) => {
                        uploadFiles(e.target.files);
                        e.target.value = "";
                      }}
                    />
                  </div>
                  {files.map((f) => (
                    <div className="edu-file-row" key={f.id}>
                      <FileText size={14} />
                      <span>
                        {f.filename}
                        <small>
                          {
                            (
                              {
                                pending: "等待解析",
                                parsing: "解析中",
                                completed: "解析完成",
                                failed: "解析失败",
                              } as Record<string, string>
                            )[f.parse_status]
                          }
                        </small>
                      </span>
                      <button
                        disabled={imageBusy}
                        onClick={() =>
                          update((d) => {
                            d.reference_file_ids =
                              d.reference_file_ids.includes(f.id)
                                ? d.reference_file_ids.filter(
                                    (id) => id !== f.id,
                                  )
                                : [...d.reference_file_ids, f.id];
                          })
                        }
                      >
                        {draft.reference_file_ids.includes(f.id)
                          ? "移除引用"
                          : "用于生成"}
                      </button>
                      {["failed", "pending"].includes(f.parse_status) && (
                        <button
                          title={f.error_message || undefined}
                          onClick={() =>
                            run(async () => {
                              await triggerFileParse(f.id);
                              await refresh();
                            })
                          }
                        >
                          {f.parse_status === "pending" ? "开始解析" : "重试"}
                        </button>
                      )}
                    </div>
                  ))}
                  <div className="edu-conversation-tip">
                    <Sparkles size={17} />
                    <p>
                      可以补充技术重点、岗位和现场操作。缺少的数据会列为待核验，不会直接当成实测结果。
                    </p>
                  </div>
                  {draft.messages.map((m) => (
                    <div key={m.id} className={`edu-message ${m.role}`}>
                      <small>
                        {m.role === "user" ? "我的补充" : "内容助手"}
                      </small>
                      <p>{m.text}</p>
                    </div>
                  ))}
                  {!!draft.questions.length && (
                    <div className="edu-questions">
                      <strong>建议补充</strong>
                      {draft.questions.map((q, i) => (
                        <p key={i}>
                          {i + 1}. {q}
                        </p>
                      ))}
                      <button
                        onClick={() =>
                          setMessage(
                            "以上信息暂时不知道，请给出标注为建议的方案，并将真实参数和素材保留为待核验。",
                          )
                        }
                      >
                        暂不知道，先给建议
                      </button>
                    </div>
                  )}
                </div>
                <div className="edu-composer">
                  {page && (
                    <label className="edu-inline">
                      <input
                        type="checkbox"
                        checked={localRewrite}
                        onChange={(e) => setLocalRewrite(e.target.checked)}
                      />
                      只修改当前页
                    </label>
                  )}
                  <textarea
                    aria-label="补充要求"
                    placeholder={
                      localRewrite
                        ? "描述当前页需要怎样修改…"
                        : "补充内容重点，或回答上方问题…"
                    }
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                  />
                  <button
                    className="edu-send"
                    aria-label="发送补充要求"
                    disabled={!message.trim() || pending || busy}
                    onClick={() =>
                      launch("messages", {
                        message,
                        page_id: localRewrite ? selected : undefined,
                      })
                    }
                  >
                    <Send size={17} />
                  </button>
                  <small>
                    补充与改写约 {snap.estimates.messages?.amount} 积分 / 次
                  </small>
                </div>
              </section>
              <section className="edu-content-panel">
                <div className="edu-tabs" role="tablist">
                  {(
                    [
                      ["outline", "文档大纲"],
                      ["detail", "逐页描述"],
                      ["materials", "素材与待补项"],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      role="tab"
                      aria-selected={tab === id}
                      key={id}
                      className={tab === id ? "active" : ""}
                      onClick={() => setTab(id)}
                    >
                      {label}
                    </button>
                  ))}
                  <span>{draft.pages.length} 页</span>
                </div>
                <div className="edu-options">
                  <label>
                    复杂度
                    <select
                      value={draft.preferences.complexity}
                      onChange={(e) =>
                        update((d) => {
                          d.preferences.complexity = e.target.value;
                        })
                      }
                    >
                      <option value="simple">简单</option>
                      <option value="balanced">平衡</option>
                      <option value="complex">复杂</option>
                    </select>
                  </label>
                  <label>
                    分页方式
                    <select
                      value={draft.preferences.pagination}
                      onChange={(e) =>
                        update((d) => {
                          d.preferences.pagination = e.target.value;
                        })
                      }
                    >
                      <option value="skill">按技能点</option>
                      <option value="compact">紧凑</option>
                      <option value="step">按连贯步骤</option>
                    </select>
                  </label>
                  <label>
                    目标页数
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={draft.preferences.target_pages}
                      onChange={(e) =>
                        update((d) => {
                          d.preferences.target_pages = Number(e.target.value);
                        })
                      }
                    />
                  </label>
                  <label>
                    视觉风格
                    <select
                      value={draft.preferences.style}
                      onChange={(e) =>
                        update((d) => {
                          d.preferences.style = e.target.value;
                        })
                      }
                    >
                      {Object.entries(snap.styles).map(([id, s]) => (
                        <option key={id} value={id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    disabled={pending || busy}
                    onClick={() => templateInput.current?.click()}
                  >
                    {snap.template_image_path ? "替换参考模板" : "参考模板"}
                  </button>
                  {snap.template_image_path && (
                    <button
                      disabled={pending || busy}
                      onClick={() =>
                        run(async () => {
                          const s = await save();
                          accept(
                            await data<Snapshot>(
                              "delete",
                              base(s.project_id) + "/template",
                              { revision: s.revision },
                            ),
                          );
                          setNotice("已清除参考模板，将使用所选基础风格");
                        })
                      }
                    >
                      使用基础风格
                    </button>
                  )}
                  <input
                    ref={templateInput}
                    hidden
                    type="file"
                    accept="image/*"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f)
                        void run(async () => {
                          const s = await save();
                          const form = new FormData();
                          form.append("template_image", f);
                          form.append("revision", String(s.revision));
                          accept(
                            await data<Snapshot>(
                              "post",
                              base(s.project_id) + "/template",
                              form,
                            ),
                          );
                          await refresh();
                          setNotice("参考模板已更新，页面需要重新生成");
                        });
                      e.target.value = "";
                    }}
                  />
                </div>
                {!!snap.warnings.length && (
                  <details className="edu-warning">
                    <summary>{snap.warnings.length} 条结构或页数提示</summary>
                    {Array.from(new Set(snap.warnings)).map((w, i) => (
                      <p key={i}>{w}</p>
                    ))}
                    {draft.structure_mode === "preserve" && (
                      <button
                        disabled={busy || pending}
                        onClick={() =>
                          launch("plan", { convert_structure: true })
                        }
                      >
                        按五章预设重新规划（会改写原稿）
                      </button>
                    )}
                  </details>
                )}
                <div className="edu-content-scroll">
                  {!draft.pages.length ? (
                    <div className="edu-empty">
                      <FileText size={46} strokeWidth={1} />
                      <h2>先把材料变成可修改的内容</h2>
                      <p>
                        上传或粘贴材料，设置团队和重点，生成大纲与逐页描述。
                      </p>
                      <button
                        className="edu-primary"
                        disabled={pending || busy}
                        onClick={() => launch("plan")}
                      >
                        <Sparkles size={17} />
                        生成内容 · 约 {snap.estimates.plan?.amount} 积分
                      </button>
                      <small>
                        默认 47 页是可调整的内容预设，不是比赛要求。
                      </small>
                    </div>
                  ) : (
                    <div className="edu-page-workspace">
                      <div className="edu-page-list">
                        {draft.pages.map((p, i) => (
                          <button
                            key={p.id}
                            className={p.id === selected ? "active" : ""}
                            onClick={() => setSelected(p.id)}
                          >
                            <span className="edu-page-number">
                              {String(i + 1).padStart(2, "0")}
                            </span>
                            <span>
                              {p.title}
                              <small>
                                {chapters[p.chapter]}
                                {p.locked ? " · 已锁定" : ""}
                              </small>
                            </span>
                            {snap.pages.find((x) => x.page_id === p.id)
                              ?.generated_image_url && <Check size={12} />}
                          </button>
                        ))}
                        <button onClick={addPage} disabled={imageBusy}>
                          <Plus size={15} />
                          添加页面
                        </button>
                      </div>
                      {page && (
                        <article className="edu-page-editor">
                          <div className="edu-page-toolbar">
                            <span>
                              第{" "}
                              {draft.pages.findIndex((p) => p.id === page.id) +
                                1}{" "}
                              页
                            </span>
                            <label className="edu-inline">
                              <input
                                type="checkbox"
                                checked={trial.includes(page.id)}
                                onChange={(e) =>
                                  setTrial((ids) =>
                                    e.target.checked
                                      ? ids.length < 3
                                        ? [...ids, page.id]
                                        : ids
                                      : ids.filter((id) => id !== page.id),
                                  )
                                }
                              />
                              加入试稿（{trial.length}/3）
                            </label>
                            <button
                              aria-label="上移页面"
                              onClick={() => move(-1)}
                              disabled={imageBusy}
                            >
                              <ArrowUp size={15} />
                            </button>
                            <button
                              aria-label="下移页面"
                              onClick={() => move(1)}
                              disabled={imageBusy}
                            >
                              <ArrowDown size={15} />
                            </button>
                            <button
                              aria-label={page.locked ? "解锁页面" : "锁定页面"}
                              onClick={() => editPage({ locked: !page.locked })}
                            >
                              {page.locked ? (
                                <Lock size={15} />
                              ) : (
                                <Unlock size={15} />
                              )}
                            </button>
                            <button
                              aria-label="删除页面"
                              disabled={imageBusy}
                              onClick={() =>
                                update((d) => {
                                  d.pages = d.pages.filter(
                                    (p) => p.id !== selected,
                                  );
                                  d.bindings = d.bindings.filter(
                                    (b) => b.page_id !== selected,
                                  );
                                  setSelected(d.pages[0]?.id || "");
                                })
                              }
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                          <input
                            className="edu-page-title"
                            aria-label="页面标题"
                            value={page.title}
                            disabled={imageBusy}
                            onChange={(e) =>
                              editPage({
                                title: e.target.value,
                                team_page: isTeamPage(page),
                              })
                            }
                          />
                          <div className="edu-page-meta">
                            <select
                              aria-label="页面类型"
                              value={page.kind}
                              onChange={(e) =>
                                editPage({
                                  kind: e.target.value as EduPage["kind"],
                                })
                              }
                            >
                              <option value="cover">封面</option>
                              <option value="contents">目录</option>
                              <option value="transition">章节过渡</option>
                              <option value="content">内容页</option>
                            </select>
                            <select
                              aria-label="所属章节"
                              value={page.chapter}
                              onChange={(e) =>
                                editPage({ chapter: Number(e.target.value) })
                              }
                            >
                              {chapters.map((c, i) => (
                                <option key={c} value={i}>
                                  {c}
                                </option>
                              ))}
                            </select>
                          </div>
                          {page.kind === "content" && page.chapter === 0 && (
                            <label className="edu-inline">
                              <input
                                type="checkbox"
                                checked={isTeamPage(page)}
                                disabled={imageBusy}
                                onChange={(e) => {
                                  const checked = e.target.checked;
                                  update((d) => {
                                    d.pages = d.pages.map((p) =>
                                      p.id === page.id
                                        ? { ...p, team_page: checked }
                                        : p,
                                    );
                                    if (!checked)
                                      d.bindings = d.bindings.filter(
                                        (b) =>
                                          b.page_id !== page.id ||
                                          b.purpose !== "person",
                                      );
                                  });
                                }}
                              />
                              团队介绍页 · 绑定成员照片
                            </label>
                          )}
                          {
                            <div className="edu-page-roles">
                              <span>关联岗位</span>
                              {draft.profile.roles.map((r, i) => (
                                <label key={r.id} className="edu-inline">
                                  <input
                                    type="checkbox"
                                    disabled={imageBusy}
                                    checked={
                                      page.role_ids?.includes(r.id) || false
                                    }
                                    onChange={(e) =>
                                      editPage({
                                        role_ids: e.target.checked
                                          ? [...(page.role_ids || []), r.id]
                                          : (page.role_ids || []).filter(
                                              (id) => id !== r.id,
                                            ),
                                      })
                                    }
                                  />
                                  {r.name || `岗位 ${i + 1}`}
                                </label>
                              ))}
                            </div>
                          }
                          {isTeamPage(page) && (
                            <TeamPhotos
                              pageId={page.id}
                              roles={draft.profile.roles}
                              bindings={draft.bindings}
                              materials={materials}
                              disabled={pending || imageBusy}
                              onUpload={(file, id) => uploadAsset(file, id)}
                              onChooseLongTerm={
                                LONG_TERM_SELECTION_ENABLED
                                  ? (id) =>
                                      setLibraryTarget({
                                        kind: "material",
                                        pageId: page.id,
                                        purpose: "person",
                                        roleId: id,
                                        label: `团队介绍 · ${draft.profile.roles.find((r) => r.id === id)?.member_name || draft.profile.roles.find((r) => r.id === id)?.name || "当前成员"}的照片`,
                                      })
                                  : undefined
                              }
                              onRemovePhoto={(id) =>
                                update((d) => {
                                  d.bindings = d.bindings.filter(
                                    (b) =>
                                      !(
                                        b.page_id === page.id &&
                                        b.purpose === "person" &&
                                        b.role_id === id
                                      ),
                                  );
                                })
                              }
                              onEdit={(id, values) =>
                                update((d) => {
                                  d.profile.roles = d.profile.roles.map((r) =>
                                    r.id === id ? { ...r, ...values } : r,
                                  );
                                })
                              }
                              onAdd={() =>
                                update((d) => {
                                  d.profile.roles.push({
                                    id: crypto.randomUUID(),
                                    name: "",
                                    responsibility: "",
                                    member_name: "",
                                  });
                                })
                              }
                              onRemove={(id) =>
                                update((d) => {
                                  d.profile.roles = d.profile.roles.filter(
                                    (r) => r.id !== id,
                                  );
                                  d.bindings = d.bindings.filter(
                                    (b) => b.role_id !== id,
                                  );
                                  d.pages = d.pages.map((p) => ({
                                    ...p,
                                    role_ids: (p.role_ids || []).filter(
                                      (r) => r !== id,
                                    ),
                                  }));
                                })
                              }
                              onSwap={(source, target) =>
                                update((d) => {
                                  d.bindings = d.bindings.map((b) =>
                                    b.page_id === page.id &&
                                    b.purpose === "person"
                                      ? {
                                          ...b,
                                          role_id:
                                            b.role_id === source
                                              ? target
                                              : b.role_id === target
                                                ? source
                                                : b.role_id,
                                        }
                                      : b,
                                  );
                                })
                              }
                            />
                          )}
                          {rendered?.status === "FAILED" && (
                            <button
                              disabled={pending || busy}
                              onClick={() =>
                                launch("images", { page_ids: [page.id] })
                              }
                            >
                              重试本页 · 约 {snap.image_unit_estimate} 积分
                            </button>
                          )}
                          {rendered?.generated_image_url && (
                            <figure className="edu-slide-preview">
                              <img
                                src={`${rendered.generated_image_url}?v=${encodeURIComponent(rendered.updated_at)}`}
                                alt={`${page.title}试稿`}
                              />
                              <figcaption>
                                已生成页面 · 修改文字或风格后需重新生成
                              </figcaption>
                            </figure>
                          )}
                          {tab === "outline" ? (
                            <>
                              <label className="edu-field">
                                展示用途
                                <input
                                  value={page.purpose}
                                  disabled={imageBusy}
                                  onChange={(e) =>
                                    editPage({ purpose: e.target.value })
                                  }
                                />
                              </label>
                              <label className="edu-field">
                                页面文字
                                <textarea
                                  rows={9}
                                  value={page.text.join("\n")}
                                  disabled={imageBusy}
                                  onChange={(e) =>
                                    editPage({
                                      text: e.target.value.split("\n"),
                                    })
                                  }
                                />
                              </label>
                              <div className="edu-hint">
                                一页一个主题。解释与现场动作放在逐页描述的配套提示中。
                              </div>
                            </>
                          ) : tab === "detail" ? (
                            <>
                              {(
                                [
                                  "text",
                                  "layout",
                                  "materials",
                                  "speaker_notes",
                                  "action_notes",
                                ] as const
                              ).map((key, i) => (
                                <label className="edu-field" key={key}>
                                  {
                                    [
                                      "页面文字",
                                      "画面与版式",
                                      "素材要求",
                                      "讲稿提示（不上屏）",
                                      "现场动作（不上屏）",
                                    ][i]
                                  }
                                  <textarea
                                    rows={key === "layout" ? 5 : 3}
                                    value={page[key].join("\n")}
                                    disabled={imageBusy}
                                    onChange={(e) =>
                                      editPage({
                                        [key]: e.target.value
                                          ? e.target.value.split("\n")
                                          : [],
                                      })
                                    }
                                  />
                                </label>
                              ))}
                            </>
                          ) : (
                            <>
                              <h3>本页素材</h3>
                              <div className="edu-asset-controls">
                                <select
                                  aria-label="素材用途"
                                  value={assetPurpose}
                                  onChange={(e) =>
                                    setAssetPurpose(
                                      e.target.value as Binding["purpose"],
                                    )
                                  }
                                >
                                  <option value="reference">参考图</option>
                                  <option value="product">产品图</option>
                                  <option value="screenshot">系统截图</option>
                                  <option value="certificate">
                                    证书与证据
                                  </option>
                                  {isTeamPage(page) && (
                                    <option value="person">成员照片</option>
                                  )}
                                </select>
                                {assetPurpose === "person" && (
                                  <select
                                    aria-label="照片对应岗位"
                                    value={roleId || draft.profile.roles[0].id}
                                    onChange={(e) => setRoleId(e.target.value)}
                                  >
                                    {draft.profile.roles.map((r, i) => (
                                      <option key={r.id} value={r.id}>
                                        {r.name || `岗位 ${i + 1}`}
                                      </option>
                                    ))}
                                  </select>
                                )}
                                <button
                                  disabled={pending || imageBusy}
                                  onClick={() => assetInput.current?.click()}
                                >
                                  <ImagePlus size={15} />
                                  上传并绑定
                                </button>
                                <input
                                  ref={assetInput}
                                  hidden
                                  type="file"
                                  accept="image/png,image/jpeg,image/webp"
                                  onChange={(e) => {
                                    uploadAsset(e.target.files?.[0]);
                                    e.target.value = "";
                                  }}
                                />
                                {LONG_TERM_SELECTION_ENABLED && (<button
                                  className="edu-library-button"
                                  disabled={pending || busy}
                                  onClick={() =>
                                    setLibraryTarget({
                                      kind: "material",
                                      pageId: page.id,
                                      purpose: assetPurpose,
                                      roleId:
                                        roleId || draft.profile.roles[0]?.id,
                                      label: `“${page.title}”页面素材`,
                                    })
                                  }
                                >
                                  从长期文件选择
                                </button>)}
                              </div>
                              <div className="edu-assets">
                                {draft.bindings
                                  .filter((b) => b.page_id === selected)
                                  .map((b, i) => {
                                    const m = materials.find(
                                      (m) => m.id === b.material_id,
                                    );
                                    return (
                                      <div key={`${b.material_id}-${i}`}>
                                        {m && (
                                          <img src={m.url} alt={m.filename} />
                                        )}
                                        <span>
                                          {m?.filename || "素材"} · {b.purpose}
                                        </span>
                                        <button
                                          onClick={() =>
                                            update((d) => {
                                              d.bindings = d.bindings.filter(
                                                (x) =>
                                                  !(
                                                    x.page_id === b.page_id &&
                                                    x.material_id ===
                                                      b.material_id
                                                  ),
                                              );
                                            })
                                          }
                                        >
                                          解除绑定
                                        </button>
                                      </div>
                                    );
                                  })}
                                <div className="edu-asset-placeholder">
                                  <ImagePlus size={25} />
                                  <span>缺少真实素材时保留占位</span>
                                </div>
                              </div>
                              <h3>证据与待补项</h3>
                              <button
                                disabled={imageBusy}
                                onClick={() =>
                                  update((d) => {
                                    d.checklist.push({
                                      category: "missing",
                                      page_ids: [selected],
                                      content: "待补事项",
                                      status: "待核验",
                                      basis: "暂无依据",
                                      action: "请填写补充办法",
                                    });
                                  })
                                }
                              >
                                添加本页待补项
                              </button>
                              {draft.checklist.map((c, i) =>
                                !c.page_ids.length ||
                                c.page_ids.includes(selected) ? (
                                  <div className="edu-evidence" key={i}>
                                    <span className={`edu-tag ${c.category}`}>
                                      {c.status}
                                    </span>
                                    <strong>{c.content}</strong>
                                    <p>依据：{c.basis}</p>
                                    <p>处理：{c.action}</p>
                                    <details>
                                      <summary>编辑事项与依据</summary>
                                      {(
                                        [
                                          "content",
                                          "status",
                                          "basis",
                                          "action",
                                        ] as const
                                      ).map((key, j) => (
                                        <label className="edu-field" key={key}>
                                          {
                                            [
                                              "事项",
                                              "核验状态",
                                              "来源依据",
                                              "补充办法",
                                            ][j]
                                          }
                                          <input
                                            disabled={imageBusy}
                                            value={c[key]}
                                            onChange={(e) =>
                                              update((d) => {
                                                d.checklist[i][key] =
                                                  e.target.value;
                                              })
                                            }
                                          />
                                        </label>
                                      ))}
                                      <button
                                        onClick={() =>
                                          update((d) => {
                                            d.checklist[i].page_ids = [
                                              selected,
                                            ];
                                          })
                                        }
                                      >
                                        关联当前页
                                      </button>
                                      <button
                                        onClick={() =>
                                          update((d) => {
                                            d.checklist.splice(i, 1);
                                          })
                                        }
                                      >
                                        删除事项
                                      </button>
                                    </details>
                                  </div>
                                ) : null,
                              )}
                              {!draft.checklist.length && (
                                <p className="edu-hint">
                                  当前未列出清单，不代表材料已核验。
                                </p>
                              )}
                              <label className="edu-field">
                                本页待补素材
                                <textarea
                                  rows={4}
                                  value={page.materials.join("\n")}
                                  onChange={(e) =>
                                    editPage({
                                      materials: e.target.value.split("\n"),
                                    })
                                  }
                                />
                              </label>
                            </>
                          )}
                        </article>
                      )}
                    </div>
                  )}
                </div>
                <footer className="edu-generation">
                  <div className="edu-task-status" role="status">
                    {busy ? (
                      <>
                        <span className="edu-spinner" />
                        {(active(editor?.task) ? editor?.task : snap.task)
                          ?.progress.current_step || "正在生成页面"}{" "}
                        <span>
                          {(active(editor?.task) ? editor?.task : snap.task)
                            ?.progress.completed || 0}{" "}
                          /{" "}
                          {(active(editor?.task) ? editor?.task : snap.task)
                            ?.progress.total || 0}
                        </span>
                      </>
                    ) : snap.task?.status === "FAILED" ? (
                      <span className="edu-error-text">
                        {snap.task.error_message}
                      </span>
                    ) : (
                      <span>
                        {draft.pages.length
                          ? `${snap.pages.filter((p) => p.generated_image_url).length} / ${draft.pages.length} 页已生成`
                          : "内容生成后，可选择三页试稿"}
                      </span>
                    )}
                  </div>
                  {!busy && !!snap.task?.progress.failed && (
                    <span className="edu-error-text">
                      {snap.task.progress.failed}{" "}
                      页未生成成功，成功页面已保留；可选择失败页重试。
                    </span>
                  )}
                  <div className="edu-main-actions">
                    <button
                      disabled={pending || busy || !draft.pages.length}
                      onClick={() => launch("plan")}
                    >
                      <Sparkles size={15} />
                      更新内容
                    </button>
                    <button
                      className="edu-primary"
                      disabled={pending || busy || !trial.length}
                      onClick={() => launch("images", { page_ids: trial })}
                    >
                      三页试稿 · 约{" "}
                      {trial.filter((id) =>
                        snap.remaining_page_ids.includes(id),
                      ).length * snap.image_unit_estimate}{" "}
                      积分
                    </button>
                    <button
                      className="edu-primary secondary"
                      disabled={
                        pending || busy || !snap.remaining_page_ids.length
                      }
                      onClick={() =>
                        run(async () => {
                          const s = await save();
                          await submitOperation(
                            s.project_id,
                            "images",
                            s.revision,
                            { page_ids: s.remaining_page_ids },
                          );
                          await refresh();
                        })
                      }
                    >
                      生成剩余 · {snap.estimates.remaining?.amount || 0} 积分
                    </button>
                    <button
                      disabled={
                        pending ||
                        busy ||
                        !draft.pages.length ||
                        snap.remaining_page_ids.length > 0
                      }
                      onClick={() =>
                        run(async () => {
                          const s = await save();
                          if (s.remaining_page_ids.length)
                            throw new Error("修改已保存，请先生成更新后的页面");
                          if (editor?.ready && !editor.stale) {
                            navigate(`/project/${projectId}/editor`);
                            return;
                          }
                          await data(
                            "post",
                            `/api/projects/${projectId}/editable-generation`,
                            editor?.stale
                              ? {
                                  regenerate: true,
                                  base_revision: editor.revision,
                                }
                              : {},
                          );
                          await refresh();
                        })
                      }
                    >
                      {editor?.stale
                        ? "按新成稿重新转换"
                        : editor?.ready
                          ? "进入在线编辑"
                          : `生成可编辑 PPT · ${snap.estimates.editable?.amount || 0} 积分`}
                    </button>
                  </div>
                  <div className="edu-exports">
                    {editor?.stale && (
                      <span>图片已更新；重新转换将保留旧编辑版本。</span>
                    )}
                    <span>
                      <Download size={13} />
                      导出
                    </span>
                    <button
                      disabled={!draft.pages.length || pending}
                      onClick={() => exportText("outline")}
                    >
                      大纲
                    </button>
                    <button
                      disabled={!draft.pages.length || pending}
                      onClick={() => exportText("descriptions")}
                    >
                      逐页描述
                    </button>
                    <button
                      disabled={!draft.pages.length || pending}
                      onClick={() => exportText("checklist")}
                    >
                      待补清单
                    </button>
                    <button
                      disabled={
                        pending ||
                        !!snap.remaining_page_ids.length ||
                        !draft.pages.length ||
                        dirty
                      }
                      onClick={() =>
                        run(async () => {
                          const result = await data<{ download_url: string }>(
                            "get",
                            `/api/projects/${projectId}/export/pdf`,
                          );
                          await download(
                            result.download_url,
                            `${draft.profile.name}.pdf`,
                          );
                        })
                      }
                    >
                      PDF
                    </button>
                    {editor?.task?.progress.download_url && !editor.stale && (
                      <button
                        onClick={() =>
                          run(async () =>
                            download(
                              editor.task!.progress.download_url!,
                              `${draft.profile.name}.pptx`,
                            ),
                          )
                        }
                      >
                        初始可编辑 PPTX
                      </button>
                    )}
                    <button
                      onClick={() =>
                        run(async () => {
                          await save();
                          setRevisions(
                            await data("get", base(projectId) + "/revisions"),
                          );
                        })
                      }
                    >
                      内容版本
                    </button>
                  </div>
                </footer>
              </section>
            </div>
          </main>
        )}
      </div>
      {showImport && (
        <div className="edu-modal-backdrop">
          <section
            className="edu-modal"
            role="dialog"
            aria-modal="true"
            aria-label="导入已有稿"
          >
            <h2>导入已有大纲与逐页描述</h2>
            <p>
              使用“第 1 页：标题”分隔每页。先保留原文，再提示与五章预设的差异。
            </p>
            <div className="edu-import-columns">
              <label className="edu-field">
                大纲
                <textarea
                  rows={13}
                  value={outline}
                  onChange={(e) => setOutline(e.target.value)}
                />
                <input
                  type="file"
                  accept=".md,.txt"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void f.text().then(setOutline);
                  }}
                />
              </label>
              <label className="edu-field">
                逐页描述（可选）
                <textarea
                  rows={13}
                  value={descriptions}
                  onChange={(e) => setDescriptions(e.target.value)}
                />
                <input
                  type="file"
                  accept=".md,.txt"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void f.text().then(setDescriptions);
                  }}
                />
              </label>
            </div>
            <div className="edu-modal-actions">
              <button onClick={() => setShowImport(false)}>取消</button>
              <button
                className="edu-primary"
                disabled={!outline.trim() || pending || imageBusy}
                onClick={doImport}
              >
                保留原文导入
              </button>
            </div>
          </section>
        </div>
      )}
      {revisions && (
        <div className="edu-modal-backdrop">
          <section
            className="edu-modal small"
            role="dialog"
            aria-modal="true"
            aria-label="内容版本"
          >
            <h2>内容版本</h2>
            <p>
              恢复会形成新版本，原版本仍保留。图片需按恢复后的内容重新生成。
            </p>
            <div className="edu-revision-list">
              {revisions.map((r) => (
                <div key={r.revision}>
                  <span>
                    v{r.revision} ·{" "}
                    {new Date(r.created_at + "Z").toLocaleString()}
                  </span>
                  <button
                    disabled={pending || busy || r.revision === snap?.revision}
                    onClick={() =>
                      run(async () => {
                        if (!snap || !projectId) return;
                        accept(
                          await data("post", base(projectId) + "/restore", {
                            revision: snap.revision,
                            restore_revision: r.revision,
                          }),
                        );
                        setRevisions(null);
                      })
                    }
                  >
                    恢复
                  </button>
                </div>
              ))}
            </div>
            <button onClick={() => setRevisions(null)}>关闭</button>
          </section>
        </div>
      )}
      {libraryTarget && (
        <LongTermPicker
          kind={libraryTarget.kind}
          context={libraryTarget.label}
          excludeProjectId={projectId}
          onClose={() => setLibraryTarget(null)}
          onSelect={selectLibraryFile}
        />
      )}
    </div>
  );
}

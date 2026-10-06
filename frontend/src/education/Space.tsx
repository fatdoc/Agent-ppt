import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Download,
  FileText,
  FolderOpen,
  Image,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
  UploadCloud,
  Presentation,
  Eye,
} from "lucide-react";
import { data, download, failure } from "./api";
import { uploadMaterial, uploadReferenceFile } from "../api/endpoints";
import "./space.css";
import { FilePreview } from "./FilePreview";

type Category = "permanent" | "temporary" | "downloads" | "trash" | "projects";
export type SpaceItem = {
  key: string;
  id: string;
  kind: "project" | "material" | "reference" | "export";
  category: Category;
  name: string;
  updated_at: string;
  deleted_at?: string;
  format: string;
  size?: number;
  page_count?: number;
  status: string;
  busy?: boolean;
  can_trash: boolean;
  download_url?: string;
  projects: { id: string; name: string; trashed: boolean }[];
};
const tabs: { id: Category; label: string; hint: string; empty: string }[] = [
  {
    id: "permanent",
    label: "长期文件",
    hint: "可复用的素材与已关联作品的材料，长期保留。",
    empty: "还没有长期文件",
  },
  {
    id: "temporary",
    label: "临时文件",
    hint: "尚未关联作品的暂存材料。可转为长期文件，当前不会自动清理。",
    empty: "没有待整理的临时文件",
  },
  {
    id: "downloads",
    label: "下载记录",
    hint: "已导出的文件，可再次下载；这里不代表浏览器已保存成功。",
    empty: "还没有导出文件",
  },
  {
    id: "trash",
    label: "回收站",
    hint: "删除的作品和文件保留在这里，可随时恢复。当前不会自动清空。",
    empty: "回收站为空",
  },
  {
    id: "projects",
    label: "作品记录",
    hint: "查看制作进度，继续编辑你的竞赛演示文稿。",
    empty: "还没有作品",
  },
];
const api = "/api/competition/space";
const endpoint = (item: SpaceItem) =>
  `${api}/${item.kind}/${encodeURIComponent(item.id)}`;
const size = (n?: number) =>
  n == null
    ? "—"
    : n < 1024
      ? `${n} B`
      : n < 1048576
        ? `${(n / 1024).toFixed(1)} KB`
        : `${(n / 1048576).toFixed(1)} MB`;
const date = (v: string) =>
  new Date(v).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

export function EducationSpace({
  onChanged,
}: {
  onChanged: () => Promise<unknown>;
}) {
  const [category, setCategory] = useState<Category>("projects");
  const [items, setItems] = useState<SpaceItem[]>([]);
  const [query, setQuery] = useState("");
  const [format, setFormat] = useState("all");
  const [sort, setSort] = useState("latest");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<SpaceItem | null>(null);
  const [dialog, setDialog] = useState<{
    action: "rename" | "trash";
    item: SpaceItem;
  } | null>(null);
  const [name, setName] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const modal = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!dialog) return;
    const trigger = document.activeElement as HTMLElement | null;
    const focusTarget =
      modal.current?.querySelector<HTMLElement>("input, select") ||
      modal.current?.querySelector<HTMLElement>("button");
    focusTarget?.focus();
    return () => {
      if (trigger?.isConnected) trigger.focus();
    };
  }, [dialog]);
  const running = useRef(false);
  const current = tabs.find((t) => t.id === category)!;
  const reload = async () => {
    const response = await data<{ items: SpaceItem[] }>("get", api);
    setItems(response.items);
  };
  useEffect(() => {
    let alive = true;
    data<{ items: SpaceItem[] }>("get", api)
      .then((r) => {
        if (alive) setItems(r.items);
      })
      .catch((e) => {
        if (alive) setError(failure(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);
  const run = async (job: () => Promise<void>, message: string) => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await job();
      setDialog(null);
      setNotice(message);
    } catch (e) {
      setError(failure(e));
    } finally {
      try {
        await reload();
        await onChanged();
      } catch (e) {
        setError(failure(e));
      }
      running.current = false;
      setBusy(false);
    }
  };
  const mutate = (item: SpaceItem, action: string, extra = {}) =>
    data("patch", endpoint(item), { action, ...extra });
  const selectTab = (next: Category) => {
    setCategory(next);
    setQuery("");
    setFormat("all");
    setPage(1);
    setNotice("");
  };
  const upload = (files: File[]) =>
    run(async () => {
      for (const file of files) {
        const image = /\.(png|jpe?g|webp|gif)$/i.test(file.name);
        const response = image
          ? await uploadMaterial(file, null, false)
          : await uploadReferenceFile(file);
        const id = image
          ? (response.data as { id: string } | undefined)?.id
          : (response.data as { file: { id: string } } | undefined)?.file?.id;
        if (!id) throw new Error(`${file.name} 上传失败`);
        if (category === "permanent")
          await data(
            "patch",
            `${api}/${image ? "material" : "reference"}/${id}`,
            { action: "permanent" },
          );
      }
    }, "文件已上传");
  const filtered = items.filter((i) => i.category === category);
  const formats = [...new Set(filtered.map((i) => i.format))].sort();
  const result = filtered
    .filter(
      (i) =>
        (!query.trim() ||
          i.name.toLowerCase().includes(query.trim().toLowerCase())) &&
        (format === "all" || format === i.format),
    )
    .sort((a, b) =>
      sort === "name"
        ? a.name.localeCompare(b.name, "zh-CN")
        : (b.deleted_at || b.updated_at).localeCompare(
            a.deleted_at || a.updated_at,
          ),
    );
  const totalPages = Math.max(1, Math.ceil(result.length / 10));
  const activePage = Math.min(page, totalPages);
  const visible = result.slice((activePage - 1) * 10, activePage * 10);
  const openDialog = (action: "rename" | "trash", item: SpaceItem) => {
    setDialog({ action, item });
    setName(item.name);
    setError("");
  };
  const submitDialog = () => {
    if (!dialog) return;
    const { action, item } = dialog;
    run(
      async () => {
        await mutate(
          item,
          action,
          action === "rename" ? { name: name.trim() } : {},
        );
      },
      action === "trash" ? "已移入回收站，可在回收站恢复" : "名称已更新",
    );
  };
  return (
    <section className="education-space" aria-label="我的空间文件管理">
      <div className="space-tabs" role="tablist" aria-label="空间分类">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            id={`space-tab-${t.id}`}
            role="tab"
            disabled={busy}
            tabIndex={category === t.id ? 0 : -1}
            aria-controls="space-panel"
            aria-selected={category === t.id}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                e.preventDefault();
                const next =
                  tabs[
                    (tabs.findIndex((x) => x.id === t.id) +
                      (e.key === "ArrowRight" ? 1 : 4)) %
                      5
                  ].id;
                selectTab(next);
                document.getElementById(`space-tab-${next}`)?.focus();
              }
            }}
            onClick={() => selectTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id="space-panel"
        aria-labelledby={`space-tab-${category}`}
      >
        <div className="space-intro">
          <p>{current.hint}</p>
          <span>
            {filtered.length} {category === "projects" ? "个作品" : "条记录"}
          </span>
        </div>
        <div className="space-toolbar">
          {(category === "permanent" || category === "temporary") && (
            <button
              className="space-primary"
              disabled={busy}
              onClick={() => input.current?.click()}
            >
              <UploadCloud size={17} />
              上传文件
            </button>
          )}
          {category === "projects" && (
            <Link className="space-primary" to="/education/create">
              <Plus size={17} />
              新建作品
            </Link>
          )}
          <input
            hidden
            ref={input}
            type="file"
            multiple
            aria-label="上传空间文件"
            accept=".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.jpeg,.webp,.gif"
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              e.target.value = "";
              if (files.length) void upload(files);
            }}
          />
          <label className="space-search">
            <Search size={17} />
            <input
              aria-label="搜索空间内容"
              placeholder={
                category === "projects" ? "搜索作品名称" : "搜索文件名称"
              }
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
            />
          </label>
          {category !== "projects" && (
            <select
              aria-label="文件类型"
              value={format}
              onChange={(e) => {
                setFormat(e.target.value);
                setPage(1);
              }}
            >
              <option value="all">全部类型</option>
              {formats.map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
          )}
          <select
            aria-label="排序方式"
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setPage(1);
            }}
          >
            <option value="latest">最近更新</option>
            <option value="name">名称排序</option>
          </select>
          <button
            className="space-refresh"
            title="刷新列表"
            aria-label="刷新列表"
            disabled={busy || loading}
            onClick={() => run(async () => {}, "列表已刷新")}
          >
            <RefreshCw size={17} />
          </button>
        </div>
        {error && (
          <div role="alert" className="space-alert">
            {error}
            <button disabled={busy} onClick={() => run(async () => {}, "")}>
              重新加载
            </button>
          </div>
        )}
        {notice && (
          <div role="status" className="space-notice">
            {notice}
          </div>
        )}
        {busy && (
          <div role="status" className="space-pending">
            正在处理，请稍候…
          </div>
        )}
        {loading ? (
          <div className="space-empty" role="status">
            正在加载我的空间…
          </div>
        ) : (
          <>
            <div className="space-table-scroll">
              <table className="space-table">
                <thead>
                  <tr>
                    <th>{category === "projects" ? "作品名称" : "文件名称"}</th>
                    <th>{category === "projects" ? "页数" : "类型 / 大小"}</th>
                    <th>{category === "trash" ? "删除时间" : "更新时间"}</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((item) => (
                    <tr key={item.key}>
                      <td>
                        <div className="space-file">
                          <span className={`space-file-icon ${item.kind}`}>
                            {item.kind === "project" ? (
                              <Presentation size={23} />
                            ) : item.kind === "material" ? (
                              <Image size={23} />
                            ) : (
                              <FileText size={23} />
                            )}
                          </span>
                          <div>
                            <strong title={item.name}>{item.name}</strong>
                            <small>
                              {item.kind === "project"
                                ? "竞赛演示文稿"
                                : item.projects.length
                                  ? item.projects.map((p) => (
                                      <span key={p.id}>
                                        {p.trashed ? (
                                          `${p.name}（回收站）`
                                        ) : (
                                          <Link
                                            to={`/education/project/${p.id}`}
                                          >
                                            {p.name}
                                          </Link>
                                        )}{" "}
                                      </span>
                                    ))
                                  : category === "temporary"
                                    ? "尚未关联作品"
                                    : "个人文件"}
                            </small>
                          </div>
                        </div>
                      </td>
                      <td>
                        {item.kind === "project" ? (
                          `${item.page_count || 0} 页`
                        ) : (
                          <>
                            {item.format}
                            <small>{size(item.size)}</small>
                          </>
                        )}
                      </td>
                      <td className="space-date">
                        {date(item.deleted_at || item.updated_at)}
                      </td>
                      <td>
                        <span
                          className={`space-status ${item.busy ? "working" : ""}`}
                        >
                          {category === "trash" ? "可恢复" : item.status}
                        </span>
                      </td>
                      <td>
                        <div className="space-actions">
                          {category === "trash" ? (
                            <button
                              disabled={busy}
                              onClick={() =>
                                run(async () => {
                                  await mutate(item, "restore");
                                }, "已恢复到原分类")
                              }
                            >
                              恢复
                            </button>
                          ) : (
                            <>
                              {category === "permanent" &&
                                item.kind !== "project" &&
                                item.kind !== "export" && (
                                  <button
                                    disabled={busy || !item.download_url}
                                    onClick={() => setPreview(item)}
                                  >
                                    <Eye size={14} />
                                    预览
                                  </button>
                                )}
                              {item.kind === "project" ? (
                                <Link to={`/education/project/${item.id}`}>
                                  继续编辑
                                </Link>
                              ) : item.download_url ? (
                                <button
                                  disabled={busy}
                                  onClick={() =>
                                    run(async () => {
                                      await download(
                                        item.download_url!,
                                        item.name,
                                      );
                                    }, "下载已发起，请查看浏览器下载列表")
                                  }
                                >
                                  <Download size={14} />
                                  下载
                                </button>
                              ) : null}
                              {item.kind !== "export" && (
                                <button
                                  disabled={busy || item.busy}
                                  onClick={() => openDialog("rename", item)}
                                >
                                  重命名
                                </button>
                              )}
                              {category === "temporary" && (
                                <button
                                  disabled={busy || item.busy}
                                  onClick={() =>
                                    run(async () => {
                                      await mutate(item, "permanent");
                                    }, "已转为长期文件")
                                  }
                                >
                                  长期保存
                                </button>
                              )}
                              {item.kind !== "export" && (
                                <button
                                  className="space-delete"
                                  title={
                                    !item.can_trash
                                      ? "关联作品的材料或进行中的任务不能移入回收站"
                                      : "移入回收站"
                                  }
                                  disabled={busy || !item.can_trash}
                                  aria-label={`移入回收站：${item.name}`}
                                  onClick={() => openDialog("trash", item)}
                                >
                                  <Trash2 size={15} />
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!visible.length && !error && (
              <div className="space-empty">
                <FolderOpen size={46} strokeWidth={1.2} />
                <h2>
                  {query || format !== "all"
                    ? "没有找到匹配的内容"
                    : current.empty}
                </h2>
                <p>
                  {category === "downloads"
                    ? "在作品工作台导出 PPTX、PDF 或内容文档后，将显示在这里。"
                    : category === "trash"
                      ? "需要恢复的文件和作品会显示在这里。"
                      : "上传材料或创建作品后，可在这里集中管理。"}
                </p>
              </div>
            )}
            <footer className="space-pagination">
              <span>共 {result.length} 条</span>
              <div>
                <button
                  disabled={activePage === 1}
                  onClick={() => setPage(activePage - 1)}
                >
                  上一页
                </button>
                <span>
                  {activePage} / {totalPages}
                </span>
                <button
                  disabled={activePage === totalPages}
                  onClick={() => setPage(activePage + 1)}
                >
                  下一页
                </button>
              </div>
            </footer>
          </>
        )}
      </div>
      {dialog && (
        <div
          className="space-modal-backdrop"
          onKeyDown={(e) => {
            if (e.key === "Escape" && !busy) setDialog(null);
            if (e.key === "Tab") {
              const nodes = Array.from(
                modal.current?.querySelectorAll<HTMLElement>(
                  "button:not(:disabled), input, select",
                ) || [],
              );
              const first = nodes[0],
                last = nodes[nodes.length - 1];
              if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last?.focus();
              } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first?.focus();
              }
            }
          }}
        >
          <section
            ref={modal}
            className="space-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="space-dialog-title"
          >
            <header>
              <h2 id="space-dialog-title">
                {dialog.action === "rename" ? "重命名" : "移入回收站"}
              </h2>
              <button
                aria-label="关闭弹窗"
                disabled={busy}
                onClick={() => setDialog(null)}
              >
                <X size={20} />
              </button>
            </header>
            {dialog.action === "rename" ? (
              <label>
                新名称
                <input
                  autoFocus
                  maxLength={200}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
            ) : (
              <p>
                将“{dialog.item.name}”移入回收站？文件与内容会保留，可随时恢复。
              </p>
            )}
            {error && <p role="alert">{error}</p>}
            <footer>
              <button disabled={busy} onClick={() => setDialog(null)}>
                取消
              </button>
              <button
                className="space-primary"
                disabled={busy || (dialog.action === "rename" && !name.trim())}
                onClick={submitDialog}
              >
                {busy ? "处理中…" : "确认"}
              </button>
            </footer>
          </section>
        </div>
      )}
      {preview && (
        <FilePreview
          key={preview.key}
          item={preview}
          onClose={() => setPreview(null)}
        />
      )}
    </section>
  );
}

import { useEffect, useRef, useState } from "react";
import { FileText, Search, X } from "lucide-react";
import { data, failure } from "./api";
import { FilePreview } from "./FilePreview";
import type { SpaceItem } from "./Space";
import "./long-term-picker.css";

// Deferred until the core PPT creation and editable export flow is accepted.
export const LONG_TERM_SELECTION_ENABLED = false;

type Props = {
  kind: "reference" | "material";
  context: string;
  excludeIds?: string[];
  excludeProjectId?: string;
  onSelect: (item: SpaceItem) => Promise<void>;
  onClose: () => void;
};
export function LongTermPicker({
  kind,
  context,
  excludeIds = [],
  excludeProjectId,
  onSelect,
  onClose,
}: Props) {
  const [items, setItems] = useState<SpaceItem[]>([]),
    [query, setQuery] = useState(""),
    [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  const [preview, setPreview] = useState<SpaceItem | null>(null);
  const modal = useRef<HTMLElement>(null),
    running = useRef(false);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    data<{ items: SpaceItem[] }>("get", "/api/competition/space")
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
  }, [retry]);
  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    modal.current?.querySelector<HTMLInputElement>("input")?.focus();
    return () => {
      if (trigger?.isConnected) trigger.focus();
    };
  }, []);
  const available = items.filter(
    (i) =>
      i.category === "permanent" &&
      i.kind === kind &&
      !excludeIds.includes(i.id) &&
      (!excludeProjectId ||
        !i.projects.some((p) => p.id === excludeProjectId)) &&
      (kind !== "material" ||
        ["PNG", "JPG", "JPEG", "WEBP", "GIF", "BMP"].includes(i.format)),
  );
  const visible = available.filter((i) =>
    i.name.toLowerCase().includes(query.trim().toLowerCase()),
  );
  const chosen = available.find((i) => i.id === selected);
  const confirm = async () => {
    if (!chosen || running.current) return;
    running.current = true;
    setBusy(true);
    setError("");
    try {
      await onSelect(chosen);
      onClose();
    } catch (e) {
      setError(failure(e));
    } finally {
      running.current = false;
      setBusy(false);
    }
  };
  return (
    <>
      <div
        className="library-backdrop"
        onKeyDown={(e) => {
          if (preview) return;
          if (e.key === "Escape" && !busy) {
            e.stopPropagation();
            onClose();
          }
          if (e.key === "Tab") {
            const nodes = Array.from(
              modal.current?.querySelectorAll<HTMLElement>(
                'button:not(:disabled),input:not(:disabled),[tabindex="0"]',
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
          role="dialog"
          aria-modal="true"
          aria-labelledby="library-title"
          className="library-modal"
        >
          <header>
            <div>
              <h2 id="library-title">从长期文件选择</h2>
              <p>{context}</p>
            </div>
            <button
              disabled={busy}
              aria-label="关闭长期文件选择"
              onClick={onClose}
            >
              <X size={20} />
            </button>
          </header>
          <label className="library-search">
            <Search size={17} />
            <input
              aria-label="搜索长期文件"
              placeholder={
                kind === "material" ? "搜索图片名称" : "搜索文档名称"
              }
              value={query}
              disabled={busy}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <p className="library-hint">
            {kind === "material" ? "仅显示可用图片。" : "仅显示文档材料。"}
            选择后用于当前步骤，原文件仍保留在长期文件中。
          </p>
          {error && (
            <div role="alert" className="library-error">
              {error}
              <button disabled={busy} onClick={() => setRetry((n) => n + 1)}>
                刷新列表
              </button>
            </div>
          )}
          <div className="library-list">
            {loading ? (
              <p role="status">正在加载长期文件…</p>
            ) : visible.length ? (
              visible.map((i) => (
                <div
                  key={i.key}
                  className={`library-row ${selected === i.id ? "selected" : ""}`}
                >
                  <label>
                    <input
                      type="radio"
                      name="long-term-file"
                      aria-label={`选择 ${i.name}`}
                      checked={selected === i.id}
                      disabled={busy || !i.download_url || i.busy}
                      onChange={() => setSelected(i.id)}
                    />
                    <FileText size={23} />
                    <span>
                      <strong>{i.name}</strong>
                      <small>
                        {i.format} ·{" "}
                        {i.size == null
                          ? "大小未知"
                          : `${(i.size / 1024).toFixed(0)} KB`}
                        {!i.download_url
                          ? " · 文件不可用"
                          : i.busy
                            ? " · 处理中"
                            : ""}
                      </small>
                    </span>
                  </label>
                  <button
                    disabled={busy || !i.download_url}
                    onClick={() => setPreview(i)}
                  >
                    预览
                  </button>
                </div>
              ))
            ) : (
              <div className="library-empty">
                <FileText size={38} />
                <p>
                  {query
                    ? "没有找到匹配的文件"
                    : `暂无可选择的长期${kind === "material" ? "图片" : "文档"}`}
                </p>
                <small>
                  可以取消后上传本地文件，或到“我的空间 →
                  长期文件”保存常用材料。
                </small>
              </div>
            )}
          </div>
          <footer>
            <span>
              {chosen
                ? `已选择：${chosen.name}`
                : `${available.length} 个可用文件`}
            </span>
            <button disabled={busy} onClick={onClose}>
              取消
            </button>
            <button
              className="library-confirm"
              disabled={
                !chosen ||
                busy ||
                loading ||
                !chosen.download_url ||
                chosen.busy
              }
              onClick={confirm}
            >
              {busy ? "正在添加…" : "确认选择"}
            </button>
          </footer>
        </section>
      </div>
      {preview && (
        <FilePreview item={preview} onClose={() => setPreview(null)} />
      )}
    </>
  );
}

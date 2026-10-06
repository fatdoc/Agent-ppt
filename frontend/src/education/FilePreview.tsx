import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Download, FileText, X } from "lucide-react";
import { apiClient } from "../api/client";
import { data, download, failure } from "./api";
import type { SpaceItem } from "./Space";
import "./file-preview.css";

type Preview = {
  kind: "image" | "pdf" | "text" | "unsupported";
  text?: string;
  note?: string;
  truncated?: boolean;
  page_count?: number;
  width?: number;
  height?: number;
};

/** Blob requests use the same cookie/access-code handling as the rest of the app. */
function PreviewImage({
  url,
  alt,
  pdf,
}: {
  url: string;
  alt: string;
  pdf: boolean;
}) {
  const [source, setSource] = useState("");
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let alive = true,
      objectUrl = "";
    setSource("");
    setError("");
    apiClient
      .get(url, { responseType: "blob", signal: controller.signal })
      .then((response) => {
        if (!alive) return;
        if (!response.data.type.startsWith("image/"))
          throw new Error("文件内容不是可显示的图片");
        objectUrl = URL.createObjectURL(response.data);
        setSource(objectUrl);
      })
      .catch((e) => {
        if (alive) setError(failure(e));
      });
    return () => {
      alive = false;
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, retry]);
  return (
    <div className={`file-preview-image ${pdf ? "pdf" : ""}`}>
      {error ? (
        <div role="alert">
          <p>预览加载失败：{error}</p>
          <button onClick={() => setRetry((n) => n + 1)}>重试加载</button>
        </div>
      ) : source ? (
        <img
          src={source}
          alt={alt}
          onError={() => setError("图片无法显示，请下载原文件查看")}
        />
      ) : (
        <p role="status">正在加载{pdf ? "页面" : "图片"}…</p>
      )}
    </div>
  );
}

export function FilePreview({
  item,
  onClose,
}: {
  item: SpaceItem;
  onClose: () => void;
}) {
  const [info, setInfo] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [retry, setRetry] = useState(0);
  const [downloading, setDownloading] = useState(false);
  const [message, setMessage] = useState("");
  const modal = useRef<HTMLElement>(null);
  const endpoint = `/api/competition/space/${item.kind}/${encodeURIComponent(item.id)}/preview`;
  useEffect(() => {
    let alive = true;
    setInfo(null);
    setError("");
    setPage(1);
    data<Preview>("get", endpoint)
      .then((result) => {
        if (alive) setInfo(result);
      })
      .catch((e) => {
        if (alive) setError(failure(e));
      });
    return () => {
      alive = false;
    };
  }, [endpoint, retry]);
  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null;
    modal.current
      ?.querySelector<HTMLElement>('[aria-label="关闭预览"]')
      ?.focus();
    return () => {
      if (trigger?.isConnected) trigger.focus();
    };
  }, []);
  const downloadOriginal = async () => {
    if (!item.download_url || downloading) return;
    setDownloading(true);
    setMessage("");
    try {
      await download(item.download_url, item.name);
      setMessage("下载已发起，请查看浏览器下载列表");
    } catch (e) {
      setMessage("下载失败：" + failure(e));
    } finally {
      setDownloading(false);
    }
  };
  return (
    <div
      className="file-preview-backdrop"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          onClose();
        }
        if (event.key === "Tab") {
          const nodes = Array.from(
            modal.current?.querySelectorAll<HTMLElement>(
              'button:not(:disabled), [tabindex="0"]',
            ) || [],
          );
          const first = nodes[0],
            last = nodes[nodes.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last?.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first?.focus();
          }
        }
      }}
    >
      <section
        ref={modal}
        className="file-preview-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="file-preview-title"
      >
        <header>
          <div>
            <FileText size={22} />
            <div>
              <h2 id="file-preview-title" title={item.name}>
                {item.name}
              </h2>
              <span>
                {info?.kind === "text" ? "文字预览" : "文件预览"} ·{" "}
                {item.format}
              </span>
            </div>
          </div>
          <div className="file-preview-actions">
            <button disabled={downloading} onClick={downloadOriginal}>
              <Download size={16} />
              {downloading ? "下载中…" : "下载原文件"}
            </button>
            <button aria-label="关闭预览" onClick={onClose}>
              <X size={21} />
            </button>
          </div>
        </header>
        {message && (
          <p className="file-preview-note" role="status">
            {message}
          </p>
        )}
        {info?.note && <p className="file-preview-note">{info.note}</p>}
        {error ? (
          <div className="file-preview-empty" role="alert">
            <p>{error}</p>
            <button onClick={() => setRetry((n) => n + 1)}>重试预览</button>
          </div>
        ) : !info ? (
          <div className="file-preview-empty" role="status">
            正在准备预览…
          </div>
        ) : (
          <>
            {info.kind === "image" && (
              <PreviewImage
                url={`${endpoint}?mode=image`}
                alt={`${item.name}预览`}
                pdf={false}
              />
            )}
            {info.kind === "pdf" && !!info.page_count && (
              <>
                <nav className="file-preview-pager" aria-label="PDF 翻页">
                  <button
                    aria-label="上一页预览"
                    disabled={page <= 1}
                    onClick={() => setPage((n) => n - 1)}
                  >
                    <ChevronLeft size={17} />
                  </button>
                  <span>
                    第 {page} / {info.page_count} 页
                  </span>
                  <button
                    aria-label="下一页预览"
                    disabled={page >= info.page_count}
                    onClick={() => setPage((n) => n + 1)}
                  >
                    <ChevronRight size={17} />
                  </button>
                </nav>
                <PreviewImage
                  key={page}
                  url={`${endpoint}?mode=image&page=${page}`}
                  alt={`${item.name}第${page}页`}
                  pdf
                />
              </>
            )}
            {info.kind === "text" && (
              <div
                className="file-preview-text"
                tabIndex={0}
                aria-label="文件文字内容"
              >
                <pre>{info.text || "没有可预览的文字内容。"}</pre>
                {info.truncated && (
                  <p className="file-preview-note">
                    内容较长，仅展示前 12 万字符；完整内容请下载原文件查看。
                  </p>
                )}
              </div>
            )}
            {(info.kind === "unsupported" ||
              (info.kind === "pdf" && !info.page_count)) && (
              <div className="file-preview-empty">
                <FileText size={42} />
                <p>
                  {info.kind === "pdf"
                    ? "PDF 没有可预览的页面。"
                    : "暂不支持直接展示此文件"}
                </p>
                <button onClick={downloadOriginal} disabled={downloading}>
                  下载原文件查看
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

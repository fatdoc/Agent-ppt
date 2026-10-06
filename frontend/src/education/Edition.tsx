import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import i18n from "../i18n";
import { apiClient, setAuthEdition } from "../api/client";
const EditionContext = createContext("general");
export const useEdition = () => useContext(EditionContext);
export function EditionProvider({ children }: { children: ReactNode }) {
  const [edition, setEdition] = useState<string | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let mounted = true;
    apiClient
      .get("/api/auth/config")
      .then(async (r) => {
        if (mounted) {
          const e = r.data.data?.edition || "general";
          setAuthEdition(e);
          if (e === "education") {
            document.title = "兰台 · 竞赛教育版";
            await i18n.changeLanguage("zh");
            document.documentElement.lang = "zh-CN";
          }
          setEdition(e);
        }
      })
      .catch(() => {
        if (mounted) setError(true);
      });
    return () => {
      mounted = false;
    };
  }, []);
  if (error)
    return (
      <div role="alert" style={{ padding: 40 }}>
        无法读取站点配置。
        <button onClick={() => location.reload()}>重试</button>
      </div>
    );
  if (!edition)
    return (
      <div role="status" style={{ padding: 40 }}>
        正在打开工作台…
      </div>
    );
  return (
    <EditionContext.Provider value={edition}>
      {children}
    </EditionContext.Provider>
  );
}

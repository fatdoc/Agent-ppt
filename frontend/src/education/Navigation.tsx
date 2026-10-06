import {
  GraduationCap,
  Home,
  Presentation,
  FolderOpen,
  LayoutTemplate,
  HelpCircle,
  Settings,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import type { MouseEvent } from "react";
import "./portal.css";
const links = [
  { to: "/education", label: "首页", icon: Home },
  { to: "/education/create", label: "智能演示", icon: Presentation },
  { to: "/education/projects", label: "我的空间", icon: FolderOpen },
  { to: "/education/templates", label: "模板中心", icon: LayoutTemplate },
  { to: "/education/help", label: "帮助中心", icon: HelpCircle },
  { to: "/settings", label: "设置", icon: Settings },
];
export function EducationNavigation({
  onNavigate,
}: {
  onNavigate?: (path: string) => void;
}) {
  const { pathname } = useLocation();
  const follow = (e: MouseEvent, path: string) => {
    if (onNavigate && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      onNavigate(path);
    }
  };
  return (
    <aside className="education-rail">
      <Link
        to="/education"
        className="education-rail-brand"
        aria-label="兰台首页"
        onClick={(e) => follow(e, "/education")}
      >
        <GraduationCap size={30} />
        <strong>兰台</strong>
      </Link>
      <nav aria-label="教育版导航">
        {links.map(({ to, label, icon: Icon }, i) => {
          const active =
            pathname === to ||
            (to === "/education/create" &&
              pathname.startsWith("/education/project/")) ||
            (to === "/education" && ["/", "/app"].includes(pathname));
          return (
            <Link
              key={to}
              to={to}
              aria-current={active ? "page" : undefined}
              className={`${active ? "active" : ""} ${i === 4 ? "rail-bottom" : ""}`}
              onClick={(e) => follow(e, to)}
            >
              <Icon size={23} strokeWidth={1.6} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

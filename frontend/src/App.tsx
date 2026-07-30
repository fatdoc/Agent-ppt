import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Home } from './pages/Home';
import { Landing } from './pages/Landing';
import { History } from './pages/History';
import { OutlineEditor } from './pages/OutlineEditor';
import { DetailEditor } from './pages/DetailEditor';
import { SlidePreview } from './pages/SlidePreview';
import { SettingsPage } from './pages/Settings';
import { PptEditor } from './pages/PptEditor';
import { useProjectStore } from './store/useProjectStore';
import { useToast, AccessCodeGuard } from './components/shared';
import { PlatformProvider } from './platform';
import { PlatformShell } from './components/platform';
import {
  AssetCenter,
  ExportCenter,
  OutlineTemplateCenter,
  ProjectRouteGate,
  TemplateLibrary,
  Workbench,
} from './pages/platform';

function App() {
  const { currentProject, syncProject, error, setError } = useProjectStore();
  const { show, ToastContainer } = useToast();

  // 恢复项目状态
  useEffect(() => {
    localStorage.removeItem('banana-auth-token');
    const savedProjectId = localStorage.getItem('currentProjectId');
    if (savedProjectId && !currentProject) {
      syncProject();
    }
  }, [currentProject, syncProject]);

  // 显示全局错误
  useEffect(() => {
    if (error) {
      show({ message: error, type: 'error' });
      setError(null);
    }
  }, [error, setError, show]);

  return (
    <AccessCodeGuard>
      <PlatformProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/app" element={<Navigate to="/workspace" replace />} />
            <Route path="/landing" element={<Navigate to="/" replace />} />
            <Route path="/history" element={<History />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/ppt-editor" element={<PptEditor />} />
            <Route element={<PlatformShell />}>
              <Route path="/workspace" element={<Workbench />} />
              <Route path="/generate" element={<Home embedded />} />
              <Route path="/outline-templates" element={<OutlineTemplateCenter />} />
              <Route path="/outline" element={<ProjectRouteGate target="outline" title="大纲规划" description="选择项目后进入真实大纲编辑、拖拽排序、AI 修改与页面计划流程。" />} />
              <Route path="/templates" element={<TemplateLibrary />} />
              <Route path="/editor" element={<ProjectRouteGate target="preview" title="在线编辑" description="选择项目后进入真实页面内容、图片、素材、讲解稿与导出编辑流程。" />} />
              <Route path="/assets" element={<AssetCenter />} />
              <Route path="/exports" element={<ExportCenter />} />
            </Route>
            <Route path="/project/:projectId/outline" element={<OutlineEditor />} />
            <Route path="/project/:projectId/detail" element={<DetailEditor />} />
            <Route path="/project/:projectId/preview" element={<SlidePreview />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <ToastContainer />
        </BrowserRouter>
      </PlatformProvider>
    </AccessCodeGuard>
  );
}

export default App;

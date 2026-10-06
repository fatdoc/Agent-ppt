import { useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { EditionProvider, useEdition } from './education/Edition';
const EducationWorkspace = lazy(() => import('./education/Workspace'));
import { Home } from './pages/Home';
import { Landing } from './pages/Landing';
import { History } from './pages/History';
import { OutlineEditor } from './pages/OutlineEditor';
import { DetailEditor } from './pages/DetailEditor';
import { SlidePreview } from './pages/SlidePreview';
import { SettingsPage } from './pages/Settings';
import { ApiDocsPage } from './pages/ApiDocs';
import { useProjectStore } from './store/useProjectStore';
import { useToast, AccessCodeGuard, AuthGuard } from './components/shared';

const PptistEditor = lazy(() => import('./pages/PptistEditor'));

function EditionEntry({landing=false}:{landing?:boolean}) {
  return useEdition()==='education' ? <Suspense fallback={<div>正在打开竞赛工作台…</div>}><EducationWorkspace /></Suspense> : landing ? <Landing /> : <Home />;
}
function EducationRoute(){
  return useEdition()==='education' ? <Suspense fallback={<div>正在打开竞赛工作台…</div>}><EducationWorkspace /></Suspense> : <Navigate to='/app' replace/>;
}
function EditionHistory() { return useEdition() === 'education' ? <Navigate to="/education/projects" replace /> : <History />; }
function App() {
  const { currentProject, syncProject, error, setError } = useProjectStore();
  const { show, ToastContainer } = useToast();

  // 恢复项目状态
  useEffect(() => {
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
    <EditionProvider><BrowserRouter>
      <AccessCodeGuard>
        <AuthGuard>
          <Routes>
            <Route path="/" element={<EditionEntry landing />} />
            <Route path="/app" element={<EditionEntry />} />
            <Route path="/landing" element={<Navigate to="/" replace />} />
            <Route path="/education" element={<EducationRoute />} />
            <Route path="/education/:section" element={<EducationRoute />} />
            <Route path="/education/project/:projectId" element={<EducationRoute />} />
            <Route path="/history" element={<EditionHistory />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/developer/api-docs" element={<ApiDocsPage />} />
            <Route path="/project/:projectId/outline" element={<OutlineEditor />} />
            <Route path="/project/:projectId/detail" element={<DetailEditor />} />
            <Route path="/project/:projectId/editor" element={<Suspense fallback={<div>正在加载编辑器…</div>}><PptistEditor /></Suspense>} />
            <Route path="/project/:projectId/preview" element={<SlidePreview />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <ToastContainer />
        </AuthGuard>
      </AccessCodeGuard>
    </BrowserRouter></EditionProvider>
  );
}

export default App;

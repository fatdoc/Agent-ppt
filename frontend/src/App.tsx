import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Home } from './pages/Home';
import { Landing } from './pages/Landing';
import { History } from './pages/History';
import { OutlineEditor } from './pages/OutlineEditor';
import { DetailEditor } from './pages/DetailEditor';
import { SlidePreview } from './pages/SlidePreview';
import { SettingsPage } from './pages/Settings';
import { useProjectStore } from './store/useProjectStore';
import { useToast, AccessCodeGuard, AuthGuard } from './components/shared';

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
    <BrowserRouter>
      <AccessCodeGuard>
        <AuthGuard>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/app" element={<Home />} />
            <Route path="/landing" element={<Navigate to="/" replace />} />
            <Route path="/history" element={<History />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/project/:projectId/outline" element={<OutlineEditor />} />
            <Route path="/project/:projectId/detail" element={<DetailEditor />} />
            <Route path="/project/:projectId/preview" element={<SlidePreview />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <ToastContainer />
        </AuthGuard>
      </AccessCodeGuard>
    </BrowserRouter>
  );
}

export default App;

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, FolderOpen } from 'lucide-react';
import { usePlatform } from '@/platform';

interface ProjectRouteGateProps {
  target: 'outline' | 'detail' | 'preview';
  title: string;
  description: string;
}

export const ProjectRouteGate = ({ target, title, description }: ProjectRouteGateProps) => {
  const navigate = useNavigate();
  const { projectContext } = usePlatform();

  useEffect(() => {
    if (projectContext.projectId) {
      navigate(`/project/${projectContext.projectId}/${target}`, { replace: true });
    }
  }, [navigate, projectContext.projectId, target]);

  if (projectContext.projectId) return null;

  return (
    <div className="grid min-h-screen place-items-center p-8">
      <div className="max-w-lg text-center">
        <span className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-blue-50 text-blue-600">
          <FolderOpen size={28} />
        </span>
        <h1 className="mt-5 text-2xl font-bold text-slate-950">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
        <button
          type="button"
          onClick={() => navigate('/workspace')}
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700"
        >
          <ArrowLeft size={17} /> 返回工作台关联项目
        </button>
      </div>
    </div>
  );
};

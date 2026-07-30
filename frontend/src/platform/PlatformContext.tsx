import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { COMPETITIONS, getCompetitionConfig } from './competitions';
import type { CompetitionConfig, PlatformProjectContext } from './types';
import { getProject, listCompetitionConfigs, persistPlatformContext } from '@/api/endpoints';

const STORAGE_KEY = 'banana-platform-project-context-v1';

const defaultContext: PlatformProjectContext = {
  projectName: '',
  competitionId: 'wvcc',
  competitionTypeId: 'championship',
  trackId: 'ai-application',
  themeId: 'ai-industry',
  targetPageCount: 39,
  style: '科技蓝',
  activeScoreDimensionIds: [],
};

interface PlatformContextValue {
  projectContext: PlatformProjectContext;
  competition: CompetitionConfig;
  competitions: CompetitionConfig[];
  updateProjectContext: (patch: Partial<PlatformProjectContext>) => void;
  selectCompetition: (competitionId: string) => void;
  resetProjectContext: () => void;
}

const PlatformContext = createContext<PlatformContextValue | null>(null);

const loadContext = (): PlatformProjectContext => {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? { ...defaultContext, ...JSON.parse(raw) } : defaultContext;
  } catch {
    return defaultContext;
  }
};

export const PlatformProvider = ({ children }: { children: ReactNode }) => {
  const [projectContext, setProjectContext] = useState<PlatformProjectContext>(loadContext);
  const [competitions, setCompetitions] = useState<CompetitionConfig[]>(COMPETITIONS);
  const hydratedProjectId = useRef<string | null>(null);
  const competition = useMemo(
    () => competitions.find((item) => item.id === projectContext.competitionId)
      ?? getCompetitionConfig(projectContext.competitionId),
    [competitions, projectContext.competitionId],
  );

  useEffect(() => {
    listCompetitionConfigs()
      .then((response) => {
        if (response.data?.competitions.length) setCompetitions(response.data.competitions);
      })
      .catch(() => {
        // Static configuration is the offline/startup fallback.
      });
  }, []);

  useEffect(() => {
    const projectId = projectContext.projectId;
    if (!projectId || hydratedProjectId.current === projectId) return;
    getProject(projectId)
      .then((response) => {
        if (response.data?.platform_context) {
          setProjectContext((current) => ({
            ...current,
            ...response.data!.platform_context,
            projectId,
            projectName: response.data?.project_title || current.projectName,
          }));
        }
      })
      .finally(() => {
        hydratedProjectId.current = projectId;
      });
  }, [projectContext.projectId]);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(projectContext));
  }, [projectContext]);

  useEffect(() => {
    const projectId = projectContext.projectId;
    if (!projectId || hydratedProjectId.current !== projectId) return;
    const timer = window.setTimeout(() => {
      persistPlatformContext(projectId, projectContext).catch(() => {
        // Local persistence remains available while backend is temporarily offline.
      });
    }, 500);
    return () => window.clearTimeout(timer);
  }, [projectContext]);

  const updateProjectContext = useCallback((patch: Partial<PlatformProjectContext>) => {
    setProjectContext((current) => ({ ...current, ...patch }));
  }, []);

  const selectCompetition = useCallback((competitionId: string) => {
    const next = competitions.find((item) => item.id === competitionId)
      ?? getCompetitionConfig(competitionId);
    setProjectContext((current) => ({
      ...current,
      competitionId: next.id,
      competitionTypeId: next.competitionTypes[0]?.id,
      trackId: next.tracks[0]?.id,
      themeId: next.themes[0]?.id,
      targetPageCount: next.recommendedPageCount ?? current.targetPageCount,
      outlineTemplateId: next.outlineTemplateIds?.[0],
      pptTemplateId: next.pptTemplateIds?.[0],
      activeScoreDimensionIds: next.scoreDimensions?.map((item) => item.id) ?? [],
    }));
  }, [competitions]);

  const resetProjectContext = useCallback(() => setProjectContext(defaultContext), []);

  const value = useMemo(
    () => ({
      projectContext,
      competition,
      competitions,
      updateProjectContext,
      selectCompetition,
      resetProjectContext,
    }),
    [competition, competitions, projectContext, resetProjectContext, selectCompetition, updateProjectContext],
  );

  return <PlatformContext.Provider value={value}>{children}</PlatformContext.Provider>;
};

export const usePlatform = () => {
  const value = useContext(PlatformContext);
  if (!value) throw new Error('usePlatform must be used inside PlatformProvider');
  return value;
};

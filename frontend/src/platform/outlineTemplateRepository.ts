import { useCallback, useEffect, useMemo, useState } from 'react';
import { SYSTEM_OUTLINE_TEMPLATES } from './outlineTemplates';
import type { OutlineTemplate } from './types';
import {
  createOutlineTemplate,
  deleteOutlineTemplate,
  duplicateOutlineTemplate,
  listOutlineTemplates,
  updateOutlineTemplate,
} from '@/api/endpoints';

const STORAGE_KEY = 'banana-outline-templates-v1';

const readUserTemplates = (): OutlineTemplate[] => {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
};

const persist = (templates: OutlineTemplate[]) => {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(templates));
};

export const useOutlineTemplateRepository = () => {
  const [userTemplates, setUserTemplates] = useState<OutlineTemplate[]>(readUserTemplates);
  const templates = useMemo(
    () => [...SYSTEM_OUTLINE_TEMPLATES, ...userTemplates],
    [userTemplates],
  );

  const commit = useCallback((next: OutlineTemplate[]) => {
    setUserTemplates(next);
    persist(next);
  }, []);

  useEffect(() => {
    listOutlineTemplates()
      .then((response) => {
        const remote = response.data?.templates ?? [];
        if (!remote.length) return;
        const localOnly = userTemplates.filter(
          (local) => !remote.some((item) => item.id === local.id),
        );
        commit([...remote, ...localOnly]);
      })
      .catch(() => {
        // Local templates remain available while the backend is offline.
      });
  }, []);

  const createTemplate = useCallback(async (template: OutlineTemplate) => {
    try {
      const response = await createOutlineTemplate(template);
      const created = response.data ?? template;
      commit([created, ...userTemplates]);
      return created;
    } catch {
      commit([template, ...userTemplates]);
      return template;
    }
  }, [commit, userTemplates]);

  const updateTemplate = useCallback(async (template: OutlineTemplate, changeNote = '编辑模板') => {
    const previous = userTemplates.find((item) => item.id === template.id);
    if (!previous) return template;
    try {
      const response = await updateOutlineTemplate(template, changeNote);
      const updated = response.data ?? template;
      commit(userTemplates.map((item) => item.id === template.id ? updated : item));
      return updated;
    } catch {
      // Keep the same version semantics for offline/local-only templates.
    }
    const now = new Date().toISOString();
    const version = previous.version + 1;
    const next: OutlineTemplate = {
      ...template,
      version,
      updatedAt: now,
      versions: [
        ...(previous.versions ?? []),
        {
          version: previous.version,
          createdAt: previous.updatedAt,
          changeNote,
          sections: previous.sections,
        },
      ],
    };
    commit(userTemplates.map((item) => item.id === template.id ? next : item));
    return next;
  }, [commit, userTemplates]);

  const duplicateTemplate = useCallback(async (source: OutlineTemplate) => {
    try {
      const response = await duplicateOutlineTemplate(source.id);
      if (response.data) {
        commit([response.data, ...userTemplates]);
        return response.data;
      }
    } catch {
      // System and local-only templates are copied locally as a fallback.
    }
    const now = new Date().toISOString();
    const copy: OutlineTemplate = {
      ...source,
      id: `outline-${Date.now()}`,
      name: `${source.name}（副本）`,
      supportScope: 'PRIVATE',
      status: 'DRAFT',
      version: 1,
      versions: [],
      createdBy: 'CURRENT_USER',
      createdAt: now,
      updatedAt: now,
    };
    commit([copy, ...userTemplates]);
    return copy;
  }, [commit, userTemplates]);

  const deleteTemplate = useCallback(async (id: string) => {
    try {
      await deleteOutlineTemplate(id);
    } catch {
      // A local-only template has no server record.
    }
    commit(userTemplates.filter((item) => item.id !== id));
  }, [commit, userTemplates]);

  const importTemplates = useCallback(async (incoming: OutlineTemplate[]) => {
    const normalized: OutlineTemplate[] = incoming.map((template, index) => ({
      ...template,
      id: `imported-${Date.now()}-${index}`,
      supportScope: template.supportScope ?? 'PRIVATE',
      status: template.status ?? 'DRAFT',
      createdBy: 'CURRENT_USER',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }));
    const imported = await Promise.all(normalized.map(async (template) => {
      try {
        const response = await createOutlineTemplate(template);
        return response.data ?? template;
      } catch {
        return template;
      }
    }));
    commit([...imported, ...userTemplates]);
    return imported;
  }, [commit, userTemplates]);

  return {
    templates,
    userTemplates,
    createTemplate,
    updateTemplate,
    duplicateTemplate,
    deleteTemplate,
    importTemplates,
  };
};

import { apiClient } from "../api/client";
export type Role = {
  id: string;
  name: string;
  responsibility: string;
  member_name?: string;
};
export type Profile = {
  name: string;
  track: string;
  education_level: string;
  duration: string;
  focus: string;
  roles: Role[];
  rule_year: string;
  rule_source: string;
};
export type EduPage = {
  id: string;
  title: string;
  kind: "cover" | "contents" | "transition" | "content";
  chapter: number;
  purpose: string;
  text: string[];
  layout: string[];
  materials: string[];
  speaker_notes: string[];
  action_notes: string[];
  role_ids?: string[];
  locked?: boolean;
  team_page?: boolean;
  original_description?: string;
};
export const isTeamPage = (p: EduPage) =>
  p.kind === "content" &&
  p.chapter === 0 &&
  (p.team_page ?? /团队|成员|team/i.test(p.title));
export type Checklist = {
  category: "fact" | "proposal" | "missing";
  page_ids: string[];
  content: string;
  status: string;
  basis: string;
  action: string;
};
export type Binding = {
  page_id: string;
  material_id: string;
  purpose: "person" | "product" | "screenshot" | "certificate" | "reference";
  role_id?: string;
};
export type Content = {
  schema_version: number;
  skill_version: string;
  profile: Profile;
  preferences: {
    complexity: string;
    pagination: string;
    target_pages: number;
    style: string;
  };
  locks: string[];
  raw_material: string;
  reference_file_ids: string[];
  pages: EduPage[];
  checklist: Checklist[];
  bindings: Binding[];
  messages: { id: string; role: string; text: string }[];
  questions: string[];
  warnings: string[];
  structure_mode: string;
  imported_outline: string;
  imported_descriptions: string;
};
export type EduTask = {
  task_id: string;
  task_type: string;
  status: string;
  error_message?: string;
  progress: {
    current_step?: string;
    completed?: number;
    failed?: number;
    total?: number;
    download_url?: string;
  };
};
export type Snapshot = {
  project_id: string;
  revision: number;
  content: Content;
  task: EduTask | null;
  warnings: string[];
  pages: {
    page_id: string;
    status: string;
    generated_image_url?: string;
    updated_at: string;
  }[];
  default_trial_page_ids: string[];
  remaining_page_ids: string[];
  template_image_path?: string;
  image_unit_estimate: number;
  styles: Record<string, { name: string; prompt: string }>;
  estimates: Record<string, { amount: number } | null>;
};
export const active = (task?: EduTask | null) =>
  !!task && ["PENDING", "PROCESSING", "RUNNING"].includes(task.status);
export const failure = (e: unknown): string => {
  const err = e as {
    response?: { data?: { error?: { message?: string } } };
    message?: string;
  };
  return (
    err.response?.data?.error?.message || err.message || "连接失败，请稍后重试"
  );
};
export async function data<T>(
  method: "get" | "post" | "patch" | "delete",
  url: string,
  body?: unknown,
): Promise<T> {
  const res = await apiClient.request({ method, url, data: body });
  if (!res.data.success) throw new Error(res.data.error?.message || "请求失败");
  return res.data.data;
}
export const base = (id: string) => `/api/projects/${id}/competition`;
export const load = (id: string) => data<Snapshot>("get", base(id));
export const create = () =>
  data<Snapshot>("post", "/api/competition/projects", {});
export const patch = (id: string, revision: number, content: Content) =>
  data<Snapshot>("patch", base(id), {
    revision,
    patch: {
      profile: content.profile,
      preferences: content.preferences,
      locks: content.locks,
      raw_material: content.raw_material,
      reference_file_ids: content.reference_file_ids,
      pages: content.pages,
      checklist: content.checklist,
      bindings: content.bindings,
    },
  });
export async function download(url: string, name: string) {
  const res = await apiClient.get(url, { responseType: "blob" });
  const objectUrl = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

/** Persist admission keys across uncertain network responses and browser refreshes. */
export async function submitOperation(
  projectId: string,
  action: string,
  revision: number,
  extra: Record<string, unknown> = {},
) {
  const storageKey = `education-request:${projectId}:${action}`;
  const input = JSON.stringify({ revision, ...extra });
  let cached: { input: string; request_key: string } | null = null;
  try {
    cached = JSON.parse(sessionStorage.getItem(storageKey) || "null");
  } catch {
    /* discard invalid cache */
  }
  const request_key =
    cached?.input === input ? cached.request_key : crypto.randomUUID();
  sessionStorage.setItem(storageKey, JSON.stringify({ input, request_key }));
  const result = await data("post", base(projectId) + "/" + action, {
    revision,
    request_key,
    ...extra,
  });
  sessionStorage.removeItem(storageKey);
  return result;
}

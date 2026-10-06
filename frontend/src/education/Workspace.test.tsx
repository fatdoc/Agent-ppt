import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import Workspace from "./Workspace";
import { uploadReferenceFile, triggerFileParse } from "../api/endpoints";
import { load, patch, data, type Snapshot } from "./api";
vi.mock("./api", async () => ({
  ...(await vi.importActual<typeof import("./api")>("./api")),
  load: vi.fn(),
  patch: vi.fn(),
  data: vi.fn(),
}));
vi.mock("../api/endpoints", () => ({
  listProjectReferenceFiles: vi.fn().mockResolvedValue({ data: { files: [] } }),
  uploadReferenceFile: vi.fn(),
  uploadMaterial: vi.fn(),
  triggerFileParse: vi.fn(),
}));
const fixture = (): Snapshot => ({
  project_id: "p",
  revision: 1,
  content: {
    schema_version: 1,
    skill_version: "test",
    profile: {
      name: "测试",
      track: "",
      education_level: "",
      duration: "",
      focus: "",
      roles: [{ id: "r", name: "操作", responsibility: "" }],
      rule_year: "",
      rule_source: "",
    },
    preferences: {
      complexity: "balanced",
      pagination: "skill",
      target_pages: 47,
      style: "minimal",
    },
    locks: [],
    raw_material: "原始材料",
    reference_file_ids: [],
    pages: [],
    checklist: [],
    bindings: [],
    messages: [],
    questions: [],
    warnings: [],
    structure_mode: "skill",
    imported_outline: "",
    imported_descriptions: "",
  },
  task: null,
  warnings: [],
  pages: [],
  default_trial_page_ids: [],
  remaining_page_ids: [],
  styles: { minimal: { name: "简洁白", prompt: "" } },
  image_unit_estimate: 100,
  estimates: {},
});
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(data).mockImplementation(async (_method, url) =>
    url === "/api/competition/projects"
      ? []
      : url.endsWith("/materials")
        ? { materials: [] }
        : { ready: false, task: null },
  );
});
afterEach(() => {
  vi.useRealTimers();
});
it("a background refresh cannot silently advance the revision of an unsaved draft", async () => {
  let server = fixture();
  vi.mocked(load).mockImplementation(async () => structuredClone(server));
  vi.mocked(patch).mockRejectedValue({
    response: {
      data: { error: { message: "内容已更新，请载入最新版本后重试" } },
    },
  });
  render(
    <MemoryRouter initialEntries={["/education/project/p"]}>
      <Routes>
        <Route path="/education/project/:projectId" element={<Workspace />} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByDisplayValue("原始材料");
  await waitFor(() => expect(load).toHaveBeenCalledTimes(2));
  fireEvent.change(screen.getByLabelText("项目材料"), {
    target: { value: "未保存的用户草稿" },
  });
  server = {
    ...server,
    revision: 2,
    content: { ...server.content, raw_material: "后台任务新结果" },
  };
  // Trigger the interval callback without replacing React's effect timers.
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 4100));
  });
  expect(screen.getByLabelText("项目材料")).toHaveValue("未保存的用户草稿");
  fireEvent.click(screen.getByRole("button", { name: /^保存$/ }));
  await screen.findByRole("alert");
  expect(vi.mocked(patch).mock.calls[0][1]).toBe(1);
  expect(screen.getByLabelText("项目材料")).toHaveValue("未保存的用户草稿");
}, 10000);

it("uploads retain selected files after input reset and start parsing", async () => {
  const server = fixture();
  vi.mocked(load).mockResolvedValue(server);
  vi.mocked(patch).mockImplementation(async (_id, revision, content) => ({
    ...server,
    revision: revision + 1,
    content,
  }));
  vi.mocked(uploadReferenceFile).mockResolvedValue({
    data: { file: { id: "ref-1" } },
  } as Awaited<ReturnType<typeof uploadReferenceFile>>);
  vi.mocked(triggerFileParse).mockResolvedValue(
    {} as Awaited<ReturnType<typeof triggerFileParse>>,
  );
  const { container } = render(
    <MemoryRouter initialEntries={["/education/project/p"]}>
      <Routes>
        <Route path="/education/project/:projectId" element={<Workspace />} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByDisplayValue("原始材料");
  const file = new File(["真实上传材料"], "材料.txt", { type: "text/plain" });
  const liveFiles = [file];
  fireEvent.change(container.querySelector('input[type="file"][multiple]')!, {
    target: { files: liveFiles },
  });
  // A browser clears the live FileList immediately when input.value is reset.
  liveFiles.length = 0;
  await waitFor(() =>
    expect(uploadReferenceFile).toHaveBeenCalledWith(file, "p"),
  );
  await waitFor(() => expect(triggerFileParse).toHaveBeenCalledWith("ref-1"));
  expect(vi.mocked(patch).mock.calls[0][2].reference_file_ids).toEqual([
    "ref-1",
  ]);
});

import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { EducationSpace, type SpaceItem } from "./Space";
import { data, download } from "./api";
import { uploadReferenceFile } from "../api/endpoints";
vi.mock("./api", async () => ({
  ...(await vi.importActual<typeof import("./api")>("./api")),
  data: vi.fn(),
  download: vi.fn(),
}));
vi.mock("../api/endpoints", () => ({
  uploadMaterial: vi.fn(),
  uploadReferenceFile: vi.fn(),
}));
let rows: SpaceItem[];
const item = (extra: Partial<SpaceItem>): SpaceItem => ({
  key: "reference:r",
  id: "r",
  kind: "reference",
  category: "temporary",
  name: "资料.txt",
  format: "TXT",
  updated_at: "2026-09-26T02:00:00Z",
  size: 12,
  status: "待整理",
  can_trash: true,
  projects: [],
  download_url: "/download/r",
  ...extra,
});
beforeEach(() => {
  vi.clearAllMocks();
  rows = [
    item({
      key: "project:p",
      id: "p",
      kind: "project",
      category: "projects",
      name: "餐饮服务作品",
      format: "作品",
      page_count: 2,
      download_url: undefined,
    }),
    item({}),
    item({
      key: "reference:bound",
      id: "bound",
      category: "permanent",
      name: "关联材料.txt",
      can_trash: false,
      projects: [{ id: "p", name: "餐饮服务作品", trashed: false }],
    }),
  ];
  vi.mocked(data).mockImplementation(async (method, url, body) => {
    if (method === "get") return { items: rows } as never;
    if (method === "patch") {
      const action = (body as { action: string }).action;
      rows = rows.map((i) =>
        url.endsWith("/" + i.id)
          ? {
              ...i,
              category:
                action === "trash"
                  ? "trash"
                  : action === "restore"
                    ? "projects"
                    : "permanent",
            }
          : i,
      );
    }
    return {} as never;
  });
});
const setup = () =>
  render(
    <MemoryRouter>
      <EducationSpace onChanged={async () => {}} />
    </MemoryRouter>,
  );
it("defaults to works, with all five tabs and searchable real rows", async () => {
  setup();
  await screen.findByText("餐饮服务作品");
  expect(screen.getAllByRole("tab")).toHaveLength(5);
  expect(screen.getByRole("tab", { name: "作品记录" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(screen.getByRole("link", { name: "继续编辑" })).toHaveAttribute(
    "href",
    "/education/project/p",
  );
  fireEvent.change(screen.getByLabelText("搜索空间内容"), {
    target: { value: "不存在" },
  });
  expect(screen.getByText("没有找到匹配的内容")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "临时文件" }));
  expect(screen.getByText(/当前不会自动清理/)).toBeInTheDocument();
  expect(screen.getByText("资料.txt")).toBeInTheDocument();
});
it("persists promotion and prevents deleting a linked file", async () => {
  setup();
  await screen.findByText("餐饮服务作品");
  fireEvent.click(screen.getByRole("tab", { name: "临时文件" }));
  fireEvent.click(screen.getByRole("button", { name: "长期保存" }));
  await waitFor(() =>
    expect(data).toHaveBeenCalledWith(
      "patch",
      "/api/competition/space/reference/r",
      { action: "permanent" },
    ),
  );
  await waitFor(() =>
    expect(screen.queryByText("资料.txt")).not.toBeInTheDocument(),
  );
  fireEvent.click(screen.getByRole("tab", { name: "长期文件" }));
  expect(screen.getByText("资料.txt")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "移入回收站：关联材料.txt" }),
  ).toBeDisabled();
});
it("moves a project to recycle bin and restores it without deletion calls", async () => {
  setup();
  await screen.findByText("餐饮服务作品");
  fireEvent.click(
    screen.getByRole("button", { name: "移入回收站：餐饮服务作品" }),
  );
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: "确认" }),
  );
  await screen.findByText("已移入回收站，可在回收站恢复");
  fireEvent.click(screen.getByRole("tab", { name: "回收站" }));
  fireEvent.click(screen.getByRole("button", { name: "恢复" }));
  await screen.findByText("已恢复到原分类");
  fireEvent.click(screen.getByRole("tab", { name: "作品记录" }));
  expect(screen.getByText("餐饮服务作品")).toBeInTheDocument();
  expect(
    vi.mocked(data).mock.calls.some(([method]) => method === "delete"),
  ).toBe(false);
});
it("uploads into long-term storage without generation and exposes download failures", async () => {
  vi.mocked(uploadReferenceFile).mockResolvedValue({
    data: { file: { id: "uploaded" } },
  } as never);
  const { container } = setup();
  await screen.findByText("餐饮服务作品");
  fireEvent.click(screen.getByRole("tab", { name: "长期文件" }));
  fireEvent.change(container.querySelector("input[type=file]")!, {
    target: { files: [new File(["资料"], "说明.txt")] },
  });
  await screen.findByText("文件已上传");
  expect(data).toHaveBeenCalledWith(
    "patch",
    "/api/competition/space/reference/uploaded",
    { action: "permanent" },
  );
  vi.mocked(download).mockRejectedValueOnce(new Error("连接中断"));
  fireEvent.click(screen.getByRole("button", { name: "下载" }));
  await screen.findByRole("alert");
  expect(screen.getByText("关联材料.txt")).toBeInTheDocument();
});

it("opens long-term preview and preserves search when it closes", async () => {
  setup();
  await screen.findByText("餐饮服务作品");
  fireEvent.click(screen.getByRole("tab", { name: "长期文件" }));
  fireEvent.change(screen.getByLabelText("搜索空间内容"), {
    target: { value: "关联材料" },
  });
  vi.mocked(data).mockResolvedValueOnce({
    kind: "text",
    text: "已经保存的材料内容",
  });
  fireEvent.click(screen.getByRole("button", { name: "预览" }));
  await screen.findByText("已经保存的材料内容");
  fireEvent.click(screen.getByRole("button", { name: "关闭预览" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByLabelText("搜索空间内容")).toHaveValue("关联材料");
  expect(screen.getByRole("tab", { name: "长期文件" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

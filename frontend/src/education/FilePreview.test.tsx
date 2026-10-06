import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { FilePreview } from "./FilePreview";
import { data } from "./api";
import { apiClient } from "../api/client";
import type { SpaceItem } from "./Space";
vi.mock("./api", async () => ({
  ...(await vi.importActual<typeof import("./api")>("./api")),
  data: vi.fn(),
  download: vi.fn(),
}));
vi.mock("../api/client", () => ({ apiClient: { get: vi.fn() } }));
const item = {
  id: "one",
  key: "reference:one",
  kind: "reference",
  name: "材料.txt",
  format: "TXT",
  download_url: "/download",
} as SpaceItem;
beforeEach(() => {
  vi.clearAllMocks();
  URL.createObjectURL = vi.fn(() => "blob:preview");
  URL.revokeObjectURL = vi.fn();
});
it("shows text as inert content, marks truncation and closes on Escape", async () => {
  vi.mocked(data).mockResolvedValue({
    kind: "text",
    text: '<img src="https://untrusted.example/pixel">材料原文',
    truncated: true,
  });
  const close = vi.fn();
  render(<FilePreview item={item} onClose={close} />);
  expect(await screen.findByText(/材料原文/)).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.getByText(/仅展示前 12 万字符/)).toBeInTheDocument();
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(close).toHaveBeenCalledOnce();
});
it("navigates PDF pages using authenticated blob requests and revokes old image URLs", async () => {
  vi.mocked(data).mockResolvedValue({ kind: "pdf", page_count: 2 });
  vi.mocked(apiClient.get).mockResolvedValue({
    data: new Blob(["png"], { type: "image/png" }),
  });
  const view = render(
    <FilePreview
      item={{ ...item, name: "方案.pdf", format: "PDF" }}
      onClose={() => {}}
    />,
  );
  await screen.findByRole("img", { name: "方案.pdf第1页" });
  expect(screen.getByRole("button", { name: "上一页预览" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "下一页预览" }));
  await screen.findByRole("img", { name: "方案.pdf第2页" });
  expect(apiClient.get).toHaveBeenLastCalledWith(
    "/api/competition/space/reference/one/preview?mode=image&page=2",
    expect.objectContaining({ responseType: "blob" }),
  );
  expect(screen.getByRole("button", { name: "下一页预览" })).toBeDisabled();
  view.unmount();
  expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
});
it("supports retry after preview failure without losing the download action", async () => {
  vi.mocked(data)
    .mockRejectedValueOnce(new Error("连接失败"))
    .mockResolvedValueOnce({ kind: "text", text: "恢复后的内容" });
  render(<FilePreview item={item} onClose={() => {}} />);
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "下载原文件" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "重试预览" }));
  await waitFor(() =>
    expect(screen.getByText("恢复后的内容")).toBeInTheDocument(),
  );
});

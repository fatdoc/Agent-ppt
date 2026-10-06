import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { TeamPhotos } from "./TeamPhotos";

function setup() {
  const props = {
    pageId: "team",
    disabled: false,
    roles: [
      {
        id: "r1",
        name: "现场操作",
        responsibility: "",
        member_name: "测试成员",
      },
      { id: "r2", name: "数据记录", responsibility: "" },
    ],
    bindings: [
      {
        page_id: "team",
        purpose: "person" as const,
        role_id: "r1",
        material_id: "photo",
      },
      {
        page_id: "other",
        purpose: "person" as const,
        role_id: "r2",
        material_id: "other-photo",
      },
    ],
    materials: [{ id: "photo", url: "/test-photo.png", filename: "photo.png" }],
    onUpload: vi.fn(),
    onRemovePhoto: vi.fn(),
    onSwap: vi.fn(),
    onEdit: vi.fn(),
    onAdd: vi.fn(),
    onRemove: vi.fn(),
  };
  return { props, ...render(<TeamPhotos {...props} />) };
}
it("shows scoped photo previews and uploads/replaces against a specific member", () => {
  const { props, container } = setup();
  expect(
    screen.getByRole("img", { name: "测试成员的已上传照片" }),
  ).toHaveAttribute("src", "/test-photo.png");
  expect(screen.getByText("1 / 2 已上传 · 最多 12 位")).toBeInTheDocument();
  const file = new File(["qa"], "qa.png", { type: "image/png" });
  const input = container.querySelector("input[type=file]")!;
  fireEvent.click(screen.getByRole("button", { name: "上传成员 2照片" }));
  fireEvent.change(input, { target: { files: [file] } });
  expect(props.onUpload).toHaveBeenLastCalledWith(file, "r2");
  fireEvent.click(screen.getByRole("button", { name: "更换测试成员照片" }));
  fireEvent.change(input, { target: { files: [file] } });
  expect(props.onUpload).toHaveBeenLastCalledWith(file, "r1");
});
it("supports drop binding, swapping members and editing slots", () => {
  const { props } = setup();
  const target = screen
    .getByRole("button", { name: "上传成员 2照片" })
    .closest("article")!;
  const file = new File(["qa"], "qa.png", { type: "image/png" });
  fireEvent.drop(target, { dataTransfer: { files: [file] } });
  expect(props.onUpload).toHaveBeenCalledWith(file, "r2");
  fireEvent.drop(target, { dataTransfer: { files: [], getData: () => "r1" } });
  expect(props.onSwap).toHaveBeenCalledWith("r1", "r2");
  fireEvent.click(within(target).getByRole("button", { name: "编辑" }));
  fireEvent.change(screen.getByLabelText("成员 2姓名"), {
    target: { value: "新成员" },
  });
  expect(props.onEdit).toHaveBeenCalledWith("r2", { member_name: "新成员" });
  fireEvent.click(screen.getByRole("button", { name: "新增人物槽位" }));
  expect(props.onAdd).toHaveBeenCalledOnce();
  fireEvent.click(within(target).getByRole("button", { name: "删除槽位" }));
  expect(props.onRemove).toHaveBeenCalledWith("r2");
});

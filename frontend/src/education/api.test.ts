import { beforeEach, expect, it, vi } from "vitest";
import { apiClient, setAuthEdition, getCsrfHeaders } from "../api/client";
import { submitOperation } from "./api";
beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});
it("reuses the admission key after a lost response but changes it for new input", async () => {
  const spy = vi
    .spyOn(apiClient, "request")
    .mockRejectedValueOnce(new Error("network lost"))
    .mockResolvedValue({
      data: { success: true, data: { task: { task_id: "t" } } },
    });
  await expect(submitOperation("p", "plan", 4)).rejects.toThrow("network lost");
  const first = (spy.mock.calls[0][0].data as { request_key: string })
    .request_key;
  await submitOperation("p", "plan", 4);
  expect(
    (spy.mock.calls[1][0].data as { request_key: string }).request_key,
  ).toBe(first);
  await submitOperation("p", "plan", 5);
  expect(
    (spy.mock.calls[2][0].data as { request_key: string }).request_key,
  ).not.toBe(first);
});
it("does not carry a general CSRF cookie into an education write", () => {
  document.cookie = "banana_csrf_token=general-token";
  document.cookie = "banana_education_csrf_token=education-token";
  setAuthEdition("education");
  expect(getCsrfHeaders()["X-CSRF-Token"]).toBe("education-token");
  setAuthEdition("general");
  expect(getCsrfHeaders()["X-CSRF-Token"]).toBe("general-token");
});

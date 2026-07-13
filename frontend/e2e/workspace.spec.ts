import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("all board workflows, recovery, accessibility basics, and downloads", async ({
  page,
}) => {
  const consoleErrors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  await page.goto("/");
  await expect(
    page.getByRole("img", { name: "Generated calibration board preview" }),
  ).toBeVisible();
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.filter((v) =>
      ["serious", "critical"].includes(v.impact || ""),
    ),
  ).toEqual([]);
  await page.getByRole("radio", { name: "ChArUco" }).click();
  await expect(page.getByLabel("Squares X")).toBeVisible();
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await page.getByRole("radio", { name: "Checkerboard" }).click();
  await expect(page.getByLabel("Border (mm)")).toBeVisible();
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await page.getByLabel("Square size (mm)").fill("20");
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await page.getByRole("switch", { name: "Board parameters" }).click();
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await page.getByRole("switch", { name: /100 mm scale ruler/ }).click();
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Landscape" }).click();
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await page.getByLabel("Square size (mm)").fill("200");
  await expect(page.getByText("validation error")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Download PDF" }),
  ).toBeDisabled();
  await page.getByLabel("Square size (mm)").fill("20");
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Download PDF" }),
  ).toBeEnabled();
  consoleErrors.length = 0;
  const jsonDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download JSON" }).click();
  expect((await jsonDownload).suggestedFilename()).toBe(
    "calibration-board.json",
  );
  const pdfDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF" }).click();
  expect((await pdfDownload).suggestedFilename()).toBe("calibration-board.pdf");
  await page.getByRole("button", { name: "Portrait" }).click();
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await page.getByRole("radio", { name: "ArUco Grid" }).click();
  await page.getByRole("switch", { name: /Export board-to-base pose/ }).click();
  await page.getByLabel("Yaw (°)").fill("90");
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("keyboard navigation reaches primary controls", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: /GitHub/ })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("radio", { name: "ArUco Grid" })).toBeFocused();
});

test("desktop workspace has no incidental vertical overflow", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  const overflow = await page.locator(".workspace").evaluate((element) =>
    element.scrollHeight - element.clientHeight
  );
  expect(overflow).toBe(0);
});

test("automatic fitting keeps clean geometry and reduces grid counts", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Landscape" }).click();
  await expect(page.getByLabel("Rows")).toHaveValue("4");
  await expect(page.getByLabel("Marker size (mm)")).toHaveValue("30");
  await expect(page.getByLabel("Separation (mm)")).toHaveValue("10");
  await expect(
    page.getByText(
      "Grid reduced to 5 × 4 markers for A4 landscape; board geometry kept unchanged.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("button", { name: "Portrait" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByLabel("Rows")).toHaveValue("7");
});

test("desktop workspace visual", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await expect(page).toHaveScreenshot("default-workspace.png", {
    animations: "disabled",
    fullPage: true,
  });
});

test("late preview responses cannot replace current settings", async ({
  page,
}) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v2/preview", async (route) => {
    const body = route.request().postDataJSON();
    if (body.board.type === "aruco" && body.board.rows === 6) await gate;
    await route.continue();
  });
  await page.goto("/");
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  const six = page.waitForRequest(
    (r) =>
      r.url().endsWith("/api/v2/preview") && r.postDataJSON().board.rows === 6,
  );
  await page.getByLabel("Rows").fill("6");
  await six;
  const five = page.waitForResponse(
    async (r) =>
      r.url().endsWith("/api/v2/preview") &&
      r.request().postDataJSON().board.rows === 5 &&
      r.status() === 200,
  );
  await page.getByLabel("Rows").fill("5");
  await five;
  release();
  await expect(page.getByText("current", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Rows")).toHaveValue("5");
});
